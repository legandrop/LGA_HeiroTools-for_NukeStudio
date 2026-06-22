> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_NKS_CreateV000

Herramienta para crear una secuencia EXR negra `v000` para uno o varios shots en Hiero/Nuke Studio.

## Descripcion

Abre un dialogo desde el Edit Panel o desde Import Shot y construye contexto por shot (secuencia, tracks, rango de frames y resolucion). La UI es unificada: siempre usa tabs por shot (single = 1 tab, bulk = N tabs) y permite crear v000 en lote para todos los tabs elegibles.

La herramienta crea archivos en disco, importa la v000 al bin correcto del proyecto y la coloca en el timeline cuando el rango destino está disponible. Las tasks `comp`, `roto` y `cleanup` se deshabilitan automáticamente si ya existen clips superpuestos en su track para el rango del shot.

## Archivos principales

- **Script principal:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_NKS_CreateV000.py`
- **Panel de control:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel.py`
- **Plan / log de desarrollo:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_NKS_CreateV000_Plan.md`

## Acceso

**Boton del panel:** "Create v000" en el Edit Panel, ubicado despues del boton "Set Shot Name".

Se activa con `open_create_v000_dialog()` o `open_create_v000_dialog(shot_targets=[...])`.

---

## Logging

El script usa el sistema de logging dual documentado en `docs\Docu_Logging_System.md` con los valores por defecto:

- `DEBUG = True`
- `DEBUG_CONSOLE = False`
- `DEBUG_LOG = True`

La salida de debug no se propaga a consola y se escribe en `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\logs\debugPy_CreateV000.log`.

El archivo se reinicia en cada carga del modulo con encabezado `Fecha: YYYY-MM-DD HH:MM:SS` y usa formato relativo `[0.123s] mensaje`.

---

## Funcionamiento general

### Prerequisitos para que el dialogo abra

Modo sin parámetros (`open_create_v000_dialog()`):
- Debe haber una sequence activa en Hiero.
- Si hay clips seleccionados en timeline, se construye un contexto por shot seleccionado.
- Si no hay selección, usa el shot bajo playhead como fallback.

Modo con parámetros (`open_create_v000_dialog(shot_targets=[...])`):
- Cada target debe poder resolverse contra tracks `editref`/`plate` de la sequence.
- Debe existir al menos un `plate` para derivar path/resolución.

Si un shot ya tiene sus 3 tasks ocupadas en timeline (solape en `_comp_`, `_roto_`, `_cleanup_`), ese shot no genera tab.

### Flujo principal

```
open_create_v000_dialog(shot_targets?)
    |
    ├── _collect_dialog_contexts()
    │     ├── _selected_shot_targets() / _collect_context_from_playhead()
    │     └── _collect_context_for_target()
    ├── filtro por tasks disponibles (_context_has_available_tasks)
    └── CreateV000TabsDialog(contexts)
            |
            ├── tabs shell (_ImportShotTabBar + _HeaderSeparator)
            ├── CreateV000Dialog(embedded=True) por shot
            └── _create_all_tabs()
                    ├── _preflight_and_create_exr() por task
                    ├── beginUndo único por proyecto
                    └── _hiero_import_for_params()
```

---

### Deteccion de isla del shot

La tabla de `FRAME RANGE` no se limita a clips exactamente bajo el playhead. El playhead se usa como ancla para identificar el shot actual y luego se expande una isla temporal de clips relacionados.

El proceso es:

1. Buscar clips ancla bajo el playhead en tracks `editref` y tracks que terminan en `plate`.
2. Elegir como ancla preferida un plate; si no hay plate bajo el playhead, usar el primer clip relevante disponible.
3. Derivar identidad del shot desde el ancla:
   - `shot_root`, cuando el path permite cortar antes de `_input`.
   - `shot_code`, usando `clean_base_name()` y `extract_shot_code()`.
4. Recorrer tracks relevantes y agregar clips que solapen con la isla temporal actual y coincidan por `shot_root` o `shot_code`.
5. Si un clip aceptado expande el rango de la isla, repetir hasta que no entren clips nuevos.

Esto permite detectar, por ejemplo, un `editref` que empieza varios frames despues del primer frame del `aPlate`, siempre que pertenezca al mismo shot.

**Implementacion:** `_collect_range_sources()`, `_range_track_entries()`, `_clip_shot_identity()`, `_clip_matches_shot_identity()`, `_timeline_ranges_overlap()`.

---

## UI del dialogo (single + bulk unificado)

```
[TAB: SHOT_A] [TAB: SHOT_B] ... [TAB: SHOT_N]

FRAME RANGE                         RESOLUTION
[ ] Track    TL IN  TL OUT  Frames  ( ) Timeline   WxH
[ ] Track    TL IN  TL OUT  Frames  ( ) aPlate     WxH
                                    ( ) cPlate     WxH

HANDLE                              TASK
[ ▼ ][ 4 ][ ▲ ]                    [ comp ] [ roto ] [ cleanup ]

[ ] Create folder structure for selected tasks if missing

OUTPUT
Path: ...
Name: ...
Timeline: ... - ... (handle ...)
Frames: ... - ... (... frames)
Resolution: ... x ... (fuente)

[ Preview In/Out ]      (en cada tab)
...
[ Cancel ] [ Create v000 (All tabs) ]     (footer global)
```

- Ancho minimo de la ventana tabulada: `980x700`.
- Shell de tabs: mismo patrón visual de `LGA_import_shots` (`_ImportShotTabBar`, `_HeaderSeparator`, `_TAB_STYLE`).
- La tabla de frame range no muestra grid ni scroll vertical.

---

## Seccion: Frame Range

Lista los tracks disponibles para el shot actual (resuelto por selección/playhead o por target explícito) en este orden:

1. Tracks cuyo nombre contiene `editref` (case-insensitive).
2. Tracks cuyo nombre termina en `plate` (case-insensitive).

Cada fila muestra: checkbox `Use`, nombre del track, `TL IN`, `TL OUT`, `Frames`.

**Reglas de seleccion:**

- Por defecto se selecciona la primera fila (editref si existe, sino plate).
- `editref` y `plate` no son combinables entre si.
  - Seleccionar un editref deselecciona todos los plates y viceversa.
- Los editref son exclusivos entre si, incluso si hay varios tracks llamados `EditRef`.
- Varios plates pueden combinarse entre si.
- El rango base se calcula con:
  - `base_timeline_in = min(timelineIn de seleccionados)`
  - `base_timeline_out = max(timelineOut de seleccionados)`

**Implementacion:** `_collect_range_sources()`, `_is_editref_track()`, `_is_plate_track()`, `_on_range_check_changed()`

---

## Seccion: Resolution

Opciones disponibles:

- `Timeline` (default): resolucion de la sequence activa via `seq.format()`.
- Una opcion por cada track `plate` detectado con su resolucion real.

La resolucion del plate se extrae en cascada desde:
1. Metodos directos del objeto `source` o `mediaSource` (`width()`, `height()`).
2. Metadata del `mediaSource` (claves `foundry.source.width/height`, `input/width/height`, `exr/displayWindow/...`).
3. `fileinfos()` del `mediaSource`.

Si un plate no devuelve resolucion valida, su radio button queda deshabilitado.

Los tracks `editref` no se usan como fuente de resolucion.

**Implementacion:** `_timeline_resolution()`, `_plate_resolution()`, `_metadata_resolution()`, `_call_int_method()`

---

## Seccion: Handle

Control custom de incremento/decremento. No usa `QSpinBox`.

```
[ ▼ ][ 4 ][ ▲ ]
```

- Valor inicial por defecto: `4`.
- Rango permitido: `0` a `99`.
- **Solo se habilita si la seleccion de frame range incluye al menos un editref.**
- Si la seleccion no tiene editref, el handle se fuerza a `0` y queda greyed out.
- El handle es persistente: al abrir la tool se lee desde `CreateV000.ini`.
- Si no existe el archivo de settings, se crea con `handle=4`.
- Cuando el usuario cambia el handle con las flechas, el nuevo valor se guarda inmediatamente.
- Si luego se vuelve a seleccionar un editref, el handle vuelve al ultimo valor guardado.
- El `0` temporal por seleccionar una fuente sin editref no se guarda.

Cuando el handle esta activo, el rango efectivo se expande:

```
timeline_in  = base_timeline_in  - handle
timeline_out = base_timeline_out + handle
```

Cualquier cambio en el handle recalcula el preview de OUTPUT en vivo.

**Implementacion:** `_read_handle_setting()`, `_write_handle_setting()`, `_build_handle_box()`, `_step_handle()`, `_set_handle_enabled()`

### Settings de Create v000

La preferencia del handle se guarda en:

| Sistema | Ruta |
|---------|------|
| Windows | `%APPDATA%/LGA/HieroTools/CreateV000.ini` |
| macOS | `~/Library/Application Support/LGA/HieroTools/CreateV000.ini` |
| Fallback | `~/.config/LGA/HieroTools/CreateV000.ini` |

Formato:

```ini
[Settings]
handle = 4
create_folders = true
```

---

## Accion: Preview In/Out

Boton secundario ubicado abajo a la izquierda del dialogo. Usa el mismo rango calculado para la v000 visible en `OUTPUT` y lo aplica como In/Out de la sequence activa:

```python
seq.setInTime(timeline_in)
seq.setOutTime(timeline_out)
viewer.setTime(timeline_in)
timeline_editor.setSelection(selected_range_clips)
QtCore.QTimer.singleShot(0, lambda: hiero.ui.findMenuAction("Zoom to Fit").trigger())
```

Esto permite previsualizar en el timeline el espacio que va a ocupar la v000 antes de crearla. Si hay varias tasks seleccionadas, el rango es el mismo para todas; se usa el primer bloque de parametros calculado por `_build_outputs()`.

Despues de setear el rango, oculta temporalmente el dialogo modal, mueve el playhead al `timeline_in`, selecciona temporalmente los clips usados como frame range, activa/focaliza la ventana del timeline y ejecuta `Zoom to Fit` con `QtCore.QTimer.singleShot(...)`, siguiendo el patron de `LGA_NKS_PrevNext_Rev.py`. Al terminar el zoom limpia la seleccion y vuelve a mostrar el dialogo.

El boton se deshabilita cuando el dialogo no tiene parametros validos (por ejemplo, sin frame range, sin task o sin resolucion).

**Implementacion:** `_preview_in_out()`, `_zoom_timeline_to_preview_range()`, `_build_outputs()`

---

## Seccion: Task

Botones toggle independientes para las tres tasks disponibles:

| Task      | Track destino | Carpeta de salida |
|-----------|---------------|-------------------|
| `comp`    | `_comp_`      | `Comp`            |
| `roto`    | `_roto_`      | `Roto`            |
| `cleanup` | `_cleanup_`   | `Cleanup`         |

**Reglas:**

- Al abrir el dialogo no hay ninguna task seleccionada.
- Se puede seleccionar una o varias tasks al mismo tiempo.
- Si no hay ninguna task seleccionada, el boton `Create v000` queda deshabilitado.
- Si ya existe cualquier clip superpuesto al rango del shot en el track de la task, esa task queda deshabilitada (greyed out).
- Si las 3 tasks están bloqueadas (`comp`, `roto`, `cleanup`), el shot no se muestra como tab elegible.
- Al confirmar multiples tasks, se procesan secuencialmente en el orden `comp`, `roto`, `cleanup`.
- Si el usuario cancela una comprobacion de una task, solo se saltea esa task y el proceso continua con la siguiente task seleccionada.

Los conflictos de timeline se validan en dos etapas:
- **UI previa:** bloqueo de task por solape en el rango del shot.
- **Creación:** validación final por task con `_timeline_overlaps()` y diálogo de resolución.

**Implementacion:** `_build_task_box()`, `_select_default_task()`, `_selected_tasks()`, `_build_outputs()`


---

## Auto-creacion de tracks faltantes

Si el track de destino para una task seleccionada no existe en el timeline, la herramienta lo crea automaticamente en la posicion correcta **antes** de crear los EXRs y la estructura de carpetas. No se muestra ningún dialogo de confirmacion.

### Orden de tracks en el panel (top to bottom)

```
BurnIn
_comp_
_roto_
_cleanup_
(tracks de plates)
```

En la API de Hiero, `videoTracks()` devuelve de abajo hacia arriba (index 0 = fondo). El orden visual es el inverso del indice.

### Workaround de insercion

Hiero no tiene `insertTrack(track, index)`. El workaround es:

1. Obtener la lista actual: `video_tracks = list(seq.videoTracks())`
2. Calcular `insert_at = above_track.trackIndex()` (el track que debe quedar justo por encima del nuevo)
3. Construir `new_list = video_tracks[:insert_at] + [new_track] + video_tracks[insert_at:]`
4. Remover todos los tracks y re-agregar en el nuevo orden

Todo envuelto en `project.beginUndo()` para soporte de Ctrl+Z.

### Logica de posicionamiento

Para determinar el `above_track` (el track que debe quedar justo encima del nuevo):

| Task nueva | Candidatos (en orden de preferencia) |
|------------|--------------------------------------|
| `_comp_`   | `BurnIn`                             |
| `_roto_`   | `_comp_`, `BurnIn`                   |
| `_cleanup_`| `_roto_`, `_comp_`, `BurnIn`         |

Se usa el primer candidato encontrado. Si ninguno existe, el nuevo track se agrega al tope.

Los nombres de track se obtienen via `track_for_task()` (de `LGA_NKS_TaskSelectionDialog`) y `BURNIN_TRACK_NAME`, sin hardcodear strings.

### Flujo de creacion en `_create_v000_for_params()`

```
1. Verificar si existen EXRs → confirm replace
2. Buscar track destino → marcar track_needs_creation si no existe
   (un track nuevo no tiene items, por eso el overlap check se omite)
3. Si track existe → verificar overlaps → dialog de opciones
4. Si checkbox activo → _ensure_task_folder_structure()  [op. de disco, fuera del undo]
5. _create_black_exr_sequence()                          [op. de disco, fuera del undo]
6. with project.beginUndo("Create v000 <task>"):         [UNICO bloque de undo]
     a. Si track_needs_creation → _insert_task_track()
     b. Importar al bin
     c. Colorear bin item
     d. Rescan clip range
     e. Colocar / reemplazar en timeline
     f. Deshabilitar track item
```

Un solo Ctrl+Z deshace todo lo que Hiero registró en el paso 6.

**Implementacion:** `_insert_task_track()`, `_get_above_neighbor_for_task()`, `_create_v000_for_params()`

---

## Seccion: Create folder structure

Checkbox sin etiqueta de seccion, ubicado entre TASK y OUTPUT.

Texto: `"Create folder structure for selected tasks if missing"`

Estado por defecto: **activado**. El estado se guarda persistentemente en `CreateV000.ini` bajo la clave `create_folders` (valores `true`/`false`). Cualquier cambio del usuario se persiste inmediatamente al hacer clic.

Si esta activado, antes de crear los EXRs se verifica y crea (si no existen) los subdirectorios estandar para cada task seleccionada bajo el `shot_root`:

```
{shot_root}/
├── Comp/
│   ├── 0_assets/
│   ├── 1_projects/
│   ├── 2_prerenders/
│   ├── 3_review/
│   └── 4_publish/
├── Roto/
│   ├── 0_assets/
│   ├── 1_projects/
│   ├── 2_prerenders/
│   ├── 3_review/
│   └── 4_publish/
└── Cleanup/
    ├── 0_assets/
    ├── 1_projects/
    ├── 2_prerenders/
    ├── 3_review/
    └── 4_publish/
```

Solo se crean las carpetas de las tasks seleccionadas al momento de ejecutar `Create v000`. Las carpetas ya existentes no se tocan. Los errores al crear carpetas se loguean como warnings sin bloquear la creacion de EXRs.

**Constantes relacionadas:**

```python
TASK_SUBFOLDERS = ("0_assets", "1_projects", "2_prerenders", "3_review", "4_publish")
```

**Implementacion:** `_build_folder_structure_section()`, `_ensure_task_folder_structure()`, `_read_create_folders_setting()`, `_write_create_folders_setting()`, `_create_v000_for_params()`

---

## Seccion: Output (preview)

Se recalcula en vivo con cada cambio en el dialogo. Muestra un bloque por cada task seleccionada usando HTML con colores (el widget es `QTextEdit` en modo readonly).

- **Task:** nombre de la task en negrita con su color definido en `TASK_COLORS`.
- **Path:** coloreado por niveles de carpeta segun el sistema compartido con LGA_mediaManager y LGA_PipeSync (ver abajo).
- Las demas lineas se muestran en gris claro `#a7a7a7`.

```
Task: roto              ← color de la task (#2abf7e para roto)
Path: T:/VFX-MOR/101/MOR_1003_020/Roto/4_publish/MOR_1003_020_roto_v000
Name: MOR_1003_020_roto_v000_####.exr
Timeline: 3813 - 4242 (handle 4)
Frames: 1001 - 1430 (430 frames)
Resolution: 4168 x 1612 (Timeline)
```

### Sistema de colores del path

Los segmentos del path se colorean segun su posicion relativa al shot folder:

| Segmento             | Color       | Descripcion             |
|----------------------|-------------|-------------------------|
| Dentro del shot root | `#c56cf0`   | Lavanda (disco/proj/grupo/shot) |
| Nivel 4 (task folder)| `#ffd369`   | Amarillo mostaza        |
| Nivel 5 (subfolder)  | `#28b5b5`   | Verde cian              |
| Nivel 6+             | ciclo 4→5→6→7 | segun diccionario    |
| Separador `/`        | `#bbbbbb`   | Gris claro              |

El corte entre lavanda y colores por nivel ocurre al agotar los segmentos del `shot_root`. Esto se calcula a partir del `shot_root` disponible en `params`, sin comparacion externa.

**Implementacion:** `_build_output()`, `_build_outputs()`, `_update_state()`, `_colorize_path()`

---

## Derivacion del path de salida

El shot root se extrae del path del plate buscando el segmento `_input`:

```
T:/VFX-MOR/101/MOR_1003_020/_input/...
                             ^^^^^^^
shot_root = T:/VFX-MOR/101/MOR_1003_020
```

El output se construye como:

```
{shot_root}/{TASK_FOLDER[task]}/4_publish/{shot_code}_{task}_v000/
```

Ejemplo para `roto`:

```
T:/VFX-MOR/101/MOR_1003_020/Roto/4_publish/MOR_1003_020_roto_v000/
```

**Implementacion:** `_derive_shot_root()`, `_build_output()`

---

## Naming de la secuencia

Patron de nombre de archivo:

```
{shot_code}_{task}_v000_####.exr
```

Ejemplo:

```
MOR_1003_020_roto_v000_1001.exr
MOR_1003_020_roto_v000_1002.exr
...
MOR_1003_020_roto_v000_1429.exr
```

El primer frame de salida siempre es `1001` (constante `START_FRAME`).
La version siempre es `v000` (constante `VERSION`).

---

## Creacion de EXR en disco

### Herramienta: oiiotool (Windows)

La secuencia se crea en dos pasos usando `oiiotool.exe` vendorizado en `LGA_NKS_Shared`:

```
C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\OIIO_Win\oiiotool.exe
```

**Paso 1 - Crear el primer frame negro:**

```
oiiotool --create WIDTHxHEIGHT 3 --chnames R,G,B -d half --compression dwaa -o SHOT_task_v000_1001.exr
```

Parametros del EXR generado:

| Parametro   | Valor    |
|-------------|----------|
| Canales     | `R,G,B`  |
| Data type   | `half`   |
| Compresion  | `dwaa`   |
| Valor pixel | negro    |

**Paso 2 - Duplicar para todos los frames restantes:**

```python
shutil.copyfile(first_file, target_frame_file)
```

Este enfoque es rapido y garantiza que todos los frames son identicos al primero.

Al finalizar se valida que la cantidad de archivos `.exr` en la carpeta coincida con `frame_count`.

### Flujo de creacion y manejo de conflictos

1. Resolver `oiiotool.exe` relativo a `LGA_NKS_Shared`.
2. Si la carpeta de salida **no existe**: crearla.
3. Si la carpeta de salida **ya existe y tiene EXRs**: mostrar dialogo de confirmacion con opciones `Cancel` / `Replace`.
   - `Replace`: borra la carpeta completa y la recrea desde cero.
4. Crear el primer frame con oiiotool.
5. Duplicar el primer frame para los frames restantes.
6. Validar cantidad de archivos escritos.

### macOS

Pendiente. No implementado hasta cerrar la version Windows.
La futura implementacion debera usar su propio `oiiotool` en `LGA_NKS_Shared/OIIO_Mac`.

**Implementacion:** `_create_black_exr_sequence()`, `_oiio_tool_path()`

---

## Parametros del diccionario de salida

La funcion `_build_output()` retorna un diccionario con todos los parametros necesarios para la creacion:

```python
{
    "shot_code": "MOR_1003_020",
    "task": "roto",
    "shot_root": "T:/VFX-MOR/101/MOR_1003_020",   # usado para coloreado del path
    "selected_range_sources": [
        {"track_name": "EditRef", "source_type": "editref"},
    ],
    "selected_plates": ["EditRef"],
    "base_timeline_in": 3817,
    "base_timeline_out": 4238,
    "handle": 4,
    "timeline_in": 3813,
    "timeline_out": 4242,
    "frame_count": 430,
    "source_first_frame": 1001,
    "source_last_frame": 1430,
    "resolution": (4168, 1612),
    "resolution_source": "Timeline",
    "output_dir": "T:/VFX-MOR/101/MOR_1003_020/Roto/4_publish/MOR_1003_020_roto_v000",
    "output_name_pattern": "MOR_1003_020_roto_v000_####.exr",
}
```

Nota: `timeline_out` es **inclusivo** (ultimo frame incluido). `frame_count = timeline_out - timeline_in + 1`.

---

## Validaciones

El dialogo bloquea `Create v000` y muestra un warning si:

| Condicion                                              | Origen                     |
|--------------------------------------------------------|----------------------------|
| No hay sequence activa                                 | `_collect_dialog_contexts()` / `_collect_context_from_playhead()` |
| No hay viewer / playhead activo (modo sin selección)   | `_collect_context_from_playhead()` |
| No hay tracks editref/plate para el shot              | `_collect_context_for_target()` / `_collect_context_from_playhead()` |
| No hay track plate (no se puede derivar path/resol.)   | `_build_context_from_sources()` |
| No se detecta shot code                                | `_build_context_from_sources()` |
| Todas las tasks del shot ya tienen solape en timeline  | filtro `_context_has_available_tasks()` |
| No hay fuente de frame range seleccionada              | `_build_output()`          |
| No hay task seleccionada                               | `_build_outputs()`         |
| No se puede derivar shot root desde `_input`           | `_build_output()`          |
| La resolucion seleccionada no es valida                | `_build_output()`          |
| El rango calculado resulta en 0 frames o menos         | `_build_output()`          |

---

## Dependencias y modulos usados

| Modulo                              | Uso                                                                 |
|-------------------------------------|---------------------------------------------------------------------|
| `hiero.core`, `hiero.ui`            | API de Hiero: sequence, tracks, clips, viewer                       |
| `LGA_NKS_Shared.LGA_QtAdapter_HieroTools` | Qt compatible con Hiero (PyQt5/PySide2 segun version)         |
| `LGA_NKS_Flow_NamingUtils`          | `clean_base_name()`, `extract_project_name()`, `extract_shot_code()` |
| `LGA_NKS_TaskSelectionDialog`       | `track_for_task()` para mapear task a nombre de track               |
| `LGA_NKS_Flow_Task_Config`          | `get_task_color()` para colores de botones de task                  |
| `oiiotool.exe` (vendorizado)        | Creacion del primer frame EXR negro                                 |
| `shutil.copyfile`                   | Duplicacion del primer frame para el resto de la secuencia          |

---

## Constantes del script

```python
START_FRAME = 1001
VERSION     = "v000"
V000_CLIP_COLOR_RGB = (138, 138, 138)  # #8a8a8a, igual al boton v_00 de ClipColor
DEFAULT_HANDLE = 4
CONFIG_DIR_NAME = "LGA"
CONFIG_SUBDIR_NAME = "HieroTools"
CONFIG_FILE_NAME = "CreateV000.ini"
CONFIG_SECTION = "Settings"
CONFIG_HANDLE_KEY = "handle"
CONFIG_CREATE_FOLDERS_KEY = "create_folders"
BURNIN_TRACK_NAME = "BurnIn"
TASKS       = ("comp", "roto", "cleanup")
TASK_FOLDER = {"comp": "Comp", "roto": "Roto", "cleanup": "Cleanup"}

# Colores de los botones de task en la UI
TASK_COLORS = {
    "comp":    "#3381e0",  # Azul
    "roto":    "#2abf7e",  # Verde
    "cleanup": "#27c8c3",  # Cyan
}

# Sistema de colores de path (compartido con LGA_mediaManager / LGA_PipeSync)
PATH_SHOT_COLOR   = "#c56cf0"   # Lavanda — segmentos del shot folder
PATH_SEP_COLOR    = "#bbbbbb"   # Gris claro — separadores /
PATH_LEVEL_COLORS = {
    0: "#ffff66",   # Amarillo       (disco)
    1: "#28b5b5",   # Verde cian     (proyecto)
    2: "#ff9a8a",   # Naranja pastel (grupo)
    3: "#0088ff",   # Azul           (shot)
    4: "#ffd369",   # Amarillo mostaza
    5: "#28b5b5",   # Verde cian
    6: "#ff9a8a",   # Naranja pastel
    7: "#6bc9ff",   # Celeste
    # ... ciclo 4-7 para niveles mayores
}
```

---

## Importacion y colocacion en Hiero

Luego de crear la secuencia EXR en disco, la herramienta la importa automaticamente al proyecto de Hiero e intenta insertarla en el timeline.

El flujo fue validado en scripts de exploracion. Ver resultados en `LGA_NKS_CreateV000_Plan.md`.

**Flujo validado:**

```python
clip = hiero.core.Clip(first_frame_path)        # Detecta secuencia completa automaticamente
bin_item = hiero.core.BinItem(clip)
target_bin.addItem(bin_item)
bin_item.setColor(QtGui.QColor(138, 138, 138))

track_item = target_track.addTrackItem(clip, timeline_in)
track_item.setName(shot_name)                   # Solo SHOT_CODE, no nombre completo de archivo
track_item.setTimes(timeline_in, timeline_out, 0, frame_count - 1)
track_item.setVersionLinkedToBin(True)          # Debe llamarse al final
track_item.setEnabled(False)                    # La v000 queda deshabilitada en timeline
```

**Politicas de la integracion:**

- Importar al bin `F <Secuencia>/<ShotName>` (estructura de `Organize Project`).
- Si ya existe un `BinItem` con el mismo media path de la v000, borrarlo del bin antes de importar. Esto fuerza a Hiero a crear un `Clip` fresco y releer el frame range real de los EXR.
- Al importar, aplicar al `BinItem` el color gris `v_00` (`#8a8a8a`, `QtGui.QColor(138, 138, 138)`).
- Despues de importar y colorear, ejecutar `clip.rescan()` y validar que el rango detectado por Hiero coincida con los EXR creados. Si no coincide, no insertar en timeline.
- Insertar en `_comp_`, `_roto_` o `_cleanup_` segun task.
- Si hay multiples tasks seleccionadas, ejecutar una task por vez en el orden `comp`, `roto`, `cleanup`.
- Cancelar si el track destino no existe (no crear tracks automaticamente).
- Si hay overlap en el rango destino, mostrar opciones:
  - `Cancel`
  - `Create EXRs Only`
  - `Create + Import to Bin`
  - `Create + Import to Bin & Timeline`
- Source relativo: `0` a `frame_count - 1`.
- `TrackItem.setTimes()` recibe `timeline_out` inclusivo.
- `setVersionLinkedToBin(True)` solo funciona despues de que el TrackItem ya fue agregado y sus tiempos ajustados.
- Si se crea un clip en timeline, deshabilitar el `TrackItem` v000 con `setEnabled(False)`.
- En una cola multi-task, `Cancel` en el dialogo de overlap o replace saltea solo la task actual y continua con la siguiente seleccionada.
- Si el usuario elige `Create EXRs Only`, no hay importacion y no se cambia ningun color.

`Create + Import to Bin & Timeline` borra solo clips reales del track destino que se solapan con el rango de la v000, importa el nuevo clip y lo coloca en timeline. No borra efectos ni clips de otros tracks.

**Scripts de exploracion de referencia:**

```
C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\+Building_Blocks\Hiero\Timeline\LGA_H-CreateV000_ImportExplore.py
C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\+Building_Blocks\Hiero\Timeline\LGA_H-TrackItem_LinkStatus_Explore.py
C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\+Building_Blocks\Hiero\Timeline\LGA_H-TrackItem_LinkStatus_SetSelected.py
```

---

## Referencias tecnicas

| Archivo | Funciones / clases clave |
|---------|--------------------------|
| `LGA_NKS_Edit_Panel_py\LGA_NKS_CreateV000.py` | `open_create_v000_dialog(shot_targets=...)`, `_collect_dialog_contexts()`, `_selected_shot_targets()`, `_collect_context_for_target()`, `_collect_context_from_playhead()`, `_task_overlap_state()`, `_context_has_available_tasks()`, `CreateV000TabsDialog`, `CreateV000Dialog`, `_create_all_tabs()`, `_build_outputs()`, `_preview_in_out()`, `_preflight_and_create_exr()`, `_hiero_import_for_params()`, `_create_black_exr_sequence()`, `_insert_task_track()` |
| `+Building_Blocks\Hiero\LGA_H-Tracks-InsertTest.py` | Referencia del workaround remove-all/re-add para insertar tracks en posicion especifica |
| `docs\Docu_Logging_System.md` | Valores por defecto y patron de `QueueHandler` / `QueueListener` |
| `LGA_NKS_ViewerTL_Panel_py\LGA_NKS_InOut_Editref.py` | Referencia para `seq.setInTime()` y `seq.setOutTime()` |
| `LGA_NKS_ViewerTL_Panel_py\LGA_NKS_PrevNext_Rev.py` | Referencia para mover playhead, enfocar timeline y ejecutar `Zoom to Fit` con `QTimer.singleShot()` |
| `LGA_NKS_ClipColor_Panel.py` | Boton `v_00`, color `QtGui.QColor(138, 138, 138)` / `#8a8a8a` |
| `LGA_NKS_Review_Panel_py\LGA_NKS_ON_Clips_OFF_v00-Clips.py` | Usa `TrackItem.setEnabled(False)` para desactivar clips v00/v000 |
| `LGA_NKS_Shared\LGA_NKS_TaskSelectionDialog.py` | `track_for_task()` |
| `LGA_NKS_Shared\LGA_NKS_Flow_NamingUtils.py` | `clean_base_name()`, `extract_project_name()`, `extract_shot_code()` |
| `LGA_NKS_Shared\LGA_NKS_Flow_Task_Config.py` | `get_task_color()` |
| `LGA_NKS_Shared\OIIO_Win\oiiotool.exe` | Creacion de EXR negro |
| `LGA_NKS_Edit_Panel_py\LGA_NKS_OrganizeProject.py` | Estructura de bins usada por la importacion |
| `LGA_NKS_Edit_Panel_py\LGA_NKS_SetShotName.py` | Logica de naming de clips usada por la importacion |
