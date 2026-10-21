"""Chequeo previo: ¿esta todo listo para correr las variantes?

Uso:
    python src/verificar.py            # revisa configuracion, sin llamar a nadie
    python src/verificar.py --llamar   # ademas hace UNA llamada de prueba por proveedor

Sirve para no descubrir a mitad de una corrida de 267 documentos que el nombre
del modelo esta mal, que falta la clave o que no esta instalado el paquete.
La llamada de prueba cuesta fracciones de centavo.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

RAIZ = Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"
PRECIOS = RAIZ / "config" / "precios.json"
INTERMEDIO = RAIZ / "data" / "interim"

CLAVES = {
    "anthropic": ("ANTHROPIC_API_KEY", "anthropic"),
    "openai": ("OPENAI_API_KEY", "openai"),
    "google": ("GOOGLE_API_KEY", "google.genai"),
}

OK, MAL, AVISO = "[ok]  ", "[MAL] ", "[?]   "


def cargar_env() -> None:
    """Lee .env sin depender de python-dotenv."""
    if not ENV.exists():
        return
    for linea in ENV.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def listar_modelos() -> None:
    """Pregunta a la API que modelos habilita esta clave.

    Los proveedores deprecan modelos y a veces dejan de ofrecerlos a cuentas
    nuevas aunque sigan documentados. Copiar un identificador de un blog -o de
    una conversacion- es como quedan los proyectos rotos seis meses despues.
    Esta es la fuente de verdad: tu clave, hoy.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Falta GOOGLE_API_KEY en .env")
        return
    try:
        from google import genai
    except ImportError:
        print("Falta el paquete. Instalalo:  pip install google-genai")
        return

    cli = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    print("Modelos habilitados para tu clave que sirven para extraer:\n")
    for m in cli.models.list():
        acciones = getattr(m, "supported_actions", None) or []
        if acciones and "generateContent" not in acciones:
            continue
        nombre = m.name.replace("models/", "")
        if "embedding" in nombre or "imagen" in nombre or "tts" in nombre:
            continue
        print(f"  {nombre:42} {getattr(m, 'display_name', '') or ''}")
    print(
        "\nElegi uno barato y uno caro, ponelos en src/variantes.py y cargá sus\n"
        "precios en config/precios.json desde ai.google.dev/gemini-api/docs/pricing"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Verifica que todo este listo para correr.")
    ap.add_argument("--llamar", action="store_true", help="hacer una llamada real de prueba")
    ap.add_argument(
        "--modelos",
        action="store_true",
        help="listar los modelos que TU clave tiene habilitados y salir",
    )
    args = ap.parse_args()

    cargar_env()

    if args.modelos:
        listar_modelos()
        return
    from variantes import VARIANTES  # noqa: E402

    problemas = 0

    # --- corpus ------------------------------------------------------------
    print("CORPUS")
    txts = list(INTERMEDIO.glob("*.txt"))
    if txts:
        print(f"{OK}{len(txts)} avisos en data/interim/")
    else:
        print(f"{MAL}no hay avisos. Corre: python src/dividir.py")
        problemas += 1

    # --- .env --------------------------------------------------------------
    print("\nCLAVES")
    if not ENV.exists():
        print(f"{MAL}no existe .env. Copialo:  cp .env.example .env")
        problemas += 1

    proveedores = {v.proveedor for v in VARIANTES} - {"mock", "reglas"}
    for prov in sorted(proveedores):
        var, modulo = CLAVES[prov]
        clave = os.environ.get(var, "")
        if not clave:
            print(f"{MAL}{prov}: falta {var} en .env")
            problemas += 1
        elif len(clave) < 20:
            print(f"{AVISO}{prov}: {var} parece demasiado corta, revisala")
        else:
            print(f"{OK}{prov}: {var} cargada ({clave[:6]}...{clave[-4:]})")

        # Ojo: `google` es un namespace package y find_spec("google") da positivo
        # aunque google-genai no este instalado. Hay que buscar el submodulo.
        try:
            hay_paquete = importlib.util.find_spec(modulo) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            hay_paquete = False
        if not hay_paquete:
            paquete = {"anthropic": "anthropic", "openai": "openai", "google": "google-genai"}[prov]
            print(f"{MAL}{prov}: falta el paquete. Instalalo:  pip install {paquete}")
            problemas += 1
        else:
            print(f"{OK}{prov}: paquete instalado")

    # --- precios -----------------------------------------------------------
    print("\nPRECIOS")
    precios = json.loads(PRECIOS.read_text(encoding="utf-8")) if PRECIOS.exists() else {}
    for v in VARIANTES:
        if v.proveedor in ("mock", "reglas"):
            continue
        p = precios.get(v.id)
        if not p or p.get("usd_por_millon_in") is None:
            print(f"{AVISO}{v.id}: sin precio cargado, el reporte no va a poder calcular costo")
        else:
            print(f"{OK}{v.id}: {p['usd_por_millon_in']} in / {p['usd_por_millon_out']} out")

    # --- esquema por proveedor ---------------------------------------------
    # Cada API pide el esquema en su propio dialecto. Esto se valida localmente,
    # sin gastar una llamada: es el error que rompe las 267 de una y conviene
    # descubrirlo gratis.
    print("\nESQUEMA")
    from esquema import json_schema

    if "google" in proveedores:
        try:
            from google.genai import types

            from proveedores import _esquema_google

            types.Schema(**_esquema_google(json_schema()))
            print(f"{OK}google: el esquema traducido es valido")
        except ImportError:
            print(f"{AVISO}google: no puedo validar el esquema sin el paquete")
        except Exception as e:  # noqa: BLE001
            print(f"{MAL}google: el esquema no es valido -> {str(e).splitlines()[0]}")
            problemas += 1

    # --- llamada de prueba -------------------------------------------------
    if args.llamar:
        print("\nLLAMADA DE PRUEBA (una por variante, con un aviso real)")
        from proveedores import llamar

        texto = txts[0].read_text(encoding="utf-8")[:3000] if txts else "Licitacion Publica 1/2026"
        vistos = set()
        for v in VARIANTES:
            if v.proveedor in ("mock", "reglas") or (v.proveedor, v.modelo) in vistos:
                continue
            vistos.add((v.proveedor, v.modelo))
            r = llamar(v.proveedor, v.prompt, texto, v.modelo, temperatura=v.temperatura)
            if r.error:
                print(f"{MAL}{v.proveedor}/{v.modelo}")
                print(f"      {r.error[:200]}")
                problemas += 1
            else:
                llenos = sum(1 for k, x in r.datos.items() if k != "confianza" and x is not None)
                print(
                    f"{OK}{v.proveedor}/{v.modelo}  "
                    f"{llenos}/8 campos, {r.tokens_in}+{r.tokens_out} tokens, {r.latencia_ms} ms"
                )

    # --- resumen -----------------------------------------------------------
    # No todo problema bloquea: si te falta un proveedor, perdes las variantes
    # de ese proveedor y el resto del experimento sigue en pie.
    from proveedores import tiene_clave

    listas, bloqueadas = [], {}
    for v in VARIANTES:
        if v.proveedor in ("mock", "reglas") or tiene_clave(v.proveedor):
            listas.append(v.id)
        else:
            bloqueadas.setdefault(v.proveedor, []).append(v.id)

    print("\nRESUMEN")
    print(f"{OK}listas para correr: {', '.join(listas)}")
    for prov, ids in bloqueadas.items():
        print(f"{AVISO}sin {CLAVES[prov][0]}: no van a correr {', '.join(ids)}")

    reales = [v for v in listas if not v.startswith("v0")]
    if not reales:
        print("\nNo hay ninguna variante con modelo lista. Cargá al menos una clave.")
        sys.exit(1)

    print("\nSiguiente paso:")
    print(f"    python src/extraer.py --variante {reales[0]} --limite 20   # prueba corta")
    print("    python src/extraer.py --todas                              # el resto")


if __name__ == "__main__":
    main()
