# Correcciones al set de oro

Un set de oro que se edita sin registro deja de ser oro. Toda corrección va acá,
con la fuente que la justifica, antes de tocar `data/gold/etiquetas.jsonl`.

## Regla

Una etiqueta se corrige **solo** si el texto del aviso la contradice de forma
verificable. No se corrige porque un modelo diga otra cosa, ni porque el
resultado quede más lindo: el modelo no es la fuente de verdad, el documento sí.
Lo que un modelo puede hacer —y acá lo hizo— es señalar dónde mirar.

## 2026-10-21 · `44538-26` · `fecha_apertura`

| | |
|---|---|
| Etiquetado | `3/07/2026 09:00:00` |
| El aviso dice | `13/07/2026 09:00:00` |
| Corregido a | `13/07/2026 09:00:00` |
| Verificado contra | el texto del aviso, bloque `Acto de Apertura` |
| Modo de etiquetado | `ciego` (sin sugerencia del extractor) |

Cómo apareció: el agente del proyecto 02 extrajo `2026-07-13` y el registro
oficial de COMPR.AR también dice `2026-07-13`, pero la etiqueta decía `03/07`.
Eso hacía que el proyecto 02 reportara una discrepancia de +10 días que no
existía. Al ir al texto:

```
Acto de Apertura
Plazo y horario: 13/07/2026 09:00:00
```

Es un typo de tipeo: se comió el `1`.

### Qué cambia

- El hallazgo del proyecto 02 baja de **7 de 39** a **6 de 39** avisos con la
  fecha de apertura vencida respecto del registro.
- El techo de 85.7% del doble ciego **no se corrige**. Ese número mide
  consistencia humana, y este typo es justamente una de las inconsistencias que
  el doble ciego existía para detectar. Sacarlo sería hacer trampa con la
  medición: el techo es bajo, en parte, precisamente porque un humano cansado
  escribe `3/07` donde dice `13/07`.

### Auditoría completa, no solo este caso

Encontrado un error, hay que preguntarse cuántos más hay. Los 39 avisos
emparejados se auditaron con un lector determinista del bloque
`Acto de Apertura` —ninguna llamada a modelo, cero costo—:

| | |
|---|---:|
| Con bloque legible | 29 de 39 |
| Etiquetas mal | **1** |
| Extracciones del modelo mal | **0 de 29** |
| Sin bloque (formato libre) | 10 |

Los 10 de formato libre no se pueden auditar así y quedan sin verificar: está
declarado, no resuelto.
