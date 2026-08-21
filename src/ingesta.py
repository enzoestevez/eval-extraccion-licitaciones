"""PDF -> texto plano.

Uso:
    python src/ingesta.py                # procesa todo data/raw/*.pdf
    python src/ingesta.py --forzar       # rehace los que ya existen

Deja un .txt por PDF en data/interim/ y un indice en data/interim/indice.json
con el largo del texto y si el PDF parecia escaneado.

Nota importante: si un PDF viene escaneado (imagen, sin capa de texto), este
script lo marca y NO lo procesa. Meter OCR en el mismo paso mezcla dos fuentes
de error distintas y despues no vas a poder decir si el modelo fallo o si fallo
el OCR. Si tenes muchos escaneados, hace un experimento aparte para eso.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw"
INTERMEDIO = RAIZ / "data" / "interim"

UMBRAL_ESCANEADO = 200  # caracteres por pagina por debajo de los cuales sospechamos


def extraer_texto(pdf: Path) -> tuple[str, int]:
    import pypdf

    lector = pypdf.PdfReader(str(pdf))
    partes = [(p.extract_text() or "") for p in lector.pages]
    return "\n\n".join(partes).strip(), len(lector.pages)


def main() -> None:
    ap = argparse.ArgumentParser(description="Convierte los PDF de data/raw a texto.")
    ap.add_argument("--forzar", action="store_true", help="rehacer los ya procesados")
    args = ap.parse_args()

    INTERMEDIO.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(CRUDO.glob("*.pdf"))
    if not pdfs:
        print(f"No hay PDFs en {CRUDO}. Bajalos primero y volve a correr.")
        return

    indice: list[dict] = []
    saltados = hechos = sospechosos = 0

    for pdf in pdfs:
        destino = INTERMEDIO / f"{pdf.stem}.txt"
        if destino.exists() and not args.forzar:
            texto = destino.read_text(encoding="utf-8")
            paginas = 0
            saltados += 1
        else:
            try:
                texto, paginas = extraer_texto(pdf)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {pdf.name}: {type(e).__name__}: {e}")
                continue
            destino.write_text(texto, encoding="utf-8")
            hechos += 1

        por_pagina = len(texto) / max(paginas, 1) if paginas else len(texto)
        escaneado = paginas > 0 and por_pagina < UMBRAL_ESCANEADO
        if escaneado:
            sospechosos += 1

        indice.append(
            {
                "id": pdf.stem,
                "pdf": pdf.name,
                "txt": destino.name,
                "caracteres": len(texto),
                "paginas": paginas,
                "posible_escaneado": escaneado,
            }
        )

    (INTERMEDIO / "indice.json").write_text(
        json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Procesados: {hechos} | Ya estaban: {saltados} | Total: {len(indice)}")
    if sospechosos:
        print(
            f"Atencion: {sospechosos} archivo(s) parecen escaneados (poco texto por pagina).\n"
            "Estan marcados en indice.json. Excluilos del set etiquetado o hace un\n"
            "experimento de OCR aparte, pero no los mezcles."
        )


if __name__ == "__main__":
    main()
