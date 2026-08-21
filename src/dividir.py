"""Boletin diario -> un archivo de texto por aviso.

Uso:
    python src/dividir.py                 # procesa todo data/raw/*.pdf
    python src/dividir.py --forzar        # rehace lo ya procesado
    python src/dividir.py --resumen       # solo muestra que encontraria, no escribe

Reemplaza a la ingesta 1-PDF-por-documento: el Boletin Oficial publica UN pdf por
dia con TODOS los avisos de contrataciones adentro (unos 60-70 por edicion), asi
que el trabajo real no es bajar 300 archivos sino cortar bien 5 o 6.

--------------------------------------------------------------------------------
COMO SE CORTA

Cada aviso termina con su pie de publicacion:

    e. 31/07/2026 N° 53047/26 v. 03/08/2026
      |              |            |
      desde          nro de aviso  vence

Ese pie es el delimitador: aparece exactamente una vez por aviso, en su posicion
correcta dentro del texto, y trae ademas el identificador del aviso. Eso lo hace
mejor que cortar por titulos o por saltos de pagina.

El PDF tambien trae marcadores ocultos #I<id>I# / #F<id>F# (inicio y fin de cada
aviso), pero pypdf los extrae al final de cada pagina en vez de en su lugar, asi
que no sirven para cortar: se limpian y se descartan. Si algun dia necesitas esos
ids, hay que leer el PDF con posiciones (pdfplumber o PyMuPDF) en vez de texto plano.

--------------------------------------------------------------------------------
DEDUPLICACION: NO ES UN DETALLE

Un aviso se publica durante VARIOS dias seguidos. El pie lo dice:

    e. 31/07/2026 ... v. 03/08/2026
      publicado desde   hasta

O sea que el mismo aviso aparece igual en las ediciones del 31/7, 1/8, 2/8 y 3/8.
Si juntas ediciones consecutivas sin deduplicar, mas de un tercio del corpus son
repeticiones, y las metricas quedan infladas: el modelo ve el mismo documento
varias veces y los aciertos (o los errores) se cuentan de nuevo.

Este script deduplica por numero de aviso y se queda con la primera aparicion.

Consecuencia practica para armar el corpus: **elegi ediciones separadas entre si**,
no dias consecutivos. Un lunes cada dos semanas rinde mucho mas que cinco dias
seguidos, porque el solapamiento es menor.

--------------------------------------------------------------------------------
LO QUE ESTE SCRIPT NO DECIDE POR VOS

La clasificacion en `tipo` y `formato` es una HEURISTICA, no una verdad. Sirve para
que puedas filtrar y para reportar resultados por segmento, que es donde el
analisis se pone interesante ("el modelo da 97% en formato COMPR.AR y 71% en
formato libre" dice mucho mas que un promedio unico).

Verificala a mano sobre 20 avisos y anota en el README cuantos clasifico mal.
Una heuristica con tasa de error medida es un dato; una sin medir es una suposicion.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw"
INTERMEDIO = RAIZ / "data" / "interim"

# Pie de publicacion: delimita el final de cada aviso y trae su numero.
PIE = re.compile(
    r"e\.\s*(\d{2}/\d{2}/\d{4})\s*N[°º]\s*(\d+/\d{2})\s*v\.\s*(\d{2}/\d{2}/\d{4})"
)

# Marcadores internos del Boletin, fuera de posicion al extraer texto plano.
MARCADORES = re.compile(r"#[IF]\d+[IF]#")

# Encabezado que se repite arriba de cada pagina.
ENCABEZADO = re.compile(
    r"^\s*BOLET[ÍI]N OFICIAL N[º°]\s*[\d.]+\s*-\s*Tercera Secci[óo]n\s+\d+\s+.*$",
    re.MULTILINE,
)

# Rubros de primer nivel. Se detectan como linea completa en mayusculas.
# PREADJUDICACIONES y ADJUDICACIONES ademas cambian el TIPO de documento:
# no son llamados a contratar sino avisos de resultado, y tienen otra forma.
RUBROS = (
    "SUMINISTROS",
    "OBRAS",
    "SERVICIOS",
    "LOCACIONES",
    "VENTAS Y OFRECIMIENTOS DEL ESTADO",
    "PREADJUDICACIONES",
    "ADJUDICACIONES",
)
TIPO_POR_RUBRO = {
    "PREADJUDICACIONES": "preadjudicacion",
    "ADJUDICACIONES": "adjudicacion",
}

# Un aviso en formato COMPR.AR trae estos campos etiquetados. Los organismos que
# publican con formato propio (universidades, BCRA, banca multilateral) no.
SENAL_COMPRAR = re.compile(r"^\s*(UOC|Expediente N[°º]|Ejercicio|Modalidad)\s*:", re.M)


def sin_tildes_may(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("\xa0", " ").strip().upper()


RUBROS_NORM = {sin_tildes_may(r): r for r in RUBROS}


def texto_del_pdf(pdf: Path) -> str:
    import pypdf

    lector = pypdf.PdfReader(str(pdf))
    return "\n".join((p.extract_text() or "") for p in lector.pages)


def limpiar(texto: str) -> str:
    """Saca marcadores, encabezados de pagina y la tapa con el sumario."""
    texto = MARCADORES.sub("", texto)
    texto = ENCABEZADO.sub("", texto)
    # La tapa y el sumario van antes de la unica aparicion de "SUMARIO".
    m = re.search(r"SUMARIO", texto)
    primer_pie = PIE.search(texto)
    if m and primer_pie and m.start() < primer_pie.start():
        texto = texto[m.end():]
    return texto


def separar_rubros(bloque: str, rubro_actual: str | None) -> tuple[str, str | None]:
    """Saca del cuerpo las lineas que son encabezados de rubro y devuelve el vigente.

    Los rubros vienen como lineas sueltas en mayusculas entre aviso y aviso.
    A veces parten en dos lineas ("MUEBLES, ARTICULOS Y UTILES / DE USO DOMESTICO"),
    por eso solo se reconocen los de primer nivel: los de segundo nivel quedan
    dentro del cuerpo, que para extraer no molesta.
    """
    salida = []
    for linea in bloque.splitlines():
        clave = sin_tildes_may(linea)
        if clave in RUBROS_NORM:
            rubro_actual = RUBROS_NORM[clave]
            continue
        salida.append(linea)
    return "\n".join(salida).strip(), rubro_actual


def partir(texto: str, fecha_edicion: str) -> list[dict]:
    """Devuelve un registro por aviso, en orden de aparicion."""
    avisos: list[dict] = []
    inicio = 0
    rubro: str | None = None

    for m in PIE.finditer(texto):
        bruto = texto[inicio:m.start()]
        inicio = m.end()
        cuerpo, rubro = separar_rubros(bruto, rubro)
        if not cuerpo:
            continue
        nro = m.group(2)
        avisos.append(
            {
                "id": nro.replace("/", "-"),
                "nro_aviso": nro,
                "edicion": fecha_edicion,
                "publicado_desde": m.group(1),
                "vence": m.group(3),
                "rubro": rubro,
                "tipo": TIPO_POR_RUBRO.get(rubro or "", "llamado"),
                "formato": "comprar" if SENAL_COMPRAR.search(cuerpo) else "libre",
                "caracteres": len(cuerpo),
                "texto": cuerpo,
            }
        )
    return avisos


def fecha_de(nombre: str) -> str:
    """Saca AAAAMMDD del nombre del archivo; si no lo encuentra, usa el nombre."""
    m = re.search(r"(20\d{6})", nombre)
    return m.group(1) if m else nombre


def main() -> None:
    ap = argparse.ArgumentParser(description="Corta los boletines diarios en avisos.")
    ap.add_argument("--forzar", action="store_true", help="rehacer los ya escritos")
    ap.add_argument("--resumen", action="store_true", help="no escribe, solo informa")
    args = ap.parse_args()

    pdfs = sorted(CRUDO.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No hay PDFs en {CRUDO}. Baja los boletines diarios primero.")

    INTERMEDIO.mkdir(parents=True, exist_ok=True)
    unicos: dict[str, dict] = {}   # nro_aviso -> primera aparicion
    brutos = 0

    for pdf in pdfs:
        texto = limpiar(texto_del_pdf(pdf))
        if len(texto) < 2000:
            print(f"  ! {pdf.name}: casi sin texto. ¿Es un PDF escaneado? Revisalo aparte.")
            continue

        avisos = partir(texto, fecha_de(pdf.stem))
        brutos += len(avisos)
        nuevos = 0
        for a in avisos:
            ya = unicos.get(a["nro_aviso"])
            if ya is None:
                a["ediciones"] = [a["edicion"]]
                unicos[a["nro_aviso"]] = a
                nuevos += 1
            else:
                ya["ediciones"].append(a["edicion"])

        llamados = sum(x["tipo"] == "llamado" for x in avisos)
        comprar = sum(x["formato"] == "comprar" for x in avisos)
        print(
            f"{pdf.name}: {len(avisos):3} avisos "
            f"({llamados} llamados, {len(avisos) - llamados} resultados) | "
            f"{comprar} COMPR.AR, {len(avisos) - comprar} libre | "
            f"{nuevos} nuevos, {len(avisos) - nuevos} repetidos"
        )

    repetidos = brutos - len(unicos)
    print(
        f"\n{brutos} avisos leidos, {repetidos} eran republicaciones "
        f"({repetidos / brutos:.0%}), quedan {len(unicos)} unicos."
    )

    if args.resumen:
        print("(resumen) No se escribio nada.")
        return

    indice = []
    escritos = saltados = 0
    for a in sorted(unicos.values(), key=lambda x: (x["edicion"], x["nro_aviso"])):
        destino = INTERMEDIO / f"{a['id']}.txt"
        if destino.exists() and not args.forzar:
            saltados += 1
        else:
            destino.write_text(a["texto"], encoding="utf-8")
            escritos += 1
        a["apariciones"] = len(a["ediciones"])
        indice.append({k: v for k, v in a.items() if k != "texto"} | {"txt": destino.name})

    (INTERMEDIO / "indice.json").write_text(
        json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Escritos {escritos} | ya estaban {saltados}")
    print(f"Indice en {(INTERMEDIO / 'indice.json').relative_to(RAIZ)}")

    llamados = sum(i["tipo"] == "llamado" for i in indice)
    print(f"\nLlamados unicos disponibles para etiquetar: {llamados}")
    if llamados < 200:
        print(
            f"Te faltan {200 - llamados} para el minimo. Baja mas ediciones, pero\n"
            "ELEGILAS SEPARADAS entre si: dias consecutivos se solapan muchisimo."
        )


if __name__ == "__main__":
    main()
