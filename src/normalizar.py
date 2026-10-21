"""Normalizadores por tipo de campo.

Por que existe este archivo: comparar strings con `==` es el error que arruina
la mayoria de los benchmarks caseros. "$ 1.250.000,50" y "1250000.5" son el mismo
monto; "MINISTERIO DE SALUD" y "Ministerio de Salud" son el mismo organismo.
Un harness que los cuenta como error mide su propio parser, no el modelo.

Cada normalizador devuelve un valor canonico o None. La comparacion se hace
siempre sobre el valor canonico.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, date

# --------------------------------------------------------------------------- texto

_ESPACIOS = re.compile(r"\s+")
_PUNTUACION_FINAL = re.compile(r"[\.,;:\-\s]+$")


def sin_tildes(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def norm_texto(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = sin_tildes(s).lower()
    s = _ESPACIOS.sub(" ", s)
    s = _PUNTUACION_FINAL.sub("", s)
    return s or None


# --------------------------------------------------------------------------- codigo

_NO_ALNUM = re.compile(r"[^a-z0-9]")


def norm_codigo(v) -> str | None:
    """Expedientes y numeros de procedimiento: solo alfanumericos, en minuscula.

    EX-2026-00123456- -APN-DGA#MS  ->  ex202600123456apndgams
    """
    if v is None:
        return None
    s = sin_tildes(str(v)).lower()
    s = _NO_ALNUM.sub("", s)
    return s or None


# --------------------------------------------------------------------------- monto

_MONTO_LIMPIO = re.compile(r"[^\d,.\-]")


def norm_monto(v) -> float | None:
    """Acepta float, int o el string tal cual sale del aviso.

    Regla para el formato argentino: si hay coma, la coma es el decimal y el
    punto es separador de miles. Si no hay coma, todos los puntos son miles.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = _MONTO_LIMPIO.sub("", str(v)).strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


# --------------------------------------------------------------------------- fecha

_FORMATOS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    # El Boletin escribe las fechas asi, con segundos: "28/08/2026 10:00:00".
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
)


def norm_fecha(v) -> str | None:
    """Devuelve YYYY-MM-DDTHH:MM, o YYYY-MM-DD si no hay hora.

    Decision explicita: la hora cuenta. En una apertura de ofertas, equivocarse
    de hora es equivocarse. Si tu caso de uso no la necesita, cambialo aca y
    dejalo escrito en el README: es un supuesto, no un detalle.
    """
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat(timespec="minutes") if isinstance(v, datetime) else v.isoformat()
    s = str(v).strip().replace("Z", "")
    if not s:
        return None
    for f in _FORMATOS:
        try:
            dt = datetime.strptime(s, f)
        except ValueError:
            continue
        if "%H" in f:
            return dt.strftime("%Y-%m-%dT%H:%M")
        return dt.strftime("%Y-%m-%d")
    return None


def norm_entero(v) -> int | None:
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


NORMALIZADORES = {
    "texto": norm_texto,
    "codigo": norm_codigo,
    "monto": norm_monto,
    "fecha": norm_fecha,
    "entero": norm_entero,
}


def normalizar(tipo: str, valor):
    return NORMALIZADORES[tipo](valor)
