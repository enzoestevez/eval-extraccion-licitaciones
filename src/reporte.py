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

    # Cobertura completa = evaluada sobre TODO el set etiquetado. Lo demas no se
    # compara, y sobre todo no gana.
    n_total = m["n_etiquetados"]
    completas = [v for v in vs if v["n_documentos"] == n_total]
    incompletas = [v for v in vs if v["n_documentos"] != n_total]
    if not completas:
        sys.exit(
            f"Ninguna variante tiene los {n_total} documentos del set etiquetado.\n"
            "Completa al menos una con src/extraer.py antes de generar el reporte: "
            "un ranking entre muestras distintas no dice nada."
        )

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
        "| Variante | n | Precision | Docs perfectos | Alucinacion | p95 latencia | USD/doc | Que cambia |"
    )
    L.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for v in vs:
        nota = POR_ID[v["variante"]].nota if v["variante"] in POR_ID else ""
        marca = "" if v["n_documentos"] == n_total else " ⚠"
        L.append(
            f"| `{v['variante']}` | {v['n_documentos']}{marca} | {pct(v['precision_ponderada'])} | "
            f"{pct(v['docs_perfectos'])} | {pct(v['tasa_alucinacion'])} | "
            f"{v['latencia_p95_ms']} ms | {usd(v['costo_por_doc_usd'])} | {nota} |"
        )
    L.append("")

    # LA COLUMNA n NO ES DECORATIVA. Una variante evaluada sobre menos
    # documentos que otra no se puede comparar con ella: no es la misma prueba.
    # Esta tabla llego a coronar `v4-modelo-caro` con 83,9% sobre 53 documentos
    # contra `v3-ejemplos` con 83,5% sobre 115, y la diferencia de 0,4 puntos no
    # significaba nada. El dato estaba en metricas.json (`n_documentos` y
    # `errores_llamada`); el reporte no lo mostraba, que es peor que no tenerlo.
    if incompletas:
        L.append(
            f"> **No comparables.** {len(incompletas)} "
            f"{'variante tiene' if len(incompletas) == 1 else 'variantes tienen'} "
            f"menos de {n_total} documentos evaluados, marcadas con ⚠:\n"
        )
        for v in incompletas:
            L.append(
                f"> - `{v['variante']}`: **{v['n_documentos']} de {n_total}** "
                f"({v['errores_llamada']} llamadas fallidas). Su precision esta "
                f"calculada sobre otro subconjunto, mas chico, y no se puede poner "
                f"al lado de las demas."
            )
        L.append(
            ">\n> Para completarla: `python src/extraer.py --variante <id>`, que es "
            "reanudable y sólo pide los documentos que faltan. **Hasta entonces esa "
            "fila no entra en ninguna conclusion.**\n"
        )
    L.append(
        "**Precision** es el promedio ponderado por campo (los pesos estan en `src/esquema.py`). "
        "**Docs perfectos** es el porcentaje de documentos sin un solo campo mal — es la metrica "
        "dura, la que importa si el registro se carga entero o no se carga. "
        "**Alucinacion** es la proporcion de campos donde el modelo puso un valor y la verdad "
        "era `null`; en produccion es el error mas caro y por eso va aparte.\n"
    )

    # La ganadora sale SOLO de las variantes con cobertura completa.
    ganadora = completas[0]

    # --- comparacion emparejada -------------------------------------------
    # Sin esto, la tabla de arriba invita a comparar 61 documentos contra 115.
    emp = m.get("emparejadas") or []
    n_emp = m.get("n_emparejado") or 0
    if emp and n_emp and n_emp < n_total:
        L.append(f"## Comparación emparejada · los mismos {n_emp} documentos\n")
        L.append(
            f"La tabla de arriba da a cada variante su propio `n`, y eso impide "
            f"compararlas entre si. **`v4-modelo-caro` tiene {n_total - n_emp} "
            f"documentos menos** porque la capa gratuita permite **20 llamadas por "
            f"día** a ese modelo: completarla serían tres días de cupo.\n"
        )
        L.append(
            f"La solución no es gastar tres días. Es medir **todas** las variantes "
            f"sobre los mismos {n_emp} documentos —la intersección donde todas "
            f"tienen extracción válida—. Las predicciones ya estaban guardadas, así "
            f"que **la comparación válida salió a costo cero.**\n"
        )
        L.append("| Variante | Precisión | Docs perfectos | Alucinación | USD/doc |")
        L.append("|---|---:|---:|---:|---:|")
        orden = sorted(emp, key=lambda x: -x["precision_ponderada"])
        for v_ in orden:
            L.append(f"| `{v_['variante']}` | {pct(v_['precision_ponderada'])} | "
                     f"{pct(v_['docs_perfectos'])} | {pct(v_['tasa_alucinacion'])} | "
                     f"{usd(v_['costo_por_doc_usd'])} |")
        L.append("")

        por = {v_["variante"]: v_ for v_ in emp}
        caro, barato = por.get("v4-modelo-caro"), por.get("v3-ejemplos")
        if caro and barato:
            dp = (caro["precision_ponderada"] - barato["precision_ponderada"]) * 100
            dd = (caro["docs_perfectos"] - barato["docs_perfectos"]) * 100
            veces = (caro["costo_por_doc_usd"] / barato["costo_por_doc_usd"]
                     if barato["costo_por_doc_usd"] else None)
            L.append(
                f"**El efecto del modelo, por fin medido sobre la misma prueba:** el "
                f"modelo caro gana **{dp:+.1f} puntos de precisión** y "
                f"**{dd:+.1f} puntos de documentos perfectos**"
                + (f", a **{veces:.1f}× el costo**" if veces else "") + ".\n"
            )
            L.append(
                "Y la métrica que decide no es la precisión: es **documentos "
                "perfectos**. El sistema que consume esto "
                "([proyecto 02](https://github.com/enzoestevez/conciliador-contrataciones)) "
                "arma una llave con varios campos — un error en "
                "`numero_procedimiento` no degrada el caso, lo **mata**. Con ese "
                f"criterio la diferencia no es de {dp:.1f} puntos sino de {dd:.1f}, "
                "y ahí la discusión del costo cambia.\n"
            )
        reglas = por.get("v0-reglas")
        if reglas and barato and reglas["docs_perfectos"] > barato["docs_perfectos"]:
            L.append(
                f"**Un detalle que la tabla global escondía:** `v0-reglas`, sin IA y "
                f"a costo cero, tiene **más documentos perfectos** que `v3-ejemplos` "
                f"({pct(reglas['docs_perfectos'])} contra {pct(barato['docs_perfectos'])}) "
                f"con {(barato['precision_ponderada'] - reglas['precision_ponderada'])*100:.1f} "
                f"puntos menos de precisión. El parser determinista acierta el "
                f"documento entero más seguido, pero cuando falla falla en más campos "
                f"a la vez. Dos perfiles de error distintos que un promedio junta.\n"
            )

    # --- por formato: el hallazgo central del proyecto ---------------------
    # Un promedio unico no se puede interpretar, porque cada formato tiene su
    # propio techo humano medido por doble ciego. Esta tabla pone cada numero al
    # lado del techo que le corresponde.
    TECHO = {"comprar": 0.987, "libre": 0.727}
    NOMBRE = {"comprar": "COMPR.AR", "libre": "formato libre"}
    if any(v.get("por_formato") for v in vs):
        L.append("## El promedio unico no sirve: hay que partir por formato\n")
        L.append(
            "El doble ciego midio el techo del experimento —la consistencia de una "
            "persona etiquetando dos veces a ciegas— en **98,7% para COMPR.AR** y "
            "**72,7% para formato libre**. Son dos problemas distintos, y comparar "
            "un modelo contra un techo que no le corresponde no dice nada.\n"
        )
        for f in ("comprar", "libre"):
            filas = [v for v in completas if v.get("por_formato", {}).get(f, {}).get("n")]
            if not filas:
                continue
            techo = TECHO.get(f)
            L.append(f"### {NOMBRE.get(f, f)} · techo humano {pct(techo)}\n")
            L.append("| Variante | n | Precision | Contra el techo | Docs perfectos | Alucinacion |")
            L.append("|---|---:|---:|---:|---:|---:|")
            for v in sorted(filas, key=lambda x: -x["por_formato"][f]["precision"]):
                d = v["por_formato"][f]
                # Un "+5,2" para algo que esta DEBAJO del techo se lee al revés.
                # La columna dice cuanto falta, o dice que ya no falta nada.
                if not techo:
                    brecha = "—"
                elif techo - d["precision"] <= 0.005:
                    brecha = "**en el techo**"
                else:
                    brecha = f"−{(techo - d['precision']) * 100:.1f} pts"
                L.append(
                    f"| `{v['variante']}` | {d['n']} | {pct(d['precision'])} | {brecha} | "
                    f"{pct(d['docs_perfectos'])} | {pct(d['alucinacion'])} |"
                )
            L.append("")

        # La lectura, calculada y no escrita a mano.
        mejor = completas[0]
        pf = mejor.get("por_formato", {})
        reglas = next((v for v in completas if v["variante"] == "v0-reglas"), None)
        if "libre" in pf and TECHO["libre"] - pf["libre"]["precision"] <= 0.01:
            L.append(
                f"**En formato libre el modelo ya esta en el techo humano** "
                f"({pct(pf['libre']['precision'])} contra {pct(TECHO['libre'])}). Lo que "
                f"queda de error no es una limitacion del modelo: es que el documento no "
                f"trae la respuesta de forma inequivoca. Ninguna version del prompt lo va "
                f"a mover, y eso se ve en que las variantes de prompt dan el mismo numero "
                f"en ese formato.\n"
            )
        if "comprar" in pf:
            L.append(
                f"**En COMPR.AR queda margen real:** {pct(pf['comprar']['precision'])} "
                f"contra un techo de {pct(TECHO['comprar'])}, "
                f"{(TECHO['comprar'] - pf['comprar']['precision']) * 100:.1f} puntos.\n"
            )
        if reglas and reglas.get("por_formato"):
            rf = reglas["por_formato"]
            partes = []
            for f in ("comprar", "libre"):
                if f in rf and f in pf:
                    partes.append(
                        f"en {NOMBRE[f]} el extractor determinista saca "
                        f"{pct(rf[f]['precision'])} a costo cero contra "
                        f"{pct(pf[f]['precision'])} del modelo, "
                        f"**{(pf[f]['precision'] - rf[f]['precision']) * 100:+.1f} puntos**"
                    )
            if partes:
                L.append(
                    "**Donde se justifica pagar por un modelo**, que es la pregunta del "
                    "proyecto: " + "; ".join(partes) + ".\n"
                )

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
