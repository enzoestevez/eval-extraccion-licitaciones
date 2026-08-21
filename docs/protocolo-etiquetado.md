# Protocolo de etiquetado

Este documento define qué es "la respuesta correcta". Sin él, el set etiquetado es
una opinión, y todas las métricas que salen de él son una opinión también.

**Regla base:** etiquetás lo que el aviso *dice*, no lo que *debería* decir. Si el
aviso está mal, la etiqueta refleja lo que está escrito.

## Reglas por campo

### `organismo`
La repartición contratante tal como aparece en el aviso, sin expandir siglas ni
corregir. Si figuran dos niveles (ministerio y dirección), se etiqueta el más
específico que aparezca como contratante.

- Si el aviso dice "MINISTERIO DE SALUD - DIRECCIÓN DE COMPRAS" → la dirección.
- Si sólo dice el ministerio → el ministerio.

### `expediente`
El identificador de la actuación administrativa, completo, con guiones y símbolos.
No lo limpies: la normalización se encarga después.

**No confundir con `numero_procedimiento`.** El expediente identifica el trámite
(suele empezar en `EX-` o `EXP-`); el procedimiento identifica el llamado.
Si el aviso trae sólo uno de los dos, el otro va `null`.

### `tipo_procedimiento`
Literal del aviso: "Licitación Pública", "Contratación Directa", "Concurso de
Precios", "Licitación Privada", "Subasta Pública". Sin agregar modalidad
("Etapa Única", "Nacional") salvo que sea parte inseparable del nombre.

### `numero_procedimiento`
Habitualmente `NN/AAAA`. Copiá el formato del aviso. Si dice "Nº 14/26",
etiquetás `14/26`, no `14/2026`.

### `objeto`
Con las palabras del aviso, sin resumir ni reformular. Si el objeto se extiende
por varias líneas, incluilas. Cortá donde el aviso pasa a hablar de otra cosa
(plazos, pliego, lugar de apertura).

Si hay varios renglones o lotes, el objeto es el **general del llamado**, no el
de cada renglón.

### `monto_estimado`
Presupuesto oficial o monto estimado, en pesos, como número.

- Si el aviso lo da en letras y en números, usás el número.
- Si hay discrepancia entre letras y números, usás el número y marcás el
  documento como **dudoso** con la nota.
- Si el aviso no trae monto → `null`. **No lo deduzcas de nada.**
- Si el monto está en dólares o en otra unidad (módulos, UVIs), lo etiquetás
  igual como número y anotás la unidad en la nota. Es un caso conocido de este
  corpus y hay que reportarlo aparte en los resultados.

### `fecha_apertura`
Fecha y hora de apertura de ofertas, ISO 8601.

- Con hora: `2026-03-12T11:00`
- Sin hora en el aviso: `2026-03-12`
- Si hay prórroga mencionada, usás **la fecha vigente** según el aviso, y marcás
  dudoso.
- Si hay varias fechas (apertura de sobre 1 y sobre 2), usás la primera y anotás.

### `valor_pliego`
Como número. Si el aviso dice "sin costo", "gratuito" o "de consulta libre" → `0`,
no `null`. `null` es "el aviso no lo menciona"; `0` es "el aviso dice que es
gratis". La distinción importa porque el modelo tiene que aprender a no rellenar.

## Cuándo marcar un documento como dudoso

Marcalo con `!` y escribí por qué siempre que:

- El aviso se contradice a sí mismo.
- Un campo admite dos lecturas razonables.
- El texto extraído del PDF vino cortado o desordenado.
- El aviso corresponde a una prórroga, ampliación o rectificación de otro.

Los dudosos **se quedan en el set** pero se reportan aparte. Si son más del 10%
del corpus, eso es un hallazgo del proyecto, no un problema a esconder: significa
que la tarea tiene ambigüedad irreducible y que ningún modelo va a llegar al 100%.

## Control de calidad del propio set

Antes de correr nada:

1. **Doble etiquetado ciego de 20 documentos.** Etiquetá 20 al azar, esperá dos
   días, volvé a etiquetarlos sin mirar los primeros, y comparalos. El porcentaje
   de coincidencia con vos mismo es tu techo: ningún modelo puede superar la
   consistencia de tu propia verdad de referencia. Poné ese número en el README.
   Casi nadie lo mide, y decirlo en una entrevista cambia cómo te miran.

2. **Revisión de los primeros 20.** Después de etiquetar 50, volvé a los primeros
   20: casi seguro cambiaste de criterio en el camino. Corregilos y actualizá este
   documento con la regla que te faltaba.

3. **Nunca etiquetes con IA.** Si la verdad de referencia la genera un modelo, no
   estás midiendo precisión: estás midiendo el acuerdo entre dos modelos. Es el
   atajo que invalida el proyecto entero.

## Versionado

Cada etiqueta guarda la versión del esquema con la que se hizo. Si cambiás
`src/esquema.py`, subí `VERSION_ESQUEMA` y revisá las etiquetas viejas con
`python label/etiquetar.py --revisar`.
