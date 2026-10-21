"""Segunda pasada ciega: mide tu propia consistencia y el baseline humano.

Uso:
    python label/doble_ciego.py              # etiqueta la muestra, a ciegas
    python label/doble_ciego.py --comparar   # compara las dos pasadas
    python label/doble_ciego.py --comparar --usd-hora 12

--------------------------------------------------------------------------------
PARA QUE SIRVE

Produce los dos numeros que el proyecto no puede inventar:

1. **El techo del experimento.** Tu coincidencia con vos mismo etiquetando el
   mismo aviso dos veces, sin mirar la primera vez. Ningun modelo puede superar
   la consistencia de la verdad contra la que se lo mide. Si te das 94%, un
   modelo que da 93% no esta lejos del techo: esta practicamente en el.

2. **El baseline humano.** La precision y el tiempo de una persona haciendo la
   tarea sin ayuda. La precision sale de la misma comparacion; el tiempo lo
   cronometra este script solo, por documento, para que no haya que estimarlo.

--------------------------------------------------------------------------------
POR QUE "A CIEGAS" EN SERIO

Este script NO te muestra lo que pusiste la primera vez y NO te muestra ninguna
sugerencia del parser. Tampoco escribe sobre data/gold/etiquetas.jsonl: guarda
aparte en _pasada2.jsonl. Si viera cualquiera de las dos cosas, la comparacion
mediria reconocimiento y no criterio.

Y conviene que pase tiempo entre las dos pasadas. Con dias de diferencia medis
tu criterio; con minutos medis tu memoria.

--------------------------------------------------------------------------------
LIMITACION QUE HAY QUE DECLARAR EN EL README

Es la MISMA persona, con el MISMO protocolo. Eso sesga la coincidencia hacia
arriba: dos operadores distintos coincidirian menos. Sirve como techo del
experimento y como referencia de precision humana, no como medida de lo que
haria un equipo de carga de datos. Escribir esa limitacion vale mas que el numero.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from esquema import CAMPOS, CAMPOS_POR_NOMBRE, PESO_TOTAL, VERSION_ESQUEMA  # noqa: E402
from normalizar import normalizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
ORO = RAIZ / "data" / "gold" / "etiquetas.jsonl"
PASADA2 = RAIZ / "data" / "gold" / "_pasada2.jsonl"
INDICE = INTERMEDIO / "indice.json"

ANCHO = 78
OBJETIVO = 20                 # documentos de la muestra
CAMPOS_SIMILITUD = {"objeto"}  # credito parcial, igual que en evaluar.py
UMBRAL_SIMILITUD = 0.85


def cargar(p: Path) -> dict[str, dict]:
    if not p.exists():
        return {}
    return {
        json.loads(l)["id"]: json.loads(l)
        for l in p.read_text(encoding="utf-8").splitlines()
        if l.strip()
    }


def guardar(registros: dict[str, dict]) -> None:
    with PASADA2.open("w", encoding="utf-8") as f:
        for k in sorted(registros):
            f.write(json.dumps(registros[k], ensure_ascii=False) + "\n")


def muestra(etiquetados: dict[str, dict], idx: dict[str, dict]) -> list[str]:
    """Muestra estratificada: mitad formato COMPR.AR, mitad formato libre.

    Estratificar importa porque los dos formatos tienen dificultad muy distinta.
    Una muestra al azar podria salir casi toda COMPR.AR y darte un techo
    optimista que no representa el corpus.
    """
    por_formato: dict[str, list[str]] = {}
    for doc_id in sorted(etiquetados):
        f = (idx.get(doc_id) or {}).get("formato", "?")
        por_formato.setdefault(f, []).append(doc_id)

    elegidos: list[str] = []
    cupo = max(1, OBJETIVO // max(len(por_formato), 1))
    for f in sorted(por_formato):
        elegidos += por_formato[f][:cupo]
    # Si quedo corta (poco de un formato), completar con lo que haya.
    for f in sorted(por_formato):
        for doc_id in por_formato[f]:
            if len(elegidos) >= OBJETIVO:
                break
            if doc_id not in elegidos:
                elegidos.append(doc_id)
    return elegidos[:OBJETIVO]


# --------------------------------------------------------------------- etiquetar


def mostrar(texto: str) -> None:
    print("\n" + "=" * ANCHO)
    print(texto[:6000])
    print("=" * ANCHO)


def pedir(campo, texto: str):
    """Sin sugerencia y sin valor previo. Enter no es null: hay que escribir `-`."""
    marca = "" if campo.obligatorio else "  [opcional]"
    while True:
        print(f"\n  {campo.nombre}  <{campo.tipo}>{marca}")
        print(f"    {campo.descripcion}")
        try:
            v = input("    [-=null  ?=ver aviso] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCortado. Lo hecho hasta el documento anterior quedo guardado.")
            sys.exit(0)
        if v == "?":
            mostrar(texto)
            continue
        if v == "":
            print("    Enter no pone null. Escribi el valor, o `-` si el dato no esta.")
            continue
        if v == "-":
            return None
        if normalizar(campo.tipo, v) is None:
            print(f"    No pude interpretar eso como {campo.tipo}. Proba de nuevo.")
            continue
        return v


def etiquetar() -> None:
    etiquetados = cargar(ORO)
    if not etiquetados:
        sys.exit(f"No hay set etiquetado en {ORO}.")
    idx = {r["id"]: r for r in json.loads(INDICE.read_text(encoding="utf-8"))}
    hechos = cargar(PASADA2)
    cola = [d for d in muestra(etiquetados, idx) if d not in hechos]

    if not hechos:
        print(
            "\nSEGUNDA PASADA CIEGA\n"
            f"{OBJETIVO} avisos ya etiquetados, estratificados por formato.\n"
            "No vas a ver lo que pusiste la primera vez ni ninguna sugerencia.\n"
            "Etiquetalos como si fuera la primera vez. El reloj corre solo.\n"
        )
    if not cola:
        print("La muestra ya esta completa. Compara con --comparar.")
        return
    print(f"{len(cola)} de {OBJETIVO} por hacer. Ctrl+C corta y guarda.\n")

    for doc_id in cola:
        texto = (INTERMEDIO / idx[doc_id]["txt"]).read_text(encoding="utf-8")
        print("\n" + "#" * ANCHO)
        print(f"# {doc_id}   [ciego]   {len(hechos) + 1}/{OBJETIVO}")
        print("#" * ANCHO)
        mostrar(texto)

        t0 = time.perf_counter()
        datos = {c.nombre: pedir(c, texto) for c in CAMPOS}
        segundos = round(time.perf_counter() - t0, 1)

        hechos[doc_id] = {
            "id": doc_id,
            "datos": datos,
            "segundos": segundos,
            "version_esquema": VERSION_ESQUEMA,
            "etiquetado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        guardar(hechos)
        print(f"  guardado · {segundos:.0f}s · {len(hechos)}/{OBJETIVO}")

    print(f"\nMuestra completa. Ahora:  python label/doble_ciego.py --comparar")


# --------------------------------------------------------------------- comparar


def comparar_campo(nombre: str, a, b) -> float:
    """Mismo criterio que evaluar.py: valor normalizado, credito parcial en texto largo."""
    campo = CAMPOS_POR_NOMBRE[nombre]
    x, y = normalizar(campo.tipo, a), normalizar(campo.tipo, b)
    if x is None and y is None:
        return 1.0
    if x is None or y is None:
        return 0.0
    if nombre in CAMPOS_SIMILITUD:
        s = SequenceMatcher(None, str(x), str(y)).ratio()
        return s if s >= UMBRAL_SIMILITUD else s
    return 1.0 if x == y else 0.0


def comparar(usd_hora: float | None) -> None:
    p1, p2 = cargar(ORO), cargar(PASADA2)
    comunes = sorted(set(p1) & set(p2))
    if not comunes:
        sys.exit("No hay documentos en comun. Corre primero sin --comparar.")

    idx = {r["id"]: r for r in json.loads(INDICE.read_text(encoding="utf-8"))}
    por_campo = {c.nombre: [] for c in CAMPOS}
    por_doc, exactos, tiempos = [], 0, []
    por_formato: dict[str, list[float]] = {}

    for doc_id in comunes:
        pond = 0.0
        todos_ok = True
        for c in CAMPOS:
            s = comparar_campo(c.nombre, p1[doc_id]["datos"].get(c.nombre),
                               p2[doc_id]["datos"].get(c.nombre))
            por_campo[c.nombre].append(s)
            pond += s * c.peso
            todos_ok &= s == 1.0
        pond /= PESO_TOTAL
        por_doc.append(pond)
        exactos += todos_ok
        f = (idx.get(doc_id) or {}).get("formato", "?")
        por_formato.setdefault(f, []).append(pond)
        if p2[doc_id].get("segundos"):
            tiempos.append(p2[doc_id]["segundos"])

    n = len(comunes)
    global_ = sum(por_doc) / n

    print(f"\nDOBLE CIEGO · {n} documentos\n")
    print(f"  Coincidencia ponderada     {global_:.1%}   <- el TECHO del experimento")
    print(f"  Documentos identicos       {exactos}/{n} ({exactos/n:.0%})")
    print()
    print("  Por formato:")
    for f in sorted(por_formato):
        v = por_formato[f]
        print(f"    {f:10} {sum(v)/len(v):.1%}  (n={len(v)})")
    print()
    print("  Por campo (donde te contradecis):")
    for c in sorted(CAMPOS, key=lambda c: sum(por_campo[c.nombre]) / len(por_campo[c.nombre])):
        v = por_campo[c.nombre]
        print(f"    {c.nombre:22} {sum(v)/len(v):.1%}")

    if tiempos:
        tiempos.sort()
        medio = sum(tiempos) / len(tiempos)
        mediano = tiempos[len(tiempos) // 2]
        print(f"\n  BASELINE HUMANO · tiempo medido sobre {len(tiempos)} documentos")
        print(f"    promedio   {medio:.0f}s  ({medio/60:.1f} min/documento)")
        print(f"    mediano    {mediano:.0f}s")
        print(f"    rango      {tiempos[0]:.0f}s – {tiempos[-1]:.0f}s")
        if usd_hora:
            costo = medio / 3600 * usd_hora
            print(f"    costo      USD {costo:.3f}/documento  (a USD {usd_hora:.2f}/hora)")
            print(f"               USD {costo*1000:.2f} por cada 1.000 documentos")
        else:
            print("    Pasa --usd-hora <valor> para el costo por documento.")
            print("    Usa un salario real de mercado para carga de datos y cita la fuente.")

    print(
        f"\n  Para el README: la precision humana sin ayuda es {global_:.1%} y ningun\n"
        f"  modelo de este experimento puede superar ese numero de forma significativa.\n"
        "  Declara la limitacion: misma persona, mismo protocolo, sesgado hacia arriba."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Segunda pasada ciega y comparacion.")
    ap.add_argument("--comparar", action="store_true")
    ap.add_argument("--usd-hora", type=float, help="costo por hora de quien cargaria los datos")
    args = ap.parse_args()
    comparar(args.usd_hora) if args.comparar else etiquetar()


if __name__ == "__main__":
    main()
