"""Las variantes que se comparan.

Una variante es una combinacion de proveedor + modelo + prompt + parametros.
La gracia del harness es que cambia UNA cosa por vez, para que la diferencia
en el resultado sea atribuible.

Regla de oro: si cambias el prompt Y el modelo entre dos variantes, no aprendiste
nada de las dos. Aprendiste que "esta combinacion anda mejor que esa", que es una
conclusion mucho mas pobre y no se puede transferir.

IMPORTANTE - los identificadores de modelo caducan. Google dejo de ofrecer
gemini-2.5-flash-lite a cuentas nuevas y la corrida fallaba con un 404 en las 267
llamadas. No copies identificadores de ningun lado: preguntale a TU clave cuales
tiene habilitados y pone esos.

    python src/verificar.py --modelos
"""

from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- prompts

PROMPT_MINIMO = """\
Extraes datos de avisos de contratacion publica argentina.
Devolve los campos del esquema. Si un dato no esta en el aviso, devolve null.
No inventes.
"""

PROMPT_CON_REGLAS = """\
Extraes datos de avisos de contratacion publica del Boletin Oficial argentino.

Reglas:
- Si un dato no figura explicitamente en el texto, devolve null. Nunca lo deduzcas
  ni lo completes con lo que suele ser habitual.
- El expediente y el numero de procedimiento son cosas distintas. El expediente
  identifica la actuacion administrativa (suele empezar con EX- o EXP-); el numero
  de procedimiento identifica el llamado (suele tener formato NN/AAAA).
- Los montos van como numero, sin simbolo de moneda ni separadores de miles.
- Las fechas van en ISO 8601. Si el aviso indica hora de apertura, incluila.
- El objeto va con las palabras del aviso. No lo resumas ni lo reformules.
- Si el aviso menciona varios renglones o lotes, el objeto es el general del llamado.

En confianza, se honesto: un valor bajo cuando el aviso es ambiguo vale mas para
mi que uno alto y equivocado, porque abajo de cierto umbral esto va a revision
humana y quiero que el corte funcione.
"""

PROMPT_CON_EJEMPLOS = (
    PROMPT_CON_REGLAS
    + """
Ejemplo de aviso ambiguo y como resolverlo:

  "...Expediente EX-2026-00412233- -APN-DCYC#MS. Licitacion Publica N 14/2026.
  Apertura: 12 de marzo de 2026 a las 11:00 hs. Presupuesto oficial: pesos dos
  millones cuatrocientos mil ($ 2.400.000,00)..."

  expediente          -> "EX-2026-00412233- -APN-DCYC#MS"
  tipo_procedimiento  -> "Licitacion Publica"
  numero_procedimiento-> "14/2026"
  fecha_apertura      -> "2026-03-12T11:00"
  monto_estimado      -> 2400000.00

Notar: el monto va en numero aunque el aviso lo escriba en letras y en numeros.
"""
)


@dataclass(frozen=True)
class Variante:
    id: str
    proveedor: str
    modelo: str
    prompt: str
    temperatura: float = 0.0
    nota: str = ""

    @property
    def etiqueta(self) -> str:
        return f"{self.id} ({self.proveedor}/{self.modelo})"


# Cada bloque cambia UNA variable respecto de la linea base.
VARIANTES: tuple[Variante, ...] = (
    Variante(
        "v0-base",
        "mock",
        "mock",
        PROMPT_MINIMO,
        nota="Linea base sin proveedor. Sirve para probar el pipeline sin gastar.",
    ),
    Variante(
        "v0-reglas",
        "reglas",
        "regex",
        "",
        nota="Extractor determinista sin IA. Costo cero. La vara a superar.",
    ),
    # --- efecto del prompt, con el modelo fijo -----------------------------
    Variante(
        "v1-minimo",
        "google",
        "gemini-3.5-flash-lite",
        PROMPT_MINIMO,
        nota="Prompt sin reglas. Es el piso: cuanto se saca sin trabajo.",
    ),
    Variante(
        "v2-reglas",
        "google",
        "gemini-3.5-flash-lite",
        PROMPT_CON_REGLAS,
        nota="Mismo modelo, prompt con reglas. Aisla el efecto del prompt.",
    ),
    Variante(
        "v3-ejemplos",
        "google",
        "gemini-3.5-flash-lite",
        PROMPT_CON_EJEMPLOS,
        nota="Mismo modelo, reglas mas un ejemplo resuelto.",
    ),
    # --- efecto del modelo, con el prompt fijo -----------------------------
    Variante(
        "v4-modelo-caro",
        "google",
        "gemini-3.5-flash",
        PROMPT_CON_EJEMPLOS,
        nota="Mismo prompt que v3, modelo mas caro de la misma familia. Aisla el efecto del modelo.",
    ),
    Variante(
        "v5-otro-proveedor",
        "anthropic",
        "claude-haiku-4-5-20251001",
        PROMPT_CON_EJEMPLOS,
        nota="Mismo prompt que v3, otro proveedor.",
    ),
)

POR_ID = {v.id: v for v in VARIANTES}
