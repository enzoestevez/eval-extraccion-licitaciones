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
PDFs (data/raw)
   │
   ├─ src/ingesta.py ──────────► texto plano (data/interim/*.txt)
   │                              + detección de escaneados
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
python src/ingesta.py
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
Los PDFs no están versionados en el repo (`data/raw/` está en `.gitignore`): son
pesados y se pueden volver a bajar. Lo que sí está versionado es el set etiquetado,
que es el activo real del proyecto.

Descarga: `COMPLETAR` — anotá acá cómo los bajaste (script, rango de fechas,
cuántos), para que sea reproducible.

## Lo que no resuelve

*(Completá esta sección cuando termines. Es la más importante del README y la que
casi nadie escribe. Un proyecto que documenta sus propios límites se lee como
trabajo profesional; uno que sólo muestra el número bueno se lee como demo.)*

- PDFs escaneados sin capa de texto: quedan fuera del corpus, marcados en
  `data/interim/indice.json`. Requerirían OCR y un experimento aparte, porque
  mezclarlos confunde el error del modelo con el error del OCR.
- `COMPLETAR`
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
- `COMPLETAR`
