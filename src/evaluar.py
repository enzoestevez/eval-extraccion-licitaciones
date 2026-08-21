"""Evaluacion campo por campo y analisis de umbral.

Uso:
    python src/evaluar.py                 # evalua todas las variantes con predicciones
    python src/evaluar.py --variante v2-reglas

Produce reports/metricas.json, que es lo que consume reporte.py.

Decisiones de medicion que tenes que poder defender:

1. Se compara sobre valores NORMALIZADOS, no sobre el string crudo. Ver normalizar.py.

2. Los campos de texto largo (objeto) se puntuan por similitud con credito parcial,
   porque exigir coincidencia exacta de un parrafo libre mide transcripcion, no
   comprension. El resto se puntua exacto: un expediente esta bien o esta mal.

3. Null acertado cuenta como acierto. Si el aviso no trae el monto y el modelo
   devuelve null, acerto. Este es el caso que casi todos los benchmarks caseros
   cuentan mal, y es justo el que separa un modelo prudente de uno que inventa.

4. Se reporta aparte la ALUCINACION: el modelo puso un valor donde la verdad era
   null. Es el error mas caro en produccion y merece su propia linea, no
   diluirse dentro de "precision".

5. La precision global es un promedio PONDERADO por el peso de cada campo, que
   esta definido en esquema.py segun cuanto duele el error. No todos los campos
   valen lo mismo y promediarlos parejo es una decision, no una neutralidad.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from esquema import CAMPOS, CAMPOS_POR_NOMBRE, PESO_TOTAL  # noqa: E402
from normalizar import normalizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
ORO = RAIZ / "data" / "gold" / "etiquetas.jsonl"
REPORTES = RAIZ / "reports"
PRECIOS = RAIZ / "config" / "precios.json"

# Campos de texto libre largo: credito parcial por similitud.
CAMPOS_SIMILITUD = {"objeto"}
UMBRAL_SIMILITUD = 0.85


def cargar_jsonl(p: Path) -> dict[str, dict]:
    if not p.exists():
        return {}
    out = {}
    for linea in p.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            r = json.loads(linea)
            out[r["id"]] = r
    return out


def comparar_campo(nombre: str, esperado, obtenido) -> tuple[float, str]:
    """Devuelve (puntaje 0..1, categoria).

    Categorias: acierto | acierto_null | error | alucinacion | omision
    """
    campo = CAMPOS_POR_NOMBRE[nombre]
    e = normalizar(campo.tipo, esperado)
    o = normalizar(campo.tipo, obtenido)

    if e is None and o is None:
        return 1.0, "acierto_null"
    if e is None and o is not None:
        return 0.0, "alucinacion"
    if e is not None and o is None:
        return 0.0, "omision"

    if nombre in CAMPOS_SIMILITUD:
        s = SequenceMatcher(None, str(e), str(o)).ratio()
        return (s, "acierto") if s >= UMBRAL_SIMILITUD else (s, "error")

    return (1.0, "acierto") if e == o else (0.0, "error")


def costo_usd(variante_id: str, tin: int, tout: int) -> float | None:
    """Costo por corrida, con precios que TENES que cargar vos.

    No hay precios hardcodeados a proposito: cambian seguido y un numero
    inventado en tu reporte es peor que no tener el numero. Cargalos en
    config/precios.json desde la pagina de precios de cada proveedor,
    y anota en el README la fecha en que los consultaste.
    """
    if not PRECIOS.exists():
        return None
    tabla = json.loads(PRECIOS.read_text(encoding="utf-8"))
    p = tabla.get(variante_id)
    if not p or p.get("usd_por_millon_in") is None:
        return None
    return tin / 1e6 * p["usd_por_millon_in"] + tout / 1e6 * p["usd_por_millon_out"]


def evaluar_variante(variante_id: str, oro: dict[str, dict]) -> dict | None:
    pred = cargar_jsonl(INTERMEDIO / f"pred_{variante_id}.jsonl")
    comunes = sorted(set(oro) & set(pred))
    if not comunes:
        return None

    por_campo: dict[str, dict] = {
        c.nombre: defaultdict(int) | {"suma": 0.0, "n": 0} for c in CAMPOS
    }
    por_doc = []
    tin = tout = lat_total = errores_llamada = 0
    latencias = []

    for doc_id in comunes:
        p = pred[doc_id]
        if p.get("error"):
            errores_llamada += 1
            continue
        datos_o = oro[doc_id]["datos"]
        datos_p = p["datos"]

        puntaje_doc = 0.0
        detalle = {}
        for c in CAMPOS:
            s, cat = comparar_campo(c.nombre, datos_o.get(c.nombre), datos_p.get(c.nombre))
            por_campo[c.nombre]["suma"] += s
            por_campo[c.nombre]["n"] += 1
            por_campo[c.nombre][cat] += 1
            puntaje_doc += s * c.peso
            detalle[c.nombre] = cat

        puntaje_doc /= PESO_TOTAL
        exacto = all(v in ("acierto", "acierto_null") for v in detalle.values())
        por_doc.append(
            {
                "id": doc_id,
                "puntaje": round(puntaje_doc, 4),
                "exacto": exacto,
                "confianza": datos_p.get("confianza", 0.0) or 0.0,
                "detalle": detalle,
            }
        )
        tin += p.get("tokens_in", 0)
        tout += p.get("tokens_out", 0)
        latencias.append(p.get("latencia_ms", 0))

    if not por_doc:
        return None

    n = len(por_doc)
    latencias.sort()
    precision = sum(d["puntaje"] for d in por_doc) / n
    alucinaciones = sum(
        por_campo[c.nombre]["alucinacion"] for c in CAMPOS
    )
    total_campos = n * len(CAMPOS)
    costo = costo_usd(variante_id, tin, tout)

    return {
        "variante": variante_id,
        "n_documentos": n,
        "errores_llamada": errores_llamada,
        "precision_ponderada": round(precision, 4),
        "docs_perfectos": round(sum(d["exacto"] for d in por_doc) / n, 4),
        "tasa_alucinacion": round(alucinaciones / total_campos, 4),
        "latencia_p50_ms": latencias[n // 2] if latencias else 0,
        "latencia_p95_ms": latencias[min(int(n * 0.95), n - 1)] if latencias else 0,
        "tokens_in": tin,
        "tokens_out": tout,
        "costo_total_usd": round(costo, 4) if costo is not None else None,
        "costo_por_doc_usd": round(costo / n, 6) if costo is not None else None,
        "por_campo": {
            c.nombre: {
                "precision": round(por_campo[c.nombre]["suma"] / por_campo[c.nombre]["n"], 4),
                "peso": c.peso,
                "acierto": por_campo[c.nombre]["acierto"],
                "acierto_null": por_campo[c.nombre]["acierto_null"],
                "error": por_campo[c.nombre]["error"],
                "alucinacion": por_campo[c.nombre]["alucinacion"],
                "omision": por_campo[c.nombre]["omision"],
            }
            for c in CAMPOS
        },
        "curva_umbral": curva_umbral(por_doc),
        "peores": sorted(por_doc, key=lambda d: d["puntaje"])[:10],
    }


def curva_umbral(por_doc: list[dict]) -> list[dict]:
    """El analisis que convierte una metrica en una decision operativa.

    Para cada umbral de confianza: que porcentaje de documentos se auto-procesa,
    que porcentaje va a revision humana, y que precision queda sobre lo que
    se auto-proceso. Ese ultimo numero es el que le importa a quien te contrata:
    "con revision del X% de los casos, el sistema sostiene Y% de precision".
    """
    filas = []
    n = len(por_doc)
    for u in [i / 20 for i in range(21)]:
        auto = [d for d in por_doc if d["confianza"] >= u]
        if not auto:
            filas.append(
                {"umbral": round(u, 2), "tasa_auto": 0.0, "tasa_revision": 1.0, "precision_auto": None}
            )
            continue
        filas.append(
            {
                "umbral": round(u, 2),
                "tasa_auto": round(len(auto) / n, 4),
                "tasa_revision": round(1 - len(auto) / n, 4),
                "precision_auto": round(sum(d["puntaje"] for d in auto) / len(auto), 4),
            }
        )
    return filas


def main() -> None:
    ap = argparse.ArgumentParser(description="Evalua las predicciones contra el set etiquetado.")
    ap.add_argument("--variante", action="append")
    args = ap.parse_args()

    oro = cargar_jsonl(ORO)
    if not oro:
        sys.exit(f"No hay set etiquetado en {ORO}. Corre label/etiquetar.py primero.")

    ids = args.variante or sorted(
        p.stem.replace("pred_", "") for p in INTERMEDIO.glob("pred_*.jsonl")
    )
    if not ids:
        sys.exit("No hay predicciones. Corre src/extraer.py primero.")

    resultados = []
    for vid in ids:
        r = evaluar_variante(vid, oro)
        if r is None:
            print(f"{vid}: sin documentos en comun entre predicciones y set etiquetado.")
            continue
        resultados.append(r)
        costo = (
            f" | {r['costo_por_doc_usd']:.6f} USD/doc"
            if r["costo_por_doc_usd"] is not None
            else " | costo sin cargar"
        )
        print(
            f"{vid:22} precision {r['precision_ponderada']:.1%} | "
            f"perfectos {r['docs_perfectos']:.1%} | "
            f"alucinacion {r['tasa_alucinacion']:.2%}{costo}"
        )

    REPORTES.mkdir(parents=True, exist_ok=True)
    salida = REPORTES / "metricas.json"
    salida.write_text(
        json.dumps({"n_etiquetados": len(oro), "variantes": resultados}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nEscrito {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
