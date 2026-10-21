"""CLI de etiquetado. Aca se construye el activo mas valioso del proyecto.

Uso:
    python label/etiquetar.py               # sigue por el primero sin etiquetar
    python label/etiquetar.py --id 53047-26
    python label/etiquetar.py --auditados   # corrige los que marco label/auditar.py
    python label/etiquetar.py --revisar     # repasa TODOS los ya etiquetados
    python label/etiquetar.py --estado      # cuantos van y tasa de correccion
    python label/etiquetar.py --sin-asistencia   # apaga la precarga en toda la sesion

--------------------------------------------------------------------------------
PRECARGA ASISTIDA, Y POR QUE HAY UNA MUESTRA CIEGA

Para no tipear ocho campos por aviso, src/reglas.py (un parser deterministico,
SIN IA) precarga los valores y vos aceptas o corregis. Eso acelera muchisimo el
formato COMPR.AR, donde los campos vienen etiquetados.

Tiene un costo real y hay que mirarlo de frente: **sesgo de anclaje**. Cuando un
valor viene sugerido, el ojo tiende a aceptarlo sin verificar de verdad, y los
errores del parser se filtran a tu verdad de referencia. Si eso pasa, el harness
despues mide mal Y ADEMAS te favorece al parser, que es la peor combinacion.

Dos defensas, las dos automaticas:

1. **Muestra ciega del 15%.** Uno de cada siete avisos, elegido de forma
   deterministica por su id, se etiqueta SIN ninguna sugerencia. Como el harness
   despues corre `v0-reglas` sobre todo el corpus, vas a poder comparar: si el
   parser acierta mucho mas en los avisos asistidos que en los ciegos, la
   diferencia es tu sesgo de anclaje, medido en puntos.

2. **Procedencia por campo.** Cada valor guarda si lo aceptaste, lo corregiste o
   lo escribiste de cero. `--estado` te da la tasa de correccion. Un numero bajo
   puede significar que el parser es bueno... o que estas apretando Enter sin
   leer. Por eso hace falta la muestra ciega para desempatar.

Todo esto va declarado en el README. Un atajo declarado y medido es metodologia;
uno escondido es un problema.

--------------------------------------------------------------------------------
CONTROLES

    Enter        -> aceptar la sugerencia (SOLO si hay una en pantalla)
    -            -> null: el dato NO figura en el aviso
    .            -> saltear el documento entero
    ?            -> volver a mostrar el texto del aviso

**Enter nunca significa null.** Si no hay sugerencia, Enter no hace nada y te
vuelve a preguntar. Para poner null tenes que escribir `-` a proposito.

Esto no es un capricho de diseno: la primera version usaba Enter para null, y
sobre 50 avisos reales produjo 43 campos marcados null cuyo dato SI estaba en el
texto. Cuando el parser no sugeria nada -que es justo lo que pasa en el formato
libre- la tecla mas comoda era la que decia "aca no hay dato". El set quedaba
siendo "lo que encontro el parser, y null en todo lo demas", lo cual hace que el
parser parezca perfecto y que cualquier modelo parezca malo.

Ademas hay una GUARDA DE NULL: si marcas null en un campo pero el texto contiene
una palabra clave de ese campo, la herramienta te muestra la linea y te pide que
confirmes. Se puede confirmar, pero no distraido.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from esquema import CAMPOS, VERSION_ESQUEMA  # noqa: E402
from normalizar import normalizar  # noqa: E402
from reglas import extraer  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
ORO = RAIZ / "data" / "gold" / "etiquetas.jsonl"
INDICE = INTERMEDIO / "indice.json"

ANCHO = 78
PORCENTAJE_CIEGO = 15

# Guarda de null: si marcas null pero el texto trae alguna de estas palabras,
# la herramienta te muestra la linea y te pide confirmar. Son las trampas
# medidas sobre el corpus real: los campos donde el formato libre esconde el
# dato con otro nombre y el parser no lo encuentra.
PISTAS_NULL = {
    "expediente": r"(expediente|expte\.?|actuaci[óo]n\s+n)",
    "fecha_apertura": r"(apertura)",
    "objeto": r"(objeto|objetivo de la contrataci)",
    "monto_estimado": r"(presupuesto\s+oficial|monto\s+estimado|valor\s+estimado)",
    "valor_pliego": r"(valor\s+del\s+pliego|costo\s+del\s+pliego|precio\s+del\s+pliego)",
    "tipo_procedimiento": r"(licitaci[óo]n|contrataci[óo]n\s+directa|concurso|subasta|compulsa)",
}


def es_ciego(doc_id: str) -> bool:
    """Deterministico: el mismo aviso cae siempre del mismo lado.

    Asi la muestra ciega es reproducible y no depende de en que orden etiquetaste.
    """
    h = int(hashlib.md5(doc_id.encode()).hexdigest(), 16)
    return h % 100 < PORCENTAJE_CIEGO


def ids_llamados() -> set[str] | None:
    """Solo los avisos de convocatoria.

    Las adjudicaciones y preadjudicaciones son avisos de RESULTADO: no tienen
    fecha de apertura ni valor de pliego, y la mitad de los campos del esquema
    no les aplica. Etiquetarlas mezcla dos tareas distintas y ensucia la metrica.
    Quedan fuera del set y eso va declarado en el README.
    """
    if not INDICE.exists():
        return None
    idx = json.loads(INDICE.read_text(encoding="utf-8"))
    return {r["id"] for r in idx if r.get("tipo") == "llamado"}


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


def confirmar_null(campo, texto: str) -> bool:
    """Si el texto trae una pista de este campo, mostrarla y pedir confirmacion."""
    patron = PISTAS_NULL.get(campo.nombre)
    if not patron:
        return True
    m = re.search(patron, texto, re.I)
    if not m:
        return True
    linea = texto[max(0, texto.rfind("\n", 0, m.start()) + 1):]
    linea = linea.split("\n")[0].strip()
    print(f"\n    ! Marcaste null, pero el aviso dice:")
    print(f"      \"{linea[:150]}\"")
    try:
        return input("      ¿Confirmás null? [s/N] > ").strip().lower() in ("s", "si", "sí")
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)


def pedir_campo(campo, texto: str, sugerido, valor_previo=None):
    """Devuelve (valor, origen, saltear_documento)."""
    marca = "" if campo.obligatorio else "  [opcional]"
    previo = f"  (actual: {valor_previo!r})" if valor_previo is not None else ""
    tiene_sug = sugerido is not None and str(sugerido).strip() != ""

    while True:
        print(f"\n  {campo.nombre}  <{campo.tipo}>{marca}{previo}")
        print(f"    {campo.descripcion}")
        if tiene_sug:
            print(f"    sugerido: {sugerido}")
            ayuda = "[Enter=aceptar  -=null]"
        else:
            ayuda = "[-=null  ?=ver aviso]"
        try:
            v = input(f"    {ayuda} > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCortado. Lo etiquetado hasta el documento anterior quedo guardado.")
            sys.exit(0)

        if v == ".":
            return None, None, True
        if v == "?":
            mostrar_texto(texto)
            continue
        if v == "":
            if tiene_sug:
                return sugerido, "aceptado", False
            # Enter NO es null. Ver el encabezado de este archivo.
            print("    Enter no pone null. Escribi el valor, o `-` si el dato no esta.")
            continue
        if v == "-":
            if not confirmar_null(campo, texto):
                continue
            return None, ("corregido" if tiene_sug else "manual"), False

        norm = normalizar(campo.tipo, v)
        if norm is None:
            print(f"    No pude interpretar eso como {campo.tipo}. Proba de nuevo.")
            continue
        print(f"    ok -> {norm!r}")
        return v, ("corregido" if tiene_sug else "manual"), False


def etiquetar_uno(doc_id: str, texto: str, previo: dict | None, asistir: bool) -> dict | None:
    ciego = es_ciego(doc_id)
    modo = "ciego" if (ciego or not asistir) else "asistido"
    sugerencias = extraer(texto) if modo == "asistido" else {}

    print("\n" + "#" * ANCHO)
    print(f"# {doc_id}   [{modo}]")
    print("#" * ANCHO)
    mostrar_texto(texto)
    if modo == "ciego":
        print("\n  Este aviso va SIN sugerencias: es parte de la muestra de control.")

    datos, origen = {}, {}
    for c in CAMPOS:
        v, org, saltear = pedir_campo(
            c,
            texto,
            sugerencias.get(c.nombre),
            (previo or {}).get("datos", {}).get(c.nombre),
        )
        if saltear:
            print("  Documento salteado.")
            return None
        datos[c.nombre] = v
        origen[c.nombre] = org

    print("\n  ¿Algo dudoso en este documento? (Enter si no)")
    try:
        nota = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)

    reg = {
        "id": doc_id,
        "datos": datos,
        "modo": modo,
        "origen": origen,
        "dudoso": bool(nota),
        "nota": nota,
        "version_esquema": VERSION_ESQUEMA,
        "etiquetado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if modo == "asistido":
        reg["sugerido"] = {k: sugerencias.get(k) for k in datos}
    return reg


def estado(registros: dict, docs: list[Path]) -> None:
    dudosos = sum(1 for r in registros.values() if r.get("dudoso"))
    viejos = sum(1 for r in registros.values() if r.get("version_esquema") != VERSION_ESQUEMA)
    asistidos = [r for r in registros.values() if r.get("modo") == "asistido"]
    ciegos = [r for r in registros.values() if r.get("modo") == "ciego"]

    print(f"Etiquetados : {len(registros)} / {len(docs)}")
    print(f"  asistidos : {len(asistidos)}")
    print(f"  ciegos    : {len(ciegos)}   (muestra de control, objetivo ~{PORCENTAJE_CIEGO}%)")
    print(f"Dudosos     : {dudosos}")
    if viejos:
        print(f"Con esquema viejo: {viejos}  -> revisalos con --revisar")

    # Hay DOS grupos de campos y hay que mirarlos por separado. Mezclarlos
    # esconde justo lo que importa:
    #
    #   con sugerencia  -> el parser propuso algo; el riesgo es aceptarlo sin leer
    #   sin sugerencia  -> el parser no encontro nada; lo escribis vos de cero
    #
    # La "tasa de correccion" solo puede hablar del primer grupo. Cuando esta en
    # 0% no significa que no revisaste: puede significar que el parser acierta
    # donde se anima a proponer, y que todo tu trabajo real esta en el segundo
    # grupo, que esta metrica no ve. Por eso ahora se reportan los dos.
    con_sug = sin_sug = corregidos = con_valor = 0
    por_campo: dict[str, list[int]] = {}
    for r in registros.values():
        origen = r.get("origen", {})
        for campo, org in origen.items():
            if org in ("aceptado", "corregido"):
                con_sug += 1
                es_corr = org == "corregido"
                corregidos += es_corr
                por_campo.setdefault(campo, []).append(es_corr)
            elif org == "manual":
                sin_sug += 1
                con_valor += r["datos"].get(campo) is not None

    if con_sug or sin_sug:
        print("\nCampos:")
        if con_sug:
            print(
                f"  con sugerencia : {con_sug:4}  -> corregiste {corregidos} "
                f"({corregidos / con_sug:.1%})"
            )
        if sin_sug:
            print(
                f"  escritos por vos: {sin_sug:4}  -> {con_valor} con valor, "
                f"{sin_sug - con_valor} en null"
            )
        if con_sug and por_campo:
            peor = sorted(
                ((c, sum(v) / len(v)) for c, v in por_campo.items() if v),
                key=lambda x: -x[1],
            )[:3]
            if peor and peor[0][1] > 0:
                print("  mas corregis   : " + ", ".join(f"{c} {pp:.0%}" for c, pp in peor))
        print(
            "\n  Una tasa de correccion baja no prueba que revisaste: solo mira los\n"
            "  campos donde el parser propuso algo. Corre `python label/auditar.py`\n"
            "  para revisar los que escribiste vos, que es donde se cuelan los null."
        )

    print(f"\nObjetivo: 200-300 para que los numeros signifiquen algo")


def main() -> None:
    ap = argparse.ArgumentParser(description="Etiquetado manual del set de referencia.")
    ap.add_argument("--id", help="etiquetar un documento puntual")
    ap.add_argument("--revisar", action="store_true", help="repasar los ya etiquetados")
    ap.add_argument(
        "--auditados",
        action="store_true",
        help="repasar solo los que marca label/auditar.py, uno atras del otro",
    )
    ap.add_argument("--estado", action="store_true")
    ap.add_argument(
        "--sin-asistencia",
        action="store_true",
        help="apagar la precarga por reglas en toda la sesion",
    )
    ap.add_argument(
        "--todos-los-tipos",
        action="store_true",
        help="incluir adjudicaciones y preadjudicaciones (por defecto se excluyen)",
    )
    args = ap.parse_args()

    docs = sorted(INTERMEDIO.glob("*.txt"))
    if not docs:
        sys.exit(f"No hay textos en {INTERMEDIO}. Corre src/dividir.py primero.")

    if not args.todos_los_tipos:
        llamados = ids_llamados()
        if llamados is None:
            print("Aviso: no encontre indice.json, no puedo filtrar por tipo.")
        else:
            antes = len(docs)
            docs = [p for p in docs if p.stem in llamados]
            if antes != len(docs):
                print(
                    f"Filtrados {antes - len(docs)} avisos de resultado "
                    "(adjudicaciones/preadjudicaciones). Con --todos-los-tipos se incluyen."
                )

    registros = cargar()
    if args.estado:
        estado(registros, docs)
        return

    if args.id:
        cola = [p for p in docs if p.stem == args.id]
        if not cola:
            sys.exit(f"No encontre {args.id} en {INTERMEDIO}")
    elif args.auditados:
        from auditar import ids_a_revisar

        marcados = ids_a_revisar()
        if not marcados:
            print("La auditoria no marco ningun aviso. Nada que corregir.")
            return
        orden = {i: n for n, i in enumerate(marcados)}
        cola = sorted((p for p in docs if p.stem in orden), key=lambda p: orden[p.stem])
        print(f"\nLa auditoria marco {len(cola)} aviso(s). Los vas a ver en orden.")
    elif args.revisar:
        cola = [p for p in docs if p.stem in registros]
    else:
        cola = [p for p in docs if p.stem not in registros]

    if not cola:
        print("No queda nada por etiquetar.")
        estado(registros, docs)
        return

    print(f"\n{len(cola)} documento(s) en cola. Ctrl+C corta y guarda lo hecho.")
    for p in cola:
        r = etiquetar_uno(
            p.stem, p.read_text(encoding="utf-8"), registros.get(p.stem), not args.sin_asistencia
        )
        if r is not None:
            registros[p.stem] = r
            guardar(registros)
            print(f"  guardado ({len(registros)} en total)")

    estado(registros, docs)


if __name__ == "__main__":
    main()
