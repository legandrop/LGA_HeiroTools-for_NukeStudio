# LGA_NKS_Flow_Shot_info

Muestra la informacion del shot y las versiones de la task seleccionada en el playhead, leyendo de `pipesync.db`.

Archivo: [LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py)

## Flujo general

1. Se resuelve la task del playhead (`comp` / `roto` / `cleanup`). Si hay varias tasks en el mismo frame, se abre `LGA_NKS_TaskSelectionDialog`, donde la task se elige con el mouse o con las teclas de atajo (1-9) que muestra cada botón.
2. Se obtiene el `project_name` del segmento `VFX-NOMBRE` de la ruta del clip (`extract_project_name_from_path`), con fallback al primer bloque del nombre del clip; el `shot_code` se parsea del nombre del clip. Ver [Docu_ProjectName_Extraction.md](Docu_ProjectName_Extraction.md).
3. Se consulta `pipesync.db` (`ShotGridManager`) y se arma una estructura `shot -> tasks -> versions -> comments -> replies`.
4. Si el timeline activo es un proyecto vendor (prefijo distinto al del clip) y el `Playlist Panel` esta registrado o el usuario es Master, se delega a `LGA_NKS_FlowPlaylist_Shot_info`.
5. La GUI (`GUIWindow`) lista cabecera del shot, descripcion, versiones, comentarios con thumbnails clickeables y replies anidados.

## Origen de los datos

Tablas usadas: `projects`, `shots`, `tasks`, `task_assignments`, `versions`, `version_notes`, `version_note_replies`. Detalle en [Documentacion_DB PipeSync.md](../LGA_NKS_Flow_Panel_py/Documentacion_DB%20PipeSync.md).

Mapeo:

| Campo UI | Origen DB |
| --- | --- |
| `shot_code` | `shots.shot_name` |
| `description` | `tasks.task_description` (de la task resuelta) |
| `assignee` | `task_assignments.assigned_to` |
| Version `version_number` | `versions.version_number` (formateado `vNNN`) |
| Version `created_by` | `versions.created_by` |
| Version `version_description` | `versions.description` |
| Version `version_date` | `versions.created_on` |
| Comment `user` | `version_notes.created_by` |
| Comment `text` | `version_notes.content` |
| Comment `date` | `version_notes.created_on` |
| Comment `attachments` | `version_notes.local_attachment_paths` (separados por `;`) |
| Reply `user` | `version_note_replies.created_by` |
| Reply `text` | `version_note_replies.content` |
| Reply `date` | `version_note_replies.created_on` |

## Hilos de comentarios

Si existe `version_note_replies`, cada reply se carga por `version_note_id` en orden cronologico y se muestra debajo de su comentario raiz. La linea vertical izquierda se aplica exclusivamente al contenedor `flowVersionCommentReply`; los labels de autor y contenido no reciben bordes propios.

## Filtro de notas auto-generadas por upload de version

PipeSync, al subir una version, escribe en paralelo:

- `versions.description` con el mensaje del review.
- `version_notes` con un registro de mismo `content`, mismo `created_by` y `created_on` cercano al de la version.

Para no mostrar ese comentario duplicado, en `find_shot` se descarta toda `version_note` que cumpla:

1. `note.created_by == version.created_by` (mismo autor, comparado tras `strip()`).
2. `note.content.strip() == version.description.strip()` (mismo texto exacto).
3. `abs(note.created_on - version.created_on) <= VERSION_DUPLICATE_NOTE_WINDOW_SECONDS`.

La constante `VERSION_DUPLICATE_NOTE_WINDOW_SECONDS` (default `600`, 10 minutos) vive en el modulo y se puede ajustar. Si alguna fecha no se puede parsear pero el resto coincide, la nota se considera duplicada.

Helpers involucrados en `LGA_NKS_Flow_Shot_info.py`:

- `_parse_pipesync_datetime(value)`: parsea el formato `YYYY-MM-DD HH:MM:SS[+/-HH:MM]` que guarda SQLite a `datetime` con tzinfo.
- `_is_version_upload_duplicate_note(note, version_description, version_created_by, version_created_on)`: aplica las tres reglas anteriores.

## Vendor dispatch

`should_redirect_to_playlist_shot_info()` decide si la ejecucion se delega al Playlist Shot Info. Condicion: prefijo de proyecto != prefijo de clip Y (Playlist Panel registrado O usuario Master segun `LGA_NKS_Playlist_Panel_Permissions.is_current_user_master`).

## Nota sobre prototipos standalone

El prototipo standalone `_prototype_shot_info.py` fue eliminado.

No reinstalar `PySide6`/`shiboken6` en `miniconda` ni en el user-site de Python para iterar esta UI. En Hiero/Nuke 15 eso puede contaminar el runtime Qt del host y provocar crash al abrir.

La UI productiva debe ejecutarse dentro de Hiero usando `LGA_QtAdapter_HieroTools`, que resuelve el binding Qt compatible con la version activa del host.

## Pendiente

- Mantener la UI productiva dentro de Hiero mediante `LGA_QtAdapter_HieroTools`; no usar prototipos standalone con PySide externo.
- Sumar la consulta a `task_timelogs` para calcular `Time logged` por version (regex `v0*N` en `description`, sumar `duration` en minutos).
- Filtrar tambien notas duplicadas por `content` exacto (segun PipeSync hace en `displayedNoteContents`).
