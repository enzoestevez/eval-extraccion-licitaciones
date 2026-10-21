# Guía de campo: cómo etiquetar sin leer el aviso entero

Tenelo abierto al lado mientras etiquetás. No es teoría: son avisos reales de
este corpus, resueltos campo por campo.

**La idea central:** no leés el aviso para entenderlo. Buscás 8 cosas y las
copiás. No te importa si compran drones, aulas o limpieza.

---

## Las 8 preguntas, en castellano

| Campo | La pregunta que estás contestando | Dónde mirar |
|---|---|---|
| `organismo` | ¿Quién compra? | Primera o segunda línea, en mayúsculas |
| `expediente` | ¿Qué número de trámite administrativo? | Busca `EXPEDIENTE`, `EXPTE`, `EX-` |
| `tipo_procedimiento` | ¿Qué clase de llamado es? | Línea con "Licitación Pública", "Contratación Directa"… |
| `numero_procedimiento` | ¿Qué número de llamado? | Pegado al tipo: "Licitación Pública **13/26**" |
| `objeto` | ¿Qué están comprando? | `Objeto:`, `OBJETO:`, o la descripción de la obra |
| `monto_estimado` | ¿Cuánto calculan gastar? | `Presupuesto Oficial`. Casi nunca está (15%) |
| `fecha_apertura` | ¿Cuándo abren los sobres? | `Apertura`. **No** confundir con recepción de ofertas |
| `valor_pliego` | ¿Cuánto cuesta el pliego? | `Valor del pliego`. Casi nunca está (13%) |

---

## Cómo se escriben las fechas y los montos

Vos escribís en un formato que la herramienta entienda, **no** copiado literal.
Si te lo rechaza, es que el formato no le sirve, no que el dato esté mal.

**Fechas** — el aviso dice "8 de julio de 2026 a las 11 hs", vos escribís:

```
08/07/2026 11:00
```

También acepta `08/07/2026 11:00:00` y, si el aviso no da hora, `08/07/2026`.

**Montos** — sólo el número, sin `$`, sin texto alrededor. La coma es el decimal:

```
1.428.322.788,00        →  se escribe así, o como 1428322788,00
```

---

## Tres avisos reales, resueltos

### 1. Universidad Nacional de Avellaneda — `33849-26`

```
UNIVERSIDAD NACIONAL DE AVELLANEDA
Licitación Pública 1/2026
...
Tipo de Obra: Ampliación Sede Arenales
Presupuesto Oficial: $1.428.322.788,00 (mes base ABRIL)
Recepción de Ofertas: Hasta el 8 de julio de 2026, a las 10:30 hs
Apertura de Ofertas: 8 de julio de 2026 a las 11 hs
Valor del pliego: Sin valor
```

| Campo | Qué escribís | Por qué |
|---|---|---|
| `organismo` | `UNIVERSIDAD NACIONAL DE AVELLANEDA` | Primera línea |
| `expediente` | `-` (null) | No hay ningún número de expediente en el aviso |
| `tipo_procedimiento` | `Licitación Pública` | |
| `numero_procedimiento` | `1/2026` | |
| `objeto` | `Ampliación Sede Arenales` | No hay etiqueta `Objeto:`; lo más específico que describe qué contratan |
| `monto_estimado` | `1428322788,00` | Marcalo **dudoso**: "monto a mes base abril" |
| `fecha_apertura` | `08/07/2026 11:00` | **Apertura**, las 11. No la recepción de las 10:30 |
| `valor_pliego` | `0` | "Sin valor" = gratis. **No es null** |

**La trampa de este aviso:** hay dos horarios seguidos. La recepción de ofertas
cierra 10:30, la apertura es 11:00. Son eventos distintos.

---

### 2. Universidad Nacional de La Plata — `35467-26`

```
UNIVERSIDAD NACIONAL DE LA PLATA -
SECRETARÍA DE PLANEAMIENTO, OBRAS Y SERVICIOS
Licitación Pública 06/26
La Secretaria de Planeamiento, Obras y Servicios llama a Licitación pública...
EXPEDIENTE: 3000-93/2026.-
OBJETO: "AULAS 1 Y 2 PUESTA EN VALOR ESTRUCTURA Y CUBIERTA" - Facultad de Arquitectura...
PRESUPUESTO OFICIAL: PESOS CIENTO VEINTICUATRO MILLONES QUINIENTOS OCHENTA MIL
OCHOCIENTOS SESENTA Y TRES con 00/100 ($ .124.580.863,00).
COMPRA Y VALOR DE LEGAJOS: Sin Costo.
PRESENTACIÓN DE OFERTAS Y ACTO DE APERTURA: ... el día 08 de Julio de 2026 a las 09.00 horas.
```

| Campo | Qué escribís | Por qué |
|---|---|---|
| `organismo` | `SECRETARÍA DE PLANEAMIENTO, OBRAS Y SERVICIOS` | Hay dos niveles; el texto dice que **la Secretaría** llama |
| `expediente` | `3000-93/2026.-` | Completo, con el guion final. No lo limpies |
| `tipo_procedimiento` | `Licitación Pública` | |
| `numero_procedimiento` | `06/26` | Con el cero. Copiás el formato del aviso |
| `objeto` | `"AULAS 1 Y 2 PUESTA EN VALOR ESTRUCTURA Y CUBIERTA" - Facultad de Arquitectura y Urbanismo.` | |
| `monto_estimado` | `124580863,00` | Ver abajo |
| `fecha_apertura` | `08/07/2026 09:00` | "09.00 horas" son las 9 |
| `valor_pliego` | `0` | "Sin Costo" |

**La trampa de este aviso:** el número tiene un error de tipeo —
`$ .124.580.863,00`, con un punto de más adelante. Las letras dicen "ciento
veinticuatro millones…", así que el monto es 124.580.863. El protocolo ya lo
cubre: ante discrepancia entre letras y números, usás el número corregido por
las letras y **marcás dudoso** con la nota.

---

### 3. ARCA / Aduana — `36227-26`

```
LIMPIEZA
AGENCIA DE RECAUDACIÓN Y CONTROL ADUANERO  -
DIRECCIÓN REGIONAL ADUANERA RÍO COLORADO
Licitación Pública 13/26
EXPEDIENTE ELECTRÓNICO: EX-2026-01504939-ARCA-DVAFRC#SDGOAI
OBJETO: Servicio integral de limpieza - Resguardo Aduanero...
FECHA DE APERTURA DE OFERTAS: 17/06/2026 a las 10:00Hs
VALOR DEL PLIEGO: Sin Costo
```

| Campo | Qué escribís | Por qué |
|---|---|---|
| `organismo` | `DIRECCIÓN REGIONAL ADUANERA RÍO COLORADO` | El nivel más específico |
| `expediente` | `EX-2026-01504939-ARCA-DVAFRC#SDGOAI` | |
| `tipo_procedimiento` | `Licitación Pública` | |
| `numero_procedimiento` | `13/26` | |
| `objeto` | `Servicio integral de limpieza - Resguardo Aduanero ubicado en la Zona Primaria Aduanera y la Oficina de Aduana en Aeropuerto dependientes de la División Aduana Bariloche.` | Completo, hasta donde cambia de tema |
| `monto_estimado` | `-` (null) | No figura |
| `fecha_apertura` | `17/06/2026 10:00` | |
| `valor_pliego` | `0` | "Sin Costo" |

**La trampa de este aviso:** la primera línea dice `LIMPIEZA`. Eso **no es el
organismo**: es la categoría del rubro, que se coló al cortar el boletín.
`src/dividir.py` limpia los rubros de primer nivel (SERVICIOS, SUMINISTROS,
OBRAS…) pero no los de segundo nivel, que a veces vienen partidos en dos líneas.

Si la primera línea es una categoría suelta en mayúsculas — `LIMPIEZA`,
`VARIOS`, `EFECTOS VARIOS`, `CIVILES`, `VIALES` — salteala y tomá la siguiente.
Es una limitación conocida y va declarada en el README.

---

## Los cuatro errores que más se cometen

**1. Confundir apertura con recepción de ofertas.** Muchos avisos traen los dos
horarios seguidos. `fecha_apertura` es cuando se abren los sobres.

**2. Poner `null` donde va `0` en `valor_pliego`.** "Sin costo", "sin valor",
"sin cargo", "gratuito" → `0`. `null` es sólo cuando el aviso no menciona el
precio del pliego para nada.

**3. Cortar el `objeto` de más o de menos.** Va completo, con las palabras del
aviso, hasta donde el texto pasa a hablar de otra cosa (plazos, dirección,
pliego). Es el campo donde más se cuela el error porque "parece bien" de un
vistazo.

**4. Confundir expediente con número de procedimiento.** El expediente es el
trámite administrativo (`EX-`, `EXP-`, `3000-93/2026`). El número de
procedimiento identifica el llamado (`13/26`, `1/2026`) y va pegado al tipo.

---

## Cuando de verdad no sabés

Dos salidas, las dos legítimas:

- **`!`** en la pregunta final marca el aviso como **dudoso** y te deja escribir
  por qué. Los dudosos se quedan en el set y se reportan aparte. Si son más del
  10% del corpus, eso es un hallazgo del proyecto: significa que la tarea tiene
  ambigüedad irreducible y que ningún modelo va a llegar al 100%.
- **`.`** saltea el aviso entero. Usalo poco, pero usalo antes que inventar.

Y cada vez que dudes y resuelvas, escribí la regla en
[`protocolo-etiquetado.md`](protocolo-etiquetado.md). Ese documento es lo que
convierte tus 250 decisiones sueltas en un criterio, y es la mitad del valor del
proyecto.
