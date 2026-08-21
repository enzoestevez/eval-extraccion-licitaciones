"""Corre una o mas variantes sobre el corpus y guarda las predicciones.

Uso:
    python src/extraer.py --variante v0-base
    python src/extraer.py --variante v2-reglas --limite 20
    python src/extraer.py --todas

Cada corrida deja data/interim/pred_<variante>.jsonl con una linea por documento:
    {"id", "datos", "tokens_in", "tokens_out", "latencia_ms", "error"}

El archivo se escribe incrementalmente y la corrida es reanudable: si la cortas
a la mitad, al volver a correr sigue desde donde quedo. Con 300 documentos y una
API que a veces falla, esto deja de ser un lujo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from proveedores import llamar  # noqa: E402
from variantes import POR_ID, VARIANTES, Variante  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
ORO = RAIZ / "data" / "gold" / "etiquetas.jsonl"

MAX_CARACTERES = 60_000  # corte de seguridad para no mandar un PDF de 400 paginas


def cargar_corpus(solo_etiquetados: bool) -> list[tuple[str, str]]:
    ids_validos = None
    if solo_etiquetados and ORO.exists():
        ids_validos = {
            json.loads(l)["id"] for l in ORO.read_text(encoding="utf-8").splitlines() if l.strip()
        }
    docs = []
    for txt in sorted(INTERMEDIO.glob("*.txt")):
        if ids_validos is not None and txt.stem not in ids_validos:
            continue
        docs.append((txt.stem, txt.read_text(encoding="utf-8")[:MAX_CARACTERES]))
    return docs


def ya_hechos(destino: Path) -> set[str]:
    if not destino.exists():
        return set()
    hechos = set()
    for linea in destino.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            r = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if not r.get("error"):
            hechos.add(r["id"])
    return hechos


def correr(v: Variante, limite: int | None, solo_etiquetados: bool) -> None:
    destino = INTERMEDIO / f"pred_{v.id}.jsonl"
    hechos = ya_hechos(destino)
    docs = cargar_corpus(solo_etiquetados)
    pendientes = [(i, t) for i, t in docs if i not in hechos]
    if limite:
        pendientes = pendientes[:limite]

    print(f"\n{v.etiqueta}")
    print(f"  corpus {len(docs)} | ya hechos {len(hechos)} | a correr {len(pendientes)}")
    if not pendientes:
        return

    t0 = time.perf_counter()
    fallos = 0
    with destino.open("a", encoding="utf-8") as f:
        for n, (doc_id, texto) in enumerate(pendientes, 1):
            r = llamar(v.proveedor, v.prompt, texto, v.modelo, temperatura=v.temperatura)
            if r.error:
                fallos += 1
            f.write(
                json.dumps(
                    {
                        "id": doc_id,
                        "variante": v.id,
                        "datos": r.datos,
                        "tokens_in": r.tokens_in,
                        "tokens_out": r.tokens_out,
                        "latencia_ms": r.latencia_ms,
                        "error": r.error,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            f.flush()
            if n % 10 == 0 or n == len(pendientes):
                seg = time.perf_counter() - t0
                print(f"  {n}/{len(pendientes)}  {seg:.0f}s  fallos {fallos}", flush=True)

    if fallos:
        print(f"  {fallos} llamada(s) con error. Volve a correr para reintentarlas.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Corre variantes sobre el corpus.")
    ap.add_argument("--variante", action="append", help="id de variante (repetible)")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--limite", type=int, help="tope de documentos por variante")
    ap.add_argument(
        "--corpus-completo",
        action="store_true",
        help="correr sobre todo, no solo sobre lo etiquetado",
    )
    args = ap.parse_args()

    if args.todas:
        seleccion = list(VARIANTES)
    elif args.variante:
        try:
            seleccion = [POR_ID[i] for i in args.variante]
        except KeyError as e:
            sys.exit(f"Variante desconocida: {e}. Disponibles: {sorted(POR_ID)}")
    else:
        sys.exit("Pasa --variante <id> o --todas. Disponibles: " + ", ".join(POR_ID))

    for v in seleccion:
        if "COMPLETAR" in v.modelo:
            print(f"\n{v.id}: salteada, el modelo dice '{v.modelo}'. Completalo en variantes.py.")
            continue
        correr(v, args.limite, not args.corpus_completo)


if __name__ == "__main__":
    main()
