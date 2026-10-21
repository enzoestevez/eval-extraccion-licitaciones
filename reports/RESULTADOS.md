# Resultados

Set etiquetado: **115 documentos** · esquema v1.1.0

## Comparacion de variantes

| Variante | n | Precision | Docs perfectos | Alucinacion | p95 latencia | USD/doc | Que cambia |
|---|---:|---:|---:|---:|---:|---:|---|
| `v4-modelo-caro` | 61 ⚠ | 84.4% | 36.1% | 2.7% | 35188 ms | 0.002844 | Mismo prompt que v3, modelo mas caro de la misma familia. Aisla el efecto del modelo. |
| `v3-ejemplos` | 115 | 83.5% | 31.3% | 2.9% | 37442 ms | 0.000751 | Mismo modelo, reglas mas un ejemplo resuelto. |
| `v1-minimo` | 115 | 83.2% | 30.4% | 3.7% | 20032 ms | 0.000622 | Prompt sin reglas. Es el piso: cuanto se saca sin trabajo. |
| `v2-reglas` | 115 | 83.1% | 27.8% | 2.6% | 4966 ms | 0.000681 | Mismo modelo, prompt con reglas. Aisla el efecto del prompt. |
| `v0-reglas` | 115 | 71.0% | 27.0% | 0.4% | 0 ms | 0.000000 | Extractor determinista sin IA. Costo cero. La vara a superar. |
| `v0-base` | 115 | 16.4% | 0.0% | 0.0% | 10 ms | — | Linea base sin proveedor. Sirve para probar el pipeline sin gastar. |

> **No comparables.** 1 variante tiene menos de 115 documentos evaluados, marcadas con ⚠:

> - `v4-modelo-caro`: **61 de 115** (54 llamadas fallidas). Su precision esta calculada sobre otro subconjunto, mas chico, y no se puede poner al lado de las demas.
>
> Para completarla: `python src/extraer.py --variante <id>`, que es reanudable y sólo pide los documentos que faltan. **Hasta entonces esa fila no entra en ninguna conclusion.**

**Precision** es el promedio ponderado por campo (los pesos estan en `src/esquema.py`). **Docs perfectos** es el porcentaje de documentos sin un solo campo mal — es la metrica dura, la que importa si el registro se carga entero o no se carga. **Alucinacion** es la proporcion de campos donde el modelo puso un valor y la verdad era `null`; en produccion es el error mas caro y por eso va aparte.

## Comparación emparejada · los mismos 61 documentos

La tabla de arriba da a cada variante su propio `n`, y eso impide compararlas entre si. **`v4-modelo-caro` tiene 54 documentos menos** porque la capa gratuita permite **20 llamadas por día** a ese modelo: completarla serían tres días de cupo.

La solución no es gastar tres días. Es medir **todas** las variantes sobre los mismos 61 documentos —la intersección donde todas tienen extracción válida—. Las predicciones ya estaban guardadas, así que **la comparación válida salió a costo cero.**

| Variante | Precisión | Docs perfectos | Alucinación | USD/doc |
|---|---:|---:|---:|---:|
| `v4-modelo-caro` | 84.4% | 36.1% | 2.7% | 0.002844 |
| `v3-ejemplos` | 81.9% | 27.9% | 3.3% | 0.000738 |
| `v2-reglas` | 81.2% | 24.6% | 2.9% | 0.000670 |
| `v1-minimo` | 80.8% | 24.6% | 4.1% | 0.000611 |
| `v0-reglas` | 72.5% | 31.1% | 0.2% | 0.000000 |
| `v0-base` | 17.9% | 0.0% | 0.0% | — |

**El efecto del modelo, por fin medido sobre la misma prueba:** el modelo caro gana **+2.5 puntos de precisión** y **+8.2 puntos de documentos perfectos**, a **3.9× el costo**.

Y la métrica que decide no es la precisión: es **documentos perfectos**. El sistema que consume esto ([proyecto 02](https://github.com/enzoestevez/conciliador-contrataciones)) arma una llave con varios campos — un error en `numero_procedimiento` no degrada el caso, lo **mata**. Con ese criterio la diferencia no es de 2.5 puntos sino de 8.2, y ahí la discusión del costo cambia.

**Un detalle que la tabla global escondía:** `v0-reglas`, sin IA y a costo cero, tiene **más documentos perfectos** que `v3-ejemplos` (31.1% contra 27.9%) con 9.5 puntos menos de precisión. El parser determinista acierta el documento entero más seguido, pero cuando falla falla en más campos a la vez. Dos perfiles de error distintos que un promedio junta.

## El promedio unico no sirve: hay que partir por formato

El doble ciego midio el techo del experimento —la consistencia de una persona etiquetando dos veces a ciegas— en **98,7% para COMPR.AR** y **72,7% para formato libre**. Son dos problemas distintos, y comparar un modelo contra un techo que no le corresponde no dice nada.

### COMPR.AR · techo humano 98.7%

| Variante | n | Precision | Contra el techo | Docs perfectos | Alucinacion |
|---|---:|---:|---:|---:|---:|
| `v3-ejemplos` | 58 | 93.5% | −5.2 pts | 56.9% | 0.0% |
| `v1-minimo` | 58 | 93.0% | −5.7 pts | 51.7% | 0.0% |
| `v2-reglas` | 58 | 92.7% | −6.0 pts | 50.0% | 0.0% |
| `v0-reglas` | 58 | 89.5% | −9.2 pts | 53.4% | 0.0% |
| `v0-base` | 58 | 12.3% | −86.4 pts | 0.0% | 0.0% |

### formato libre · techo humano 72.7%

| Variante | n | Precision | Contra el techo | Docs perfectos | Alucinacion |
|---|---:|---:|---:|---:|---:|
| `v3-ejemplos` | 57 | 73.2% | **en el techo** | 5.3% | 5.9% |
| `v2-reglas` | 57 | 73.2% | **en el techo** | 5.3% | 5.3% |
| `v1-minimo` | 57 | 73.2% | **en el techo** | 8.8% | 7.5% |
| `v0-reglas` | 57 | 52.1% | −20.6 pts | 0.0% | 0.9% |
| `v0-base` | 57 | 20.6% | −52.1 pts | 0.0% | 0.0% |

**En formato libre el modelo ya esta en el techo humano** (73.2% contra 72.7%). Lo que queda de error no es una limitacion del modelo: es que el documento no trae la respuesta de forma inequivoca. Ninguna version del prompt lo va a mover, y eso se ve en que las variantes de prompt dan el mismo numero en ese formato.

**En COMPR.AR queda margen real:** 93.5% contra un techo de 98.7%, 5.2 puntos.

**Donde se justifica pagar por un modelo**, que es la pregunta del proyecto: en COMPR.AR el extractor determinista saca 89.5% a costo cero contra 93.5% del modelo, **+4.0 puntos**; en formato libre el extractor determinista saca 52.1% a costo cero contra 73.2% del modelo, **+21.1 puntos**.

## Donde se equivoca la mejor variante (`v3-ejemplos`)

| Campo | Peso | Precision | Acierto | Null ok | Error | Alucinacion | Omision |
|---|---:|---:|---:|---:|---:|---:|---:|
| `organismo` | 1.5 | 64.3% | 74 | 0 | 41 | 0 | 0 |
| `expediente` | 2.0 | 91.3% | 82 | 23 | 7 | 2 | 1 |
| `tipo_procedimiento` | 1.0 | 87.8% | 101 | 0 | 14 | 0 | 0 |
| `numero_procedimiento` | 1.5 | 87.8% | 101 | 0 | 5 | 9 | 0 |
| `objeto` | 1.0 | 74.5% | 71 | 0 | 33 | 11 | 0 |
| `monto_estimado` | 0.5 | 89.6% | 13 | 90 | 1 | 0 | 11 |
| `fecha_apertura` | 2.0 | 87.8% | 89 | 12 | 11 | 0 | 3 |
| `valor_pliego` | 0.5 | 81.7% | 8 | 86 | 0 | 5 | 16 |

El campo mas debil es `organismo` (64.3%). Escribi aca por que, mirando los casos de `reports/metricas.json` → `peores`. Un promedio sin explicacion de la cola no dice nada.

## Umbral de confianza: cuanto derivar a revision humana

| Umbral | Auto-procesado | A revision | Precision sobre lo auto-procesado |
|---:|---:|---:|---:|
| 0.00 | 100.0% | 0.0% | 83.5% |
| 0.05 | 100.0% | 0.0% | 83.5% |
| 0.10 | 100.0% | 0.0% | 83.5% |
| 0.15 | 100.0% | 0.0% | 83.5% |
| 0.20 | 100.0% | 0.0% | 83.5% |
| 0.25 | 100.0% | 0.0% | 83.5% |
| 0.30 | 100.0% | 0.0% | 83.5% |
| 0.35 | 100.0% | 0.0% | 83.5% |
| 0.40 | 100.0% | 0.0% | 83.5% |
| 0.45 | 100.0% | 0.0% | 83.5% |
| 0.50 | 100.0% | 0.0% | 83.5% |
| 0.55 | 100.0% | 0.0% | 83.5% |
| 0.60 | 100.0% | 0.0% | 83.5% |
| 0.65 | 100.0% | 0.0% | 83.5% |
| 0.70 | 100.0% | 0.0% | 83.5% |
| 0.75 | 100.0% | 0.0% | 83.5% |
| 0.80 | 100.0% | 0.0% | 83.5% |
| 0.85 | 96.5% | 3.5% | 83.9% |
| 0.90 | 93.0% | 7.0% | 84.6% |
| 0.95 | 89.6% | 10.4% | 85.1% |
| 1.00 | 55.6% | 44.4% | 91.0% |

Esta tabla es la conclusion operativa del proyecto. No se elige el umbral por la metrica: se elige por cuanto cuesta un error contra cuanto cuesta una revision humana. Escribi debajo el umbral que elegiste y con que numeros lo justificaste.

**Umbral elegido:** `COMPLETAR` — justificacion: `COMPLETAR`

## Contra el baseline humano

| | Precision | Tiempo por documento | Costo por documento |
|---|---:|---:|---:|
| Carga manual | `COMPLETAR` | `COMPLETAR` | `COMPLETAR` |
| `v3-ejemplos` | 83.5% | 3.9 s | 0.000751 USD |
| `v3-ejemplos` + revision del umbral elegido | `COMPLETAR` | `COMPLETAR` | `COMPLETAR` |

Para el baseline humano: cronometra vos mismo la carga manual de 20 documentos tomados al azar del corpus, contra el mismo esquema. Anota el metodo. Sin ese numero medido, todo lo de arriba es una demo sin punto de comparacion — que es exactamente el error del 95% de los pilotos.
