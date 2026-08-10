> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios.

# LGA_import_shots — Rename

Documentacion especifica de la sub-vista `Rename` del dialogo de Import Shot.

## Objetivo

Permitir renombrado masivo con preview en vivo, de forma segura y modular.

- Aplica sobre todos los items detectados (input y publish), **independientemente** de lo marcado en el tab Import.
- Todos los items aparecen chequeados por defecto al abrir el tab.
- En secuencias EXR, renombra la secuencia y su carpeta contenedora.
- Bloquea automaticamente casos inseguros (mismatch de carpeta/secuencia, conflictos de destino).

## Archivos involucrados

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots.py`
  - `ImportShotDialog._build_page_rename()`
  - `ImportShotDialog._update_rename_page()`
  - `ImportShotDialog._refresh_rename_preview()`
  - `ImportShotDialog._run_rename()`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots_rename.py`
  - `build_selected_rows()`
  - `compute_preview()`
  - `build_row_ops_for_ui()` (liviana, para preview/colisiones)
  - `build_row_ops()` (pesada, para ejecutar)
  - `execute_ops()`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots_rename_settings.py`
  - `load_settings()`
  - `save_settings()`
  - `get_settings_path()`
  - `load_rename_presets()`
  - `save_rename_presets()`
  - `show_save_rename_preset_dialog()`
  - constante `PRESET_FIELDS`

## Tabla de preview

### Secciones

La tabla está organizada en **secciones** igual que el tab Import, con el mismo sistema
de cabeceras de color. Solo se muestran las secciones que tienen ítems detectados:

| Sección | Color barra | Texto header | Condición |
|---------|-------------|--------------|-----------|
| PUBLISH | gradiente comp→roto→cleanup | gradiente | items de `source = "publish"` |
| PLATES | `#42616d` azul petróleo | `#6fc9d9` celeste (= tabla principal) | items de `source = "plates"` |
| REFERENCES | `#aa9e54` dorado | `#aa9e54` dorado | items de `source = "refs"` |

La barra de color de cada fila de dato usa el color de la tarea (para publish) o el color de
sección (para plates/references). Para publish: comp=`#3381e0`, roto=`#2abf7e`,
cleanup=`#27c8c3`, dmp=`#e08033`. La barra nunca se grisea aunque la fila esté bloqueada.

### Columnas

| Col | Header | Ancho inicial | Resize | Notas |
|-----|--------|---------------|--------|-------|
| 0 | (barra color) | 10 px | Fixed | |
| 1 | (checkbox) | 28 px | Fixed | |
| 2 | `Original` | 300 px | Interactive | |
| 3 | `→` | 24 px | Fixed | |
| 4 | `Renamed` | 300 px | Interactive | vacío/`—` si checkbox off |
| 5 | `Folder Original` | 210 px | Interactive | |
| 6 | `Folder Renamed` | 210 px | Interactive | vacío/`—` si checkbox off |
| 7 | `Estado` | 220 px | Interactive | alineado a la izquierda |

Todas las columnas de contenido (2, 4, 5, 6, 7) son **resizables** por el usuario.

### Comportamiento de cols según checkbox

Los colores de preview (original y renamed) solo se muestran para filas con checkbox activo.
Filas bloqueadas (mismatch, conflicto) y filas desactivadas por el usuario muestran siempre
texto plano `#a7a7a7`, sin ningún resaltado de cambio.

| Condición | Original (2) | Folder Orig (5) | Renamed (4) | Folder Renamed (6) | Estado (7) |
|-----------|-------------|-----------------|-------------|-------------------|------------|
| Activo, con cambios | coloreado | coloreado | preview coloreado | preview coloreado | `Pendiente` cian |
| Activo, sin cambios | nombre igual | folder igual | nombre igual | folder igual | `Sin cambios` gris |
| Desactivado por usuario | plano `#a7a7a7` | plano `#a7a7a7` | `—` `#444444` | `—` `#444444` | `—` `#444444` |
| Bloqueado (mismatch, conflicto) | plano `#a7a7a7` | plano `#a7a7a7` | `—` `#444444` | `—` `#444444` | warning rojo |

La **barra de color** (col 0) siempre usa el color de sección/tarea, independientemente de
si la fila está bloqueada o desactivada.

La actualización de cols 2, 4, 5, 6, 7 es en vivo (sin recalcular el preview completo)
mediante `_on_rename_chk_changed(row_i)`.

### Estructura interna: display rows

La tabla usa `_rename_display_rows` (lista de dicts) que mezcla filas de sección y filas de
dato, igual que `_table_rows` en la tabla principal:

```
{"type": "section_header", "label": "PLATES", "color": "#42616d", "source": "plates"}
{"type": "data", "preview_row": <dict de compute_preview>}
```

`_rename_checkboxes` y los handlers de click usan el índice de display row (no de preview row).
Las filas de tipo `section_header` son ignoradas en los handlers de click/doble-click y en
`_update_rename_btn_state()` / `_run_rename()`.
Shift+click en una fila de datos o en su checkbox deja checked solo esa fila y deselecciona
las demas filas habilitadas.

Para secuencias EXR se muestra una sola entrada con placeholder de padding:

- `nombre_####.exr`
- `nombre.####.exr`

La cantidad de `#` refleja el padding real en origen y el calculado en destino.

## Pipeline secuencial (4 etapas)

El preview aplica estas etapas en orden:

1. Search/Replace 1 (`case_sensitive` opcional) — botón ⇄ intercambia Search y Replace
2. Search/Replace 2 (`case_sensitive` opcional) — botón ⇄ intercambia Search y Replace
3. Delimiter antes del frame (`_` o `.`)
4. Padding de frames (spinbox) — respeta el mínimo de dígitos necesario por secuencia

Cada etapa tiene color propio, reutilizando la paleta ya existente de transcode:

- etapa 1: `_CLR_COMP_DWAA` (verde suave) — se eligió verde para no chocar con el amarillo de la etapa 4
- etapa 2: `_CLR_PAR` (rosa)
- etapa 3: `_CLR_COMP` (azul comp publish)
- etapa 4: `_CLR_FRAMES` (ámbar cálido)

## Layout de opciones (3 columnas)

`opts_row` se divide en dos mitades con stretch=1 cada una para que la columna 1 conserve
exactamente el ancho que tenía antes de existir las columnas 2 y 3 (~50% del ancho de la ventana):

- **Mitad izquierda** = `col_left` (stretch 1): `Search & Replace 1` + `Search & Replace 2`.
- **Mitad derecha** = `right_wrap` (QHBoxLayout con stretch 1 dentro de `opts_row`), que contiene en orden:
  - `addSpacing(30)` — espacio libre entre `col_left` y el separador vertical.
  - **Separador vertical** entre col 1 y col 2.
  - `addSpacing(20)` — separación entre el separador y el contenido de la columna 2.
  - **Columna 2** = `col_pref_suf` (stretch 1 dentro de `right_wrap`): `Prefix` + `Suffix`.
  - **Columna 3** = `col_right` (stretch 1 dentro de `right_wrap`): `Delimiter` + `Frame Number Digit`.
  - `addSpacing(100)` para separar la columna 3 de la columna 2.
  - Separador vertical.
  - `addSpacing(20)` — separación entre el separador y el contenido de la columna 3.
  - **Columna 3** = `col_extra` (stretch 0, `setSpacing(12)` para más aire entre filas).
    Contiene en orden:
    1. Fila `Preset:` + `_rename_preset_combo` (dropdown con presets).
    2. Botón `Save Preset` con estilo `_BTN_SMALL`.
    3. Botón `Reset Values` con estilo `_BTN_SMALL`

Anchos actuales:

- `opts_row` distribuye `col_left:right_wrap` con stretch `3:5` para restar ancho a Search & Replace y darselo al bloque derecho.
- Dentro de `right_wrap`, `Prefix/Suffix:Delimiter/Digits` usa stretch `2:1`.
- Las filas de `Prefix` y `Suffix` agregan `addSpacing(20)` a la derecha para igualar el padding visual de las otras columnas sin cambiar el ancho total.
- Las filas de `Delimiter` y `Frame Number Digit` tambien agregan `addSpacing(20)` a la derecha.
- El espacio libre a la derecha de Preset es `_RENAME_COL3_RIGHT_PADDING = 20`.
       (mismo estilo que `Select All` / `Clear` / `Plates` del tab Import).
  - `addSpacing(_RENAME_COL3_RIGHT_PADDING)` (variable local marcada con `✅✅` en el código)
    para dejar un margen libre a la derecha y que la columna 3 no quede pegada al borde
    derecho de la ventana.

## Presets de rename

El dropdown `Preset:` permite guardar y aplicar combinaciones completas de los 6 steps.

### Persistencia

Los presets viven en el mismo INI de rename (`%APPDATA%\LGA\HieroTools\ImportShotsRename.ini`),
en secciones `[RenamePreset_0]`, `[RenamePreset_1]`, ... Cada sección tiene los campos:

- `name` — nombre visible en el combo.
- `sr1_search`, `sr1_replace`, `sr1_case` — Search & Replace 1.
- `sr2_search`, `sr2_replace`, `sr2_case` — Search & Replace 2.
- `prefix` — Prefix.
- `suffix` — Suffix.
- `delim` — Delimiter (`_` o `.`).
- `digits` — Frame Number Digit (string del int).

Funciones nuevas en `LGA_import_shots_rename_settings.py`:

- `load_rename_presets()` — devuelve `list[dict]`.
- `save_rename_presets(presets)` — sobrescribe todas las secciones `[RenamePreset_N]`.
- `show_save_rename_preset_dialog(parent=None)` — diálogo modal con título "Guardar preset
  de rename", barra divisoria, campo de texto y botones Cancelar/Guardar. Devuelve el nombre
  o `None`. Estilo idéntico al de `show_save_preset_dialog` de transcode pero **sin** la
  línea `WxH`.
- Constante `PRESET_FIELDS` con los nombres de los 8 campos persistidos.

### UI del combo

Reusa por completo el patrón del combo `Destino:` de Transcode:

- `_RenamePresetListView(_ResPresetListView)` y
  `_RenamePresetDelegate(_ResPresetDelegate)` — sólo overridean `_is_deletable(text)` para
  que TODOS los items sean deletables (con trash icon hover/click) excepto los placeholders
  virtuales `----` y `(sin presets)`.
- `_pix_trash` y `_pix_hover` reusan los mismos SVG en `LGA_NKS_Shared/icons/`.

### Estados del dropdown

- **Sin presets guardados**: el combo contiene un único item `(sin presets)` y está
  deshabilitado (`setEnabled(False)`), no se puede abrir.
- **Con presets**: el combo lista siempre el item virtual `----` en la posición 0 (no
  deletable, elegirlo desde el combo no hace nada) seguido de todos los presets reales.
  En cada cambio de los 6 steps se evalúa el match contra todos los presets; si alguno
  coincide exactamente queda seleccionado, sino se selecciona `----`.

### Comparación de match

`_preset_matches_current(preset)` compara campo a campo los 8 valores de `PRESET_FIELDS`
contra el snapshot actual (`_current_rename_preset_dict()`). La comparación es exacta de
strings (incluyendo `case_sensitive` como `"true"`/`"false"` y `digits` como string del int).
La búsqueda es lineal sobre la lista de presets — barata porque son pocos campos cortos.

### Aplicar un preset

`_on_rename_preset_combo_changed(idx)` → `_apply_rename_preset(preset)`:

- Setea los 8 widgets desde el preset.
- Cada `setText` / `setChecked` / `setCurrentIndex` / `setValue` dispara su señal, que está
  conectada a `_on_rename_settings_changed` (autosave + reinicio del timer de debounce
  + recálculo de la selección del combo).
- Se usa la bandera `self._rename_applying_preset = True` durante el apply para que
  `_on_rename_settings_changed` NO recalcule el combo en cada uno de los setteos
  intermedios mientras estamos cargando el preset.

### Guardar un preset

`_on_rename_save_preset_clicked()`:

1. Abre `show_save_rename_preset_dialog`.
2. Si el usuario confirma, arma el dict con `name` + snapshot de los 8 campos actuales.
3. Hace append a `self._rename_presets` y `save_rename_presets`.
4. Reconstruye el combo con `_rebuild_rename_preset_combo(force_select=N-1)` para dejar
   seleccionado el preset recién guardado.

### Borrar un preset

El trash icon dispara `_on_rename_preset_delete(row)`:

1. Convierte el row del combo al índice de `self._rename_presets` (los presets reales
   empiezan en row 1 porque el row 0 es `----`).
2. Elimina del INI.
3. `hidePopup()` (mismo patrón que el combo de transcode, para que Qt recalcule el alto
   del desplegable sin filas vacías).
4. `_rebuild_rename_preset_combo()` reconstruye el combo dejando `----` seleccionado
   (o `(sin presets)` si quedó vacío).
5. `_update_rename_preset_combo_selection()` re-evalúa el match contra los presets
   restantes; si el estado actual coincide con uno, lo selecciona.

### Sincronización con cambios manuales

Cada vez que el usuario edita un widget de los 6 steps, `_on_rename_settings_changed` llama
a `_update_rename_preset_combo_selection()` (excepto si está activa la bandera
`_rename_applying_preset`). Ese método busca un preset que matchee el estado actual y
selecciona el item correspondiente en el combo (`match_idx + 1` por el `----` en pos 0), o
selecciona `----` si ninguno matchea. Las señales del combo se bloquean durante el cambio.

### Botón `Reset Values`

Método: `_reset_rename_to_defaults()`.

Acciones:

- Vacía los 4 campos de texto: SR1 Search, SR1 Replace, SR2 Search, SR2 Replace.
- Limpia `Prefix` y `Suffix`.
- Setea el combo de Delimiter en `_`.
- Setea el spinbox de Frame Number Digit en `4`.

Los `case_sensitive` de SR1/SR2 NO se tocan (no son parte del defaults requerido).

Cada `setText` / `setCurrentIndex` / `setValue` dispara la señal correspondiente, que está
conectada a `_on_rename_settings_changed`. Por lo tanto la persistencia en el INI ocurre
automáticamente igual que si el usuario hubiera editado los campos a mano.

## Tab order y foco

El ciclo de Tab en el tab Rename incluye **sólo los 4 line edits** de SR1/SR2:

```
sr1_search → sr1_replace → sr2_search → sr2_replace → (vuelve al primero)
```

Forzado con `QtWidgets.QWidget.setTabOrder(...)` al final de `_build_page_rename`.

Para que los demás widgets no aparezcan en el ciclo ni muestren el rectángulo de foco
amarillo del estilo después de navegar con teclado, se setea `setFocusPolicy(QtCore.Qt.NoFocus)`
en:

- Botones swap `⇄` (SR1 y SR2).
- Checkboxes `Case Sensitive` (SR1 y SR2).
- Combo de Delimiter y spinbox de Frame Number Digit.
- Combo `Preset:` y botones `Save Preset` / `Reset Values`.
- Botón `Run Rename` del footer.

## Botón ⇄ (Swap Search / Replace)

Cada sección SR1 y SR2 tiene un botón pequeño `⇄` entre el campo Search y el Replace.
Al pulsarlo, intercambia el texto de ambos campos (método `_swap_sr(search_edit, replace_edit)`).
El swap dispara `textChanged` en ambos campos, por lo que el preview se actualiza
automáticamente igual que si el usuario hubiera editado manualmente.

## Performance: debounce + ops livianas para el preview

El refresh del preview tiene dos optimizaciones clave para que tipear en los campos de
search/replace sea instantáneo, incluso sobre carpetas en discos de red con cientos de
frames por secuencia.

### Debounce del refresh

`_on_rename_settings_changed` no llama directamente a `_refresh_rename_preview`. En lugar
de eso reinicia un `QTimer` single-shot (`self._rename_refresh_timer`) con intervalo
`_RENAME_REFRESH_DEBOUNCE_MS = 100` (constante a nivel módulo). Cada keystroke reinicia
el timer; el refresh sólo corre cuando el usuario pausa de tipear ese tiempo.

`save_settings` (escritura del INI) y `_mark_rename_preset_dirty` (cambio del combo a `----`)
siguen corriendo síncronamente porque son baratos y necesitamos feedback inmediato del
combo de presets.

`_run_rename` flushea el timer pendiente antes de ejecutar (lo detiene y corre el refresh
manualmente) para garantizar que la tabla refleje el último estado de los settings.

### Ops livianas para colisiones (`build_row_ops_for_ui`)

`_mark_collisions` no llama a `build_row_ops`. Llama a `build_row_ops_for_ui`, que devuelve
hasta 2 ops representativas por fila SIN tocar el disco:

- **No-secuencia**: la op real `(src_file, dst_file)` (que ya era barata).
- **Secuencia EXR**: una op del primer frame (mapeando `item.first_file` a su nombre nuevo)
  + una op del folder rename (sólo si el folder cambia de nombre).

Eso es suficiente para detectar:

- Colisiones entre filas (`claimed_targets` / `planned_src`).
- "Destino ya existe" via `os.path.exists` sobre rutas representativas.

Además se cachea el resultado de `build_row_ops_for_ui` por fila al inicio de
`_mark_collisions` (dict `ops_by_pr_id`), reutilizándolo en las 3 pasadas siguientes (claim,
planned_src, exists check).

**`build_row_ops` original (que sí hace `iterdir()` y produce una op por cada frame del
disco) se sigue usando en `execute_ops`** — al apretar Run Rename necesitamos enumerar y
mover cada archivo, así que ahí se paga ese costo una sola vez.

## Preservación de checkboxes en refresh

Cada vez que `_refresh_rename_preview()` reconstruye la tabla (al cambiar cualquier setting),
se preserva el estado de cada checkbox usando `item_path` como clave de identidad.
El estado inicial del checkbox en la nueva tabla se toma del estado guardado; si el item es
nuevo (no tenía estado previo), se usa el default (`True` para no bloqueados, `False` para
bloqueados).

## Dígitos mínimos por secuencia (Frame Number Digit)

El spinbox de "Frame Digits" fija el padding solicitado por el usuario (`user_digits`), pero
`compute_preview` aplica un `effective_digits` por secuencia:

```
effective_digits = max(user_digits, min_digits_needed)
min_digits_needed = len(str(last_frame))   # frame más alto de la secuencia
```

Ejemplos:

| Secuencia | Frame máx | min_digits | user_digits | effective | Cambio de padding |
|-----------|-----------|------------|-------------|-----------|-------------------|
| seq_####  | 9999      | 4          | 3           | 4         | NO (4 == 4)       |
| seq_####  | 9999      | 4          | 5           | 5         | SÍ (4 → 5)        |
| seq_####### | 98776  | 5          | 3           | 5         | SÍ (7 → 5)        |
| seq_####### | 98776  | 5          | 5           | 5         | SÍ (7 → 5)        |
| seq_####### | 98776  | 5          | 7           | 7         | NO (7 == 7)       |

- Si `effective_digits == original_padding` → Stage 4 no genera cambio; sin color en la tabla.
- El preview muestra `#####` (effective_digits hashes), no los user_digits solicitados.
- `min_digits_needed` se calcula en `build_selected_rows()` a partir de `item["last_frame"]`.
- El preview row almacena `"effective_digits"` y `"user_digits"` para referencia futura.

## Reglas de bloqueo

Una fila queda bloqueada y excluida del rename cuando:

- **Mismatch carpeta/seq**: en secuencias EXR el nombre de carpeta difiere del prefijo.
  - Ejemplo válido: carpeta `TEST_013_030_aPlate_v01` + secuencia `TEST_013_030_aPlate_v01_####.exr`
- **Conflicto de destino**: el destino ya existe en disco Y la fuente (`op.src`) también existe
  (ambas condiciones necesarias; si la fuente ya no existe significa que el rename fue exitoso
  y no hay conflicto real).
- **Destino duplicado en batch**: dos filas del mismo batch apuntan al mismo destino final.

## Ejecucion segura

La ejecucion usa dos fases para minimizar conflictos:

1. Renombra cada origen a nombre temporal unico (`.__rename_tmp_*__`).
2. Renombra temporales a destinos finales.

Incluye rollback basico si falla durante la segunda fase.

## Refresh de la tabla tras rename exitoso

Después de que `execute_ops` completa sin errores, `_run_rename` hace:

1. **Actualiza `self._table_rows`**: recorre todas las filas de la tabla principal y actualiza
   `item["path"]`, `item["name"]` e `item["first_file"]` para los ítems renombrados, usando
   el mapping `old_path → new_path` construido antes de ejecutar.
2. **`_update_rename_page()`**: reconstruye `_rename_selected_rows` desde los ítems actualizados
   (ya sin rutas obsoletas que causarían falsos "Destino ya existe").
3. **`_refresh_rename_preview()`**: reconstruye la tabla de rename con el estado actualizado.
4. **Restaura checkboxes**: por cada checkbox de la tabla de rename que existía antes, si su
   nuevo estado difiere del guardado, lo restaura llamando `chk.setChecked(was_checked)`, lo
   que dispara `_on_rename_chk_changed` y actualiza las celdas visualmente.

Los checkboxes de la **tabla principal** (`self._checkboxes`) no cambian.
Cuando el usuario vuelve a PAGE_MEDIA, `_rename_happened = True` dispara `_refresh_media_page()`
que re-escanea el disco y reconstruye la tabla principal con los nombres actualizados.

## Persistencia de settings

Archivo INI dedicado:

- `%APPDATA%\LGA\HieroTools\ImportShotsRename.ini`

Secciones:

- `[SearchReplace1]`
- `[SearchReplace2]`
- `[Prefix]`
- `[Suffix]`
- `[Delimiter]`
- `[Padding]`

Valores persistidos:

- `search`, `replace`, `case_sensitive` (para SR1/SR2)
- `text` (para Prefix/Suffix)
- `char` (`_` o `.`)
- `digits` (padding)
