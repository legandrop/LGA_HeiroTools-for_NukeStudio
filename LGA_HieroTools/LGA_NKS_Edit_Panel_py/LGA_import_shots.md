> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

> ⚠ **PENDIENTE — Transcode de MOV no implementado**: la pagina
> "Transcode Plates" acepta plates en cualquier formato (EXR o MOV), pero el
> motor de transcode (`TranscodeWorker`) solo procesa EXR sequences via `LGA_EXR_Convert.py`.
> Los plates MOV aparecen en la tabla con checkbox deshabilitado y estado
> "No soportado". Implementar cuando haya herramienta de transcode MOV disponible.

# LGA_import_shots

Herramienta para importar uno o varios shots completos al timeline de Hiero/Nuke Studio.
Analiza la carpeta del shot, detecta plates/editrefs y versiones en publish,
y los coloca automaticamente en el timeline en la posicion alfabeticamente correcta.

## Descripcion

Abre un browser Qt no nativo que permite elegir una o varias carpetas de shot
con Ctrl/Shift. Una carpeta conserva el flujo individual. Varias carpetas abren
el Bulk Import: un tab editable por shot y un tab **Preview** grafico que muestra
el resultado combinado desde el vecino anterior al primer shot nuevo hasta el
vecino siguiente al ultimo. Conserva las barras de color por tipo de track, los
chips coloreados y proporcionales a la duracion, los offsets de EditRef, tooltips
y la representacion grafica de BurnIn del preview individual. Los clips de shots
existentes se muestran desaturados en gris. Los shots existentes o repetidos se omiten y se
informan en la ventana. El batch se ejecuta en orden alfabetico y dentro de un
unico bloque de undo.

En el flujo individual presenta una ventana que siempre abre en el tab **Import**. Por defecto solo se muestra
ese tab. Los tabs **Rename**, **Transcode Plates** y el boton **Open Queue**
estan temporalmente controlados por el flag global `RENAME_TRANSCODE_TABS`,
definido en `False`; no se muestra un checkbox para habilitarlos.

En Bulk Import, el footer muestra solamente `N Shots omitidos`; la lista de
nombres queda disponible en el tooltip. Los tabs usan el ancho natural del
shot name y habilitan botones de scroll cuando el total excede la ventana, sin
recortar los labels ni la palabra `PREVIEW`.

La posicion de insercion en el timeline se calcula automaticamente escaneando
los shots existentes y determinando la posicion alfabeticamente correcta,
sin depender del playhead.

Para cada shot existente, el rango master se calcula agrupando todos los
TrackItems con el mismo `item.name()` en todos los video tracks no-BurnIn. El
TC IN del shot es el menor `timelineIn()` encontrado y el TC OUT es el mayor
`timelineOut()` encontrado. Por eso el master puede venir de un plate, un
editref, un `_comp_` o cualquier otro track real; un clip corto u offseteado en
un track secundario no puede acortar el rango master del shot.

## Archivos principales

- **Script principal:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots.py` (v1.27)
- **Boton:** Edit Panel → "Import shot" (verde `#2a4d3a`)
- **Plan de desarrollo:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\LGA_import_shots_PLAN.md`

### Modulos auxiliares

| Archivo | Contenido | Estado |
|---------|-----------|--------|
| `LGA_import_shots_transcode.py` | `TranscodeWorkerSignals`, `TranscodeWorker`, `build_manifest_for_sequence`, `check_existing_outputs`, `delete_existing_outputs`, `show_overwrite_warning` | **implementado** |
| `LGA_import_shots_transcode_queue.py` | Manager global de cola de transcode. `TranscodeQueueManager`, `get_manager` | Etapas 1, 2 y 3 implementadas y testeadas |
| `LGA_import_shots_settings.py` | Persistencia de settings, UI e INI de presets de resolución. `load_all_settings`, `save_all_settings`, `load_res_presets`, `save_res_presets`, `preset_to_tuple`, `show_save_preset_dialog` | **implementado** |
| `LGA_import_shots_rename.py` | Lógica de preview/validación/ejecución para Rename. `build_selected_rows`, `compute_preview`, `build_row_ops`, `execute_ops` | **implementado** |
| `LGA_import_shots_rename_settings.py` | Persistencia INI dedicada de Rename. `load_settings`, `save_settings`, `get_settings_path` | **implementado** |
| `LGA_import_shots_preview.py` | Lógica de datos del Import Preview. `build_import_preview_data`, `classify_track_type`, `_find_adjacent_clips` | **implementado** |
| `LGA_import_shots_timeline.py` | Helpers de timeline para el import real. `push_clips_right`, `place_clip_in_timeline`, `stretch_burnin`, `set_debug_print` | **implementado** |
| `LGA_import_shots_bin.py` | Helpers de bin para el import real. `find_or_create_shot_bin`, `import_item_to_bin`, `set_debug_print` | **implementado** |
| `LGA_import_shots_bulk.py` | Browser multi-carpeta y simulacion pura del layout final. `pick_shot_folders`, `simulate_bulk_layout` | **implementado** |
| `LGA_import_shots_scan.py` | Helpers de escaneo de carpetas y metadata | pendiente |
| `LGA_import_shots_ui.py` | Estilos CSS, widgets helpers, separadores | pendiente |

### Documentación de secciones

| Sección | MD de referencia |
|---------|-----------------|
| Tab Import — vista preview | [`LGA_import_shots_preview.md`](LGA_import_shots_preview.md) |
| Import Real (`_do_import`) | [`LGA_import_shots_do.md`](LGA_import_shots_do.md) |
| Tab Rename | [`LGA_import_shots_rename.md`](LGA_import_shots_rename.md) |
| Tab Transcode Plates | [`LGA_import_shots_transcode.md`](LGA_import_shots_transcode.md) |
| Cola global de Transcode Plates | [`LGA_import_shots_transcode_queue.md`](LGA_import_shots_transcode_queue.md) |
| Plan de cola global de Transcode Plates | [`LGA_import_shots_transcode_queue_PLAN.md`](LGA_import_shots_transcode_queue_PLAN.md) |
| UI de Open Queue | [`LGA_import_shots_transcode_queue_ui.md`](LGA_import_shots_transcode_queue_ui.md) |

---

## Acceso

La ventana usa decoracion nativa con boton de minimizar habilitado y sin boton de ayuda
contextual `?`. Sigue siendo no modal para permitir trabajar con varias ventanas de
Import Shot abiertas al mismo tiempo.

**Boton del panel:** "Import shot" en el Edit Panel (verde, posicion: antes de "Set Shot Name").

Llama a `main()` al ejecutarse como script externo desde el panel.

### Patrón no-bloqueante

El diálogo usa `show()` en lugar de `exec_()`, igual que `LGA_NKS_CreateV000.py`. Hiero permanece completamente interactivo mientras la ventana está abierta.

Para evitar que el diálogo sea destruido por el garbage collector se usa el patrón singleton:

```python
_import_shot_dialog_instance = None   # módulo global

dlg.finished.connect(_clear_import_dialog)
dlg.destroyed.connect(_clear_import_dialog)
_import_shot_dialog_instance = dlg    # mantiene referencia viva
dlg.show()
```

Cada ventana queda marcada con propiedades Qt (`shot_name` y `shot_root`). Si el usuario elige una carpeta cuyo `shot_name` ya tiene una ventana de Import Shot visible, la herramienta muestra un aviso con estilo propio, trae la ventana existente al frente y aborta la segunda apertura.

---

## Tab Header

**Nombre del conjunto:** "Tab Header" (o "header de tabs"). Cuando se hable de
"la tab bar" en este proyecto, se refiere a **toda la franja superior** que
incluye los tres tabs, el espacio entre el último tab y el corner widget, y el
corner widget con `seq / shotname` a la derecha.

El header **NO usa `QTabWidget`** (probado y descartado: `setCornerWidget` no
respeta `SizePolicy::Expanding`, lo que dejaba el shotname más bajo que los
tabs y con franjas grises arriba). En su lugar es un `QHBoxLayout` plano con
tabs + stretch + shotname como hermanos:

```
QWidget (objectName "LGA_ImportShotHeader")  ← fondo #232323, WA_StyledBackground
└── QHBoxLayout (margins 0, spacing 0)
    ├── QTabBar  ← subclase _ImportShotTabBar (tabSizeHint con +24px para letter-spacing)
    │      tabs: RENAME / TRANSCODE PLATES / IMPORT
    │      RENAME y TRANSCODE PLATES se ocultan si el setting de UI esta apagado
    │      AlignBottom para que las solapas queden pegadas al separador
    ├── stretch
    └── QLabel  ← seq / shotname (AlignVCenter, font-size 16px)
```

Bajo el header hay una línea separadora de 1px implementada con la subclase
`_HeaderSeparator(QWidget)`: pinta la línea en `#4a4a4a` salvo en el rect
horizontal del tab activo, donde pinta `#2b2b2b` (= bg del tab seleccionado
= bg del body) para que el tab "abra" el separador y se conecte visualmente
con la página debajo. La actualización se dispara con
`tab_bar.currentChanged.connect(self.update)`. Debajo del separador va
un `QStackedWidget` (atributo `self._tab_widget` por compatibilidad con código
existente) que aloja las tres páginas. El `QTabBar.currentChanged` está
conectado a `QStackedWidget.setCurrentIndex` y a `_on_tab_changed`.

El padding vertical del header se controla en `QTabBar::tab { padding: ... }`
(actualmente `13px 14px`); el QLabel del shotname se centra verticalmente
dentro de la altura que dictan los tabs.

Detalles técnicos relevantes para tocar el header:

- **`tabSizeHint` ampliado** (`_ImportShotTabBar.EXTRA_WIDTH = 24`) compensa
  el `letter-spacing: 1px` del QSS, que Qt no contempla en su cálculo de ancho
  → sin esto el texto de los tabs se cropea en los extremos.
- **`WA_StyledBackground`** en el wrapper del header: sin este flag, un
  `QWidget` plano no pinta el background definido por stylesheet.
- **Root layout `setContentsMargins(0, 0, 0, 0)`**: margins en cero para que
  el fondo dark del header y la línea separadora lleguen edge-to-edge a los
  bordes izquierdo, derecho y superior del diálogo. El padding lateral de 9px
  se aplica adentro del header (`_hdr_lay`) y en un wrapper del stack
  (`_body` con `setContentsMargins(9, 0, 9, 9)`), de forma que tabs, shotname
  y contenido de páginas queden en su posición visual original.

API de compatibilidad para abrir/cerrar/cambiar tabs desde otros métodos:

- `self._tab_bar.setCurrentIndex(idx)` — cambiar de tab
- `self._tab_bar.setTabEnabled(idx, bool)` — habilitar/deshabilitar tab
- `self._tab_widget` — el `QStackedWidget` con las páginas (sigue el cambio
  de tab automáticamente vía signal)

## Footer global

Todas las secciones principales de la herramienta muestran una fila inferior compartida:

```text
[Open Queue] [Shot Rename and Transcode tabs] [estado global] ... [botones de accion de la seccion]
```

- `Open Queue`: abre o trae al frente la ventana global de cola de transcode.
  Solo se muestra cuando el checkbox **Shot Rename and Transcode tabs** esta activado.
- `Shot Rename and Transcode tabs`: checkbox persistente. Apagado por defecto; cuando
  esta apagado solo se muestra el tab Import y se ocultan Rename, Transcode Plates y Open Queue.
  La UI de esa ventana vive en `LGA_import_shots_transcode_queue_ui.py`; durante desarrollo
  ese modulo se recarga solo si no hay ventanas `Import Shot` ni `Open Queue` visibles.
  La accion para traer todas las ventanas de Import Shot vive dentro de esa ventana, en el
  boton `Show All Import Windows`.
- `estado global`: muestra actividad de la cola global de transcode cuando hay jobs activos
  o pendientes.
- Si hay un shot convirtiendo, el nombre del shot aparece en `SHOTNAME_COLOR` como boton
  plano; al clickearlo trae al frente la ventana de ese shot.

El footer es UI general de `Import Shot`, aunque el estado y `Open Queue` usen datos del
manager global de transcode. Su layout se reutiliza en los tres tabs (Rename, Transcode Plates, Import).

---

## Logging

Usa el sistema de logging dual estandar del proyecto (Sistema A — timer + limpieza por ejecucion).

### Variables de control

```python
DEBUG = True                  # Master switch
DEBUG_CONSOLE = False         # Salida a consola (off por defecto)
DEBUG_LOG = True              # Escritura al archivo .log
Transcode_TEST_Mode = False   # Output a /test_transcode; checkboxes de
                              # originals quedan inertes
```

### Archivo de log

`C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\logs\debugPy_ImportShots.log`

Formato: `[0.123s] mensaje` antes de elegir shot, y `[0.123s] [SHOT] mensaje`
cuando ya existe contexto de shot.

El archivo se borra y recrea con encabezado `Fecha: YYYY-MM-DD HH:MM:SS` solo
cuando no hay otra ventana `Import Shot` visible. Si ya hay ventanas abiertas, la
nueva ejecucion agrega un separador `--- Nueva ventana: ... ---` y continua en el
mismo `.log`, para preservar trazabilidad entre ventanas.

### Funciones del sistema

| Funcion | Descripcion |
|---------|-------------|
| `RelativeTimeFormatter` | Formatter con tiempo relativo desde inicio |
| `setup_debug_logging(script_name)` | Configura `QueueHandler + QueueListener`, `propagate=False` |
| `set_debug_context(context)` | Define prefijo de contexto para logs posteriores (`[SHOT] ...`) |
| `debug_print(*message, level="info")` | Funcion de logging publica, acepta multiples argumentos |
| `cleanup_logging()` | Detiene el listener; registrado con `atexit` |

Logger name: `importshots_logger`

### Como agregar debug prints

Usar `debug_print()` (argumentos variadicos, igual que `print`):

```python
debug_print("=== Iniciando escaneo ===")
debug_print("Shot root:", shot_root, "name:", shot_name)
debug_print("Track no existe:", track_name, level="warning")
debug_print("Error critico:", e, level="error")
```

Puntos clave donde ya hay instrumentacion:
- `main()`: inicio, carpeta elegida, deteccion de duplicado
- `_scan_input_folder()` / `_scan_publish_folders()`: cantidad de items encontrados
- `_find_insert_frame()`: insert_frame, frames_to_push, duracion
- `_push_clips_right()`: frame de insercion y cantidad desplazada
- `_place_clip_in_timeline()`: nombre del clip, track, frame de colocacion
- `_import_clip_to_bin()`: nombre del clip importado al bin
- `_stretch_burnin()`: frame final del burnin
- Errores de movimiento de clips y stretch

---

## Flujo general

```
main()
    |
    ├── hiero.ui.activeSequence()           -> sequence activa
    ├── QFileDialog.getExistingDirectory()  -> shot_root elegido por usuario
    ├── _visible_import_dialog_for_shot()   -> evita dos ventanas abiertas del mismo shot
    ├── _shot_exists_in_timeline()          -> verificacion de duplicado (aborta si existe)
    ├── _scan_input_folder()                -> lista de media en _input/
    ├── _scan_publish_folders()             -> versiones en {Task}/4_publish/
    ├── _find_insert_frame()                -> posicion alfabetica en el timeline
    └── ImportShotDialog(...)               -> ventana abre siempre en Import
            |
            ├── [Tab Rename]           -> todos los items detectados (input + publish)
            │                             todos chequeados por defecto
            │                             preview en vivo + ejecución segura en batch
            │                             tras rename: marca transcode e import para refresh
            ├── [Tab Transcode Plates] -> todos los EXR/MOV de _input/
            │                             todos los EXR chequeados por defecto
            │                             solo EXR convertibles; MOVs = checkbox off/disabled
            │                             durante transcode: tabs Rename e Import deshabilitados
            │                             tras transcode: marca rename e import para refresh
            └── [Tab Import]           -> sub-vista MAIN (tabla de media + quick select)
                    |                     botones: Preview Timeline / Import Now / Import V000
                    ├── [Preview Timeline] -> sub-vista PREVIEW (tabla de chips de timeline)
                    │                         botones: ← Go Back / Import Now / Import V000
                    ├── [Import Now]       -> _do_import() directo sin preview
                    └── [Import V000]      -> _do_import_and_v000() directo sin preview
```

---

## Estructura de carpetas del shot (asumida)

```
T:/VFX-PROYECTO/101/MOR_1012C_010/          <- shot root
│
├── _input/                                  <- nivel raiz del shot
│   ├── MOR_1012C_010_aPlate_v01/            <- subcarpeta por secuencia EXR
│   │   └── MOR_1012C_010_aPlate_v01_1001.exr
│   ├── MOR_1012C_010_EditRefComp_v01.mov    <- editref: va al track EditRef
│   └── MOR_1012C_010_SeqRef_v01.mov         <- seqref: solo al bin, no al timeline
│
├── Comp/
│   └── 4_publish/
│       └── MOR_1012C_010_comp_v00/
└── Roto/
    └── 4_publish/
        └── MOR_1012C_010_roto_v002/
```

---

## Ventana principal — Tabla de media

La tabla esta organizada en **secciones**, no como un file browser plano.
Solo se muestran las secciones que contienen media.

### Orden de secciones (de arriba a abajo)

1. **PUBLISH** — EXR sequences en `{Task}/4_publish/`
2. **PLATES** — EXR sequences en `_input/`
3. **REFERENCES** — MOVs de `_input/` (editref, seqref)

### Sistema de colores por fila

Cada fila tiene una barra de color de 4 px en el borde izquierdo que indica su tipo:

| Tipo | Color |
|------|-------|
| comp (publish) | `#3381e0` azul |
| roto (publish) | `#2abf7e` verde |
| cleanup (publish) | `#27c8c3` cyan |
| dmp (publish) | `#e08033` naranja |
| plates (input EXR/MOV plate) | `#42616d` azul petróleo |
| references (editref/seqref) | `#aa9e54` dorado |

Los mismos colores se usan en los titulos de las secciones.

### Fuentes analizadas

| Carpeta | Contenido | Seccion | Track destino |
|---------|-----------|---------|---------------|
| `{shot}/_input/*/` | Subcarpetas con EXR sequences | PLATES | `aPlate`, `bPlate`, etc. |
| `{shot}/_input/` | `.mov`/`.mxf` con keyword `plate` | PLATES | `aPlate`..`ePlate`/`fgPlate`/`bgPlate` (según nombre; fallback `aPlate`) |
| `{shot}/_input/` | `.mov`/`.mxf` con keyword `editref` | REFERENCES | `EditRef` |
| `{shot}/_input/` | `.mov`/`.mxf` con keyword `seqref` | REFERENCES | *(solo bin)* |
| `{shot}/{Task}/4_publish/` | **Todas** las versiones EXR | PUBLISH | `_{task}_` |

### Comportamiento de la seccion PUBLISH

- Se listan **todas las versiones** encontradas (no solo la mas alta).
- Ordenadas: por task (`comp → roto → cleanup → dmp`), luego por version descendente.
- La version mas alta de cada task aparece primera y con texto mas claro (`#CCCCCC`).
- Versiones anteriores en gris oscuro (`#777777`).

### Comportamiento de checkboxes

- EXR de `_input` con `is_latest=True` → checked por defecto.
- Todo lo demas (publish, versiones anteriores, MOVs) → unchecked por defecto.
- Click en cualquier celda de la fila (excepto la barra de color y el checkbox) togglea el checkbox.
- Shift+click en cualquier fila o checkbox deja checked solo esa fila y deselecciona las demas.

### Coloreado del shotname en la columna Nombre

En la columna Nombre de la tabla, si el nombre del archivo o carpeta comienza con el
`shot_name` (comparación case-sensitive, usando `str.startswith()`), el prefijo coincidente
se colorea con `SHOTNAME_COLOR` (magenta). El resto del nombre mantiene su color base habitual.

- Aplica a **todas las filas**, incluyendo versiones no-latest (en esos casos el magenta
  también se oscurece/aclara proporcionalmente al greyed-out de la fila, igual que
  el resto del texto).
- La columna Nombre pasa de `QTableWidgetItem` plano a `setCellWidget(_cell_html_label(html))`,
  el mismo patrón ya usado en Resolución y Compresión de esta tabla.
- `SHOTNAME_COLOR` se define una sola vez al inicio de `LGA_import_shots.py` con el
  comentario `✅✅` para fácil localización.

### Columnas

| Col | Contenido | Formato / color |
|-----|-----------|-----------------|
| (barra) | Color indicator | 4 px, sin header |
| (checkbox) | Seleccion | 28 px, sin header |
| Nombre | Nombre del clip/version | Prefijo = shotname → `SHOTNAME_COLOR`. Resto = color base de la fila |
| Tipo | `EXR seq`, `MOV`, etc. | — |
| Res | Resolucion + AR | `2048×1152` en gris, `(16:9)` en dorado `#a89060` (muted si row greyed out) |
| FPS | Frames por segundo | `23.976` |
| Compresion | Codec | `dwaa` → verde `#6a9960`, `zip`/`piz` → rojo `#a06060`, resto → gris |
| Frames | Rango y duracion | `1001–1480  (480f - 20.0s)` — count+secs en ámbar `#b09040` |
| Track | Asignacion de track | dropdown editable para inputs (ver detalle abajo), label para publish |

### Dropdown de asignación de track (columna Track)

Aparece únicamente en filas de input (EXR seq y MOV plate/ref). Implementado con
`_ArrowComboBox` + `_TrackComboListView` + `_TrackComboDelegate`.

**Opciones en el dropdown:**

1. `— sin track —` — primera opción; indica que el clip no se importará a ningún track.
2. Tracks existentes en el timeline (sin BurnIn, ordenados visualmente top→bottom).
3. `+ Crear track <name>` — última opción, solo visible si el track auto-detectado es un
   plate track (`aPlate`…`ePlate`, `fgPlate`, `bgPlate`) y **aún no existe** en el timeline.

**Comportamiento del botón "Crear track":**

La opción `+ Crear track <name>` **no es un ítem seleccionable** sino un botón integrado
en el popup del dropdown. Mismo patrón que el ícono 🗑 del combo de resoluciones.

- Click interceptado en el viewport del popup (`_TrackComboListView.eventFilter`).
- Se llama directamente `_on_track_combo_changed(row_id, "+ Crear track <name>")`.
- Evento consumido (`return True`) → el combo **no cambia** su valor actual.
- `_on_track_combo_changed` crea el track en el timeline (con undo) y llama a
  `_refresh_track_combo_options(created_track_name, creator_row=row_id)`.
- El combo del row que inició la creación pasa a mostrar el track recién creado.
- Todos los demás combos se reconstruyen: el nuevo track aparece en su lista de opciones
  y la opción "Crear…" desaparece de los combos que esperaban ese mismo track.

**Posición de inserción del track creado (`_create_plate_track`):**

El nuevo track se inserta en la posición **alfabética correcta dentro de la sección
de plates**, según `_IMPORT_TRACK_ORDER` (bt-order: `aPlate` = fondo del stack,
`_dmp_` = tope del stack; visualmente en el panel: `_dmp_` arriba, `aPlate` abajo).

Ejemplo con `aPlate` y `bPlate` existentes → crear `dPlate`:
- bt-order resultante: `[aPlate, bPlate, dPlate, ...]`
- Visual en el panel (de arriba hacia abajo): `..., dPlate, bPlate, aPlate`
- `dPlate` queda entre `bPlate` y el siguiente track de mayor rango (`ePlate`, `fgPlate`, `EditRef`, etc.)

**Sistema de coordenadas de Hiero:**
- `seq.videoTracks()` devuelve bt-order: índice 0 = fondo del panel, índice mayor = tope.
- `aPlate` tiene el **mayor** trackIndex (está en el tope del panel, arriba de todo).
- `_IMPORT_TRACK_ORDER = ["aPlate", "bPlate", ..., "_dmp_"]` está en orden visual
  **top→bottom** (índice 0 = arriba). Por eso un rank bajo en `_IMPORT_TRACK_ORDER`
  corresponde a un bt-trackIndex **alto** (arriba en el panel).

**Estrategia de inserción — no se re-ordena el stack existente:**

`_create_plate_track` **no cambia el orden de los tracks existentes**. En cambio
busca los *vecinos canónicos* del nuevo track:

- **`lower_idx`**: track con mayor rank en `_IMPORT_TRACK_ORDER` aún `< new_pos`
  (p. ej. `bPlate` para `dPlate`). En Hiero este track tiene **mayor** bt-trackIndex
  que el nuevo → está **encima** del nuevo en el panel. El nuevo track se inserta en
  `insert_at = lower_idx` (ocupa su posición y ese track sube un índice).
- **`upper_idx`**: track con menor rank en `_IMPORT_TRACK_ORDER` aún `> new_pos`
  (p. ej. `EditRef` para `dPlate`). Tiene menor bt-trackIndex → está **debajo** del
  nuevo. Se usa como fallback cuando no hay `lower_idx`.

Esto garantiza que el nuevo track se coloca correctamente sin alterar el orden de los
demás. La lógica sigue el patrón de `LGA_H-Tracks-InsertTest.py`:
`insert_at = ref_track.trackIndex()` donde `ref_track` es el track encima del cual
se inserta.

El log confirma la inserción con: `"creado entre '<lower>' (abajo) y '<upper>' (arriba)  insert_at=N"`.

Cada plate tiene su propia opción de creación independiente. Si hay un `dPlate` y un
`ePlate` sin track, cada uno muestra `+ Crear track dPlate` y `+ Crear track ePlate`
respectivamente.

**Estilo visual:**

- La opción `+ Crear track …` se pinta con fondo verde oscuro (`#1a2a1a`) y texto verde
  suave (`#7aba7a`), diferenciándola de las opciones normales.
- En hover el fondo se aclara a `#253525`.
- El combo cerrado siempre muestra `— sin track —` cuando el track no existe (nunca muestra
  el texto "Crear track").

**Selección inicial:**

- Track auto-detectado existe en timeline → combo muestra ese track.
- Track auto-detectado no existe (hay opción "Crear…") → combo muestra `— sin track —`.
- Track `"?"` o sin detectar → `— sin track —`.

**Resolución de conflictos (un solo clip por track):**

- EXR desplaza a MOV existente en el mismo track.
- MOV cede ante EXR existente.
- Mismo tipo: gana la versión más alta; en empate gana el primero en cargarse.

### Deteccion de track por nombre de carpeta (case-insensitive)

| Keyword | Track |
|---------|-------|
| `seqref` | *(solo bin)* |
| `editrefclean` | `EditRefClean` |
| `editref` | `EditRef` |
| `fgplate` | `fgPlate` |
| `bgplate` | `bgPlate` |
| `aplate` | `aPlate` |
| `bplate` | `bPlate` |
| `cplate` | `cPlate` |
| `dplate` | `dPlate` |

Fallback: EXR sin coincidencia se asignan alfabeticamente (`aPlate`, `bPlate`...).
MOV/MXF con `plate` en el nombre se distribuyen en PLATES. MOV/MXF sin coincidencia quedan con track `?` para decisión manual.

### Botones de seleccion rapida

Fila de botones pequenos encima de los botones de accion:

| Boton | Accion |
|-------|--------|
| Select All | marca todos los checkboxes |
| Clear | desmarca todos |
| Plates | marca solo los items de la seccion PLATES |
| References | marca solo los items de la seccion REFERENCES |
| Publish | marca solo los items de la seccion PUBLISH |

### Botones de accion

Los botones de accion operan sobre los items que tienen el checkbox marcado.

| Boton | Color | Habilitado cuando | Accion |
|-------|-------|-------------------|--------|
| Rename | secundario `#3a3a3a` | hay al menos 1 item marcado | abre sub-vista de renombrado |
| Transcode Plates | secundario `#3a3a3a` | hay al menos 1 EXR seq de input marcado | abre sub-vista de conversion |
| Import | primario `#2a4d3a` | hay al menos 1 item marcado | ejecuta import (ver logica abajo) |

> Los botones "Go Back" de todas las sub-vistas (Rename, Convert, Import) no tienen flecha; el texto es simplemente `"Go Back"`. En la sub-vista Convert el boton cambia a `"Transcoding, wait..."` mientras hay jobs activos o en cola, y vuelve a `"Go Back"` al terminar.

#### Botones de la página Import Preview

La página Import Preview (PAGE_IMPORT) tiene sus propios botones de acción:

| Boton | Color | Habilitado cuando | Accion |
|-------|-------|-------------------|--------|
| ← Go Back | secundario | siempre | vuelve a PAGE_MEDIA |
| Import Now | primario violeta `#443a91` | hay al menos 1 ítem con track asignado | ejecuta `_do_import()` |
| Import and Create V000 | primario violeta `#443a91` | hay al menos 1 ítem con track asignado | ejecuta `_do_import_and_v000()` → import + abre CreateV000 al cerrar |

### Logica de Import (comportamiento previsto)

> **Estado actual:** Import cierra el dialogo sin importar nada (stub).

Cuando se implemente:
- **Plates / References:** se importan exactamente los items que tienen checkbox marcado.
- **Publish:** para cada task que tenga al menos una version chequeada, se importa
  **siempre la version mas alta** de esa task, independientemente de cual version
  este chequeada. Esto previene importar accidentalmente una version obsoleta.
- La seleccion de versiones anteriores de publish sirve exclusivamente para Rename o Convert.

---

## Sub-vista Rename

Estilo PowerRename: find/replace con preview en tiempo real sobre los nombres
de los items marcados.

> **Estado actual:** implementado.
> Documentación detallada: `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots_rename.md`

### Coloreado del shotname en la tabla de Rename

Las cuatro columnas de texto (nombre original, nombre renombrado, carpeta original,
carpeta renombrada) aplican `SHOTNAME_COLOR` al prefijo que coincida con el `shot_name`,
con las siguientes reglas:

- **Verificación:** `text.startswith(shot_name)` (case-sensitive). Si coincide, los primeros
  `len(shot_name)` caracteres se colorean con `SHOTNAME_COLOR`.
- **Prioridad S&R sobre magenta:** si alguna regla de Search & Replace afecta a uno o más
  caracteres dentro del prefijo del shotname, esos caracteres conservan el color de S&R
  (que ya tiene un peso visual más fuerte, `font-weight:600`). El magenta del shotname
  actúa como capa base; S&R la sobreescribe posición a posición. El mecanismo exacto:
  se pre-llena el dict `colors_by_index` con `SHOTNAME_COLOR` para las primeras N
  posiciones; luego se mergean los colores de S&R encima (`{**shotname_colors, **sr_colors}`).
- **Columna "original":** el prefijo magenta aplica sobre el nombre original si comienza con shot_name.
- **Columna "renamed":** el prefijo magenta aplica sobre el nombre renombrado si también comienza
  con shot_name (puede que S&R haya cambiado el prefijo — en ese caso S&R tiene prioridad y
  el magenta cede en esas posiciones).
- **Columnas de carpeta:** mismo criterio que las de nombre de archivo.
- **Filas blocked o unchecked:** cuando la fila está bloqueada o desmarcada, el texto se muestra
  en plano (`#a7a7a7`) sin colorear el prefijo del shotname (coherente con que el resto de los
  colores de S&R tampoco se muestran en ese estado).
- **Greyed-out:** igual que en la tabla principal, si la fila estuviera oscurecida, el magenta
  también se oscurece proporcionalmente.

**Implementación:** `shot_name` y `SHOTNAME_COLOR` se pasan como parámetros adicionales a
`compute_preview()` en `LGA_import_shots_rename.py`. No se define la constante de color en
el módulo de rename; se recibe del script principal.

---

## Sub-vista Convert

Ver documentación detallada en [`LGA_import_shots_transcode.md`](LGA_import_shots_transcode.md).

---

## Import real

Ver documentación detallada en [`LGA_import_shots_do.md`](LGA_import_shots_do.md).

---

## Validaciones

| Condicion | Resultado |
|-----------|-----------|
| No hay sequence activa | Warning y salida |
| Usuario cancela el file browser | Salida silenciosa |
| El shot ya existe en el timeline | Error critico, solo opcion Cancelar |
| No hay EXR en `_input/` | `max_frames` fallback a 100, continua |
| Track destino no existe en timeline | Error por clip, continua con los demas |

---

## Constantes relevantes

```python
# Color del shotname en las columnas de nombre de las tres tablas
SHOTNAME_COLOR = "#..."   # ✅✅ cambiar aquí para ajustar el magenta en todas las tablas

# Colores para anotaciones en tabla / dropdowns
# Derivados de la paleta PATH_LEVEL_COLORS, desaturados ~40 %
_CLR_AR            = "#a89060"   # aspect ratio          — dorado suave
_CLR_PAR           = "#c4787a"   # pixel aspect ratio    — rosa suave
_CLR_FRAMES        = "#b09040"   # cantidad de frames    — ámbar cálido
_CLR_COMP_ZIP      = "#a06060"   # compresión zip/piz    — rojo suave
_CLR_COMP_DWAA     = "#6a9960"   # compresión dwaa/dwab  — verde suave
_CLR_STATUS_PENDING  = "#5a9ab5" # estado Pendiente      — cian suave
_CLR_STATUS_DONE     = "#6a9960" # estado Terminado      — verde suave
_CLR_STATUS_ERROR    = "#a06060" # estado Error          — rojo suave
_CLR_STATUS_UPSCALE  = "#a06060" # estado Upscale (bloq) — rojo suave

BURNIN_TRACK_NAMES = {"burnin", "burn in", "burn_in"}

PLATE_KEYWORDS = [
    ("seqref",       None),
    ("editrefclean", "EditRefClean"),
    ("editref",      "EditRef"),
    ("fgplate",      "fgPlate"),
    ("bgplate",      "bgPlate"),
    ("aplate",       "aPlate"),
    ("bplate",       "bPlate"),
    ("cplate",       "cPlate"),
    ("dplate",       "dPlate"),
    ("eplate",       "ePlate"),
]

TASK_FOLDERS = {
    "comp":    ("Comp",    "_comp_"),
    "roto":    ("Roto",    "_roto_"),
    "cleanup": ("Cleanup", "_cleanup_"),
    "dmp":     ("DMP",     "_dmp_"),
}

# Colores de borde izquierdo por tipo de fila (tabla de media)
_CLR_COMP    = "#3381e0"   # comp publish    (= TASK_COLORS["comp"]    en CreateV000)
_CLR_ROTO    = "#2abf7e"   # roto publish    (= TASK_COLORS["roto"]    en CreateV000)
_CLR_CLEANUP = "#27c8c3"   # cleanup publish (= TASK_COLORS["cleanup"] en CreateV000)
_CLR_DMP     = "#e08033"   # dmp publish
_CLR_PLATES  = "#42616d"   # plates input (EXR)
_CLR_REFS    = "#aa9e54"   # references (editref / seqref)
_TASK_ORDER  = {"comp": 0, "roto": 1, "cleanup": 2, "dmp": 3}
```

---

## Estilo de la UI

Basado en `LGA_NKS_CreateV000.py`:

- Fondo: `#2B2B2B`, texto principal: `#CCCCCC`, texto secundario: `#a7a7a7`
- Tablas: fondo `#272727`, borde `#333333`, headers `#999999`
- Boton primario (Import): `#2a4d3a` con borde `#3a7a55`
- Botones secundarios (Rename, Transcode EXR): `#3a3a3a` con borde `#555555`
- Botones pequenos (seleccion): `#2e2e2e` con borde `#444444`, texto `#999999`
- Boton cancelar/volver: `#555555` con borde `#666666`
- Ancho minimo del dialogo: `1300px` (requiere espacio para la tabla de transcode con Origen 400 px + Destino amplio)
- Titulos de seccion de tabla: color de la seccion sobre fondo `#313131`
- Referencias (seqref en bin): texto color `#aa9e54`
- Selection highlight en QSpinBox (custom W/H): `#505060` bg / `#d0d0d0` texto (gris legible, no blanco ni violeta)
- Espacio entre separador horizontal y fila de botones de acción: constante `_BTN_ROW_TOP_SPACING = 15` (px). Aplicado en páginas media y convert. Buscar `# ✅✅` en el código para ajustar.
- Diálogo "Guardar preset": QLineEdit con fondo `#272727` (neutro, coherente con el resto de la app)
- Avisos de duplicado (ventana ya abierta / shot ya existente en timeline): usan `_show_tool_message()` con `QDialog` propio, sin iconos, fondo `#2B2B2B` y botón primario de la tool.

---

## Settings persistentes

Los settings de la sub-vista Convert se guardan en:

| Sistema | Ruta |
|---------|------|
| Windows | `%APPDATA%\LGA\HieroTools\ImportShots.ini` |
| macOS   | `~/Library/Application Support/LGA/HieroTools/ImportShots.ini` |
| Fallback | `~/.config/LGA/HieroTools/ImportShots.ini` |

El módulo `LGA_import_shots_settings.py` es el único responsable de leer y escribir este archivo.

### Secciones del INI

```ini
[Codec]
dwaa = true            ; true = DWAA con compression fija 45
channels = all          ; "all" | "rgb"
filter = lanczos3

[Resolution]
preset_index = 0
custom_w = 2048
custom_h = 1152
keep_ar = true
match_dim = 0           ; 0 = "Match target width", 1 = "Match target height"
deana = false
deana_par = 2.0
even_dims = true        ; true = forzar dimensiones pares (resta 1 px si queda impar)

[Originals]
move = false
delete = false

[UI]
advanced_tabs = false ; false = solo Import y Open Queue oculto
last_shot_directory =  ; ultima carpeta elegida en el browser

[ResPreset_0]
name = Original
special = original

[ResPreset_1]
name = 2K — 2048×1152
w = 2048
h = 1152

[ResPreset_2]
name = UHD — 3840×2160
w = 3840
h = 2160

[ResPreset_3]
name = 4K — 4096×2304
w = 4096
h = 2304

[ResPreset_4]
name = Custom...
special = custom
```

### Flujo de carga / guardado

1. **Apertura de la herramienta:** `load_all_settings()` y `load_res_presets()` se llaman en
   `ImportShotDialog.__init__` **antes** de construir la UI.
   Antes de abrir `QFileDialog`, `main()` carga `ui/last_shot_directory` y la usa como
   carpeta inicial si aun existe. Al confirmar una carpeta, la guarda inmediatamente.
2. **Construccion de la UI:** los widgets se crean con sus defaults internos, luego
   `_load_settings_to_ui()` aplica los valores guardados (sin activar auto-save).
3. **Tabs avanzados:** `ImportShotDialog.__init__` aplica `ui/advanced_tabs` y luego
   fuerza la apertura en el tab Import. Si el setting esta apagado, Rename y Transcode
   Plates quedan ocultos y Open Queue no se muestra en el footer.
4. **Auto-save:** al final de `_build_page_convert` se conecta `_save_all_settings` a
   todas las señales `stateChanged` / `valueChanged` / `currentIndexChanged` de los
   widgets de settings. Cualquier cambio del usuario dispara `save_all_settings()`.
   El checkbox **Shot Rename and Transcode tabs** guarda solo la seccion `ui` con
   `_save_ui_settings()`.
5. **Presets de resolución:** al borrar un preset (`_on_delete_preset`) o guardar uno nuevo
   (`_on_save_preset_clicked`), se llama `save_res_presets()` y se reconstruye el combo
   con `_rebuild_res_combo()`.

### Iconos de la UI

Los iconos SVG para el trash del dropdown de presets viven en:

```
LGA_NKS_Shared/icons/trash.svg        — estado normal
LGA_NKS_Shared/icons/trash_hover.svg  — estado hover
```

---

## Herramientas externas (LGA_NKS_Shared)

Las siguientes tools binarias estan disponibles en `LGA_NKS_Shared/` y se referencian
siempre con rutas **relativas a SHARED_DIR** para que funcionen en cualquier maquina
donde se distribuya la repo.

| Tool | Ruta relativa | Plataforma | Uso |
|------|---------------|------------|-----|
| oiiotool | `OIIO_Win/oiiotool.exe` | Windows | Lectura de metadata EXR (res, compresion) |
| ffprobe | `FFmpeg_Win/bin/ffprobe.exe` | Windows | Lectura de metadata MOV/MXF (res, fps, codec) |

> **Mac/Linux pendiente:** las rutas para macOS y Linux aun no estan implementadas.
> Cuando se agreguen las carpetas `OIIO_Mac/` y `FFmpeg_Mac/` en Shared, hay que
> agregar la rama `elif _OS == "Darwin":` en la seccion de constantes del script.

### Metadata leida

| Columna | EXR (oiiotool) | MOV/MXF (ffprobe) |
|---------|---------------|-------------------|
| Res | `W x H` de la primera linea de `--info -v` | `width` / `height` del video stream |
| FPS | `framesPerSecond` (si el archivo lo tiene embebido) | `r_frame_rate` del video stream |
| Compresion | `compression:` de la salida verbose | `codec_name` del video stream |
| Frames | rango escaneado de la secuencia EXR | `nb_frames` del video stream (fallback: `duration × fps`) |
| Tipo | `EXR seq` | extension real del archivo: `MOV`, `MXF`, `MP4` |

---

## Pendiente de implementacion

- **Convert — Transcode de MOV:** plates MOV aparecen en la tabla con checkbox deshabilitado
  y estado "No soportado". Implementar cuando haya herramienta de transcode MOV disponible.
- **Import real — generalizar:** quitar el flag `_IMPORT_ONLY_COMP` y soportar todos los tracks. Ver `LGA_import_shots_do.md`.
- **Post-import — SetShotName:** llamada al script externo post-importacion.
- **Post-import — CreateV000:** dialogo post-import para crear v000 en tasks sin versiones.

---

## Referencias tecnicas

| Archivo | Funciones / clases clave |
|---------|--------------------------|
| `LGA_NKS_Edit_Panel_py/LGA_import_shots.py` | `main()`, `_import_shot_dialog_instance`, `_clear_import_dialog()`, `_visible_import_dialog_for_shot()`, `_show_tool_message()`, `_launch_create_v000()`, `ImportShotDialog`, `_do_import_and_v000()`, `_show_page()`, `_build_page_media()`, `_build_page_rename()`, `_update_rename_page()`, `_refresh_rename_preview()`, `_populate_rename_section_header()`, `_on_rename_chk_changed()`, `_update_rename_btn_state()`, `_run_rename()`, `_rn_escape()`, `_swap_sr()`, `_update_rename_summary()`, `_build_page_convert()`, `_update_convert_page()`, `_on_res_preset_changed()`, `_on_keep_ar_changed()`, `_update_match_dim_visibility()`, `_get_representative_res()`, `_on_custom_w_changed()`, `_on_custom_h_changed()`, `_current_target_res()`, `_target_compression()`, `_refresh_convert_destinos()`, `_update_res_combo_labels()`, `_on_dwaa_chk_changed()`, `_on_deana_chk_changed()`, `_apply_deana_if_active()`, `_load_settings_to_ui()`, `_save_all_settings()`, `_rebuild_res_combo()`, `_on_delete_preset()`, `_on_save_preset_clicked()`, `_run_transcode()`, `_start_next_sequence()`, `_on_sequence_started()`, `_poll_transcode_progress()`, `_on_sequence_done()`, `_on_worker_batch_done()`, `_finalize_transcode()`, `_on_transcode_error()`, `_fmt_bd()`, `_fmt_par()`, `_ar_str()`, `_read_exr_metadata()`, `_read_mov_metadata()`, `_find_insert_frame()` (retorna `insert_frame, frames_to_push, prev_shot_name, next_shot_name`), `_collect_timeline_shots()`, `_build_track_combo()`, `_on_track_combo_changed()`, `_refresh_track_combo_options(created_track_name, creator_row)`, `_create_plate_track()`, `_get_seq_track_names()` — widgets: `_TrackComboListView`, `_TrackComboDelegate` (botón "Crear track" en dropdown de track) |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode.py` | `TranscodeWorkerSignals` (señales: `log_message`, `sequence_started(row_i, dst_dir, total_frames)`, `sequence_done`, `all_done`, `error`), `TranscodeWorker`, `build_manifest_for_sequence(channels, pixel_aspect_ratio)`, `check_existing_outputs()`, `delete_existing_outputs()`, `show_overwrite_warning()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue.py` | `TranscodeQueueManager`, `get_manager()`, `enqueue_jobs()`, `snapshot()`, `_start_next_if_idle()`, `_prepare_job_or_cancel()`, `_launch_worker()`, logging propio `debugPy_ImportShotsTranscodeQueue.log` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue_ui.py` | `TranscodeQueueWindow`, `show_queue_window()`, UI no modal `Import Shots - Transcode Queue`, historial visual, `Keep this window on top` persistente |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue.md` | Especificacion pendiente de la cola global entre ventanas: `TranscodeQueueManager`, modelo de job, estados por fila, footer global, ventana `Open Queue`, cierre de ventanas y riesgos conocidos |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue_PLAN.md` | Plan por etapas para implementar y testear la cola global. Incluye la regla de actualizar la especificacion principal cuando cambien decisiones durante la implementacion |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue_ui.md` | Especificacion visual y tecnica de la ventana `Import Shots - Transcode Queue`: tabla global, columnas Shot/Plate/Duracion/Estado, historial visual, `Clear Completed`, `Keep this window on top` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_settings.py` | `get_settings_path()`, `load_all_settings()`, `save_all_settings()`, `load_res_presets()`, `save_res_presets()`, `preset_to_tuple()`, `show_save_preset_dialog()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_timeline.py` | `push_clips_right()`, `place_clip_in_timeline()`, `stretch_burnin()`, `set_viewer_to_shot()`, `_zoom_and_restore()`, `set_debug_print()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_bin.py` | `find_or_create_shot_bin()`, `import_item_to_bin()`, `set_debug_print()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_rename.py` | `build_selected_rows()`, `compute_preview(rows, settings, stage_colors, shot_name="", shotname_color="")`, `build_row_ops()`, `execute_ops()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_rename_settings.py` | `get_settings_path()`, `load_settings()`, `save_settings()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_rename.md` | Especificación funcional y técnica de la sección Rename |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode.md` | Especificación funcional de la sub-vista Convert (PAGE_CONVERT): tabla EXRs, opciones Codec/Resolución, manejo de originales, presets INI, `_ArrowSpinBox` |
| `LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py` | Referencia de UI, bin import, timeline placement, colorize path, patrón de settings persistentes |
| `LGA_NKS_Edit_Panel_py/LGA_NKS_SetShotName.py` | Renombrado de clips post-importacion |
| `LGA_NKS_Edit_Panel_py/LGA_NKS_OrganizeProject.py` | Estructura de bins `F <grupo>/<shot>` |
| `LGA_NKS_Shared/LGA_EXR_Convert.py` | Motor de transcode EXR. Llamado via subprocess con `--manifest` JSON. Soporta DWAA, resize, channels, pixel_aspect_ratio, OCIO, workers paralelos. |
| `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py` | `clean_base_name()`, `extract_shot_code()` |
| `LGA_NKS_Shared/LGA_QtAdapter_HieroTools.py` | Qt adapter (PyQt5/PySide2) |
| `LGA_NKS_Shared/icons/trash.svg` | Ícono de papelera para borrar presets (estado normal) |
| `LGA_NKS_Shared/icons/trash_hover.svg` | Ícono de papelera (estado hover) |
| `LGA_NKS_Shared/OIIO_Win/oiiotool.exe` | Lectura metadata EXR (Windows). Llamado con `--info -v` |
| `LGA_NKS_Shared/OIIO_Win/bin/python/python.exe` | Python bundled usado por `TranscodeWorker` para invocar `LGA_EXR_Convert.py` |
| `LGA_NKS_Shared/FFmpeg_Win/bin/ffprobe.exe` | Lectura metadata MOV/MXF (Windows). Salida JSON |
| `docs/LGA_import_shots_PLAN.md` | Plan de desarrollo, decisiones de diseno, preguntas resueltas |
