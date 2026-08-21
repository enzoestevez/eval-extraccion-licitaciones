"""Genera reports/RESULTADOS.md a partir de reports/metricas.json.

Uso:
    python src/reporte.py

Este archivo es el que va a leer un reclutador. Todo lo demas es evidencia.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from esquema import CAMPOS, VERSION_ESQUEMA  # noqa: E402
from variantes import POR_ID  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
REPORTES = RAIZ / "reports"


def pct(x) -> str:
    return "—" if x is None else f"{x:.1%}"


def usd(x) -> str:
    return "—" if x is None else f"{x:.6f}"


def main() -> None:
    origen = REPORTES / "metricas.json"
    if not origen.exists():
        sys.exit(f"Falta {origen}. Corre src/evaluar.py primero.")
    m = json.loads(origen.read_text(encoding="utf-8"))
    vs = sorted(m["variantes"], key=lambda v: -v["precision_ponderada"])
    if not vs:
        sys.exit("metricas.json no tiene variantes evaluadas.")

    L: list[str] = []
    L.append("# Resultados\n")
    L.append(
        f"Set etiquetado: **{m['n_etiquetados']} documentos** · esquema v{VERSION_ESQUEMA}\n"
    )
    if any("mock" in v["variante"] for v in vs):
        L.append(
            "> Hay variantes `mock` en la tabla. Son de prueba del pipeline y sus "
            "numeros no significan nada.\n"
        )

    # --- tabla principal ---------------------------------------------------
    L.append("## Comparacion de variantes\n")
    L.append(
        "| Variante | Precision | Docs perfectos | Alucinacion | p95 latencia | USD/doc | Que cambia |"
    )
    L.append("|---|---:|---:|---:|---:|---:|---|")
    for v in vs:
        nota = POR_ID[v["variante"]].nota if v["variante"] in POR_ID else ""
        L.append(
            f"| `{v['variante']}` | {pct(v['precision_ponderada'])} | "
            f"{pct(v['docs_perfectos'])} | {pct(v['tasa_alucinacion'])} | "
            f"{v['latencia_p95_ms']} ms | {usd(v['costo_por_doc_usd'])} | {nota} |"
        )
    L.append("")
    L.append(
        "**Precision** es el promedio ponderado por campo (los pesos estan en `src/esquema.py`). "
        "**Docs perfectos** es el porcentaje de documentos sin un solo campo mal — es la metrica "
        "dura, la que importa si el registro se carga entero o no se carga. "
        "**Alucinacion** es la proporcion de campos donde el modelo puso un valor y la verdad "
        "era `null`; en produccion es el error mas caro y por eso va aparte.\n"
    )

    ganadora = vs[0]

    # --- por campo ---------------------------------------------------------
    L.append(f"## Donde se equivoca la mejor variante (`{ganadora['variante']}`)\n")
    L.append("| Campo | Peso | Precision | Acierto | Null ok | Error | Alucinacion | Omision |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for c in CAMPOS:
        d = ganadora["por_campo"][c.nombre]
        L.append(
            f"| `{c.nombre}` | {d['peso']} | {pct(d['precision'])} | {d['acierto']} | "
            f"{d['acierto_null']} | {d['error']} | {d['alucinacion']} | {d['omision']} |"
        )
    L.append("")
    peor = min(CAMPOS, key=lambda c: ganadora["por_campo"][c.nombre]["precision"])
    L.append(
        f"El campo mas debil es `{peor.nombre}` "
        f"({pct(ganadora['por_campo'][peor.nombre]['precision'])}). "
        "Escribi aca por que, mirando los casos de `reports/metricas.json` → `peores`. "
        "Un promedio sin explicacion de la cola no dice nada.\n"
    )

    # --- umbral ------------------------------------------------------------
    L.append("## Umbral de confianza: cuanto derivar a revision humana\n")
    L.append("| Umbral | Auto-procesado | A revision | Precision sobre lo auto-procesado |")
    L.append("|---:|---:|---:|---:|")
    for f in ganadora["curva_umbral"]:
        if f["tasa_auto"] == 0:
            continue
        L.append(
            f"| {f['umbral']:.2f} | {pct(f['tasa_auto'])} | {pct(f['tasa_revision'])} | "
            f"{pct(f['precision_auto'])} |"
        )
    L.append("")
    L.append(
        "Esta tabla es la conclusion operativa del proyecto. No se elige el umbral "
        "por la metrica: se elige por cuanto cuesta un error contra cuanto cuesta una "
        "revision humana. Escribi debajo el umbral que elegiste y con que numeros lo "
        "justificaste.\n"
    )
    L.append("**Umbral elegido:** `COMPLETAR` — justificacion: `COMPLETAR`\n")

    # --- baseline ----------------------------------------------------------
    L.append("## Contra el baseline humano\n")
    L.append(
        "| | Precision | Tiempo por documento | Costo por documento |\n"
        "|---|---:|---:|---:|\n"
        "| Carga manual | `COMPLETAR` | `COMPLETAR` | `COMPLETAR` |\n"
        f"| `{ganadora['variante']}` | {pct(ganadora['precision_ponderada'])} | "
        f"{ganadora['latencia_p50_ms']/1000:.1f} s | {usd(ganadora['costo_por_doc_usd'])} USD |\n"
        f"| `{ganadora['variante']}` + revision del umbral elegido | `COMPLETAR` | "
        "`COMPLETAR` | `COMPLETAR` |\n"
    )
    L.append(
        "Para el baseline humano: cronometra vos mismo la carga manual de 20 documentos "
        "tomados al azar del corpus, contra el mismo esquema. Anota el metodo. Sin ese "
        "numero medido, todo lo de arriba es una demo sin punto de comparacion — que es "
        "exactamente el error del 95% de los pilotos.\n"
    )

    REPORTES.mkdir(parents=True, exist_ok=True)
    salida = REPORTES / "RESULTADOS.md"
    salida.write_text("\n".join(L), encoding="utf-8")
    print(f"Escrito {salida.relative_to(RAIZ)}")
    print(f"Mejor variante: {ganadora['variante']} ({pct(ganadora['precision_ponderada'])})")


if __name__ == "__main__":
    main()
