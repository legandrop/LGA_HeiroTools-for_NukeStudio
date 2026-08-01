# Task Name Aliases — Patrón Canónico

**Fecha:** 2026-05-22  
**Afecta a:** todos los scripts que filtren clips por nombre de task o busquen tasks en la DB.

---

## El problema

Algunos proyectos publican archivos cuyo nombre de task en el filename **no coincide exactamente** con el nombre de la task en Flow/DB ni con el nombre del track en NukeStudio:

| Filename                          | Task en filename | Task en DB / Track |
|-----------------------------------|------------------|--------------------|
| `MOR_1048_060_Compo_v012.%04d.exr` | `compo`          | `comp` / `_comp_`  |

Esto provoca tres fallos en cascada:

1. **Filtro de clips:** `_comp_` no está en `_compo_`, el clip se descarta con `continue`.
2. **Búsqueda en DB:** `find_task(shot, "compo")` no encuentra nada → sin status, sin update.
3. **Mismatch dialog:** el check detecta `_compo_` vs `_comp_` y muestra una advertencia falsa.

---

## La solución

Definir aliases en un único lugar (`LGA_NKS_Flow_NamingUtils`) y aplicarlos explícitamente en cada script, **solo donde se procesa el nombre del clip** — nunca en la extracción global.

### Aliases definidos

```python
# LGA_NKS_Flow_NamingUtils.py
TASK_NAME_ALIASES = {
    "compo": "comp",
}
```

### Función disponible

```python
from LGA_NKS_Flow_NamingUtils import TASK_NAME_ALIASES, normalize_task_name

normalize_task_name("compo")  # → "comp"
normalize_task_name("Comp")   # → "comp"
normalize_task_name("roto")   # → "roto"  (sin alias, solo lowercase)
```

> `normalize_task_name` siempre devuelve lowercase. Si no hay alias, devuelve el nombre en lowercase sin cambios.

---

## Patrón de implementación — 4 puntos por script

### 1. Import

```python
from LGA_NKS_Flow_NamingUtils import TASK_NAME_ALIASES, normalize_task_name
```

### 2. Filtro de clips (filename check)

```python
# Antes
task_name_patterns = [t.strip("_") for t in TASK_EXR_TRACKS] + ["cmp"]
if not any(f"_{p}_" in exr_name.lower() for p in task_name_patterns):
    continue

# Después
task_name_patterns = [t.strip("_") for t in TASK_EXR_TRACKS] + ["cmp"] + list(TASK_NAME_ALIASES.keys())
if not any(f"_{p}_" in exr_name.lower() for p in task_name_patterns):
    continue
```

### 3. Extracción de task_name para búsqueda en DB

```python
# Antes
task_name_extracted = extract_task_name(base_name)
if task_name_extracted:
    task_name = task_name_extracted.lower()

# Después
task_name_extracted = extract_task_name(base_name)
if task_name_extracted:
    task_name = normalize_task_name(task_name_extracted)  # "compo" → "comp"
```

### 4. Wrapper para mismatch check / task selection dialog

```python
# Antes
collect_task_mismatches(..., extract_task_name, ...)

# Después
def _extract_task_normalized(base_name):
    raw = extract_task_name(base_name)
    return normalize_task_name(raw) if raw else raw

collect_task_mismatches(..., _extract_task_normalized, ...)
```

> Aplica igual para `resolve_task_with_mismatch_check` del Push.

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
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py` | ✅ Actualizado v3.43 |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py` | ✅ Actualizado v4.01 |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push_connector.py` | ✅ Actualizado v1.01 — proceso separado; normaliza task y agrega aliases inversos en task_tokens de búsqueda de versiones en Flow |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py` | 🔵 Analizado · no necesitaba cambio — task resuelta por track, no por filename |
| `LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py` | ✅ Actualizado v1.21 — `_extract_task_normalized` wrapper en `resolve_task_with_mismatch_check` |

### Assignee Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py` | ✅ Actualizado v1.25 — normalize_task_name aplicado a default_task en ShotTaskDiscoveryWorker.run() |
| `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py` | ✅ Actualizado v1.25 — ídem |
| `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py` | ✅ Actualizado v1.25 — ídem |

### Coordination Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py` | 🔵 Analizado · no necesitaba cambio — busca task "Comp" hardcodeado, no desde filename |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py` | 🔵 Analizado · no necesitaba cambio — no interactúa con task names |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py` | 🔵 Analizado · no necesitaba cambio — no filtra clips por task name ni busca en DB por task |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py` | 🔵 Analizado · no necesitaba cambio — ídem CreateShot |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py` | 🔵 Analizado · no necesitaba cambio — no usa task name en absoluto |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py` | 🔵 Analizado · no necesitaba cambio — no filtra clips por task name del filename |

### FileManagerS3 Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py` | 🔵 Analizado · no aplica — no usa task names |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py` | 🔵 Analizado · no aplica — no usa task names |
| `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_DownloadClip.py` | 🔵 Analizado · no aplica — descarga el archivo tal cual, sin interpretar task name |

### Edit Panel

| Script | Estado |
|--------|--------|
| `LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py` | ✅ Actualizado v0.81 — filtro `_comp_` expandido con aliases de `TASK_NAME_ALIASES` para no descartar clips `_Compo_` del track _comp_ |
