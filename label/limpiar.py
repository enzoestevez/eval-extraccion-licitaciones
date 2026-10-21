"""Limpieza del set de referencia: aplica las reglas que el doble ciego descubrio.

Uso:
    python label/limpiar.py              # muestra qué cambiaría, no escribe
    python label/limpiar.py --aplicar    # escribe

--------------------------------------------------------------------------------
QUE DESCUBRIO EL DOBLE CIEGO

La segunda pasada ciega dio 79,7% de coincidencia. Al mirar los desacuerdos uno
por uno, casi ninguno era ambiguedad real de la tarea: eran reglas que le
faltaban al protocolo, y afectan a TODO el set, no solo a la muestra de 20.

REGLA 1 · `tipo_procedimiento` no lleva el numero.
    mal:  "Licitación Pública 0023/2026"
    bien: "Licitación Pública"           (el numero va en numero_procedimiento)
    Deterministico: se compara contra la lista canonica de tipos y se recorta
    lo que venga pegado atras.

REGLA 2 · el organismo no incluye el rubro del boletin.
    Al cortar el boletin, src/dividir.py limpia los rubros de primer nivel
    (SUMINISTROS, OBRAS, SERVICIOS) pero no los de segundo nivel. Entonces el
    aviso arranca con "PRODUCTOS ALIMENTICIOS" y abajo "ARMADA ARGENTINA".
    mal:  "PRODUCTOS ALIMENTICIOS ARMADA ARGENTINA"
    bien: "ARMADA ARGENTINA"

--------------------------------------------------------------------------------
UNA REGLA QUE HUBO QUE TIRAR, Y POR QUE

El primer intento de la regla 2 suponia que la primera linea del aviso era el
rubro. Resulto falso en las dos direcciones y habria corrompido el set:

    'ADMINISTRACIÓN DE INFRAESTRUCTURAS FERROVIARIAS SOCIEDAD ANÓNIMA'
      -> 'FERROVIARIAS SOCIEDAD ANÓNIMA'      (partio el nombre al medio)

    'BANCO DE LA NACIÓN ARGENTINA Licitación Pública CDS 1307/2026 OBJETO: ...'
      -> 'Licitación Pública CDS 1307/2026 OBJETO: ...'   (borro la respuesta)

La version que quedo no adivina: recorta un prefijo SOLO si coincide exacto con
un rubro de la lista de abajo, y esa lista no es inventada, sale de los SUMARIOS
de las cinco ediciones del corpus. Un prefijo que no este en la lista no se toca.

LO QUE **NO** SE ARREGLA SOLO

El organismo que siguio capturando texto de las lineas siguientes. Donde termina
el organismo es criterio, no regla. Se listan al final y los decide la persona.

--------------------------------------------------------------------------------
POR QUE SE LIMPIAN LAS DOS PASADAS

Las mismas reglas valen para `etiquetas.jsonl` y para `_pasada2.jsonl`. Si se
limpia solo una, la comparacion del doble ciego deja de medir consistencia y
empieza a medir cual de las dos se limpio.

Y POR QUE NO SE VUELVE A CORTAR EL CORPUS

Arreglar dividir.py para que saque los rubros de segundo nivel seria lo prolijo,
pero cambiaria el texto que vieron los modelos y habria que rehacer las
predicciones ya corridas. El rubro colado lo ven el humano y el modelo por igual,
asi que la comparacion sigue siendo justa. Queda declarado en el README.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reglas import TIPOS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
GOLD = RAIZ / "data" / "gold"
ARCHIVOS = ("etiquetas.jsonl", "_pasada2.jsonl")

# Rubros extraidos de los SUMARIOS de las cinco ediciones del corpus
# (1/6, 19/6, 1/7, 20/7 y 3/8 de 2026). No es una lista a ojo: son las
# categorias que el propio Boletin declara en su indice.
RUBROS = (
    "ADJUDICACIONES", "BOMBAS Y COMPRESORES", "CIVILES", "CONCESIONES",
    "DICTÁMENES DE EVALUACIÓN", "EFECTOS VARIOS",
    "ELECTRICIDAD Y FERRETERÍA ELÉCTRICA",
    "EQ. PROC. AUTOMÁTICO DE DATOS, SOFT., SUM. Y EQ. APOYO",
    "EQ. REFRIG. ACONDICIONAMIENTO Y CIRCULACIÓN DE AIRE",
    "EQ. Y SUM. DE PLOMERÍA, CALEFACCIÓN Y SANITARIOS",
    "EQ. Y SUM. MEDICINA, ODONTOLOGÍA Y VETERINARIA",
    "EQUIPOS FERROVIARIOS, REPUESTOS Y SUMINISTROS", "EQUIPOS PARA FOTOCOPIADO",
    "INMUEBLES (LOC)", "INMUEBLES", "INSTRUMENTAL Y EQUIPOS DE LABORATORIO",
    "LIMPIEZA", "LOCACIONES", "MATERIALES DE FERRETERÍA Y ABRASIVOS",
    "MATERIALES PARA CONSTRUCCIÓN Y EDIFICACIÓN",
    "MUEBLES, ARTÍCULOS Y ÚTILES DE USO DOMÉSTICO",
    "MÁQUINAS Y SUMINISTROS PARA OFICINA", "OBRAS", "PREADJUDICACIONES",
    "PRODUCTOS ALIMENTICIOS", "REFRIGERACIÓN Y CALEFACCIÓN", "SEGUROS",
    "SERVICIO DE FOTOCOPIADO Y MANTENIMIENTO", "SERVICIOS DE CONTROL DE PLAGAS",
    "SERVICIOS DIVERSOS", "SERVICIOS", "SUMINISTROS",
    "VEHÍCULOS EF. SUELO, AUTOMOT., ACOPLADOS, CICLISMO",
    "VENTAS Y OFRECIMIENTOS DEL ESTADO",
    "VESTUARIO, EQUIPOS INDIVIDUALES, DISTINTIVOS", "VIALES", "VARIOS",
)
# De mas largo a mas corto, para que "SERVICIOS DIVERSOS" gane sobre "SERVICIOS".
RUBROS = tuple(sorted(RUBROS, key=len, reverse=True))

# Senales de que el organismo siguio capturando texto que no le corresponde.
# No se usa la comilla sola: hay organismos cuyo nombre lleva comillas, como
# HOSPITAL DE PEDIATRÍA S.A.M.I.C. "PROF. DR. JUAN P. GARRAHAN".
SOBRE_CAPTURA = re.compile(
    r"(OBJETO\s*:|Objeto\s*:|Expediente|EXPEDIENTE|UOC\s*:|Concepto\s*:"
    r"|Contrato\s+[A-Z]{2}-|Proyecto\s+[A-Z]{4})"
    r"|(" + "|".join(re.escape(t) for t in TIPOS) + r")"
)


def norm_sp(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).replace("\xa0", " ")).strip()


def sin_esp(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def regla_tipo(valor):
    """Recorta el identificador pegado al nombre del procedimiento."""
    if not valor:
        return valor, None
    v = norm_sp(valor)
    for t in sorted(TIPOS, key=len, reverse=True):
        if v.lower().startswith(t.lower()):
            resto = v[len(t):].strip()
            return (t, f"recortado {resto!r}") if resto else (valor, None)
    return valor, None


def regla_rubro(valor):
    """Recorta un prefijo SOLO si coincide exacto con un rubro declarado."""
    if not valor:
        return valor, None
    v = norm_sp(valor)
    for rub in RUBROS:
        # Con espacio normal.
        if v.upper().startswith(rub + " "):
            resto = v[len(rub):].strip(" -–—:")
            if resto:
                return resto, f"rubro {rub!r}"
        # Pegado, como "CIVILESUNIVERSIDAD NACIONAL DE CUYO".
        if sin_esp(v).startswith(sin_esp(rub)) and len(sin_esp(v)) > len(sin_esp(rub)):
            objetivo, acum = len(sin_esp(rub)), 0
            for i, ch in enumerate(v):
                if not ch.isspace():
                    acum += 1
                if acum == objetivo:
                    resto = v[i + 1:].strip(" -–—:")
                    if resto and resto.upper() != v.upper():
                        return resto, f"rubro pegado {rub!r}"
                    break
    return valor, None


def main() -> None:
    ap = argparse.ArgumentParser(description="Limpia el set con las reglas del doble ciego.")
    ap.add_argument("--aplicar", action="store_true", help="escribir los cambios")
    args = ap.parse_args()

    total = 0
    a_revisar: dict[str, str] = {}

    for nombre in ARCHIVOS:
        ruta = GOLD / nombre
        if not ruta.exists():
            print(f"({nombre} no existe, salteado)\n")
            continue

        regs = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
        cambios = []

        for r in regs:
            for campo, regla in (("tipo_procedimiento", regla_tipo), ("organismo", regla_rubro)):
                nuevo, nota = regla(r["datos"].get(campo))
                if nota:
                    cambios.append((r["id"], campo, r["datos"][campo], nuevo, nota))
                    r["datos"][campo] = nuevo

            org = r["datos"].get("organismo")
            if org and SOBRE_CAPTURA.search(norm_sp(org)):
                a_revisar[r["id"]] = norm_sp(org)[:95]

        print(f"=== {nombre} · {len(regs)} registros · {len(cambios)} cambios")
        for doc_id, campo, antes, despues, nota in cambios:
            print(f"  {doc_id} · {campo}  ({nota})")
            print(f"      {norm_sp(antes)!r}")
            print(f"   -> {norm_sp(despues)!r}")
        print()
        total += len(cambios)

        if args.aplicar:
            with ruta.open("w", encoding="utf-8") as f:
                for r in sorted(regs, key=lambda x: x["id"]):
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if a_revisar:
        print(f"=== A REVISAR A MANO · {len(a_revisar)} aviso(s)")
        print("El organismo siguió capturando texto de las líneas siguientes.")
        print("Dónde termina el organismo es criterio tuyo, así que no lo toco.\n")
        for doc_id, org in sorted(a_revisar.items()):
            print(f"  {doc_id}  {org}")
        print("\n  python label/etiquetar.py --id <ID>")

    print(f"\n{total} cambios automáticos.")
    print("Nada escrito. Repetí con --aplicar si estás de acuerdo." if not args.aplicar
          else "Escrito. Ahora:  python label/doble_ciego.py --comparar")


if __name__ == "__main__":
    main()
