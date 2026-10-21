# Qué falta y cómo se completa

Todo lo que dice `COMPLETAR` en el repo, en orden de dependencia. Cada punto dice
**de dónde sale el número**, no sólo dónde escribirlo. Un número que no sabés cómo
se midió no lo vas a poder defender en una entrevista, y ese es el único punto de
todo esto.

Tachá cada casilla cuando la termines. Este archivo se commitea: el historial de
cómo se fue llenando es parte de lo que muestra que el trabajo lo hiciste vos.

---

## Bloque 0 — Conseguir el corpus

> Bloqueante de todo lo demás. `data/raw/` está vacío.

- [ ] **Bajar 4 ediciones diarias más de la Tercera Sección.**
  Ya tenés la del 3/8/2026, que dio 68 avisos (66 llamados). Con 5 ediciones
  llegás a ~330 avisos y ~300 llamados, que es el objetivo.

  **Elegí días de semana consecutivos o de semanas distintas, pero anotá cuáles.**
  No elijas los días "que parezcan mejores": un criterio arbitrario y declarado
  vale más que uno cómodo y silencioso.

- [ ] **Cortar las ediciones en avisos.**
  ```bash
  python src/dividir.py --resumen    # ver qué encontraría, sin escribir
  python src/dividir.py              # escribir los .txt
  ```
  Mirá los conteos que imprime: cuántos llamados contra cuántos resultados, y
  cuántos de formato COMPR.AR contra formato libre. Esos números van al README.

- [ ] **Verificar la heurística de clasificación sobre 20 avisos.**
  Abrí 20 al azar y comprobá a mano que `tipo` y `formato` en
  `data/interim/indice.json` están bien. Anotá cuántos clasificó mal. Una
  heurística con tasa de error medida es un dato; una sin medir es una suposición.

- [ ] **README → "De dónde salen los datos" → `Descarga: COMPLETAR`.**
  Fechas exactas de las ediciones, total de avisos, cuántos llamados, cuántos de
  cada formato, y cómo las bajaste. Tres renglones. Es lo que lo hace reproducible.

---

## Bloque 1 — El set de referencia

> Es el activo del proyecto. Los modelos cambian cada tres meses; un corpus
> etiquetado a mano contra un protocolo escrito, no.

- [ ] **Etiquetar los primeros 20.**
  ```bash
  python label/etiquetar.py
  ```
  Van a ser lentos y está bien. Cada vez que dudes, la duda es una regla que le
  falta al protocolo: anotala en el momento en `docs/protocolo-etiquetado.md`.
  No confíes en acordarte después.

- [ ] **Guardar una copia de esos 20 para el doble ciego.**
  ```bash
  cp data/gold/etiquetas.jsonl data/gold/_pasada1_20.jsonl
  ```
  Este archivo no se toca más. Es la primera pasada del control de calidad.

- [ ] **Anotar el reloj.** Cronometrá cuánto tardaste en esos 20 y anotá el
  promedio en minutos por documento. Este número reaparece en el bloque 4.

- [ ] **Seguir hasta 200–300 etiquetados.**
  ```bash
  python label/etiquetar.py --estado    # para ver cuántos van
  ```
  Abajo de 200 los porcentajes tienen demasiado ruido: una diferencia de 2 puntos
  entre variantes no significa nada con 50 documentos.

- [ ] **Después de los primeros 50, volver a los primeros 20.**
  ```bash
  python label/etiquetar.py --revisar
  ```
  Casi seguro cambiaste de criterio en el camino. Corregilos y actualizá el
  protocolo con la regla que te faltaba.

---

## Bloque 2 — El techo del experimento

> Esperá al menos dos días entre las dos pasadas. Por eso arranca temprano:
> tiene tiempo de espera que no depende de vos.

- [ ] **Segunda pasada ciega sobre los mismos 20 documentos.**
  Sin mirar `_pasada1_20.jsonl`. Guardala aparte como `_pasada2_20.jsonl`.

- [ ] **Comparar las dos pasadas y sacar el porcentaje de coincidencia.**
  Ese número es **el techo del experimento**: ningún modelo puede superar la
  consistencia de la verdad contra la que se lo mide. Si te diste 94% con vos
  mismo, un modelo que da 93% no está lejos del techo, está prácticamente en él.

- [ ] **README → "Consistencia del propio set de referencia" → `COMPLETAR`%.**
  Escribí también en qué campos te contradijiste. Casi nadie mide esto. Decirlo
  en una entrevista cambia cómo te miran.

---

## Bloque 3 — Configurar las variantes

- [ ] **`src/variantes.py` → los 5 `COMPLETAR-MODELO-*`.**
  Sacá los identificadores exactos de la documentación vigente de cada proveedor.
  Necesitás tres cosas: un modelo barato (va en `v1`, `v2`, `v3`), uno caro del
  mismo proveedor (`v4`), y uno de otro proveedor (`v5`).

  Cuidá la lógica del diseño: `v1→v2→v3` cambian **sólo el prompt** con el modelo
  fijo, y `v3→v4` cambia **sólo el modelo** con el prompt fijo. Si rompés eso, la
  comparación deja de ser atribuible y el proyecto pierde su razón de ser.

- [ ] **`config/precios.json` → precios de cada variante y `_consultado_el`.**
  De la página de precios oficial de cada proveedor, no de un blog. Poné la fecha
  en que los consultaste: los precios cambian y un reporte sin fecha envejece mal.

- [ ] **`.env` con la clave del proveedor.**
  ```bash
  cp .env.example .env
  ```
  Verificá que `.env` no aparezca en `git status` antes de commitear nada.

---

## Bloque 4 — El baseline humano

> Es lo que separa este proyecto de una demo. Sin punto de comparación, "94% de
> precisión" no significa absolutamente nada.

- [ ] **Precisión humana.** Sale gratis del bloque 2: la coincidencia entre tus
  dos pasadas *es* la precisión de un humano haciendo la tarea sin ayuda.
  **Declaralo con su límite:** es la misma persona, con el mismo criterio y el
  mismo protocolo, así que está sesgado hacia arriba — un operador distinto daría
  peor. Escribir esa limitación vale más que el número.

- [ ] **Tiempo por documento.** El promedio que cronometraste en el bloque 1.

- [ ] **Costo por documento.** Minutos por documento × costo por minuto de la
  persona que haría la carga. Buscá un salario real de mercado para un puesto de
  carga de datos, citá la fuente, y dividí. No lo inventes: es el número que un
  entrevistador de negocio va a querer auditar primero.

- [ ] **`reports/RESULTADOS.md` → tabla "Contra el baseline humano".**
  La fila `Carga manual` con esos tres números. Ojo: `RESULTADOS.md` se
  **regenera** cada vez que corrés `src/reporte.py`, así que completala al final,
  o mové esos números al README para no perderlos.

---

## Bloque 5 — Correr y decidir

- [ ] **Correr las variantes.**
  ```bash
  python src/extraer.py --variante v1-minimo --limite 20   # probá con pocos primero
  python src/extraer.py --todas                            # después, todo
  python src/evaluar.py
  python src/reporte.py
  ```
  Empezá siempre con `--limite 20`: si algo está mal configurado, lo descubrís
  gastando centavos en vez de gastar el presupuesto entero.

- [ ] **Elegir el umbral de confianza y justificarlo.**
  Mirá la curva en `RESULTADOS.md`. **El umbral no se elige por la métrica**: se
  elige comparando lo que cuesta un error que pasa contra lo que cuesta una
  revisión humana. Con tu costo por documento manual del bloque 4 ya tenés el
  segundo número. Para el primero, poné un supuesto explícito de cuánto cuesta
  un registro mal cargado y declaralo.

- [ ] **`RESULTADOS.md` → `Umbral elegido` y su justificación.**
  Dos renglones con la cuenta hecha, no una opinión.

- [ ] **README → el bloque del número, arriba de todo.**
  Los seis `COMPLETAR` de las primeras líneas. Es lo único que un reclutador lee
  con seguridad. Escribilo último, cuando los números sean reales.

---

## Bloque 6 — Lo que casi nadie escribe

> Estas dos secciones son las que hacen que el proyecto se lea como trabajo
> profesional en vez de como demo. No las dejes para nunca.

- [ ] **README → "Lo que no resuelve".**
  Candidatos que van a aparecer solos mientras trabajás: los PDFs escaneados;
  los avisos con montos en dólares, módulos o UVIs; las prórrogas y
  rectificaciones que referencian otro aviso; los llamados con múltiples
  renglones donde "el objeto" es discutible; el corte de 60.000 caracteres en
  `extraer.py` si algún aviso lo supera.

- [ ] **README → "Decisiones que tomé y por qué".**
  Ya hay dos escritas de ejemplo. Sumá las tuyas a medida que aparezcan. Las
  candidatas fuertes: por qué esos pesos y no otros en `esquema.py`; por qué
  crédito parcial sólo en `objeto`; por qué la alucinación se reporta aparte;
  qué dejaste afuera del esquema y por qué.

  **Esta sección es literalmente tu guion de entrevista.** Cada punto acá es una
  respuesta que ya tenés preparada.

---

## Control final antes de mostrarlo

- [ ] No queda ningún `COMPLETAR` en el repo:
      `grep -rn "COMPLETAR" . --include="*.py" --include="*.md" --include="*.json"`
      (los de `src/extraer.py` y `src/reporte.py` son código, no placeholders: se quedan)
- [ ] `data/gold/etiquetas.jsonl` está versionado y `.env` no
- [ ] `RESULTADOS.md` no tiene ninguna fila `mock`
- [ ] Podés explicar, sin mirar, por qué la comparación se hace sobre valores
      normalizados y no sobre strings
- [ ] Podés explicar por qué un `null` acertado cuenta como acierto
- [ ] Podés defender los pesos de `esquema.py` frente a alguien que proponga otros

## 22/10/2026 · registrar QUE modelo contesto

Las predicciones guardan el modelo que se PIDIO, no el que contesto. El 429 de
la corrida de v4 del 21/10 llego atribuido a `gemini-3.6-flash`, pero
`variantes.py` pide `gemini-3.5-flash`: el proveedor enruta a otro modelo y el
experimento no se entera.

Es el capitulo siguiente de la leccion que ya esta en el README (los
identificadores caducan): **no solo caducan, el proveedor puede contestar con
otro modelo, y si no se registra cual, no se puede saber.**

Arreglo: en `proveedores.py`, leer el identificador que devuelve la respuesta
(`model_version` en el SDK de Google) y guardarlo en cada registro de
prediccion junto al pedido. Si difieren, `evaluar.py` tiene que avisarlo: una
comparacion entre variantes que en realidad corrieron en el mismo modelo no
mide el efecto del modelo.
