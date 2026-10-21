"""Extractor determinista por reglas. Sin IA, sin API, sin costo.

Existe por dos motivos distintos y los dos importan:

1. COMO ASISTENTE DE ETIQUETADO. Precarga valores en label/etiquetar.py para que
   no tengas que tipear ocho campos a mano en cada aviso. Vos confirmas o corriges.

2. COMO LINEA BASE DEL EXPERIMENTO. Es una variante mas del harness, con proveedor
   "reglas". Si este parser resuelve buena parte del corpus a costo cero, entonces
   la pregunta del proyecto deja de ser "que modelo anda mejor" y pasa a ser
   "donde se justifica pagar por un modelo". Esa es una conclusion mucho mas fuerte,
   y es de las pocas que un entrevistador no escucho antes.

El formato COMPR.AR / CONTRAT.AR publica los campos etiquetados, asi que es casi
determinista. El formato libre no: ahi este parser va a fallar mucho, y ESO es
justamente el hallazgo.
"""

from __future__ import annotations

import re

# Encabezados de campo del formato COMPR.AR. Sirven para saber donde termina
# un valor que ocupa varias lineas (tipico de `Objeto:`).
ETIQUETAS = (
    "UOC", "Ejercicio", "Clase", "Modalidad", "Expediente N", "Objeto",
    "Presupuesto Oficial", "Retiro del Pliego", "Consulta del Pliego",
    "Presentacion de Ofertas", "Presentación de Ofertas", "Acto de Apertura",
    "Lugar y dirección", "Plazo y horario", "Texto del Aviso", "Tipo de Circular",
    "Número de Circular", "Año de Circular", "Fecha de Circular", "Valor del Pliego",
    "Texto de la Circular", "Observaciones",
)
_ES_ETIQUETA = re.compile(
    r"^\s*(" + "|".join(re.escape(e) for e in ETIQUETAS) + r")\s*[:°]?", re.I
)

TIPOS = (
    "Licitación Pública", "Licitación Privada", "Contratación Directa",
    "Concurso de Precios", "Concurso Público", "Subasta Pública",
    "Compulsa Abreviada", "Contratación Menor", "Comparación de Precios",
    "Concurso de Proyectos", "Remate Público",
)
_LINEA_TIPO = re.compile(
    r"^\s*(" + "|".join(re.escape(t) for t in TIPOS) + r")\s*(?:N[°º]\s*)?([\w/\-\.]+)?\s*$",
    re.I,
)

_EXPEDIENTE = re.compile(r"^\s*Expediente\s*N[°º]?\s*:\s*(.+?)\s*$", re.I | re.M)
_OBJETO = re.compile(r"^\s*Objeto\s*:\s*(.*)$", re.I | re.M)
_PRESUPUESTO = re.compile(
    r"^\s*Presupuesto\s+Oficial\s*:?\s*\$?\s*([\d.,]+)", re.I | re.M
)
_VALOR_PLIEGO = re.compile(r"^\s*Valor\s+del\s+[Pp]liego\s*:?\s*\$?\s*([\d.,]+|sin cargo|gratuito)", re.I | re.M)


def _lineas(texto: str) -> list[str]:
    return [l.rstrip() for l in texto.splitlines()]


def _organismo(lineas: list[str]) -> str | None:
    """Todo lo que hay antes de la linea de tipo de procedimiento.

    Puede ocupar dos lineas ("MINISTERIO DE ECONOMIA -\nSECRETARIA DE HACIENDA").
    """
    partes: list[str] = []
    for l in lineas:
        if _LINEA_TIPO.match(l):
            break
        if l.strip():
            partes.append(l.strip())
        if len(partes) >= 3:  # mas de tres lineas ya no es un encabezado
            break
    if not partes:
        return None
    return re.sub(r"\s*-\s*$", "", " ".join(partes)).strip() or None


def _tipo_y_numero(lineas: list[str]) -> tuple[str | None, str | None]:
    for l in lineas:
        m = _LINEA_TIPO.match(l)
        if m:
            tipo = m.group(1).strip()
            # Normaliza la capitalizacion al nombre canonico de la lista.
            for t in TIPOS:
                if t.lower() == tipo.lower():
                    tipo = t
                    break
            return tipo, (m.group(2).strip() if m.group(2) else None)
    return None, None


def _objeto(texto: str, lineas: list[str]) -> str | None:
    m = _OBJETO.search(texto)
    if not m:
        return None
    inicio = texto[: m.start()].count("\n")
    partes = [m.group(1).strip()]
    for l in lineas[inicio + 1:]:
        if not l.strip() or _ES_ETIQUETA.match(l):
            break
        partes.append(l.strip())
    valor = " ".join(p for p in partes if p).strip()
    return valor or None


def _fecha_apertura(lineas: list[str]) -> str | None:
    """El `Plazo y horario:` que viene despues del bloque `Acto de Apertura`.

    Ojo: hay varios bloques con `Plazo y horario` (retiro del pliego, consultas,
    presentacion de ofertas). Solo vale el que sigue a `Acto de Apertura`.
    """
    dentro = False
    for l in lineas:
        if re.match(r"^\s*Acto de Apertura\s*$", l, re.I):
            dentro = True
            continue
        if dentro:
            m = re.match(r"^\s*Plazo y horario\s*:\s*(.+?)\s*$", l, re.I)
            if m:
                return m.group(1).strip()
            if _LINEA_TIPO.match(l):
                break
    return None


def extraer(texto: str) -> dict:
    """Devuelve {campo: valor|None} mas 'confianza' estimada por cobertura.

    La confianza NO es una probabilidad: es la proporcion de campos estructurales
    que el parser pudo ubicar. Sirve para el analisis de umbral igual que la del
    modelo, y para saber cuando el aviso no es de formato COMPR.AR.
    """
    lineas = _lineas(texto)
    tipo, numero = _tipo_y_numero(lineas)
    m_exp = _EXPEDIENTE.search(texto)
    m_pre = _PRESUPUESTO.search(texto)
    m_val = _VALOR_PLIEGO.search(texto)

    pliego = None
    if m_val:
        bruto = m_val.group(1).strip().lower()
        pliego = 0 if bruto in ("sin cargo", "gratuito") else bruto

    d = {
        "organismo": _organismo(lineas),
        "expediente": m_exp.group(1).strip() if m_exp else None,
        "tipo_procedimiento": tipo,
        "numero_procedimiento": numero,
        "objeto": _objeto(texto, lineas),
        "monto_estimado": m_pre.group(1) if m_pre else None,
        "fecha_apertura": _fecha_apertura(lineas),
        "valor_pliego": pliego,
    }
    # Campos estructurales: los que el formato COMPR.AR siempre trae.
    estructurales = ("organismo", "expediente", "tipo_procedimiento",
                     "numero_procedimiento", "objeto", "fecha_apertura")
    hallados = sum(d[c] is not None for c in estructurales)
    d["confianza"] = round(hallados / len(estructurales), 2)
    return d
