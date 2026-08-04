> **Regla de documentacion**: este archivo describe el mapeo real entre la UI esperada de `Shot Info` del Playlist Panel y las fuentes de datos disponibles.
> **Regla de documentacion**: este archivo debe mantenerse alineado con el schema real de `pipesync_playlists.db`, con el codigo de `FlowPlaylist_Shot_info.py` y con las decisiones del plan principal.

# LGA NKS Playlist ShotInfo Data Mapping

## Objetivo

Dejar documentado que el `Shot Info` del Playlist Panel puede reconstruirse con la data actual disponible en:

- `pipesync.db`
- `pipesync_playlists.db`

sin necesidad de ampliar schema para la lectura visual actual.

## Caso validado

Caso real validado:

- shot: `PROJA_2004_030`
- proyecto abierto en Hiero: `PROJALT_SUP_v004`
- proyecto real en `pipesync.db`: `PROJALT`
- playlist visible en captura: `PROJA - 2026.04.21`

## Conclusiones del analisis

La DB actual contiene la informacion necesaria para reconstruir:

- `Descripcion Tarea`
- `Descripcion Version`
- nombre de playlist
- fecha/hora de la aparicion en playlist
- autor de la subida/version
- notas principales
- replies
- attachments de nota
- attachments de reply
- frame number de attachments cuando existe

No hace falta ampliar schema para implementar el `Shot Info` de lectura.

## Fuente 1: pipesync.db

Se usa solo para el bloque superior del shot:

- `shots.shot_name`
- `tasks.task_description`

Query conceptual:

- buscar `shot_name`
- dentro del `project_name` real del shot
- tomar la task `Comp`
- leer `task_description`

Ejemplo validado:

- `task_description = "Mejorar union de peluca Susana."`

## Fuente 2: pipesync_playlists.db

### Playlist appearance / version block

Tabla principal:

- `playlist_versions`

Campos usados:

- `playlist_id`
- `version_sg_id`
- `version_code`
- `shot_code`
- `version_review_message`
- `version_created_at`
- `version_user`
- `client_approved_at`
- `client_approved_by`

Join requerido:

- `playlists.code`
- `playlists.created_at_flow`

Esto permite renderizar lineas del tipo:

```text
v001 | Subida por Nombre Apellido | ayer 3:03pm | playlist "PROJA - 2026.04.21"
Descripcion Version: fix peluca
```

### Notas principales

Tabla:

- `playlist_notes`

Campos usados:

- `playlist_id`
- `version_sg_id`
- `content`
- `author_name`
- `author_avatar_path`
- `created_at_flow`
- `sort_order`

Permite renderizar:

- autor
- fecha/hora
- texto principal de la nota

### Replies

Tabla:

- `playlist_note_replies`

Campos usados:

- `note_id`
- `content`
- `author_name`
- `author_avatar_path`
- `created_at_flow`
- `sort_order`

Permite renderizar replies indentados bajo la nota principal.

### Attachments

Tabla:

- `playlist_note_attachments`

Campos usados:

- `note_id`
- `reply_id`
- `parent_type`
- `display_name`
- `local_thumb_path`
- `local_file_path`
- `frame_number`
- `created_at_flow`
- `created_by_name`
- `sort_order`

## Hallazgo importante sobre attachments

Los adjuntos de notas y replies no se resuelven igual:

- attachments de nota: `playlist_note_attachments.note_id`
- attachments de reply: `playlist_note_attachments.reply_id`

Esto es critico.

Si una query mira solo `note_id`, se pierden los adjuntos que cuelgan de replies.

Caso real validado:

- nota principal con attachment en `frame 0`
- reply con attachment en `frame 50`

Por lo tanto, el `Shot Info` debe resolver ambos casos de forma separada.

## Multiples apariciones de la misma version

El schema actual permite mostrar varias apariciones de una misma version number si pertenecen a playlists distintas.

Caso real validado:

- `PROJA_2004_030_comp_v01` en playlist `PROJA - 2026.04.21`
- `PROJALT_2004_030_comp_v01` en playlist `PROJALT - 2026.04.20`

Ambas comparten:

- mismo `shot_code = PROJA_2004_030`

pero tienen:

- distinto `version_code`
- distinta playlist
- distinta fecha/contexto
- distintos comentarios/replies/attachments

Esto confirma que la UI del `Shot Info` no debe colapsar solo por `version number`.

## Regla de orden visual

Para `Shot Info` del Playlist Panel, el orden debe responder al contexto playlist:

- primero playlist mas reciente
- luego playlist mas vieja
- dentro de cada aparicion:
  - notas por `sort_order`, `created_at_flow`, `id`
  - replies por `sort_order`, `created_at_flow`, `id`
  - attachments por `sort_order`, `created_at_flow`, `id`

## Normalizacion de proyecto vendor

Para lookup vendor no alcanza con:

- `project_name` parseado del clip

ni con:

- `project.name()` crudo de Hiero

Porque en Hiero puede existir algo como:

- `PROJALT_SUP_v004`

y en DB el proyecto real es:

- `PROJALT`

Por eso `FlowPlaylist_Shot_info.py` debe (desde v0.02):

0. **Primario:** extraer `project_name` del segmento `VFX-NOMBRE` de la ruta del
   clip con `extract_project_name_from_path(file_path)`. Esta es la fuente de
   verdad: el folder en disco siempre lleva el nombre real del proyecto.
1. **Fallback:** resolver el proyecto del timeline activo
2. normalizarlo a `project_name` real de PipeSync
3. si tampoco hay contexto de timeline, caer al `project_name` parseado del filename
4. usar ese valor para buscar en `pipesync.db`

> El paso 0 cubre el caso en que el prefijo del shot no coincide con el nombre del
> proyecto (ej: shots `PROJA_...` que en realidad son del proyecto `PROJALT`).
> Ver `docs/Docu_ProjectName_Extraction.md`.

## Estado actual de implementacion

`FlowPlaylist_Shot_info.py` ya implementa:

- logging avanzado a archivo
- lookup vendor con `project_name` desde el path (`VFX-NOMBRE`) como primario,
  con fallback al proyecto del timeline normalizado y luego al parseado del filename
- `Descripcion Tarea` desde `pipesync.db`
- `Descripcion Version` desde `pipesync_playlists.db`
- notas desde `playlist_notes`
- replies desde `playlist_note_replies`
- attachments de nota y de reply desde `playlist_note_attachments`
- multiples apariciones de la misma version/shot en playlists distintas

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Playlist_Panel_py\LGA_NKS_FlowPlaylist_Shot_info.py`
  - `MainDbManager`
  - `PlaylistDbManager`
  - `HieroOperations::process_selected_clips()`
  - `HieroOperations::build_playlist_entries()`
  - `GUIWindow::create_shot_header_widget()`
  - `GUIWindow::create_version_widget()`
  - `GUIWindow::create_note_widget()`
  - `GUIWindow::create_reply_widget()`
  - `GUIWindow::create_thumbnails_widget()`
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_DB_Playlist.md`
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_Tab_Playlist.md`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\LGA_NKS_Playlist_Panel_Plan.md`
