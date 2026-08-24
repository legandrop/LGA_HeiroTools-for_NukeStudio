> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Lógica de Nombres de Tracks del Timeline

Este documento centraliza la convención de nombres de tracks usada por las herramientas de Hiero / Nuke Studio en este repo.

## Objetivo

Separar claramente por dominio:

- tracks de **EXR por task** (renders publicados por cada task)
- tracks de **review MOV/MXF por task** (renders para revisar)
- tracks de **referencia editorial**
- tracks de **utilidad de viewer / timeline**

## Convención única para tasks

Para cada task hay dos tracks posibles:

| Tipo de track | Patrón del nombre | Ejemplos |
|---|---|---|
| EXR de la task | `_{task}_` | `_comp_`, `_roto_`, `_cleanup_` |
| Review MOV/MXF de la task | `_{task}Rev_` | `_compRev_`, `_rotoRev_`, `_cleanupRev_` |

El track `Rev` contiene archivos `.mov` o `.mxf` indistintamente según el proyecto. El sufijo `Rev` identifica la función (review), no el contenedor.

## Tasks vigentes

### Comp

| Dominio | Track | Variable |
|---|---|---|
| EXR | `_comp_` | `TRACK_comp_EXR` |
| Review MOV/MXF | `_compRev_` | `TRACK_comp_REV` |

### Roto

| Dominio | Track | Variable |
|---|---|---|
| EXR | `_roto_` | `TRACK_roto_EXR` |
| Review MOV/MXF | `_rotoRev_` | `TRACK_roto_REV` |

### Cleanup

| Dominio | Track | Variable |
|---|---|---|
| EXR | `_cleanup_` | `TRACK_cleanup_EXR` |
| Review MOV/MXF | `_cleanupRev_` | `TRACK_cleanup_REV` |

### CG (solo contexto client)

| Dominio | Track | Variable |
|---|---|---|
| EXR | `_cg_` | `TRACK_cg_EXR` |
| Review MOV/MXF | `_cgRev_` | `TRACK_cg_REV` |

La task **CG existe solo en contexto client** (en studio no existe; ver
[Doc_HieroTools_Studio_Client_Context.md](Doc_HieroTools_Studio_Client_Context.md)).
El nombre de la task (`CG_TASK_NAME`) se deriva del propio token del track:
`TRACK_cg_EXR.strip("_").lower()`, así que renombrar la variable del track
renombra la familia entera.

**Puede haber VARIOS tracks `_cg_` en el mismo timeline**, uno por disciplina
(layout, lighting, anim, fx, ...). A diferencia de comp/roto/cleanup, en CG el
filename **no lleva el token de task** — lleva la disciplina como "stream"
(ej: `PROJA_1013_0800_layout_v003`, nunca `..._cg_v003`). Los helpers que
buscan clips por nombre de track (`find_clip_at_playhead_in_track()`,
`get_selected_clips_in_track()` en
[LGA_NKS_Shared/LGA_NKS_GetClip.py](../LGA_NKS_Shared/LGA_NKS_GetClip.py))
aceptan múltiples tracks con el mismo nombre y los recorren todos — no
asumen un único track `_cg_`.

## Listas centralizadas

Cualquier script que opere sobre "todas las tasks" debe iterar las listas y no hardcodear nombres.

- `TASK_EXR_TRACKS = [TRACK_comp_EXR, TRACK_roto_EXR, TRACK_cleanup_EXR, TRACK_cg_EXR]`
- `TASK_REV_TRACKS = [TRACK_comp_REV, TRACK_roto_REV, TRACK_cleanup_REV, TRACK_cg_REV]`

`registered_task_names()` devuelve los nombres de task derivados de
`TASK_EXR_TRACKS` (`["comp", "roto", "cleanup", "cg"]`); ningún script debe
mantener su propia lista de nombres de task en paralelo.

## Tracks editoriales y auxiliares

- **`EditRef`** — Referencia editorial para navegación, in/out y comparaciones.
- **`EditRefClean`** — Variante limpia de referencia editorial usada por algunos scripts.
- **`aPlate`** — Track de plate para comparaciones de rango o imagen contra comp.
- **`BurnIn`** — Track auxiliar para overlays de viewer.

## Semántica

El nombre del track importa:

- `_comp_` = **EXR de la task comp**, no "cualquier EXR"
- `_roto_` = **EXR de la task roto**
- `_cg_` = **EXR de la task CG** (client), con la disciplina en el filename
- `_compRev_` = **MOV/MXF de review de comp**
- `_rotoRev_` = **MOV/MXF de review de roto**

Por lo tanto:

- si el script trabaja solo con una task, usar la variable específica (`TRACK_comp_EXR`, `TRACK_roto_REV`, etc.)
- si el script trabaja con todas las tasks EXR, iterar `TASK_EXR_TRACKS`
- si el script trabaja con todas las reviews, iterar `TASK_REV_TRACKS`

## Agregar una nueva task

Los pasos para sumar una task nueva son:

1. Agregar las variables en [LGA_NKS_Shared/LGA_NKS_GetClip.py](../LGA_NKS_Shared/LGA_NKS_GetClip.py):
   ```python
   TRACK_nueva_EXR = "_nueva_"
   TRACK_nueva_REV = "_nuevaRev_"
   ```
2. Sumarlas a las listas centralizadas:
   ```python
   TASK_EXR_TRACKS = [..., TRACK_nueva_EXR]
   TASK_REV_TRACKS = [..., TRACK_nueva_REV]
   ```
3. **Nada que tocar en el mapa task→track**: `_TASK_TO_TRACK` de
   [LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py](../LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py)
   se deriva de `TASK_EXR_TRACKS` (`{t.strip("_").lower(): t for t in TASK_EXR_TRACKS}`),
   así que sumar el track ahí alcanza para que el selector de task, el chequeo
   de mismatch y `registered_task_names()` lo reconozcan solos.
4. Revisar filtros por nombre de archivo, regex y detección de task en los scripts que ya soportan multi-task.
5. Revisar UI donde hay acciones específicas por task (ej. botones on/off del Review Panel).
6. Actualizar la tabla de tasks vigentes de este documento.
7. Revisar el estado en [Docu_MultiTask.md](Docu_MultiTask.md).

## Reglas de implementación

- No hardcodear nombres de track si ya existe una variable centralizada.
- Para selección por track EXR principal, preferir `track_name=None` cuando el comportamiento deba respetar `TRACK_comp_EXR`.
- Para lógica multi-task, iterar `TASK_EXR_TRACKS` o `TASK_REV_TRACKS` según corresponda.
- Nombres históricos en desuso: `_rev_`, `REV`, `_compMov_`. Toda documentación o código que los nombre como vigentes está desactualizada.

## Referencias técnicas

- **Módulo central:** [LGA_NKS_Shared/LGA_NKS_GetClip.py](../LGA_NKS_Shared/LGA_NKS_GetClip.py)
  - Variables: `TRACK_comp_EXR`, `TRACK_comp_REV`, `TRACK_roto_EXR`, `TRACK_roto_REV`, `TRACK_cleanup_EXR`, `TRACK_cleanup_REV`, `TRACK_cg_EXR`, `TRACK_cg_REV`, `TASK_EXR_TRACKS`, `TASK_REV_TRACKS`, `CG_TASK_NAME`, `registered_task_names()`
  - Funciones: `get_clip_to_process()`, `get_clips_to_process()`, `find_clip_at_playhead_in_track()` (acepta múltiples tracks con el mismo nombre), `get_selected_clips_in_track()` (ídem)

- **Estado multi-task por script:** [Docu_MultiTask.md](Docu_MultiTask.md)

- **Selección de clips:** [Docu_Metodos_Seleccion_Clip.md](Docu_Metodos_Seleccion_Clip.md)

- **Push multi-task:** [LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py)
  - Funciones: `push_from_selected_clips()`, `_show_task_selection_dialog()`

- **Pull multi-task:** [LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py)
  - Métodos: `HieroOperations.process_selected_clips()`, `HieroOperations.change_to_highest_version()`, `SGManager.find_highest_version_for_task()`

- **Review on/off por track:** [LGA_NKS_Review_Panel.py](../LGA_NKS_Review_Panel.py)
  - Métodos: `execute_DisableEXR()`, `execute_DisableRoto()`

- **Script de toggle (escenario comp por default):** [LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py)
  - Función: `main(track_name=None, enable_rev_fallback=True)`
  - Default `enable_rev_fallback=True`: trabaja exclusivamente sobre el playhead. Si `_comp_` está vacío en el playhead o tiene un clip v00/v000, busca un track `_compXXX_`. Si coincide con `TRACK_comp_REV` (case-insensitive) opera ahí; si no, ofrece renombrarlo al nombre canónico antes de operar.
  - `enable_rev_fallback=False`: comportamiento original (playhead con fallback a selección, sin lógica REV). Usado por wrappers de otras tasks.

- **Wrapper roto:** [LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableRoto.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableRoto.py)
  - Función: `main()` → llama a `disable_main(track_name=TRACK_roto_EXR, enable_rev_fallback=False)`

- **Selección de task en playhead (single-task tools):** [LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py](../LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py)
  - Funciones: `get_tasks_at_playhead()`, `track_for_task()`, `prompt_task_selection()`, `resolve_task_at_playhead()`
  - `_TASK_TO_TRACK` (y su inverso `_TRACK_TO_TASK`) se derivan de `TASK_EXR_TRACKS`: agregar una task nueva en `GetClip.py` los registra solos, sin tocar este módulo.
