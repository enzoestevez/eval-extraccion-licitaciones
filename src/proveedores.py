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
from dataclasses import dataclass, field

from esquema import json_schema, registro_vacio


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


# --------------------------------------------------------------------------- anthropic


def _anthropic(prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    import anthropic

    cli = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    t0 = time.perf_counter()
    try:
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
    from openai import OpenAI

    cli = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    t0 = time.perf_counter()
    try:
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
    except Exception as e:  # noqa: BLE001
        return Respuesta(registro_vacio(), error=f"{type(e).__name__}: {e}")
    ms = int((time.perf_counter() - t0) * 1000)
    try:
        datos = {**registro_vacio(), **json.loads(r.choices[0].message.content)}
    except (json.JSONDecodeError, TypeError) as e:
        return Respuesta(registro_vacio(), error=f"json invalido: {e}", latencia_ms=ms)
    return Respuesta(datos, r.usage.prompt_tokens, r.usage.completion_tokens, ms)


# --------------------------------------------------------------------------- google


def _google(prompt: str, texto: str, modelo: str, **kw) -> Respuesta:
    from google import genai
    from google.genai import types

    cli = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    t0 = time.perf_counter()
    try:
        r = cli.models.generate_content(
            model=modelo,
            contents=texto,
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=kw.get("temperatura", 0),
                response_mime_type="application/json",
                response_schema=json_schema(),
            ),
        )
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
