# Extracción de datos de avisos de contratación pública — banco de evaluación

> **El número:** `COMPLETAR`% de precisión a nivel campo sobre un set de
> `COMPLETAR` avisos etiquetados a mano, a `COMPLETAR` USD por documento.
> Con umbral de confianza en `COMPLETAR`, el `COMPLETAR`% se procesa solo y el
> resto va a revisión humana, sosteniendo `COMPLETAR`% de precisión efectiva.
> El baseline humano es `COMPLETAR`% a `COMPLETAR` USD por documento.
>
> *(Reemplazá esto por los números reales cuando corras el proyecto. Es lo único
> que un reclutador lee con seguridad.)*

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

Ver [`reports/RESULTADOS.md`](reports/RESULTADOS.md) — se genera solo.

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
promedio único. `COMPLETAR`% en formato COMPR.AR contra `COMPLETAR`% en formato
libre es un hallazgo; el promedio de los dos esconde justamente dónde falla.

## Lo que no resuelve

*(Completá esta sección cuando termines. Es la más importante del README y la que
casi nadie escribe. Un proyecto que documenta sus propios límites se lee como
trabajo profesional; uno que sólo muestra el número bueno se lee como demo.)*

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
- `COMPLETAR`

## Consistencia del propio set de referencia

Doble etiquetado ciego de 20 documentos: `COMPLETAR`% de coincidencia conmigo
mismo. Ese es el techo de este experimento — ningún modelo puede superar la
consistencia de la verdad de referencia contra la que se lo mide.

## Decisiones que tomé y por qué

*(Completá con las tuyas a medida que aparezcan. Esta sección es la que se
convierte en tus respuestas de entrevista.)*

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
- `COMPLETAR`
