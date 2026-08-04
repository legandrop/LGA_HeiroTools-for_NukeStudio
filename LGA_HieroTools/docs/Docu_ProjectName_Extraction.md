# Extracción de Project Name (y Sequence) desde el path — Patrón Canónico

**Fecha:** 2026-05-22 (extendido 2026-06-13: Playlist Panel + Edit/CreateV000 + sequence desde el path en CreateShot/ModifyShot)  
**Afecta a:** todos los scripts que busquen shots/tasks en la DB de PipeSync usando `project_name`, y los que asignen `sg_sequence` al crear/modificar shots en Flow.

---

## El problema

El método histórico extraía el nombre del proyecto del primer bloque del filename:

```
PROJA_1048_060_Compo_v012.%04d.exr  →  "PROJA"
```

Esto falla cuando el proyecto tiene nombre largo en la DB pero un prefijo corto en los shots:

| Folder en disco  | En DB      | Desde filename |
|------------------|------------|----------------|
| `VFX-PROJALT`    | `PROJALT`  | `PROJA` ❌        |
| `VFX-PROJF`       | `PROJF`     | `PROJF` ✓ (coincide de casualidad) |
| `VFX-PROJE`      | `PROJE`    | `PROJE` ✓      |

El resultado: `find_shot("PROJA", ...)` no encuentra nada aunque el shot exista en la DB como proyecto `PROJALT`.

---

## La solución

Los proyectos **siempre** viven en una carpeta raíz con el patrón `VFX-NOMBRE`:

```
T:/VFX-PROJALT/101/PROJA_1048_060/Comp/4_publish/...
     ^^^^^^^^^^
     segmento con prefijo "VFX-"
```

El nombre del proyecto en la DB es el segmento **sin el prefijo `VFX-`**:

```
"VFX-PROJALT"  →  "PROJALT"
"VFX-PROJF"     →  "PROJF"
"VFX-PROJG"     →  "PROJG"
```

---

## Funciones disponibles en `LGA_NKS_Flow_NamingUtils`

```python
from LGA_NKS_Flow_NamingUtils import extract_project_name_from_path, extract_project_name

# Primario: desde la ruta del archivo
project_name = extract_project_name_from_path(file_path)

# Fallback: desde el nombre base del archivo (comportamiento histórico)
if not project_name:
    project_name = extract_project_name(base_name)
```

### `extract_project_name_from_path(file_path)`
- Recorre los segmentos de la ruta normalizada.
- Devuelve el texto después del primer `VFX-` (case-insensitive).
- Devuelve `None` si no encuentra el patrón → usar fallback.

### `extract_project_name(base_name)` _(fallback)_
- Devuelve el primer bloque del nombre base antes del primer `_`.
- Comportamiento original, sin cambios.

---

## Extensión: Sequence Name desde el path

El mismo problema aplica a la **secuencia**. Históricamente la secuencia para Flow
(`sg_sequence`) se tomaba del **nombre del timeline de Hiero** (`seq.name()`), que
puede no coincidir con el code de la Sequence en Flow (ej. un timeline llamado
`PROJALT_SUP_v004`).

La estructura en disco **siempre** es `…/VFX-PROYECTO/SECUENCIA/SHOT/…`, así que la
secuencia es el segmento que **sigue inmediatamente** al `VFX-NOMBRE`:

```
T:/VFX-PROJALT/101/PROJA_1048_060/Comp/4_publish/...
                ^^^
                segmento de secuencia
```

```python
from LGA_NKS_Flow_NamingUtils import extract_sequence_name_from_path

# Primario: segmento despues de VFX-NOMBRE
sequence_name = extract_sequence_name_from_path(file_path)

# Fallback: nombre del timeline de Hiero (comportamiento anterior)
if not sequence_name:
    sequence_name = seq.name()
```

### `extract_sequence_name_from_path(file_path)`
- Busca el segmento `VFX-*` y devuelve el **siguiente** segmento de la ruta.
- Devuelve `None` si no hay `VFX-*` o no hay segmento siguiente → usar fallback.

> Nota: **Pull / Push no usan secuencia** — buscan shots existentes por
> `(project_name, shot_code)`, y el `shot_code` ya trae el bloque SEQ desde el
> filename. La secuencia para Flow solo se asigna al **crear/modificar** shots
> (`CreateShot`, `ModifyShot`).

---

## Patrón de implementación

Buscar en cada script el bloque donde se extrae `project_name` y reemplazarlo:

### Antes
```python
project_name = extract_project_name(base_name)
debug_print(f"Project name: {project_name}")
```

### Después
```python
project_name = extract_project_name_from_path(file_path)
if project_name:
    debug_print(f"Project name (from path): {project_name}")
else:
    project_name = extract_project_name(base_name)
    debug_print(f"Project name (from filename fallback): {project_name}")
```

> `file_path` es la ruta completa del archivo del clip (obtenida antes de este punto en todos los scripts existentes).

---

## Scripts — estado de análisis

Leyenda:
- ✅ **Analizado · necesitaba cambio → aplicado**
- 🔵 **Analizado · no necesitaba cambio**
- ⬜ **Sin analizar todavía**

---

### Flow Pull / Push / Info

| Script | Estado |
|--------|--------|
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py` | ✅ Actualizado v3.44 |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py` | ✅ Actualizado v4.01 |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push_connector.py` | ✅ Actualizado v1.01 — proceso separado; recibe file_path vía JSON |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py` | ✅ Actualizado v1.92 — fix en `process_selected_clips()` |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py` | 🔵 Analizado · no necesitaba cambio — solo cache local, no extrae project_name |

### Assignee Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py` | ✅ Actualizado v1.25 — file_path propagado desde panel v1.56; ShotTaskDiscoveryWorker extrae project_name desde VFX-NOMBRE del path |
| `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py` | ✅ Actualizado v1.25 — ídem |
| `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py` | ✅ Actualizado v1.25 — ídem |

### Coordination Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py` | ✅ Actualizado v1.29 — 3 call sites: `HieroOperations.process_clip()`, `ShowInFlowWorker.run()`, `ShowShotInFlowWorker.run()` |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py` | ✅ Actualizado v1.02 — fix en `get_project_name_from_clip()` |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py` | ✅ project_name v1.36 (`get_selected_clips_info()`); **sequence v1.37** — `create_shot()` toma `sg_sequence` del segmento post-`VFX-` por clip (`get_active_sequence_name(file_path)` para el default del diálogo) |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py` | ✅ project_name hereda de CreateShot v1.36; **sequence v1.36** — `get_active_sequence_name(clip_info["file_path"])` |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py` | ✅ Actualizado v1.01 — fix en `_collect_shots_from_track()` |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py` | ✅ Actualizado v1.01 — fix en `get_selected_clips_info()` |

### FileManagerS3 Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py` | 🔵 Analizado · no aplica — pasa shot_path directo al CLI de FileManagerS3 |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py` | 🔵 Analizado · no aplica — ídem |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_DownloadClip.py` | 🔵 Analizado · no aplica — pasa file_path directo al CLI |

### Edit Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py` | 🔵 Analizado · no aplica — no interactúa con Flow ni DB, solo compara versiones dentro de Hiero |
| `LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py` | ✅ Actualizado v1.08 — fix en `_collect_context()`; usa `default_plate["media_path"]` |

### Playlist Panel

> El Playlist Panel es un panel WIP (todos sus scripts en título `v0.01`). Su
> changelog interno hereda numeración de los scripts Flow originales; las entradas
> propias del panel arrancan en `v0.02`.

| Script | Estado |
|--------|--------|
| `LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Pull.py` | ✅ Actualizado v0.02 — `file_path` ya estaba en scope del loop de clips |
| `LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Push.py` | ✅ Actualizado v0.02 — `file_path` propagado por `InputDialog`, `Worker`, `Push_Task_Status` y `push_from_selected_clips`; fix en `get_shot_assignee()` y `update_local_database()` |
| `LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Push_connector.py` | ✅ Actualizado v0.02 — proceso separado; recibe `file_path` vía JSON en `execute_full_push` y `check_version`. ⚠️ Nota: `FlowPlaylist_Push.py` apunta su `connector_script` a `LGA_NKS_Flow_Push_connector.py` (nombre inexistente en la carpeta del panel) — bug preexistente del panel WIP, no relacionado con este cambio |
| `LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Shot_info.py` | ✅ Actualizado v0.02 — path como primario; fallback a nombre del timeline / filename en `process_selected_clips()` |
| `LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_ReviewPic.py` | 🔵 Analizado · no necesitaba cambio — solo cache local, no extrae project_name (espejo de `LGA_NKS_ReviewPic.py`) |

---

## Proyectos confirmados en DB (al 2026-05-22)

```
PROJF, PROJB, PROJG, PROJA, PROJALT, PROJE, TEST, PROJH
```

> Nota: `PROJA` existe en la DB como proyecto separado. No confundir con el prefijo
> de los shot codes del proyecto `PROJALT` (cuyos shots empiezan con `PROJA_`).
