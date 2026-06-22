> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_import_shots — Sección Import Real

Subsección de la herramienta `LGA_import_shots`.

Ejecuta la importación física de los ítems seleccionados al bin de Hiero y al timeline.
Se activa al pulsar `Import Now` tanto en el tab `IMPORT` como en el tab
`PREVIEW`.

---

## Flujo de navegación

```
Tab IMPORT o tab PREVIEW
  └─ click "Import Now"
       └─ ImportShotDialog._do_import()
            ├─ [dentro del bloque beginUndo]
            │    ├─ Paso 1: push_clips_right()       → hace espacio en el timeline
            │    ├─ Paso 2: import_item_to_bin()
            │    │           bin_item.setColor()
            │    │           place_clip_in_timeline()
            │    ├─ Paso 3: stretch_burnin()         → extiende BurnIn hasta el último frame
            │    └─ Paso 4: seq.setInTime/setOutTime → In/Out del timeline al rango del shot
            ├─ [fuera del bloque de undo — solo UI]
            │    └─ Paso 5: set_viewer_to_shot()     → playhead a TC IN + zoom con contexto
            └─ self.accept()
```

---

## Recolección de ítems

```python
# items_by_track: {track_name: [(item_dict, hex_color), ...]}
```

Para cada fila chequeada con track asignado:
- Se obtiene `row_data` de `_table_rows[row]`
- Se extrae `item = row_data.get("item", {})` y `track` del dropdown
- Se calcula el color con `_item_hiero_color(row_data)` (ver abajo)
- Se almacena la tupla `(item, color)` en `items_by_track[track]`

---

## Color por ítem: `_item_hiero_color`

```python
def _item_hiero_color(self, row_data: dict) -> str:
```

Devuelve el color hex que se aplica al `BinItem` en Hiero. Misma lógica que `_chip_color` en el preview:

| Sección | Color |
|---------|-------|
| `"plates"` | `_CLR_PLATES` = `#42616d` |
| `"refs"` | `_CLR_REFS` = `#aa9e54` |
| `"publish"` / comp | `_CLR_COMP` = `#3381e0` |
| `"publish"` / roto | `_CLR_ROTO` = `#2abf7e` |
| `"publish"` / cleanup | `_CLR_CLEANUP` = `#27c8c3` |
| `"publish"` / dmp | `_CLR_DMP` = `#e08033` |
| Publish v000 | `#474747` (gris oscuro) |

La regla v000: si el track_type es `comp`, `roto` o `cleanup` y el nombre del clip contiene `_v000`, `_v00`, etc. (regex `[._]v0{2,}(?:\b|_|$)`), el color es `#474747`.

---

## Paso 1 — Hacer espacio (`push_clips_right`)

### Cuándo se ejecuta

Solo si `self.frames_to_push > 0`. Este valor lo calcula `_find_insert_frame()` al abrir el diálogo: si el nuevo shot va al final del timeline, no hay nada que empujar.

### Cálculo del rango master de shots existentes

Antes de decidir `insert_frame`, `_find_insert_frame()` usa `_collect_timeline_shots()` para construir una lista de shots existentes. Esa lista no toma el primer clip encontrado como master: agrupa todos los TrackItems con el mismo `item.name()` en todos los video tracks no-BurnIn y calcula:

```python
timeline_in  = min(timelineIn de todos los clips del shot)
timeline_out = max(timelineOut de todos los clips del shot)
```

El master puede estar en cualquier track real (`aPlate`, `bPlate`, `_comp_`, `EditRef`, etc.). Si un track tiene un clip corto u offseteado del mismo shot, ese clip puede contribuir al `timeline_in`, pero no acorta el `timeline_out` cuando otro track llega mas lejos. Cuando el shot nuevo va al final, `insert_frame = timeline_out master + 1`.

### Implementación

`timeline_mod.push_clips_right(seq, from_frame, amount)` → `(moved_count, effective_insert_frame)`:

- Itera todos los `videoTracks()` de la secuencia, **excluyendo** los tracks BurnIn.
- Recolecta dos grupos:
  - **TrackItems** (`track.items()`, excluyendo `EffectTrackItem`) cuyo `tl_out >= from_frame`.
  - **EffectTrackItems** (soft effects, `track.subTrackItems()`) cuyo `tl_out >= from_frame`.
  - Criterio `tl_out >= from_frame`: captura tanto clips que empiezan en `from_frame` o después, como clips que **cruzan** `from_frame` (empiezan antes, terminan después). Estos últimos son los del shot siguiente con inicio desalineado entre tracks.
- Calcula `effective_insert_frame = min(tl_in de los TrackItems seleccionados)` **antes de moverlos**. Este es el frame real donde debe empezar el nuevo shot para quedar adyacente al siguiente sin gap ni overlap.
- Selecciona los **TrackItems** en el Timeline Editor con `hiero.ui.getTimelineEditor(seq).setSelection(items)` (nota: `setSelection` no acepta `EffectTrackItem`).
- Combina TrackItems + EffectTrackItems y los ordena de **derecha a izquierda** (por `timelineIn()` descendente) para evitar colisiones.
- Para cada ítem, mueve:
  ```python
  item.setTimelineOut(item.timelineOut() + amount)  # out primero
  item.setTimelineIn(item.timelineIn()  + amount)   # luego in
  ```
  Se mueve `out` primero para que el clip no colapse si Hiero valida `out >= in`.
- Retorna `(moved_count, effective_insert_frame)` donde `moved_count` cuenta solo TrackItems.

### Por qué `effective_insert_frame` ≠ `self.insert_frame`

`self.insert_frame` se calcula desde el TCIN del clip del shot siguiente en el track más a la derecha (bPlate en el ejemplo). Pero otros tracks pueden tener clips del shot siguiente que empiezan **antes** de ese frame. El `effective_insert_frame` es el mínimo de todos, garantizando que el nuevo clip quede pegado al slot siguiente sin importar qué track lo define.

Ejemplo:
- `insert_frame` = 548 (desde bPlate)
- `_comp_` y `aPlate` del shot siguiente empiezan en 480
- `effective_insert_frame` = 480
- Después del push de 484f: _comp_/aPlate del shot sig. quedan en 964
- Nuevo clip: 480–963 → adyacente ✓

### Tracks BurnIn

Se **excluyen** del push. Se estiran por separado con `stretch_burnin()` (pendiente de implementar en el flujo de import generalizado).

---

## Paso 2 — Import al bin, color y colocación en timeline

### Bin destino

```
clipsBin / F <seq_name> / <shot_name>
```

`bin_mod.find_or_create_shot_bin(seq, shot_name)` busca o crea la estructura.

### Import al bin

`bin_mod.import_item_to_bin(item, target_bin)` → `(clip, error_str)`:
- `kind == "exr_seq"` → `hiero.core.Clip(str(item["first_file"]))` — Hiero detecta la secuencia completa automáticamente desde el primer frame.
- `kind == "mov"` → `hiero.core.Clip(str(item["path"]))`
- Llama `clip.setName(name)`, crea `hiero.core.BinItem(clip)` y lo agrega al bin.
- Llama `clip.rescan()` y loguea el rango detectado.
- Los publish items tienen `kind="exr_seq"` garantizado por `_scan_publish_folders`.

### Color del BinItem

Inmediatamente después de importar al bin, se colorea el `BinItem`:

```python
bin_item = clip.binItem()
bin_item.setColor(QtGui.QColor(clip_color))
```

Donde `clip_color` es el hex calculado por `_item_hiero_color()` al momento de la recolección. Esto hace que el clip aparezca con el mismo color que el chip del preview tanto en el bin como en el timeline.

### `frame_count` por ítem

En este orden:
1. `item.get("frame_count")` — campo que setea `_scan_input_folder` / `_scan_publish_folders`.
2. Fallback: `clip.mediaSource().duration()` (después del rescan, Hiero tiene el rango real).

### Colocación en timeline

`timeline_mod.place_clip_in_timeline(seq, clip, track_name, tl_in, frame_count, shot_name)`:
- Busca el track por nombre con `_find_video_track(seq, track_name)`. Cuando existen varios tracks con el mismo nombre, siempre se usa el **más alto visualmente** (iteración top-to-bottom via `reversed(seq.videoTracks())`). Si no existe ninguno, retorna error.
- `tl_out = tl_in + frame_count - 1`
- Llama `track.addTrackItem(clip, tl_in)`.
- Ajusta: `track_item.setTimes(tl_in, tl_out, 0, frame_count - 1)`
- Finalmente: `track_item.setVersionLinkedToBin(True)`.
- `tl_in` = `effective_insert_frame` para plates/publish; `effective_insert_frame + handle_in` para editrefs.

### Handle offset para editrefs

Antes de llamar a `place_clip_in_timeline`, si el track es de tipo `editref` y `self._handle_info` tiene datos para ese track, se suma `handle_info["handle_in"]` al `effective_insert_frame`:

```python
clip_tl_in = effective_insert_frame
if classify_track_type(track_name) == "editref":
    handle_info = self._handle_info.get(track_name)
    if handle_info:
        clip_tl_in += handle_info["handle_in"]
```

`_handle_info` lo calcula `_update_import_page()` justo antes de construir el preview. Ver documentación en `LGA_import_shots_preview.md — Handle automático para EditRef`.

---

## Bloque de undo

Se usa `with project.beginUndo("Import Shot: <shot_name>"):` envolviendo toda la operación (push + import al bin + colocación en timeline). El patrón `with` es el correcto en la API de Hiero: garantiza que el bloque se abre y se cierra como un único paso de undo, sin importar si ocurren excepciones.

---

## Manejo de errores

Los errores de bin o timeline se acumulan en una lista `errors`. Al finalizar:
- Si hay errores: `QMessageBox.warning` con la lista.
- Si todo OK: log con `debug_print`.

En ambos casos se llama `self.accept()` para cerrar el diálogo.

---

## Colocación en timeline — políticas

| Política | Detalle |
|----------|---------|
| `tl_in` plates/publish | `effective_insert_frame` (min tl_in de los clips empujados) |
| `tl_in` editrefs | `effective_insert_frame + handle_in` (handle calculado automáticamente) |
| Source in/out | Siempre `0 .. frame_count-1`. Los EXR físicos empiezan en `1001`; Hiero mapea internamente. |
| `setVersionLinkedToBin(True)` | Solo después de que el TrackItem ya está insertado y sus tiempos ajustados. |
| Track no encontrado | Error por clip, continua con los demás. No crea tracks automáticamente. |
| Nombre del TrackItem | `shot_name` (solo el código del shot). |

---

## Paso 3 — Estirar BurnIn (`stretch_burnin`)

Se ejecuta al final del import, solo si al menos un clip fue colocado exitosamente.

`timeline_mod.stretch_burnin(seq)`:

- Localiza el track BurnIn por nombre normalizado (`burnin`, `burn in`, `burn_in`).
- Recolecta los **soft effects** (`EffectTrackItem`) vía `track.subTrackItems()` — NO `track.items()`.
- Calcula `target_out = max(timelineOut)` de todos los clips reales del timeline (excluye `EffectTrackItem`).
- Para cada efecto: si su `timelineOut` ≠ `target_out`, llama `effect.setTimelineOut(target_out)`.
- Loguea cuántos efectos fueron ajustados.

Patrón idéntico al de `LGA_NKS_BurnIn_Extend_To_LastVisible.py` (Building Blocks).

---

## Post-import — In/Out del timeline (PASO 4, dentro del undo)

Al final de `_run_import()`, **dentro del bloque `with beginUndo`**, se establecen los puntos In/Out de la secuencia al rango exacto del shot recién importado.

`tc_in` y `tc_out` se calculan como el mínimo `timelineIn()` y el máximo `timelineOut()` de los `valid_items` (clips con `parentTrack() != None`). Esto excluye los TrackItems desplazados por versiones posteriores del mismo slot, que quedan con `parentTrack() == None`.

```python
valid_items = [ti for ti in placed_items if ti.parentTrack() is not None]
tc_in  = min(int(ti.timelineIn())  for ti in valid_items)
tc_out = max(int(ti.timelineOut()) for ti in valid_items)
self.seq.setInTime(tc_in)
self.seq.setOutTime(tc_out)
```

Los valores `tc_in` / `tc_out` también se guardan en variables `nonlocal` (`_view_tc_in`, `_view_tc_out`) para que el PASO 5, que se ejecuta fuera del bloque de undo, no tenga que recalcularlos.

**Por qué dentro del bloque de undo:** `setInTime` / `setOutTime` modifican el modelo de la secuencia. Al incluirlos en el undo, un Ctrl+Z revierte el import completo, incluyendo el cambio de In/Out.

---

## Post-import — Vista del timeline (`set_viewer_to_shot`, PASO 5)

Al final de `_do_import()`, **fuera del bloque `with beginUndo`**, se ajusta la vista del timeline con las coordenadas `_view_tc_in` / `_view_tc_out` calculadas en el PASO 4.

`timeline_mod.set_viewer_to_shot(seq, tc_in, tc_out)` ejecuta tres operaciones de UI pura (no undoables):

### 1. Deseleccionar todos los clips

```python
te = hiero.ui.getTimelineEditor(seq)
te.selectNone()
```

Limpia cualquier selección que haya quedado de operaciones anteriores (por ejemplo, `push_clips_right` selecciona los clips que empuja).

### 2. Playhead al TC IN

```python
viewer = hiero.ui.currentViewer()
viewer.setTime(tc_in)
```

### 3. Zoom con contexto lateral

Se usa la misma técnica que `ajustar_vista_al_clip` de `LGA_NKS_PrevNext_Rev.py`, pero con padding para que los shots vecinos sean visibles:

```
pad = shot_dur // 2   # 50 % del shot en cada lado → el shot ocupa ~50 % de la vista
```

Secuencia:
1. Activar y enfocar la ventana del timeline (`window.activateWindow`, `window.setFocus`).
2. Poner temporalmente `seq.setInTime(tc_in - pad)` / `seq.setOutTime(tc_out + pad)`.
3. `QTimer.singleShot(50ms, _zoom_and_restore)` — espera a que el diálogo se cierre y el timeline recupere el foco.
4. `_zoom_and_restore`: dispara `hiero.ui.findMenuAction("Zoom to Fit").trigger()` y luego restaura el In/Out exacto `tc_in` / `tc_out`.

El resultado: "Zoom to Fit" encaja el rango ampliado (shot + 50% a cada lado), mostrando el shot a ~50% del ancho visible con shots vecinos a la vista. El In/Out restaurado queda con los valores exactos del shot.

**Por qué fuera del bloque de undo:** `viewer.setTime` y las operaciones de zoom son estado puro de UI/viewer. No deben ser undoables.

### Referencia de implementación

| Función en PrevNext_Rev.py | Equivalente aquí |
|---------------------------|------------------|
| `timeline_editor.selectNone()` | `te.selectNone()` |
| `set_in_out_from_clip(clip)` | `seq.setInTime/setOutTime` en PASO 4 (dentro del undo) |
| `move_playhead_to_position(pos)` | `viewer.setTime(tc_in)` |
| `ajustar_vista_al_clip()` | activar ventana + `QTimer` + `Zoom to Fit` + restaurar In/Out |

---

## Versioning de ítems (EXR seqs y MOVs)

### EXR sequences

`_scan_input_folder` agrupa las carpetas por `base_key` (nombre sin `_vNN`). Dentro de cada grupo, la entrada con el `version_num` más alto tiene `is_latest=True`; las demás tienen `is_latest=False`.

### MOV files

El mismo patrón se aplica a los MOV sueltos de `_input/`. Se agrupan en `mov_groups` con estas claves:

| Tipo de track | Clave de agrupación |
|---------------|---------------------|
| Track nombrado (EditRef, EditRefClean, aPlate, …) | `"track:<track_name>"` |
| Track None (seqref) o desconocido (`"?"`) | `"name:<base_sin_version>"` |

Regla de `is_latest` dentro de cada grupo:
- Si el grupo tiene versiones (`version_num != -1`): solo la de mayor `version_num` tiene `is_latest=True`.
- Si ningún archivo tiene versión (`max_ver == -1`): todos tienen `is_latest=True` (no hay versioning real).

Ejemplo:
- `editref_v001.mov` → `is_latest=False`
- `editref_v002.mov` → `is_latest=True`
- `editref.mov` + `editrefclean.mov` → ambos `is_latest=True` (tracks distintos)

### Checkbox inicial

El checkbox de cada fila de la tabla se inicializa con `chk.setChecked(is_latest)`. Las versiones no-latest aparecen desmarcadas por defecto, pero son visibles para referencia.

---

## Combo de track — tracks existentes + opción "Crear"

### Fuente de opciones

`_build_track_combo()` ya **no** usa una lista hardcodeada. Las opciones son:

1. `"— sin track —"` (siempre primero)
2. Tracks de video existentes en `self.seq`, en orden visual top-to-bottom (excluyendo BurnIn), obtenidos por `_get_seq_track_names()`. Los nombres duplicados se deduplican: si el timeline tiene dos tracks llamados "EditRef", el dropdown solo muestra "EditRef" una vez.
3. `"+ Crear track <name>"` (solo al final, solo si el track auto-detectado del ítem es un `*Plate` y todavía no existe en el timeline).

La opción "?" fue eliminada. Los ítems que antes recibían `track="?"` ahora muestran `"— sin track —"` como valor inicial.

### Selección inicial

- Si el track auto-detectado existe en el timeline → se pre-selecciona.
- Si no existe y es un plate → se pre-selecciona `"+ Crear track <name>"` (con `blockSignals=True`, sin crear nada todavía).
- En cualquier otro caso → `"— sin track —"`.

### Conflicto entre ítems del mismo track

Cuando dos ítems quieren el mismo track al cargar la tabla:

| Situación | Resultado |
|-----------|-----------|
| EXR actual vs MOV existente | EXR gana, MOV queda en `"— sin track —"` |
| MOV actual vs EXR existente | MOV cede, queda en `"— sin track —"` |
| Mismo tipo, `version_num` actual > existente | Actual gana, existente queda en `"— sin track —"` |
| Mismo tipo, `version_num` actual ≤ existente | Actual cede, queda en `"— sin track —"` |

### Creación de track desde el combo

Cuando el usuario elige `"+ Crear track <name>"` manualmente (señal `currentTextChanged`):
1. `_on_track_combo_changed` detecta el prefijo `_CREATE_TRACK_PREFIX`.
2. Llama `_create_plate_track(track_name)` dentro de un `with project.beginUndo(...)`.
3. `_create_plate_track` crea `hiero.core.VideoTrack(track_name)`, calcula la posición de inserción usando `_IMPORT_TRACK_ORDER` (bottom-to-top), y re-agrega todos los tracks en orden correcto.
4. Llama `_refresh_track_combo_options(created_track_name)` para actualizar las opciones de **todos** los combos y seleccionar automáticamente el track recién creado en el combo actual.

### `_IMPORT_TRACK_ORDER`

Constante de módulo que define el orden canónico bottom-to-top (index 0 = fondo del stack):

```
aPlate, bPlate, cPlate, dPlate, ePlate, fgPlate, bgPlate,
EditRef, EditRefClean, _comp_, _roto_, _cleanup_, _dmp_
```

BurnIn no figura en la lista (se trata como índice infinito, siempre en el tope).

---

## Pendiente

- **Post-import — SetShotName:** llamar `LGA_NKS_SetShotName` para renombrar los clips.
- **Post-import — CreateV000:** dialogo para crear v000 en tasks sin versiones.

---

## Referencias técnicas

| Archivo | Funciones / clases clave |
|---------|--------------------------|
| `LGA_NKS_Edit_Panel_py/LGA_import_shots.py` | `ImportShotDialog._do_import()`, `_item_hiero_color()`, `_item_section_color()`, `_chip_color()`, `_find_insert_frame()`, `_collect_timeline_shots()`, `_scan_input_folder()`, `_build_track_combo()`, `_get_seq_track_names()`, `_create_plate_track()`, `_refresh_track_combo_options()`, `_on_track_combo_changed()`, `_get_track_for_row()`, `_populate_data_row()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_timeline.py` | `push_clips_right()`, `place_clip_in_timeline()`, `stretch_burnin()`, `set_viewer_to_shot()`, `_zoom_and_restore()`, `_find_video_track()`, `_get_last_timeline_out()`, `_is_burnin_track()`, `set_debug_print()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_bin.py` | `find_or_create_shot_bin()`, `import_item_to_bin()`, `set_debug_print()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.md` | Documentación de la página de preview que precede al import |
| `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_PrevNext_Rev.py` | Referencia del patrón view: `set_in_out_from_clip`, `move_playhead_to_position`, `ajustar_vista_al_clip` (activar ventana + QTimer + Zoom to Fit) |
| `+Building_Blocks/Hiero/Timeline/LGA_H-SelectFromPlayhead.py` | Referencia del patrón `setTimelineOut/setTimelineIn` para mover clips |
| `LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py` | Referencia del flujo: `_import_v000_to_bin`, `_set_v000_clip_color`, `bin_item.setColor()` |
| `+Building_Blocks/LGA_NKS_BurnIn_Extend_To_LastVisible.py` | Referencia del patrón `stretch_burnin`: `get_burnin_effects()` via `subTrackItems()`, `get_last_visible_clip()`, `effect.setTimelineOut()` |
| `LGA_NKS_Edit_Panel_py/LGA_NKS_OrganizeProject.py` | Estructura de bins `F <seq_name>/<shot_name>` |
