# Extracción de datos de avisos de contratación pública — banco de evaluación

> **El número, y por qué el número no es el resultado.**
>
> 83,5% de precisión ponderada por campo sobre **115 avisos etiquetados a mano**,
> a USD 0,00075 por documento. Pero ese promedio no se puede interpretar:
>
> | | Precisión | Techo humano medido | |
> |---|---:|---:|---|
> | Formato COMPR.AR | **93,5%** | 98,7% | quedan 5,2 puntos |
> | Formato libre | **73,2%** | 72,7% | **ya está en el techo** |
>
> **En la mitad difícil el modelo alcanzó la consistencia de una persona**, y
> ninguna versión del prompt lo mueve: tres prompts distintos dan 73,2% los tres.
> Lo que queda de error no es una limitación del modelo, es que el documento no
> trae la respuesta.
>
> **Línea base humana:** 85,7% de precisión, 113 segundos y USD 0,058 por
> documento, con el costo anclado al salario mínimo legal. El modelo es **77×
> más barato y 29× más rápido**.
>
> **Línea base sin IA:** un parser de expresiones regulares saca 89,5% en
> COMPR.AR a costo cero. El modelo sólo le gana por 4 puntos ahí, y por 21 en
> formato libre. **Ahí está la respuesta a dónde se justifica pagar por un
> modelo**, que es la pregunta que el proyecto se hizo.
>
> **Y el modelo caro:** +2,5 puntos de precisión, +8,2 de documentos perfectos,
> 3,9× el costo — medido sobre los mismos 61 documentos, porque la capa gratuita
> permite 20 pedidos por día y comparar 61 contra 115 no es comparar.

---

## El problema

Los avisos de contratación pública del Boletín Oficial se publican como texto
corrido dentro de PDFs. Quien necesita usarlos —un proveedor del Estado buscando
oportunidades, un organismo de control, un periodista de datos— tiene que leerlos
a mano y transcribir los campos uno por uno.

La pregunta que este proyecto responde no es "¿se puede automatizar con un LLM?".
La respuesta a eso es obviamente sí, y se demuestra en diez minutos. La pregunta
es la que hace que un piloto llegue a producción o muera en el intento:

**¿Con cuánta precisión, en qué campos se equivoca, a qué costo, y a partir de qué
umbral de confianza conviene dejar de revisarlo a mano?**

## Cómo está medido

- **Set de referencia etiquetado a mano**, contra un protocolo escrito
  ([`docs/protocolo-etiquetado.md`](docs/protocolo-etiquetado.md)). Sin IA en el
  etiquetado: si la verdad la genera un modelo, no se mide precisión, se mide el
  acuerdo entre dos modelos.
- **Etiquetado asistido por reglas, con muestra ciega de control.** Para no
  tipear ocho campos por aviso, un parser determinista (`src/reglas.py`, sin IA)
  precarga los valores y yo acepto o corrijo. Eso introduce **sesgo de anclaje**:
  un valor sugerido se acepta con menos escrutinio que uno escrito de cero. Por
  eso el **15% de los avisos se etiqueta sin ninguna sugerencia**, elegido de
  forma determinista por su id, y cada campo guarda si fue aceptado, corregido o
  escrito a mano. Comparar el desempeño del parser en los avisos asistidos contra
  los ciegos mide el sesgo en puntos, en vez de dejarlo como una sospecha.
- **Comparación normalizada**, no por igualdad de strings. `"$ 1.250.000,50"` y
  `1250000.5` son el mismo monto. Comparar crudo mide el parser, no el modelo.
- **Precisión ponderada por campo.** Errar el expediente no cuesta lo mismo que
  errar el valor del pliego. Los pesos están en `src/esquema.py` y son una
  decisión de negocio explícita, no un promedio neutro.
- **La alucinación se reporta aparte**: campos donde el modelo puso un valor y la
  verdad era `null`. En producción es el error más caro y diluirlo dentro de
  "precisión" esconde justo lo que hay que mirar.
- **Una variable por variante.** Si cambiás el prompt *y* el modelo entre dos
  corridas, no aprendiste nada de ninguna de las dos.

## Resultados

Tabla completa en [`reports/RESULTADOS.md`](reports/RESULTADOS.md) — se genera
sola con `src/reporte.py`, desde `reports/metricas.json`.

| Variante | n | Precisión | COMPR.AR | Libre | Docs perfectos | Alucinación | USD/doc |
|---|---:|---:|---:|---:|---:|---:|---:|
| `v3-ejemplos` | 115 | **83,5%** | 93,5% | 73,2% | 31,3% | 2,9% | 0,000751 |
| `v1-minimo` | 115 | 83,2% | 93,0% | 73,2% | 30,4% | 3,7% | 0,000622 |
| `v2-reglas` | 115 | 83,1% | 92,7% | 73,2% | 27,8% | 2,6% | 0,000681 |
| `v0-reglas` *(sin IA)* | 115 | 71,0% | 89,5% | 52,1% | 27,0% | **0,4%** | **0** |
| `v4-modelo-caro` | **61** ⚠ | 84,4% | 96,7% | 73,3% | 36,1% | 2,7% | 0,002844 |

`v4-modelo-caro` está marcada porque tiene 61 de 115 documentos: su precisión
está calculada sobre otro subconjunto y **no entra en esta tabla como
conclusión**. El reporte la marca solo y elige la variante ganadora únicamente
entre las que tienen cobertura completa.

**Por qué le faltan 54 documentos, y por qué no se completó.** La capa gratuita
permite **20 pedidos por día** a ese modelo:

```
Quota exceeded for metric: generate_content_free_tier_requests,
limit: 20, model: gemini-3.6-flash
Please retry in 9h21m26.597663521s
```

Completarla serían tres días de cupo. **Pero la pregunta se contesta sin gastar
nada** — ver la sección siguiente.

### Comparación emparejada: el efecto del modelo, sobre la misma prueba

La comparación válida nunca fue 61 contra 115. Es medir **todas** las variantes
sobre los **mismos 61 documentos**: la intersección donde todas tienen extracción
válida. Las predicciones ya estaban guardadas, así que **la comparación salió a
costo cero.**

| Variante | Precisión | Docs perfectos | Alucinación | USD/doc |
|---|---:|---:|---:|---:|
| `v4-modelo-caro` | **84,4%** | **36,1%** | 2,7% | 0,002844 |
| `v3-ejemplos` | 81,9% | 27,9% | 3,3% | 0,000738 |
| `v2-reglas` | 81,2% | 24,6% | 2,9% | 0,000670 |
| `v1-minimo` | 80,8% | 24,6% | 4,1% | 0,000611 |
| `v0-reglas` *(sin IA)* | 72,5% | **31,1%** | **0,2%** | **0** |

**El modelo caro gana +2,5 puntos de precisión y +8,2 de documentos perfectos, a
3,9× el costo.**

Y la métrica que decide **no es la precisión: son los documentos perfectos.** El
sistema que consume esta extracción
([proyecto 02](https://github.com/enzoestevez/conciliador-contrataciones)) arma
una llave con varios campos — un error en `numero_procedimiento` no degrada el
caso, lo **mata**. Con ese criterio la diferencia no es de 2,5 puntos sino de
8,2, y ahí la discusión del costo cambia de signo.

**Y un detalle que el promedio global escondía:** `v0-reglas`, sin IA y gratis,
tiene **más documentos perfectos que `v3-ejemplos`** (31,1% contra 27,9%) con 9,5
puntos menos de precisión. El parser determinista acierta el documento entero más
seguido, pero cuando falla, falla en más campos a la vez. **Son dos perfiles de
error distintos que un promedio junta en un solo número.**

**Tres cosas que este cuadro dice y un promedio no diría:**

1. **Todo el eje de ingeniería de prompt vale 0,3 puntos** (83,2% sin reglas
   contra 83,5% con reglas y un ejemplo resuelto), y **cero** en el formato
   difícil, donde las tres variantes dan 73,2% exacto. El trabajo que movió la
   aguja fue medir el techo, no escribir el prompt.
2. **La alucinación se parte igual que la precisión:** 0,0% en COMPR.AR y 5,9%
   en formato libre. El modelo inventa justo donde el documento no tiene el dato,
   que es el error más caro en producción.
3. **El parser sin IA alucina nueve veces menos** (0,4% contra 2,9%) y en
   COMPR.AR está a 4 puntos del modelo, gratis.

### La confianza que el modelo se autoasigna no sirve para rutear

| Umbral | Auto-procesado | A revisión | Precisión sobre lo auto |
|---:|---:|---:|---:|
| 0,00 – 0,80 | 100% | 0% | 83,5% |
| 0,85 | 97% | 3% | 83,9% |
| 0,95 | 90% | 10% | 85,1% |
| **1,00** | **56%** | **44%** | **91,0%** |

El modelo se declara con confianza ≥ 0,85 en el 97% de los documentos: la escala
está colapsada y lo único que informa es el corte entre `1,00` y el resto.

**Rutear por formato es mejor y es gratis.** El formato se conoce antes de llamar
al modelo: auto-procesar COMPR.AR da el 50% del corpus al 93,5%, contra el 56% al
91,0% que da el umbral de confianza. Más precisión, sin pagar la llamada para
enterarse. **Esa es la conclusión operativa del proyecto, y contradice lo que yo
esperaba encontrar cuando escribí la curva.**

## Arquitectura

```
Boletines diarios (data/raw/*.pdf)   ~68 avisos por edición
   │
   ├─ src/dividir.py ──────────► un .txt por aviso (data/interim/*.txt)
   │                              + data/interim/indice.json con rubro,
   │                                tipo (llamado/adjudicación) y formato
   │
   ├─ label/etiquetar.py ──────► set de referencia (data/gold/etiquetas.jsonl)
   │                              etiquetado a mano, protocolo versionado
   │
   ├─ src/extraer.py ──────────► predicciones por variante
   │      │                       (data/interim/pred_<variante>.jsonl)
   │      └─ src/proveedores.py   capa única sobre anthropic / openai / google / mock
   │         src/variantes.py     las combinaciones que se comparan
   │         src/esquema.py       el contrato: campos, tipos, pesos, JSON Schema
   │
   ├─ src/evaluar.py ──────────► métricas (reports/metricas.json)
   │      └─ src/normalizar.py    comparación por valor canónico, no por string
   │
   └─ src/reporte.py ──────────► reports/RESULTADOS.md
```

## Cómo correrlo

```bash
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Probá el pipeline entero sin gastar un peso ni tener API key.
python src/dividir.py                # boletines diarios -> un .txt por aviso
python label/etiquetar.py            # etiquetá 3 o 4 para probar
python src/extraer.py --variante v0-base
python src/evaluar.py
python src/reporte.py

# 2. Recién ahí, con el pipeline verificado, poné la API key y corré en serio.
cp .env.example .env                 # completá la clave del proveedor que uses
# completá los nombres de modelo en src/variantes.py
# completá los precios en config/precios.json
python src/extraer.py --todas
python src/evaluar.py && python src/reporte.py
```

## De dónde salen los datos

Avisos de la Tercera Sección (Contrataciones) del
[Boletín Oficial de la República Argentina](https://www.boletinoficial.gob.ar/).
Cada edición diaria es un solo PDF con todos los avisos del día adentro —
alrededor de 68 en la edición del 3/8/2026— así que el corpus se arma bajando
unas 5 ediciones, no 300 archivos.

Los PDFs no están versionados en el repo (`data/raw/` está en `.gitignore`): son
pesados y se pueden volver a bajar. Lo que sí está versionado es el set etiquetado,
que es el activo real del proyecto.

Descarga: 5 ediciones de la Tercera Sección — **1/6, 19/6, 1/7, 20/7 y 3/8 de
2026**— bajadas a mano desde el sitio del Boletín Oficial. Dieron **300 avisos en
bruto y 296 únicos**, de los cuales **267 son llamados** (el resto,
adjudicaciones y preadjudicaciones, quedan fuera del set).

### Por qué las fechas están espaciadas

Un aviso no se publica un día: se publica durante varios días seguidos, y el pie
lo dice (`e. 31/07/2026 ... v. 03/08/2026`). Un primer intento con **cinco
ediciones consecutivas** dio 304 avisos de los cuales **el 38% eran
republicaciones del mismo aviso**. Sin deduplicar, el modelo habría visto el
mismo documento hasta cuatro veces y cada acierto o error se habría contado de
nuevo: la precisión reportada habría estado inflada.

Con **fechas espaciadas** el solapamiento cayó al **1%**. `src/dividir.py`
deduplica igual por número de aviso, pero el diseño del muestreo es lo que hace
que el corpus sea realmente diverso y no cinco fotos del mismo día.

### Cómo se corta cada edición

Cada aviso termina con su pie de publicación —
`e. 31/07/2026 N° 53047/26 v. 03/08/2026`— que aparece exactamente una vez por
aviso y trae su identificador. Ese pie es el delimitador. `src/dividir.py` además
clasifica cada aviso por rubro, por tipo (llamado / preadjudicación / adjudicación)
y por formato:

- **`comprar`**: los que publica el sistema COMPR.AR, con campos etiquetados
  (`UOC:`, `Expediente N°:`, `Objeto:`). Homogéneos y fáciles.
- **`libre`**: los que cada organismo redacta a su manera —universidades, BCRA,
  Ministerio Público, banca multilateral—. Prosa corrida, campos en mayúsculas o
  directamente ausentes.

Esa distinción importa: reportar el resultado por segmento dice mucho más que un
promedio único. **93,5% en formato COMPR.AR contra 73,2% en formato libre** es un
hallazgo; el 83,5% promedio de los dos esconde justamente dónde falla.

Y la distinción no es sólo del modelo: el techo humano también se parte, 98,7%
contra 72,7%. **Los dos lados de la grieta aparecen en las dos mediciones
independientes**, lo que dice que la variable es el documento y no el extractor.

## Lo que no resuelve

- **Adjudicaciones y preadjudicaciones** (29 de los 296 avisos del corpus) quedan
  fuera. Son avisos de *resultado*, no de convocatoria: no tienen fecha de
  apertura ni valor de pliego, y la mitad del esquema no les aplica. Meterlas
  mezclaría dos tareas de extracción distintas bajo una sola métrica. Extraer de
  ellas es un proyecto aparte, con su propio esquema.
- **PDFs escaneados sin capa de texto.** Las cinco ediciones de este corpus traen
  texto, pero si apareciera una escaneada `src/dividir.py` la detecta y avisa.
  Requeriría OCR y un experimento aparte: mezclarlos confunde el error del modelo
  con el error del OCR.
- **Avisos de más de 60.000 caracteres.** `src/extraer.py` los corta. Ninguno del
  corpus actual se acerca (el más largo tiene 4.220), pero el límite existe y hay
  que declararlo.
- **El techo lo midió la misma persona dos veces.** Es consistencia propia, no
  acuerdo entre anotadores: está sesgado hacia arriba, porque una persona repite
  sus propios criterios —y sus propios malentendidos— mejor de lo que dos
  personas coinciden. Un segundo anotador bajaría el techo, y con eso cambiaría
  la lectura de "el modelo está en el techo" a "el modelo está por encima de lo
  que una persona sola logra reproducir". **No está medido y no se afirma.**
- **El efecto del modelo está medido sobre 61 documentos, no sobre 115.** La capa
  gratuita permite 20 pedidos por día a ese modelo, así que la comparación se
  hizo sobre la intersección donde todas las variantes tienen extracción válida.
  Es una comparación **válida** —misma prueba para todas— pero con la mitad de la
  muestra: el intervalo es más ancho de lo que sugiere un número con un decimal,
  y la cobertura completa queda sin medir.
- **El 429 llegó atribuido a `gemini-3.6-flash` y `variantes.py` pide
  `gemini-3.5-flash`.** El proveedor enruta a otro modelo y las predicciones
  guardan el modelo que se **pidió**, no el que **contestó**. Es el capítulo
  siguiente de la lección que ya está más arriba: no sólo caducan los
  identificadores — el proveedor puede contestar con otro modelo, y si no se
  registra cuál, no se puede saber. **Eso vuelve provisorio el "efecto del
  modelo":** si las dos variantes corrieron en el mismo modelo, lo medido no es
  el efecto del modelo. Anotado en `docs/PENDIENTES.md`.
- **Una etiqueta del set de oro estaba mal y la encontró un modelo**, no yo: el
  aviso `44538-26` decía apertura el 13/07 y yo había tipeado 3/07. Apareció
  desde el [proyecto 02](https://github.com/enzoestevez/conciliador-contrataciones)
  al cruzar contra el registro oficial. Corregida y registrada en
  [`docs/CORRECCIONES.md`](docs/CORRECCIONES.md). **Auditados los avisos con
  bloque legible: 1 etiqueta mal, 0 extracciones del modelo mal sobre 29.** Si
  hay un error en 29 campos auditables, es razonable suponer que hay otros en los
  que no se pudieron auditar.
- **La confianza del modelo no se puede usar para rutear**, como muestra la curva
  de umbral. El proyecto se planteaba encontrar el umbral óptimo y lo que
  encontró es que esa palanca casi no existe en este modelo. Es un resultado
  negativo y se informa igual.

## Consistencia del propio set de referencia

Doble etiquetado ciego de 20 documentos, estratificado por formato, sin ver las
respuestas anteriores y cronometrado: **85,7% de coincidencia conmigo mismo.**
Ese es el techo de este experimento — ningún modelo puede superar la consistencia
de la verdad de referencia contra la que se lo mide.

**Y el techo se parte igual que todo lo demás:**

| | Techo humano |
|---|---:|
| Formato COMPR.AR | **98,7%** |
| Formato libre | **72,7%** |

Ese desglose es el hallazgo más importante del proyecto. Un modelo al 73% en
formato libre no está fallando: está en el límite de lo que el documento permite
decidir sin información que no está escrita. Reportar "73%" sin el techo al lado
invita a la conclusión equivocada, que es gastar en un modelo mejor.

**Lo que el control ciego detectó además del número:**

1. **El sesgo de anclaje, medido y no supuesto.** La pasada asistida aceptaba la
   sobre-captura del parser en `organismo` donde la pasada ciega acertaba. El
   control encontró un error sistemático de la propia metodología.
2. **Dos reglas faltantes del protocolo.** Al escribirlas y aplicarlas, el techo
   subió de 79,7% a 85,7% y los documentos idénticos entre pasadas de 10% a 35%.
   Buena parte de lo que parecía inconsistencia humana era protocolo incompleto.
3. **El tiempo humano real:** 113 segundos por documento (mediana). El promedio
   de 222 s se descarta: un documento se llevó 1.080 s y arrastra el promedio.
   Reportar la media habría inflado el ahorro del modelo al doble.

## Decisiones que tomé y por qué

- **La hora cuenta en `fecha_apertura`.** En una apertura de ofertas, equivocarse
  de hora es equivocarse. Si el caso de uso no la necesitara, cambiaría el
  normalizador — pero sería un supuesto distinto y habría que declararlo.
- **`valor_pliego` distingue `0` de `null`.** "El pliego es gratuito" y "el aviso
  no menciona el pliego" son hechos distintos. Meterlos en la misma bolsa
  entrenaría al sistema a rellenar huecos.
- **`monto_estimado` bajó de peso 2.0 a 0.5** después de medir la cobertura sobre
  los 267 llamados: sólo el 15% de los avisos trae monto, así que en el 85% de
  los casos la respuesta correcta es `null`. Con peso 2.0, un modelo que
  contestara `null` siempre ganaba en el campo más pesado del esquema — o sea que
  ese campo medía prudencia, no capacidad de extracción. Lo que sí mide bien es la
  alucinación, y eso se reporta en su propia línea.
- **Los pesos salen de una tabla de cobertura medida**, no de una intuición. Está
  en el encabezado de `src/esquema.py` con el método para reproducirla.
- **El corpus se muestrea con fechas espaciadas**, por la republicación de avisos.
  Ver arriba: es la diferencia entre 38% y 1% de duplicados.
- **La línea base no es un modelo barato: es un parser sin IA.** `v0-reglas`
  extrae con expresiones regulares, a costo cero y latencia despreciable. Ubica
  los campos estructurales en el **95%** de los avisos de formato COMPR.AR y en
  el **51%** de los de formato libre. Cualquier modelo tiene que justificar su
  costo contra esa vara, y sólo en el segmento donde la diferencia existe. La
  pregunta del proyecto deja de ser "qué modelo anda mejor" y pasa a ser **dónde
  se justifica pagar por un modelo**.
- **Nunca un promedio único.** Cada número va con su `n` y partido por formato,
  al lado de su propio techo. El 83,5% global es cierto y no sirve para decidir
  nada.
- **La variante ganadora se elige sólo entre las que tienen cobertura completa.**
  La tabla llegó a coronar a `v4-modelo-caro` con 83,9% sobre 53 documentos
  contra `v3-ejemplos` con 83,5% sobre 115. No es la misma prueba, así que esos
  0,4 puntos no significaban nada. El dato estaba en `metricas.json`
  (`n_documentos: 53`, `errores_llamada: 62`) y el reporte no lo mostraba, **que
  es peor que no tenerlo**. Ahora la columna `n` está en la tabla, las variantes
  incompletas quedan marcadas, y si ninguna tiene cobertura completa el reporte
  se niega a generarse.
- **Rutear por formato, no por la confianza del modelo.** Es más preciso, se sabe
  antes de llamar al modelo y sale gratis. Lo encontré buscando lo contrario.
- **Un número demasiado limpio se investiga antes de publicarlo.** Esta regla
  salió del proyecto 02, donde un "cero discrepancias" resultó ser seis bugs
  propios, y se aplica para atrás: por eso `v4` se marca en vez de celebrarse.
