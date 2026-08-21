"""CLI de etiquetado. Aca se construye el activo mas valioso del proyecto.

Uso:
    python label/etiquetar.py               # sigue por el primero sin etiquetar
    python label/etiquetar.py --id 20260312-3s-0004
    python label/etiquetar.py --revisar     # repasa los ya etiquetados
    python label/etiquetar.py --estado      # cuantos van

Controles dentro de un campo:
    Enter vacio  -> null (el dato NO figura en el aviso)
    .            -> saltear el documento entero y seguir con el siguiente
    ?            -> volver a mostrar el texto del aviso
    !            -> marcar el documento como dudoso y anotar por que

El set etiquetado se guarda en data/gold/etiquetas.jsonl y ES EL PROYECTO.
Los modelos cambian cada tres meses; un corpus etiquetado a mano contra un
protocolo escrito no. Etiquetalo vos, no con IA: si la verdad de referencia la
genera un modelo, no estas midiendo nada, estas midiendo el acuerdo entre dos
modelos. Esa distincion sola ya te pone arriba de la mayoria.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from esquema import CAMPOS, VERSION_ESQUEMA  # noqa: E402
from normalizar import normalizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
ORO = RAIZ / "data" / "gold" / "etiquetas.jsonl"

ANCHO = 78


def cargar() -> dict[str, dict]:
    if not ORO.exists():
        return {}
    return {
        json.loads(l)["id"]: json.loads(l)
        for l in ORO.read_text(encoding="utf-8").splitlines()
        if l.strip()
    }


def guardar(registros: dict[str, dict]) -> None:
    ORO.parent.mkdir(parents=True, exist_ok=True)
    with ORO.open("w", encoding="utf-8") as f:
        for k in sorted(registros):
            f.write(json.dumps(registros[k], ensure_ascii=False) + "\n")


def mostrar_texto(texto: str) -> None:
    print("\n" + "=" * ANCHO)
    print(texto[:6000])
    if len(texto) > 6000:
        print(f"\n[... {len(texto) - 6000} caracteres mas; abri el .txt si necesitas ver todo]")
    print("=" * ANCHO)


def pedir_campo(campo, texto: str, valor_previo=None) -> tuple[object, bool]:
    """Devuelve (valor, saltear_documento)."""
    marca = "" if campo.obligatorio else "  [opcional]"
    previo = f"  (actual: {valor_previo!r})" if valor_previo is not None else ""
    while True:
        print(f"\n  {campo.nombre}  <{campo.tipo}>{marca}{previo}")
        print(f"    {campo.descripcion}")
        try:
            v = input("    > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCortado. Lo etiquetado hasta el documento anterior quedo guardado.")
            sys.exit(0)

        if v == ".":
            return None, True
        if v == "?":
            mostrar_texto(texto)
            continue
        if v == "":
            return None, False

        norm = normalizar(campo.tipo, v)
        if norm is None:
            print(f"    No pude interpretar eso como {campo.tipo}. Probá de nuevo.")
            continue
        print(f"    ok -> {norm!r}")
        return v, False


def etiquetar_uno(doc_id: str, texto: str, previo: dict | None) -> dict | None:
    print("\n" + "#" * ANCHO)
    print(f"# {doc_id}")
    print("#" * ANCHO)
    mostrar_texto(texto)

    datos = {}
    for c in CAMPOS:
        v, saltear = pedir_campo(c, texto, (previo or {}).get("datos", {}).get(c.nombre))
        if saltear:
            print("  Documento salteado.")
            return None
        datos[c.nombre] = v

    print("\n  ¿Algo dudoso en este documento? (Enter si no)")
    try:
        nota = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)

    return {
        "id": doc_id,
        "datos": datos,
        "dudoso": bool(nota),
        "nota": nota,
        "version_esquema": VERSION_ESQUEMA,
        "etiquetado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def estado(registros: dict, docs: list[Path]) -> None:
    dudosos = sum(1 for r in registros.values() if r.get("dudoso"))
    viejos = sum(1 for r in registros.values() if r.get("version_esquema") != VERSION_ESQUEMA)
    print(f"Etiquetados : {len(registros)} / {len(docs)}")
    print(f"Dudosos     : {dudosos}")
    if viejos:
        print(f"Con esquema viejo: {viejos}  -> revisalos con --revisar")
    print(f"Objetivo    : 200-300 para que los numeros signifiquen algo")


def main() -> None:
    ap = argparse.ArgumentParser(description="Etiquetado manual del set de referencia.")
    ap.add_argument("--id", help="etiquetar un documento puntual")
    ap.add_argument("--revisar", action="store_true", help="repasar los ya etiquetados")
    ap.add_argument("--estado", action="store_true")
    args = ap.parse_args()

    docs = sorted(INTERMEDIO.glob("*.txt"))
    if not docs:
        sys.exit(f"No hay textos en {INTERMEDIO}. Corre src/ingesta.py primero.")

    registros = cargar()
    if args.estado:
        estado(registros, docs)
        return

    if args.id:
        cola = [p for p in docs if p.stem == args.id]
        if not cola:
            sys.exit(f"No encontre {args.id} en {INTERMEDIO}")
    elif args.revisar:
        cola = [p for p in docs if p.stem in registros]
    else:
        cola = [p for p in docs if p.stem not in registros]

    if not cola:
        print("No queda nada por etiquetar.")
        estado(registros, docs)
        return

    print(f"{len(cola)} documento(s) en cola. Ctrl+C corta y guarda lo hecho.")
    for p in cola:
        r = etiquetar_uno(p.stem, p.read_text(encoding="utf-8"), registros.get(p.stem))
        if r is not None:
            registros[p.stem] = r
            guardar(registros)
            print(f"  guardado ({len(registros)} en total)")

    estado(registros, docs)


if __name__ == "__main__":
    main()
