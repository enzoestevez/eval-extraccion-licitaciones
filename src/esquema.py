"""Esquema de extraccion para avisos de contratacion del Boletin Oficial.

Este archivo es el contrato del proyecto. Todo lo demas (etiquetado, extraccion,
evaluacion) depende de estas definiciones, asi que cualquier cambio aca invalida
el set etiquetado. Si tenes que cambiarlo, subi VERSION_ESQUEMA y volve a validar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VERSION_ESQUEMA = "1.0.0"

TipoCampo = Literal["texto", "monto", "fecha", "entero", "codigo"]


@dataclass(frozen=True)
class Campo:
    nombre: str
    tipo: TipoCampo
    descripcion: str
    # Peso en el score global. Un campo que si sale mal invalida el registro
    # entero pesa mas que uno cosmetico. Esto es una decision de negocio,
    # no tecnica: defendela con el criterio de para que se usa el dato.
    peso: float = 1.0
    obligatorio: bool = True


CAMPOS: tuple[Campo, ...] = (
    Campo(
        "organismo",
        "texto",
        "Reparticion u organismo contratante, tal como figura en el aviso.",
        peso=1.5,
    ),
    Campo(
        "expediente",
        "codigo",
        "Numero de expediente o actuacion. Formato variable segun organismo.",
        peso=2.0,
    ),
    Campo(
        "tipo_procedimiento",
        "texto",
        "Licitacion Publica, Contratacion Directa, Concurso de Precios, etc.",
        peso=1.0,
    ),
    Campo(
        "numero_procedimiento",
        "codigo",
        "Numero del llamado, habitualmente con formato NN/AAAA.",
        peso=1.5,
    ),
    Campo(
        "objeto",
        "texto",
        "Objeto de la contratacion en las palabras del aviso, sin resumir.",
        peso=1.0,
    ),
    Campo(
        "monto_estimado",
        "monto",
        "Presupuesto oficial o monto estimado en pesos. None si el aviso no lo trae.",
        peso=2.0,
        obligatorio=False,
    ),
    Campo(
        "fecha_apertura",
        "fecha",
        "Fecha y hora de apertura de ofertas, en ISO 8601.",
        peso=2.0,
    ),
    Campo(
        "valor_pliego",
        "monto",
        "Valor del pliego. None si es gratuito o no se menciona.",
        peso=0.5,
        obligatorio=False,
    ),
)

CAMPOS_POR_NOMBRE = {c.nombre: c for c in CAMPOS}
PESO_TOTAL = sum(c.peso for c in CAMPOS)


def json_schema() -> dict:
    """Esquema JSON para forzar salida estructurada del modelo.

    Forzar el esquema en la llamada (en vez de pedirlo en el prompt y parsear)
    es lo que hace que la tasa de fallo de formato sea cero. Es la diferencia
    entre un harness que mide extraccion y uno que mide obediencia de formato.
    """
    tipos = {
        "texto": {"type": ["string", "null"]},
        "codigo": {"type": ["string", "null"]},
        "monto": {"type": ["number", "null"]},
        "entero": {"type": ["integer", "null"]},
        "fecha": {"type": ["string", "null"], "description": "ISO 8601"},
    }
    props = {}
    for c in CAMPOS:
        prop = dict(tipos[c.tipo])
        prop["description"] = c.descripcion
        props[c.nombre] = prop
    props["confianza"] = {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "description": (
            "Que tan seguro estas de la extraccion completa. Se honesto: "
            "un valor bajo cuando el aviso es ambiguo vale mas que uno alto y errado."
        ),
    }
    return {
        "type": "object",
        "properties": props,
        "required": [c.nombre for c in CAMPOS] + ["confianza"],
        "additionalProperties": False,
    }


def registro_vacio() -> dict:
    d = {c.nombre: None for c in CAMPOS}
    d["confianza"] = 0.0
    return d
