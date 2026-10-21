"""Auditoria del set de referencia. Busca errores en TUS etiquetas, no en el modelo.

Uso:
    python label/auditar.py              # informe completo
    python label/auditar.py --ids        # solo la lista de ids a revisar

Por que existe: el set etiquetado es la vara con la que se mide todo lo demas.
Si la vara esta torcida, todas las metricas del proyecto son ficcion y encima
parecen buenas. Nadie audita su propio set de referencia, y es lo primero que
habria que hacer.

Que revisa:

1. **Nulls sospechosos.** Campos marcados null cuyo dato SI aparece mencionado en
   el texto del aviso. Es el error tipico del etiquetado asistido: cuando el
   parser no sugiere nada, la tecla comoda es la que dice "no hay dato".

2. **Registros con todos los campos en null.** Casi siempre es un aviso que se
   paso de largo sin querer.

3. **Registros sin procedencia.** Etiquetados con una version vieja de la
   herramienta, sin el campo `modo`. No son invalidos, pero no entran en el
   analisis de sesgo.

4. **Balance de la muestra ciega.** Si quedo muy por debajo del objetivo, el
   control pierde poder.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from esquema import CAMPOS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
ORO = RAIZ / "data" / "gold" / "etiquetas.jsonl"
INDICE = INTERMEDIO / "indice.json"

PISTAS = {
    "expediente": r"(expediente|expte\.?|actuaci[óo]n\s+n)",
    "fecha_apertura": r"(apertura)",
    "objeto": r"(objeto|objetivo de la contrataci)",
    "monto_estimado": r"(presupuesto\s+oficial|monto\s+estimado|valor\s+estimado)",
    "valor_pliego": r"(valor\s+del\s+pliego|costo\s+del\s+pliego|precio\s+del\s+pliego)",
    "tipo_procedimiento": r"(licitaci[óo]n|contrataci[óo]n\s+directa|concurso|subasta|compulsa)",
}


def linea_de(texto: str, m: re.Match) -> str:
    inicio = texto.rfind("\n", 0, m.start()) + 1
    return texto[inicio:].split("\n")[0].strip()[:120]


def analizar() -> tuple[list[dict], dict, dict, list[str], list[str], int]:
    """Corre la auditoria y devuelve los hallazgos, sin imprimir nada.

    La usa tanto el informe de este archivo como
    `etiquetar.py --auditados`, para que la lista sea la misma en los dos lados.
    """
    if not ORO.exists():
        sys.exit(f"No hay set etiquetado en {ORO}.")
    regs = [json.loads(l) for l in ORO.read_text(encoding="utf-8").splitlines() if l.strip()]
    idx = {r["id"]: r for r in json.loads(INDICE.read_text(encoding="utf-8"))}

    sospechosos: dict[str, list[tuple[str, str]]] = {}
    vacios: list[str] = []
    sin_modo: list[str] = []
    ciegos = 0

    for r in regs:
        meta = idx.get(r["id"])
        if not meta:
            continue
        texto = (INTERMEDIO / meta["txt"]).read_text(encoding="utf-8")
        datos = r["datos"]

        if all(datos.get(c.nombre) is None for c in CAMPOS):
            vacios.append(r["id"])
        if "modo" not in r:
            sin_modo.append(r["id"])
        if r.get("modo") == "ciego":
            ciegos += 1

        for c in CAMPOS:
            if datos.get(c.nombre) is not None:
                continue
            patron = PISTAS.get(c.nombre)
            if not patron:
                continue
            m = re.search(patron, texto, re.I)
            if m:
                sospechosos.setdefault(r["id"], []).append((c.nombre, linea_de(texto, m)))

    return regs, idx, sospechosos, vacios, sin_modo, ciegos


def ids_a_revisar() -> list[str]:
    """Los ids que la auditoria marca para volver a mirar, en orden."""
    _, _, sospechosos, vacios, sin_modo, _ = analizar()
    return sorted(set(sospechosos) | set(vacios) | set(sin_modo))


def main() -> None:
    ap = argparse.ArgumentParser(description="Audita el set de referencia.")
    ap.add_argument("--ids", action="store_true", help="solo imprimir los ids a revisar")
    args = ap.parse_args()

    regs, idx, sospechosos, vacios, sin_modo, ciegos = analizar()

    if args.ids:
        for i in sorted(set(sospechosos) | set(vacios) | set(sin_modo)):
            print(i)
        return

    total_campos = sum(len(v) for v in sospechosos.values())
    print(f"Registros auditados: {len(regs)}")
    print(f"Muestra ciega: {ciegos} ({ciegos / len(regs):.0%} de lo etiquetado)")
    print()

    if vacios:
        print(f"[!] {len(vacios)} registro(s) con TODOS los campos en null: {', '.join(vacios)}")
        print("    Casi seguro son avisos que se pasaron de largo. Rehacelos.\n")

    if sin_modo:
        print(f"[!] {len(sin_modo)} registro(s) sin procedencia (version vieja): {', '.join(sin_modo)}")
        print("    Rehacelos para que entren en el analisis de sesgo.\n")

    if sospechosos:
        print(f"[!] {total_campos} campo(s) en null cuyo dato aparece en el texto, "
              f"en {len(sospechosos)} aviso(s):\n")
        for doc_id in sorted(sospechosos):
            print(f"  {doc_id}  ({idx[doc_id]['formato']})")
            for campo, linea in sospechosos[doc_id]:
                print(f"     {campo:20} el aviso dice: \"{linea}\"")
            print()
    else:
        print("Sin nulls sospechosos. \n")

    a_revisar = sorted(set(sospechosos) | set(vacios) | set(sin_modo))
    if a_revisar:
        print(f"A revisar: {len(a_revisar)} aviso(s).")
        print()
        print("  Este archivo SOLO INFORMA, no modifica nada.")
        print("  Para corregirlos todos, uno atras del otro:")
        print()
        print("      python label/etiquetar.py --auditados")
        print()
        print("  O uno puntual:  python label/etiquetar.py --id <ID>")
        print()
        print("OJO: que un campo aparezca aca no significa que este mal. La palabra")
        print("puede estar en el aviso sin que el dato lo este ('el pliego se retira")
        print("en...' no es un valor de pliego). Lo unico que dice el auditor es")
        print("'mira esto de nuevo'. La decision sigue siendo tuya.")


if __name__ == "__main__":
    main()
