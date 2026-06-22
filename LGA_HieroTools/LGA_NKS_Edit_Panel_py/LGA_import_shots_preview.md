> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_import_shots — Sección Import Preview

Tab principal `PREVIEW` de la herramienta `LGA_import_shots`.

Muestra una preview visual tipo timeline de cómo quedará el timeline de Nuke Studio una vez que se importen los ítems seleccionados.

## Propósito

Antes de ejecutar la importación real, el usuario puede revisar:

- En qué track irá cada ítem seleccionado.
- Qué clips existen actualmente a la izquierda y a la derecha del punto de inserción en cada track.
- Qué ítems no tienen track asignado y quedarán fuera del timeline.

Desde este tab también se puede ejecutar la importación real.

---

## Flujo de navegación

```
Tab IMPORT
  └─ click tab PREVIEW
       └─ Tab PREVIEW
            └─ click "Import Now" →  _do_import() → cierra el diálogo
```

El tab se habilita cuando existe al menos un ítem marcado. Al seleccionarlo,
`_on_tab_changed()` llama a `_update_import_page()`.

---

## Tabla timeline

La tabla NO usa el look estándar de las otras secciones (Rename, Transcode). Su aspecto imita un timeline de Nuke Studio: filas horizontales = tracks, celdas = bloques de clips.

### Columnas

| Col | Contenido | Ancho |
|-----|-----------|-------|
| 0 | Barra de color de track (10 px) | 10 px fijo |
| 1 | Nombre del track | 130 px fijo |
| 2 | **Shot Anterior** — eje temporal del shot previo | stretch igual |
| 3 | **Shot Nuevo** — eje temporal del shot importado | stretch igual |
| 4 | **Shot Siguiente** — eje temporal del shot siguiente | stretch igual |

Cada columna representa un **shot completo** con su propio eje de tiempo independiente:

- **Shot Anterior**: ventana temporal de los clips que existen completamente antes de `insert_frame`. El clip más largo define 100% del ancho. Clips más cortos se posicionan con offset proporcional a su `tl_in`.
- **Shot Nuevo**: todos los clips comienzan en TC 0 (sin offset). El clip con más frames = 100%. Otros se escalan proporcionalmente.
- **Shot Siguiente**: mismo principio que Shot Anterior, para los clips que pertenecen al shot siguiente (`item.name() == next_shot_name`).

Entre columnas hay 2-4 px de separador (padding de celdas).

---

## Track BurnIn — representación gráfica especial

Cuando existe un track cuyo nombre es `"BurnIn"` (normalizado: case-insensitive, sin espacios ni guiones bajos), la fila no muestra chips de clips normales.

En su lugar, `_build_burnin_row()` genera un `QWidget` con 3 tiras horizontales delgadas que:
- Usan `setSpan(row_i, 2, 1, 3)` para ocupar las 3 columnas de shots.
- Se distribuyen verticalmente en la misma altura que una fila normal.
- Color `#c0c0c0`, `border-radius: 2px`, `SizePolicy.Expanding` en ambos ejes.
- Sin tooltip, sin hover, sin interacción.

Esto representa gráficamente los burn-ins que ocupan todo el ancho del timeline en el pipeline.

`_is_burnin_track(name)` normaliza el nombre: `name.strip().lower().replace(" ","").replace("_","") == "burnin"`.

---

## Chips de clips

### Nombre a mostrar

El nombre del chip se obtiene del **nombre del archivo fuente** del clip en Hiero, no de `item.name()` (que devuelve solo el shot name/basename). Se usa `_clip_display_name(item)`:

```python
file_path = item.source().mediaSource().fileinfos()[0].filename()
basename  = os.path.basename(file_path)
# Quitar frame number y extensión:
# "TEST_013_010_aPlate_v01_%04d.exr" → "TEST_013_010_aPlate_v01"
# "TEST_013_020_EditRef.mov"          → "TEST_013_020_EditRef"
name = re.sub(r'[_.]%\d*d\.[^.]+$', '', basename)  # quita _%04d.exr
name = re.sub(r'[_.]\d{4,}\.[^.]+$', '', name)     # quita _1001.exr
name = re.sub(r'\.[^.]+$', '', name)                # quita .mov
```

Si la extracción falla, se usa `item.name()` como fallback.

### Color

El color de TODOS los chips se deriva del `track_color`:

- `bg     = mix_colors(track_color, "#1a1a1a", 0.35)`
- `border = track_color`
- `text   = mix_colors(track_color, "#ffffff", 0.75)`
- `weight = "bold"` para clips nuevos (a importar), `"normal"` para contexto.

**Excepción — color v000 (#474747):**
`_chip_color(clip_name, bar_color, track_type)` detecta versiones `v000`,
`v00`, etc. en tracks `comp`, `roto`, `cleanup` o `dmp`. En Preview, esos
chips usan fondo y texto de la paleta V000, pero conservan como borde el color
`_PREVIEW_<TASK>_BORDER_COLOR` de su task. El color único gris de
`_chip_color()` se mantiene para usos que
solo admiten un color, como el BinItem.

### Shrink y text crop

Los chips pueden shrinkear por debajo de su `sizeHint`:
- `QSizePolicy.Ignored` (horizontal) + `minimumWidth=1`
- El texto se cropea naturalmente si el chip es muy angosto.
- Garantiza que los anchos porcentuales se respeten exactamente.

### Tooltip

Al hacer hover sobre cualquier chip, se muestra un tooltip estilizado con:
- Nombre completo del clip (en accent color del track)
- Duración en frames y segundos

Implementado via `LGA_NKS_Shared/LGA_tooltip_helper.py` → `set_clip_tooltip()`. El CSS global de `QToolTip` se aplica una sola vez en `_build_page_import()` via `apply_tooltip_stylesheet()`.

---

## Anchos proporcionales por columna (K = 1000)

Cada columna usa `K = 1000` unidades de stretch. Los chips se arman con `QHBoxLayout`:
`addWidget(label, chip_K)` y `addStretch(trail_K)`.

**Shot Anterior** (`_build_before_cell`):

```
shot_start = min(tl_in de todos los before clips del timeline)
shot_dur   = max(tl_out) − shot_start + 1

offset_K   = (clip.tl_in − shot_start) / shot_dur × K
chip_K     = clip.duration / shot_dur × K
trail_K    = K − offset_K − chip_K

layout: [spacer(offset_K)] [chip(chip_K)] [spacer(trail_K)]
```

**Shot Nuevo** (`_build_new_cell`):

```
shot_dur = max(frame_count de todos los clips nuevos)

chip_K   = clip.frame_count / shot_dur × K   (sin offset)
trail_K  = K − chip_K

layout: [chip(chip_K)] [spacer(trail_K)]
```

**Shot Siguiente** (`_build_after_cell`):

```
shot_start = min(tl_in de todos los after clips del timeline)
shot_dur   = max(tl_out) − shot_start + 1

offset_K   = (clip.tl_in − shot_start) / shot_dur × K
chip_K     = clip.duration / shot_dur × K
trail_K    = K − offset_K − chip_K

layout: [spacer(offset_K)] [chip(chip_K)] [spacer(trail_K)]
```

Las métricas globales (`before_shot_start`, `before_shot_dur`, etc.) se calculan en `_populate_import_table` antes de iterar los tracks. Los cálculos se loguean con `debug_print`.

---

## Colores de barra de track

| Tipo | Color |
|------|-------|
| plate | `#42616d` (`_CLR_PLATES`) |
| editref | `#aa9e54` (`_CLR_REFS`) |
| comp | `#3381e0` (`_CLR_COMP`) |
| roto | `#2abf7e` (`_CLR_ROTO`) |
| cleanup | `#27c8c3` (`_CLR_CLEANUP`) |
| other | `#555555` |

---

## Sección "SIN TRACK ASIGNADO"

Debajo de todos los tracks, si hay ítems sin track asignado:

1. **Encabezado** — fila separadora con texto `SIN TRACK ASIGNADO` en span 1-4.
2. **Chip por ítem** — en la columna **Shot Nuevo** (col 3) únicamente:
   - Cols 2 y 4 permanecen vacías.
   - El chip usa `new_shot_dur` como referencia: si el ítem tiene tantos frames o más que el clip nuevo más largo, ocupa el 100%. Si tiene menos, ocupa el porcentaje proporcional.
   - Col 1 permanece vacía (el nombre ya está en el chip de col 3).
   - Color según su sección de origen (plates → `_CLR_PLATES`, refs → `_CLR_REFS`, publish → color de task).
   - Tooltip con nombre completo y duración.
   - Estos ítems **no se importan al timeline** al pulsar "Import Now".

---

## Handle automático para EditRef

Los tracks de tipo `editref` (`EditRef`, `EditRefClean`, etc.) suelen tener menos frames que el plate master porque el edit no incluye los frames de handle que sí están en el plate.

### Cálculo

```
master_dur  = max(frame_count) de todos los clips asignados a tracks
editref_dur = frame_count del clip editref
diff        = master_dur - editref_dur
handle_in   = diff // 2
handle_out  = diff - handle_in   (== handle_in si diff es par; handle_in + 1 si impar)
```

Solo se calcula si `editref_dur < master_dur`. Si el editref tiene igual o más frames que el master, no se aplica offset.

Si la diferencia es impar (`diff % 2 != 0`), el handle es asimétrico: `handle_in` y `handle_out` difieren en 1 frame. Se muestra una advertencia naranja en el label.

Con dos tracks editref distintos (`EditRef` y `EditRefClean`), se calcula un handle independiente para cada uno.

### Efecto en el preview

En la columna **Shot Nuevo**, el chip del editref no empieza en TC 0 sino con un spacer proporcional a `handle_in / shot_dur * K` delante. Visualmente el clip aparece corrido a la derecha dentro de la celda.

### Label informativo (debajo de la tabla)

`_update_import_handle_label()` escribe en `self._import_handle_lbl` (color `#aa9e54` para el valor, `#e08033` para advertencias impares):

- Un track editref: `EditRef handle: 5 f`
- Dos tracks: `EditRef handle: 5 f  |  EditRefClean handle: 3 f`
- Handle impar: `EditRef handle: 4 f  (in 4 / out 5)  ⚠ diferencia impar — handle asimétrico`

El label es invisible cuando no hay editrefs en la lista de importación.

### Efecto en el import real

En `_do_import._run_import()`, antes de llamar a `place_clip_in_timeline`, se suma `handle_in` al `effective_insert_frame` para los tracks editref:

```python
if classify_track_type(track_name) == "editref":
    clip_tl_in = effective_insert_frame + handle_info["handle_in"]
```

---

## Reglas de inclusión de tracks

`build_import_preview_data()` itera todos los `videoTracks()` de la secuencia activa.

Hiero devuelve los tracks de abajo hacia arriba. Se aplica `reversed()` para mostrarlos de arriba hacia abajo (orden visual del timeline).

Se incluyen **TODOS** los tracks del timeline sin excepción. Un track puede aparecer con las 3 columnas vacías (solo como contexto visual). Si un ítem está asignado a un track que no existe en el timeline, ese track se añade al final de la lista.

### Tracks duplicados (mismo nombre)

Cuando existen dos o más tracks con el mismo nombre en el timeline (ej. dos tracks llamados "EditRef"), solo el **primero encontrado** — el más alto visualmente, ya que se itera top-to-bottom — recibe los `new_items` del ítem asignado. Los tracks duplicados subsiguientes muestran `new_items = []`.

Esto evita que un ítem aparezca duplicado en la preview cuando el timeline tiene nombres de track repetidos.

La lógica se implementa con el set `assigned_track_names`: una vez que un `track_name` recibió ítems, las apariciones posteriores del mismo nombre son tratadas como contexto vacío.

---

## Clasificación de clips: before / after

`_find_adjacent_clips(track, prev_shot_name, next_shot_name)` busca en el track los clips cuyo `item.name()` coincide exactamente con el nombre del shot anterior o siguiente.

| Condición | Bucket |
|-----------|--------|
| `item.name() == prev_shot_name` | **before** |
| `item.name() == next_shot_name` | **after** |
| cualquier otro nombre | ignorado |

La búsqueda es **por nombre de shot**, no por posición de frames. Esto garantiza que si un track no tiene clip para el shot vecino (aunque tenga clips de otros shots más lejanos), el bucket queda `None` correctamente.

**Por qué por nombre y no por posición:**  
Con la lógica anterior (por `insert_frame`), si en un track no existía el shot siguiente pero sí había un clip de `MOR_1010_050` mucho más adelante, ese clip era clasificado incorrectamente como `after`. Con la búsqueda por nombre, solo el clip que pertenece al shot contiguo real aparece en el preview.

`prev_shot_name` y `next_shot_name` los calcula `_find_insert_frame()` como parte del mismo ordenamiento alfabético que determina el punto de inserción, y se propagan hasta aquí via `ImportShotDialog` → `build_import_preview_data`.

Para ese ordenamiento, `_find_insert_frame()` recibe shots ya agregados por `_collect_timeline_shots()`: cada `shot_name` usa `min(timelineIn)` y `max(timelineOut)` entre todos sus TrackItems en video tracks no-BurnIn. Esto permite que el shot master venga de cualquier track real (`_comp_`, plates, editrefs, etc.) y evita que un clip corto u offseteado del mismo shot cambie incorrectamente el punto de inserción.

---

## Un clip por track

La página principal (Media) aplica la regla de **un solo clip por track** en dos momentos:

**En carga inicial** (`_build_track_combo`):
- Prioridad entre tipos distintos: **EXR desplaza a MOV**; MOV cede ante EXR existente.
- Prioridad entre el mismo tipo (EXR vs EXR, o MOV vs MOV): **gana la versión más alta** (`version_num`). Si el ítem actual tiene mayor `version_num` que el que ya ocupa el track, desplaza al existente. Si es menor o igual, el actual cede.
- El ítem desplazado queda en `"— sin track —"` y su checkbox se inicializa con `is_latest` (desmarcado si no es la última versión).
- Los conflictos se loguean con `debug_print`.

**Por interacción del usuario** (`_on_track_combo_changed`):
- Cuando el usuario cambia un dropdown a un track ya ocupado, el anterior ítem queda en `"— sin track —"` automáticamente.

---

## Deduplicación de versiones

En `_update_import_page()`, antes de llamar a `build_import_preview_data()`, se deduplica por track: si hay múltiples ítems chequeados asignados al mismo track, **solo se importa el de mayor `version_num`**.

---

## Logging

El módulo `LGA_import_shots_preview.py` usa un logger inyectable. El módulo principal llama a `set_debug_print(debug_print)` via `_inject_preview_logger()` después de importar el módulo.

Prefijos de log: `_find_adjacent_clips`, `[before_cell]`, `[new_cell]`, `[after_cell]`, `[populate_import_table]`.

Archivo de log: `logs/debugPy_ImportShots.log`.

---

## Función principal: `build_import_preview_data`

**Archivo:** `LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py`

```python
def build_import_preview_data(
    seq,
    shot_name: str,
    insert_frame: int,
    prev_shot_name,        # nombre exacto del shot anterior (o None)
    next_shot_name,        # nombre exacto del shot siguiente (o None)
    items_by_track: dict[str, list[dict]],
    unassigned_items: list[dict],
) -> dict:
```

### Retorno

```python
{
  "tracks": [
    {
      "track_name": str,
      "track_type": "plate" | "editref" | "comp" | "roto" | "cleanup" | "dmp" | "other",
      "before_clip": {"name": str, "tl_in": int, "tl_out": int, "duration": int} | None,
      "new_items":   [item_dict],
      "after_clip":  {"name": str, "tl_in": int, "tl_out": int, "duration": int} | None,
    },
    ...
  ],
  "unassigned": [item_dict],  # cada uno tiene "_color"
}
```

El campo `"name"` en `before_clip`/`after_clip` proviene de `_clip_display_name(item)`: nombre del archivo fuente sin frame number ni extensión (ej. `TEST_013_010_aPlate_v01`).

---

## Funciones auxiliares: importación real

**Archivo:** `LGA_NKS_Edit_Panel_py/LGA_import_shots.py`

### `_do_import()`

Orquesta la importación completa:
1. Recopilar ítems chequeados con track asignado.
2. Llamar `_find_or_create_shot_bin()`.
3. Por cada ítem: `_import_item_to_bin()` → `_place_clip_in_timeline()`.
4. Todo envuelto en `project.beginUndo() / endUndo()`.
5. Si hay errores parciales: muestra `QMessageBox.warning`.
6. Cierra el diálogo con `self.accept()`.

---

## Referencias técnicas

### Archivos principales

| Archivo | Función / Clase |
|---------|----------------|
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py` | `build_import_preview_data` (incl. `assigned_track_names` para dedup de tracks duplicados), `_find_adjacent_clips`, `_clip_display_name`, `classify_track_type`, `mix_colors`, `set_debug_print`, `_log` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots.py` | `ImportShotDialog._build_page_import`, `_update_import_page`, `_populate_import_table`, `_populate_data_row`, `_build_before_cell`, `_build_new_cell`, `_build_after_cell`, `_build_burnin_row`, `_is_burnin_track`, `_chip_color`, `_make_chip_label`, `_build_track_combo`, `_on_track_combo_changed`, `_get_track_for_row`, `_inject_preview_logger`, `_track_bar_color`, `_item_section_color`, `_scan_input_folder`, `_find_insert_frame`, `_collect_timeline_shots` |
| `LGA_NKS_Shared/LGA_tooltip_helper.py` | `apply_tooltip_stylesheet`, `set_clip_tooltip`, `set_rich_tooltip`, `make_tooltip_html` |
| `LGA_NKS_Shared/LGA_tooltip_helper.md` | Documentación de uso del helper de tooltips |

### Documentación relacionada

- `LGA_NKS_Edit_Panel_py/LGA_import_shots.md` — documentación general de la herramienta
- `+Building_Blocks/LGA_NKS_CreateV000_Plan.md` — referencia para el flujo de importación Hiero
- `+Building_Blocks/Hiero/LGA_H-Tracks-Print_All_Tracks_With_Clips.py` — referencia para obtener tracks, clips, TL IN/OUT y media paths
- `+Building_Blocks/Hiero/LGA_H-Clip_PrintName_from_Playhead.py` — referencia para obtener nombre de archivo fuente de un clip
