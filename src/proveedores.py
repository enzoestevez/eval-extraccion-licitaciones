"""Capa unica sobre los proveedores de LLM.

El objetivo es que el harness no sepa con quien esta hablando. Eso permite
comparar Anthropic contra Google contra OpenAI contra un mock, sin tocar
el resto del codigo, y es lo que hace que la comparacion sea honesta:
mismo corpus, mismo esquema, misma medicion.

Cada llamada devuelve siempre lo mismo:
    Respuesta(datos, tokens_in, tokens_out, latencia_ms, error)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from esquema import json_schema, registro_vacio

# --------------------------------------------------------------------------- .env

_ENV = Path(__file__).resolve().parent.parent / ".env"


def cargar_env() -> None:
    """Lee .env y lo mete en el entorno, sin depender de python-dotenv.

    Se llama al importar este modulo, asi cualquier script que use un proveedor
    ve las claves sin tener que acordarse de cargarlas. Antes esto solo pasaba
    en verificar.py, y extraer.py no encontraba la clave aunque estuviera bien
    puesta en .env: el error decia "falta la clave" con la clave ahi al lado.
    """
    if not _ENV.exists():
        return
    for linea in _ENV.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env()

# Que variable de entorno necesita cada proveedor.
CLAVE_DE = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def tiene_clave(proveedor: str) -> bool:
    """True si el proveedor no necesita clave o si la clave esta cargada."""
    var = CLAVE_DE.get(proveedor)
    return var is None or bool(os.environ.get(var))


@dataclass
class Respuesta:
    datos: dict
    tokens_in: int = 0
    tokens_out: int = 0
    latencia_ms: int = 0
    error: str | None = None


# --------------------------------------------------------------------------- mock


def _mock(prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    """Proveedor de prueba. No llama a nada ni gasta un peso.

    Existe para que puedas correr el pipeline entero antes de tener API key:
    verifica que la ingesta, el etiquetado, la evaluacion y el reporte funcionan.
    Sus numeros no significan nada y el reporte los marca como tales.
    """
    time.sleep(0.01)
    d = registro_vacio()
    d["organismo"] = "MOCK - sin proveedor configurado"
    d["confianza"] = 0.0
    return Respuesta(d, len(texto) // 4, 120, 10)


# --------------------------------------------------------------------------- reglas


def _reglas(prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    """Extractor determinista, sin IA. Ver src/reglas.py.

    Es la linea base honesta del experimento: costo cero, latencia despreciable,
    resultado identico en cada corrida. Cualquier modelo que se compare contra
    esto tiene que justificar su costo con la diferencia de precision, y solo en
    el segmento donde esa diferencia existe.
    """
    from reglas import extraer

    t0 = time.perf_counter()
    datos = {**registro_vacio(), **extraer(texto)}
    return Respuesta(datos, 0, 0, int((time.perf_counter() - t0) * 1000))


# --------------------------------------------------------------------------- anthropic


def _anthropic(prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    t0 = time.perf_counter()
    try:
        import anthropic

        cli = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        r = cli.messages.create(
            model=modelo,
            max_tokens=2048,
            temperature=kw.get("temperatura", 0),
            system=prompt,
            tools=[
                {
                    "name": "registrar_aviso",
                    "description": "Registra los campos extraidos del aviso.",
                    "input_schema": json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "registrar_aviso"},
            messages=[{"role": "user", "content": texto}],
        )
    except ImportError as e:
        return Respuesta(registro_vacio(), error=f"falta el paquete: {e}")
    except Exception as e:  # noqa: BLE001
        return Respuesta(registro_vacio(), error=f"{type(e).__name__}: {e}")
    ms = int((time.perf_counter() - t0) * 1000)
    datos = registro_vacio()
    for b in r.content:
        if b.type == "tool_use":
            datos = {**datos, **b.input}
    return Respuesta(datos, r.usage.input_tokens, r.usage.output_tokens, ms)


# --------------------------------------------------------------------------- openai


def _openai(prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    t0 = time.perf_counter()
    try:
        from openai import OpenAI

        cli = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        r = cli.chat.completions.create(
            model=modelo,
            temperature=kw.get("temperatura", 0),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "aviso",
                    "strict": True,
                    "schema": json_schema(),
                },
            },
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": texto},
            ],
        )
    except ImportError as e:
        return Respuesta(registro_vacio(), error=f"falta el paquete: {e}")
    except Exception as e:  # noqa: BLE001
        return Respuesta(registro_vacio(), error=f"{type(e).__name__}: {e}")
    ms = int((time.perf_counter() - t0) * 1000)
    try:
        datos = {**registro_vacio(), **json.loads(r.choices[0].message.content)}
    except (json.JSONDecodeError, TypeError) as e:
        return Respuesta(registro_vacio(), error=f"json invalido: {e}", latencia_ms=ms)
    return Respuesta(datos, r.usage.prompt_tokens, r.usage.completion_tokens, ms)


# --------------------------------------------------------------------------- google


def _esquema_google(js: dict) -> dict:
    """Traduce el esquema canonico (JSON Schema) al dialecto de Google.

    Los tres proveedores dicen aceptar "un esquema", pero no el mismo:

      OpenAI y Anthropic  ->  {"type": ["string", "null"]}
      Google              ->  {"type": "STRING", "nullable": true}

    Google ademas quiere el tipo en MAYUSCULAS y rechaza claves que no conoce
    (`additionalProperties`, `minimum`, `maximum`). Si le pasas el esquema
    canonico tal cual, falla con "8 validation errors for Schema" y ni una sola
    llamada sale.

    Por eso la traduccion vive aca, en la capa de proveedores, y no en
    esquema.py: esquema.py define QUE se extrae, cada proveedor se arregla con
    COMO lo pide su API.
    """
    TIPOS = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
    }

    def campo(prop: dict) -> dict:
        tipos = prop["type"]
        tipos = tipos if isinstance(tipos, list) else [tipos]
        nulos = "null" in tipos
        concretos = [t for t in tipos if t != "null"]
        out: dict = {"type": TIPOS[concretos[0]]}
        if nulos:
            out["nullable"] = True
        if prop.get("description"):
            out["description"] = prop["description"]
        return out

    return {
        "type": "OBJECT",
        "properties": {k: campo(v) for k, v in js["properties"].items()},
        "required": list(js["required"]),
    }


def _google(prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    t0 = time.perf_counter()
    try:
        import logging

        from google import genai
        from google.genai import types

        # El SDK avisa en cada llamada sobre "automatic function calling".
        # No aplica a lo que hacemos y ensucia 267 lineas de salida.
        logging.getLogger("google_genai.models").setLevel(logging.ERROR)

        cli = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        r = cli.models.generate_content(
            model=modelo,
            contents=texto,
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=kw.get("temperatura", 0),
                response_mime_type="application/json",
                response_schema=_esquema_google(json_schema()),
            ),
        )
    except ImportError as e:
        return Respuesta(registro_vacio(), error=f"falta el paquete: {e}")
    except Exception as e:  # noqa: BLE001
        return Respuesta(registro_vacio(), error=f"{type(e).__name__}: {e}")
    ms = int((time.perf_counter() - t0) * 1000)
    try:
        datos = {**registro_vacio(), **json.loads(r.text)}
    except (json.JSONDecodeError, TypeError) as e:
        return Respuesta(registro_vacio(), error=f"json invalido: {e}", latencia_ms=ms)
    u = getattr(r, "usage_metadata", None)
    return Respuesta(
        datos,
        getattr(u, "prompt_token_count", 0) or 0,
        getattr(u, "candidates_token_count", 0) or 0,
        ms,
    )


PROVEEDORES = {
    "mock": _mock,
    "reglas": _reglas,
    "anthropic": _anthropic,
    "openai": _openai,
    "google": _google,
}


def llamar(proveedor: str, prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    if proveedor not in PROVEEDORES:
        raise ValueError(
            f"proveedor '{proveedor}' desconocido. Disponibles: {sorted(PROVEEDORES)}"
        )
    return PROVEEDORES[proveedor](prompt, texto, modelo, **kw)
