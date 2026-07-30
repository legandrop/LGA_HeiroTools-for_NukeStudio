> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Ramas de versiones

## Que es una rama

Cuando mas de un compositor trabaja el mismo shot, cada uno numera en su
propio bloque: uno va por `v001..v0xx` (la **rama 0**) y el otro por
`v100..v1xx` (la **rama 100**). Las dos ramas conviven, cada una es trabajo
valido y en algun momento una absorbe el trabajo de la otra y lo une con el
suyo.

La consecuencia que atraviesa todo el repo:

> **El maximo global NO es "la version vigente".** Cada rama tiene su propia
> cabeza y todas las cabezas son validas a la vez.

Cualquier `max()` sobre versiones que decida una accion esta mal en cuanto
aparece una segunda rama: manda el clip, el script o la descarga al trabajo
de otra persona.

## La regla

Se ordenan las versiones, se sacan duplicados, y **un salto de 50 o mas entre
versiones consecutivas abre una rama nueva**.

```
[1, 2, 3, 12, 100, 101, 103, 200] -> [1,2,3,12] [100,101,103] [200]
cabezas:                              12         103           200
```

- `v099` -> `v100` = misma rama (salto 1).
- `v012` -> `v100` = dos ramas (salto 88).
- Un salto de exactamente 50 **si** abre rama: el criterio es `>=`.

Es la misma regla y el mismo gap que PipeSync
(`C:\Portable\LGA_PipeSync_2\src\utils\VersionBranching.cpp`, `kBranchGap = 50`).
Si se cambia el numero hay que cambiarlo en los dos lados: las dos apps miran
los mismos shots. FileManager tiene una tercera copia inline en
`C:\Portable\LGA_FileManager\src\s3Celery\S3Celery_ConflictChecker.cpp`.

### Familias

Las ramas se calculan **siempre dentro de una familia**: el nombre sin el
token de version. `SHOT_comp_v012.mov` y `SHOT_comp_v103.mov` son la misma
familia; `SHOT_roto_v012.mov` y `SHOT_comp_v012.exr` no. Dos series distintas
en la misma carpeta no comparten ramas.

### Nombre de cada rama

La etiqueta es el **bloque de centena** del arranque: `v000`, `v100`, `v200`.
Se eligio asi por dos razones:

1. Es como se las nombra en produccion ("la rama 0", "la rama 100").
2. Es **estable entre fuentes**. Si Flow conoce `v100..v103` y Wasabi solo
   tiene `v103`, las dos siguen siendo la rama `v100`. Etiquetar por la
   primera version observada las haria aparecer como ramas distintas segun
   quien conteste, y el dialogo de descarga y el tooltip del Pull dejarian de
   coincidir.

Si dos ramas caen en la misma centena (por ejemplo `v001` y `v060`, que la
regla de 50 separa), las colisionadas se etiquetan por su arranque real.

## Las dos preguntas

Todo el repo se resuelve con dos primitivas:

| Pregunta | Primitiva | Donde se usa |
|---|---|---|
| "¿estoy atrasado?" | cabeza de **MI** rama | Pull, Push, MatchVerToEXR, OpenInNukeX, Reconnect, watcher |
| "traeme todo lo vigente" | cabezas de **TODAS** las ramas | Download Clip, `is_latest` de import_shots |

Y una regla de oro:

> **Nunca cambiar de rama automaticamente.** El maximo global se puede
> mostrar, nunca usar para actuar. Un clip cambia de rama solo si el usuario
> lo pide explicitamente.

## Comportamiento por herramienta

### Flow Pull

- La version de Flow contra la que se compara es la cabeza de la rama del
  clip, no el maximo de la task. Pushear o quedarse en `v012` con otro
  compositor en `v103` ya no genera `Version Mismatch` falso.
- El salto de version se limita a la rama del clip
  (`change_to_branch_head`).
- **Cada rama ajena con novedad agrega su propia fila informativa**, aunque
  el estado de la task no haya cambiado: `v_NKS` es la cabeza que tenemos
  bajada de esa rama (o `-`), `v_SG` la cabeza en Flow, y `New Status` dice
  `Other branch`. Esas filas **no tocan el clip** y `update_row_after_push`
  las saltea (marcadas con `is_other_branch` en el nav data).
- Si la unica novedad es de otra rama, no se agrega la fila normal: seria
  una fila sin cambios.
- Novedad = la cabeza de esa rama en Flow esta por encima de la que tenemos
  bajada. Una rama ajena ya bajada completa no genera fila.
- La columna `v_SG` muestra el **icono de ramas** (el mismo SVG de PipeSync)
  cuando la task tiene mas de una rama, con un tooltip que lista NKS y Flow
  rama por rama. Verde = al dia en su rama, rojo = atras, gris = sin dato.
- Las versiones locales se leen de `bin_item.items()` **sin** `doScan`: el
  Pull recorre todos los clips del timeline y un escaneo por clip lo haria
  lento. Lo que no este escaneado se muestra como `-`.

### Flow Push

- La advertencia "la version que intentas actualizar no es la mas reciente"
  compara contra la cabeza de la rama del clip. Con otro compositor arriba en
  otra rama, el push no pregunta nada.
- Cuando hay mas de una rama el dialogo las lista por separado y marca cual
  es la del clip.
- El selector de version de Flow (Shift+Click) rotula cada version con su
  rama: `v103 [v100]`.

### Download Clip (FileManager)

El modo latest (click; Shift+Click sigue bajando la version actual) ya no
delega en `--download-latest`, que resuelve el maximo global y por lo tanto
cruza de rama. Ahora:

1. Se lista Wasabi desde HieroTools (`LGA_NKS_S3VersionLister`) para la
   carpeta padre del media, filtrando por familia. Una sola llamada
   `list_objects_v2` con `Delimiter='/'`, en hilo secundario.
2. Con una sola rama no se pregunta nada: se baja su cabeza, igual que antes.
3. Con mas de una rama se abre un dialogo con una opcion por rama mas "All
   branches", que se responde **con el mouse o con el numero** (1 = todas,
   2..N = cada rama); ESC cancela.
4. Se le pasan a FileManager rutas explicitas con los flags que ya existen
   (`--download` / `--download-file`). **FileManager no cambia**: no hay
   contrato nuevo de CLI ni acople de versiones entre las dos apps.

Por que el listado vive en HieroTools y no en FileManager: el dialogo tiene
que salir donde el usuario hizo el click. Resolviendo aca las cabezas, el CLI
recibe rutas ya resueltas y las dos apps quedan desacopladas.

Si el listado falla (sin credenciales, sin red, ruta que no resuelve bucket)
se cae al `--download-latest` de siempre, logueado con el motivo.

Detalles de implementacion que importan:

- `boto3` vive dentro de `LGA_NKS_Assignee_Panel_py/` (es el unico del repo).
  Se inserta en `sys.path` en la **posicion 0**, no al final: agregandolo al
  final, cualquier otro `botocore` que ya este en el path gana la resolucion
  y se mezcla un `boto3` con el `botocore` de otro runtime, que revienta con
  `cannot import name DEFAULT_CHECKSUM_ALGORITHM`.
- El endpoint de `config.secure` viene **sin esquema** (`s3.wasabisys.com`) y
  boto3 lo rechaza con `Invalid endpoint`: se le agrega `https://`.

### Watcher de Download Clip

El marcador que escribe FileManager solo trae la ruta descargada, y con eso
no se puede distinguir "bajaron mi rama" de "bajaron la rama de otro". Por
eso DownloadClip deja un **intent** por ruta en
`LGA_HieroTools/logs/download_clip_intent/`, que el watcher lee cuando llega
el marcador:

- Rama elegida explicitamente -> el clip va a la cabeza de esa rama (el
  usuario la pidio, no es un efecto lateral).
- "All branches" -> el clip solo se mueve dentro de su propia rama.
- Descarga de una rama ajena -> el clip **no se toca**; el marcador se
  considera atendido igual.
- Sin intent (marcador `latest` de FileManager, o fallback) -> cabeza de la
  rama del clip. Nunca el maximo global.

Los intents vencen a las 6 horas y se borran al consumirse.

### Otras herramientas

| Herramienta | Comportamiento |
|---|---|
| **MatchVerToEXR** | Pide directamente la version del EXR; si no esta bajada, la cabeza de la rama del clip. Antes llamaba a un `change_to_highest_version` copiado del Pull. |
| **Compare Versions** (Review) | La "version anterior" se busca dentro de la rama. Antes, parado en `v100`, bajaba a `v012`. |
| **OpenInNukeX** | La "version mas reciente" que ofrece abrir es la cabeza de la rama del script pedido. |
| **Reconnect** | Reconecta a la cabeza de la rama del clip, no a la mas alta del directorio. En el fallback de archivos sin token de version se usa la rama mas baja, que es la serie original. |
| **import_shots** | `is_latest` marca **cabezas de rama**: con ramas hay mas de una version "ultima", y todas quedan pre-tildeadas y sin atenuar. |
| **CompareVerToEditref / CompareEXR_to_aPlate** | Su `change_to_branch_head` quedo con la regla correcta. Hoy no lo llama nadie. |
| **z_version_everywhere.py** | **Fuera de alcance a proposito.** Usa la API de Hiero (`maxVersion()`, `minVersion()`, `nextVersion()`, `prevVersion()`), que no sabe de ramas: `Max Version` puede saltar a la rama de otro y Next/Prev cruzan el borde. Hacerlo branch-aware es reescribir la tool. |

Dos `max()` de `LGA_import_shots.py` (deduplicacion por track cuando el
usuario tildo dos versiones de la misma familia) **no** son branch-aware a
proposito: en un track entra una sola version y el usuario eligio las dos
explicitamente, asi que ahi el maximo es solo un criterio de desempate.

## Deteccion: de donde salen las versiones

| Fuente | De donde | Costo |
|---|---|---|
| Clip en Hiero | `bin_item.items()` (con `doScan` solo donde ya se hacia) | gratis |
| Flow | tabla `versions` de la task en la DB local de PipeSync | gratis, ya se leia entera |
| Disco | listado del directorio agrupado por familia | gratis, ya se hacia |
| Wasabi | `list_objects_v2` con `Delimiter='/'` (solo Download Clip) | una llamada, en hilo secundario |

Trampa: la deteccion vale solo si la fuente trajo la lista completa. Si
`doScan` no corrio o el clip esta offline, el bin puede tener una sola
version y ahi **no se puede saber si hay ramas**. En ese caso el
comportamiento degrada al de una sola rama, que es lo correcto: no inventa
avisos.

## Duplicacion aceptada

La regla existe en tres runtimes: PipeSync (C++), FileManager (C++) y
HieroTools (Python). Es inevitable, pero el `50` y el criterio `>=` tienen
que quedar iguales. El caso de prueba compartido es:
`v099` -> `v100` misma rama, `v012` -> `v100` ramas distintas.

Dentro de HieroTools, Flow Pull y el watcher conservan su propia funcion de
cambio de version (agregan manejo de clips offline con `reconnectMedia` /
`refresh` y logging propio). Comparten la **regla** de ramas, no el codigo.

## Referencias tecnicas

### `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_VersionBranching.py`
Nucleo. Sin Qt, sin Hiero, sin red: solo enteros.
- `BRANCH_GAP` — el 50.
- `split_into_branches()` / `branch_heads()` / `latest_versions_per_branch()`
- `head_of_branch_containing()` — el reemplazo de `max()` en todo lo que decide.
- `branch_containing()` — la rama de una version, incluyendola.
- `compare_branches()` — primitiva de "¿que hay nuevo y donde?" (remoto vs
  local vs version actual). La usan el Pull y el Download Clip.
- `describe_branches()` / `branch_label()` / `_assign_labels()` — etiquetas.
- `family_key()` / `group_by_family()` — agrupacion por serie.
- `extract_version_number()` / `format_version()` (3 digitos).

### `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_VersionBranchesUI.py`
Presentacion: `BRANCH_COLOR_CONFLICT/CURRENT/NEUTRAL`, `branch_icon()`,
`branch_pixmap()`, `branches_tooltip_html()` y `tooltip()`, que saca los
textos de `TOOLTIPS[LANGUAGE]` (capa intermedia para la migracion bilingue).
El SVG es `LGA_NKS_Shared/icons/version_branches.svg`, copiado de PipeSync.

### `LGA_HieroTools/LGA_NKS_Shared/LGA_QtAdapter_HieroTools.py`
- `QtSvg` (import opcional), `svg_pixmap()`, `svg_icon()` — rasterizado 3x
  con inset y `devicePixelRatio`, misma tecnica que
  `VersionsWidget::refreshBranchIcons()` de PipeSync.

### `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ClipVersions.py`
- `pick_branch_version()`, `switch_clip_to_version()` — cambio de version
  acotado a la rama. Reemplaza las tres copias identicas de
  `get_highest_version` + `change_to_highest_version`.

### `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_S3VersionLister.py`
- `resolve_remote_context()`, `list_family_versions()`, `_default_lister()`,
  `_ensure_boto3_on_path()`. La funcion de listado es inyectable (`lister`)
  para testear sin red.

### `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_BranchDownloadPlan.py`
- `build_clip_branches()`, `aggregate_branch_options()`, `plan_downloads()`
- `write_intents()` / `read_intent()` / `clear_intent()` / `prune_intents()`
- `SELECTION_ALL`

### `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
- `ShotGridManager.find_highest_version_for_task(clip_version=...)`
- `ShotGridManager.find_branches_for_task()`
- `HieroOperations.local_versions_for_clip()`, `collect_other_branch_news()`,
  `build_branch_tooltip_cells()`, `get_branch_head_version()`,
  `change_to_branch_head()`, `add_row_to_table(branch_cells, is_other_branch)`
- `GUI_Table._row_matches_push()` — saltea filas informativas.
- `OTHER_BRANCH_STATUS_TEXT`

### `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
- `get_clip_versions_from_timeline()` — devuelve la cabeza de la rama.
- `PushVersionDialog` — detalle por rama.
- `show_flow_version_selection_dialog()` — etiqueta de rama por version.

### `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManager_DownloadClip.py`
- `BranchScanWorker` / `BranchScanSignals` — listado en hilo secundario.
- `BranchDownloadDialog` — opciones por teclas numericas.
- `_collect_clip_entries()`, `_apply_branch_scan()`, `_download_latest_legacy()`
- `get_intent_dir()`

### `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_DownloadClip_Watcher.py`
- `get_intent_dir()`, `_apply_intent()`, `_pick_version()`,
  `_switch_clip_to_version()`

### Pruebas
- `LGA_HieroTools/LGA_NKS_Shared/tests/test_version_branching.py` — la regla,
  las etiquetas, las familias y `compare_branches`.
- `LGA_HieroTools/LGA_NKS_Shared/tests/test_branch_download_plan.py` — listado
  remoto (con lister falso), opciones del dialogo, plan e intents.
- `LGA_HieroTools/LGA_NKS_Shared/tests/test_downloadclip_branch_wiring.py` —
  carga el modulo real de Download Clip con FileManager mockeado y verifica que
  las piezas esten conectadas (una rama sin dialogo, fallback a
  `--download-latest`, clip salteado sin `parent_local`).

Se corren con `python <archivo>` y no necesitan Hiero, Qt ni red.

Lo que **no** esta cubierto por tests y hay que probar a mano en Hiero: el
dialogo de ramas (Qt), las filas informativas del Pull, el icono/tooltip, y
todo lo que toca la API de Hiero (`setActiveVersion`, `VersionScanner`,
`reconnectMedia`).

### PipeSync / FileManager
- `C:\Portable\LGA_PipeSync_2\src\utils\VersionBranching.cpp` — la regla.
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_VersionsWidget.md` — seccion "Ramas de versiones".
- `C:\Portable\LGA_FileManager\src\s3Celery\S3Celery_ConflictChecker.cpp` — copia inline.
- `C:\Portable\LGA_FileManager\src\main.cpp` — `startCliDownloadLatestFolder()` /
  `startCliDownloadLatestFile()`, que siguen resolviendo el maximo global (es
  el fallback).
