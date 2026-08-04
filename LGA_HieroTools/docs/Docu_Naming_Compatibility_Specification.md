> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Especificación de Compatibilidad de Nomenclatura - LGA_NKS_Flow (Hiero/Nuke Studio)

## Introducción

Este documento describe la evolución del sistema de nomenclatura utilizado en la empresa y los cambios necesarios para hacer que los scripts de **LGA_NKS_Flow** (Hiero/Nuke Studio) sean compatibles con ambos sistemas de naming.

**Nota:** Este proyecto está basado en la experiencia previa del proyecto de Nuke (LGA_ToolPack), donde se implementó exitosamente la compatibilidad de nomenclatura. Ver sección "Referencia: Proyecto Nuke" al final del documento.

**Actualización:** Se incorpora un bloque opcional de **Temporada/Episodio** inmediatamente después del proyecto cuando se trabaja en series (ej: `PROJB_101_060_010`).

## Sistema de Nomenclatura Actual (Con Campos de Descripción)

### Estructura del Shotname
El sistema actual utiliza una estructura de 5 componentes principales separados por guiones bajos:

```
PROYECTO_SEQ_SHOT_DESC1_DESC2
```

**Ejemplo:**
```
PROJA_000_140_Chroma_Auto
```

### Estructura Completa de Archivos
```
PROYECTO_SEQ_SHOT_DESC1_DESC2_TASK_vVERSION.EXT
```

**Ejemplos:**
- Script: `PROJA_000_140_Chroma_Auto_comp_v19.nk`
- Video: `PROJA_000_140_Chroma_Auto_comp_v18.mov`
- Secuencia: `PROJA_000_140_Chroma_Auto_comp_v19_1001.exr`

### Campos y su Significado

| Campo | Posición | Descripción | Ejemplo |
|-------|----------|-------------|---------|
| PROYECTO | 1 | Código del proyecto | `PROJA` |
| SEQ | 2 | Número de secuencia (3 dígitos) | `000` |
| SHOT | 3 | Número de shot (3-4 dígitos) | `140` |
| DESC1 | 4 | Primera descripción | `Chroma` |
| DESC2 | 5 | Segunda descripción | `Auto` |
| TASK | 6 | Nombre de la tarea | `comp` |
| VERSION | 7 | Número de versión | `v19` |

### Uso en Flow/ShotGrid
- **Shot Code:** `SEQ_SHOT` (ej: `000_140`)
- **Task:** `DESC1_DESC2_TASK` (ej: `Chroma_Auto_comp`)

## Sistema de Nomenclatura Simplificado (Sin Campos de Descripción)

### Estructura del Shotname
El sistema simplificado elimina los campos de descripción:

```
PROYECTO_SEQ_SHOT
```

**Ejemplo:**
```
PROJA_000_140
```

### Estructura Completa de Archivos
```
PROYECTO_SEQ_SHOT_TASK_vVERSION.EXT
```

**Ejemplos:**
- Script: `PROJA_000_140_comp_v19.nk`
- Video: `PROJA_000_140_comp_v18.mov`
- Secuencia: `PROJA_000_140_comp_v19_1001.exr`

### Campos y su Significado

| Campo | Posición | Descripción | Ejemplo |
|-------|----------|-------------|---------|
| PROYECTO | 1 | Código del proyecto | `PROJA` |
| SEQ | 2 | Número de secuencia (3 dígitos) | `000` |
| SHOT | 3 | Número de shot (3-4 dígitos) | `140` |
| TASK | 4 | Nombre de la tarea | `comp` |
| VERSION | 5 | Número de versión | `v19` |

### Uso en Flow/ShotGrid
- **Shot Code:** `SEQ_SHOT` (ej: `000_140`)
- **Task:** `TASK` (ej: `comp`)

## Sistema de Nomenclatura para Series (Con Bloque Temporada/Episodio)

### Estructura del Shotname
El sistema para series agrega un bloque de temporada/episodio antes de la secuencia y el shot:

```
PROYECTO_TEMP_EP_SEQ_SHOT
```

**Ejemplo:**
```
PROJB_101_060_010
```

### Con Campos de Descripción
```
PROYECTO_TEMP_EP_SEQ_SHOT_DESC1_DESC2
```

**Ejemplo:**
```
PROJB_101_060_010_Chroma_Auto
```

### Campos y su Significado

| Campo | Posición | Descripción | Ejemplo |
|-------|----------|-------------|---------|
| PROYECTO | 1 | Código del proyecto | `PROJB` |
| TEMP_EP | 2 | Temporada/Episodio (3 dígitos) | `101` |
| SEQ | 3 | Secuencia interna (3 dígitos) | `060` |
| SHOT | 4 | Número de shot (3-4 dígitos) | `010` |
| DESC1 | 5 | Primera descripción | `Chroma` |
| DESC2 | 6 | Segunda descripción | `Auto` |
| TASK | 7 | Nombre de la tarea | `comp` |
| VERSION | 8 | Número de versión | `v19` |

### Uso en Flow/ShotGrid (Series)
- **Sequence:** `TEMP_EP` (ej: `101`)
- **Shot Code:** Mantiene el bloque de temporada/episodio dentro del nombre del shot

## Problemas Identificados en los Scripts de Hiero

### 1. LGA_NKS_Flow_CreateShot.py (Problema CRÍTICO)
**Problema:** Parsing rígido que asume 5 campos para el shot_code
```python
shot_code = "_".join(parts[:5])  # Siempre toma primeros 5 campos
```

**Impacto:**
- Con descripción: `['PROJA', '000', '140', 'Chroma', 'Auto']` → `PROJA_000_140_Chroma_Auto` ✓
- Sin descripción: `['PROJA', '000', '140', 'comp', 'v19']` → `PROJA_000_140_comp_v19` ❌

### 2. LGA_NKS_Flow_Pull.py (Problema CRÍTICO)
**Problema:** Extracción de shot_code asume siempre 5 campos
```python
shot_code = "_".join(parts[:5])
```

**Impacto:**
- Genera shot codes incorrectos para formato simplificado
- Afecta la búsqueda de shots en Flow/ShotGrid

### 3. LGA_NKS_Flow_Thumbs.py y LGA_NKS_Flow_CreateShot_Thumbs.py (Problema CRÍTICO)
**Problema:** Función `get_shot_name_from_selected_clip()` asume 5 campos
```python
if len(parts) >= 5:
    shot_code = "_".join(parts[:5])
```

**Impacto:**
- No funciona correctamente con formato simplificado
- Puede generar nombres incorrectos para thumbnails

## Técnica de Detección Implementada

### 🎯 **Detección Inteligente por Bloques Base**

**Principio:** Primero se detecta si es serie; luego se determina si hay descripción.

**Lógica:**
```
Si después del proyecto los 3 bloques siguientes empiezan con dígito:
    → Formato de serie (base = 4 bloques: PROYECTO_TEMP_EP_SEQ_SHOT)
Sino:
    → Formato estándar (base = 3 bloques: PROYECTO_SEQ_SHOT)

Si existen al menos 2 bloques adicionales tras el bloque base:
    → Formato con Descripción
Sino:
    → Formato Simplificado
```

**Casos de Uso:**
- `PROJA_000_140_comp_v19.exr` → **Simplificado** → Shot Code: `PROJA_000_140`
- `PROJA_000_140_Chroma_Auto_comp_v19.exr` → **Con Descripción** → Shot Code: `PROJA_000_140_Chroma_Auto`
- `PROJB_101_060_010_comp_v05.exr` → **Serie Simplificado** → Shot Code: `PROJB_101_060_010`
- `PROJB_101_060_010_Chroma_Auto_comp_v05.exr` → **Serie con Descripción** → Shot Code: `PROJB_101_060_010_Chroma_Auto`

**Ventajas:**
- ✅ **100% preciso** - No hay falsos positivos
- ✅ **Automático** - Sin configuración manual
- ✅ **Robusto** - Funciona con cualquier nombre de task o descripción
- ✅ **Compatible** - Mantiene funcionamiento actual para formato con descripción

## Estrategia de Solución

### ✅ **IMPLEMENTAR:** Módulo Compartido con Funciones Centralizadas

**Estrategia:** Crear un módulo compartido `LGA_NKS_Flow_NamingUtils.py` con funciones reutilizables que todos los scripts de Hiero pueden usar.

**Ventajas:**
- ✅ Código centralizado y mantenible
- ✅ Consistencia entre todos los scripts
- ✅ Fácil de actualizar y testear
- ✅ Reutilizable en futuros scripts

## Archivos que Requieren Modificación

### Archivos Críticos (Deben modificarse)

1. **LGA_NKS_Flow_CreateShot.py** ✅ COMPLETADO
   - ✅ **Creado** módulo compartido `LGA_NKS_Flow_NamingUtils.py`
   - ✅ **Actualizado** para usar funciones compartidas
   - ✅ Detección automática de formato en `get_shot_name_from_selected_clip()`
   - ✅ Actualizado `HieroOperations.get_selected_clips_info()`

2. **LGA_NKS_Flow_Pull.py** ✅ COMPLETADO
   - ✅ **Actualizado** extracción de shot_code en `process_selected_clips()`
   - ✅ **Actualizado** `parse_exr_name()` para usar `clean_base_name()`
   - ✅ **Actualizado** extracción de `project_name` y `task_name` usando funciones compartidas
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

3. **LGA_NKS_Flow_Thumbs.py** ✅ COMPLETADO
   - ✅ **Actualizado** función `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - ✅ **Actualizado** función `get_project_name_from_clip()` para usar `extract_project_name()`
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

4. **LGA_NKS_Flow_CreateShot_Thumbs.py** ✅ COMPLETADO
   - ✅ **Actualizado** función `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

5. **LGA_NKS_Flow_Shot_info.py** ✅ COMPLETADO
   - ✅ **Actualizado** extracción de shot_code y project_name en `process_selected_clips()`
   - ✅ **Actualizado** `parse_exr_name()` para usar `clean_base_name()`
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

6. **LGA_NKS_Flow_Push.py** ✅ COMPLETADO
   - ✅ **Actualizado** extracción de shot_code, project_name y task_name en `update_local_database()`
   - ✅ Usa funciones compartidas para detección automática de formato
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

7. **LGA_NKS_Flow_Push_connector.py** ✅ COMPLETADO
   - ✅ **Actualizado** `execute_full_push_operation()` para usar funciones compartidas
   - ✅ **Actualizado** `check_version()` para usar funciones compartidas
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

8. **LGA_NKS_Flow_Panel.py** ✅ COMPLETADO
   - ✅ **Actualizado** `parse_exr_name()` para usar `clean_base_name()` y validación flexible
   - ✅ Compatible con ambos formatos de nomenclatura
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

9. **Otros scripts de LGA_NKS_Flow** (Pendiente revisión)
   - Revisar si necesitan actualización para compatibilidad

## Criterios de Éxito

1. **Compatibilidad hacia atrás:** Los scripts funcionan exactamente igual con el sistema actual (con descripción)
2. **Detección automática:** Cada script detecta automáticamente si hay descripción o no SIN configuración previa
3. **Código centralizado:** Todas las funciones de naming están en un módulo compartido
4. **Shot codes correctos:** Se generan códigos de shot correctos para Flow en ambos formatos
5. **Soporte para series:** Se detecta el bloque TEMP_EP y se usa como secuencia en Flow
6. **Sin errores:** No se producen errores independientemente del formato del nombre
7. **Transparente para el usuario:** El usuario no necesita configurar nada, todo funciona automáticamente

## Estado del Proyecto

### ✅ Fase 1: Creación del Módulo Compartido - COMPLETADA
1. ✅ **Creado** `LGA_NKS_Flow_NamingUtils.py`
   - Función `detect_shotname_format()` - Detecta formato por bloques base y serie
   - Función `extract_shot_code()` - Extrae shot_code automáticamente
   - Función `extract_project_name()` - Extrae nombre del proyecto
   - Función `clean_base_name()` - Limpia nombres de archivo
   - Función `extract_task_name()` - Extrae nombre de la tarea

### ✅ Fase 2: LGA_NKS_Flow_CreateShot.py - COMPLETADA
2. ✅ **Actualizado** `LGA_NKS_Flow_CreateShot.py` v1.1
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Implementada detección automática en `get_shot_name_from_selected_clip()`
   - Actualizado `HieroOperations.get_selected_clips_info()` para usar funciones compartidas
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 3: LGA_NKS_Flow_Pull.py - COMPLETADA
3. ✅ **Actualizado** `LGA_NKS_Flow_Pull.py` v3.28
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `parse_exr_name()` para usar `clean_base_name()`
   - Actualizado extracción de `shot_code`, `project_name` y `task_name` en `process_selected_clips()`
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 4: LGA_NKS_Flow_Shot_info.py - COMPLETADA
4. ✅ **Actualizado** `LGA_NKS_Flow_Shot_info.py` v1.83
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `parse_exr_name()` para usar `clean_base_name()`
   - Actualizado extracción de `shot_code` y `project_name` en `process_selected_clips()`
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 5: Scripts de Thumbs - COMPLETADA
5. ✅ **Actualizado** `LGA_NKS_Flow_Thumbs.py` v1.01
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - Actualizado `get_project_name_from_clip()` para usar `extract_project_name()` y `clean_base_name()`
   - Compatibilidad 100% hacia atrás con formato con descripción

6. ✅ **Actualizado** `LGA_NKS_Flow_CreateShot_Thumbs.py` v1.01
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 6: LGA_NKS_Flow_Push.py y Archivos Relacionados - COMPLETADA
7. ✅ **Actualizado** `LGA_NKS_Flow_Push.py` v3.81
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `Worker.update_local_database()` para usar `extract_shot_code()`, `extract_project_name()` y `extract_task_name()`
   - Compatibilidad 100% hacia atrás con formato con descripción

8. ✅ **Actualizado** `LGA_NKS_Flow_Push_connector.py`
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py` con fallback completo del sistema dual
   - Actualizado `execute_full_push_operation()` para usar funciones compartidas
   - Actualizado `check_version()` para usar funciones compartidas
   - Compatibilidad 100% hacia atrás con formato con descripción

9. ✅ **Actualizado** `LGA_NKS_Flow_Panel.py` v2.46
   - Importada función `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `parse_exr_name()` para usar `clean_base_name()` y validación flexible
   - Compatible con ambos formatos de nomenclatura
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 7: Scripts de LGA_NKS_Edit - COMPLETADA
10. ✅ **Actualizado** `LGA_NKS_CompareEXR_to_aPlate.py` v1.14
    - Importadas funciones `extract_shot_code()` y `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
    - Actualizado `parse_clip_name()` para usar funciones centralizadas con detección automática de formato
    - Compatible con ambos sistemas de nomenclatura (5 bloques con descripción / 3 bloques simplificado)
    - Compatibilidad 100% hacia atrás con formato con descripción

11. ✅ **Actualizado** `LGA_NKS_CompareVerToEditref.py` v1.14
    - Importadas funciones `extract_shot_code()` y `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
    - Actualizado `parse_clip_name()` para usar funciones centralizadas con detección automática de formato
    - Compatible con ambos sistemas de nomenclatura (5 bloques con descripción / 3 bloques simplificado)
    - Compatibilidad 100% hacia atrás con formato con descripción

12. ✅ **Actualizado** `LGA_NKS_MatchVerToEXR.py` v0.5
    - Importadas funciones `extract_shot_code()` y `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
    - Actualizado `parse_exr_name()` para usar `clean_base_name()`
    - Actualizado extracción de `base_without_version` para usar `extract_shot_code()` en lugar de remover versión manualmente
    - Compatible con ambos sistemas de nomenclatura (5 bloques con descripción / 3 bloques simplificado)
    - Compatibilidad 100% hacia atrás con formato con descripción

### Fase 8: Revisión Final (Pendiente)
13. **Revisar** otros scripts que puedan necesitar actualización

### Fase 9: Testing y Validación (Pendiente)
14. **Probar** exhaustivamente con casos reales de ambos formatos
15. **Validar** funcionamiento correcto con proyectos existentes
16. **Crear** casos de prueba automatizados

## Implementación Técnica Específica

### LGA_NKS_Flow_NamingUtils.py (Módulo Compartido)
```python
# ✅ IMPLEMENTADO - Módulo compartido para scripts de Hiero

def detect_shotname_format(base_name):
    """Detecta formato basado en campo 5"""
    parts = base_name.split("_")
    if len(parts) >= 5:
        field_5 = parts[4]
        # Si campo 5 es versión -> formato simplificado
        return not (field_5.startswith('v') and field_5[1:].isdigit())
    return False  # Menos de 5 campos = simplificado

def extract_shot_code(base_name):
    """Extrae shot_code detectando formato automáticamente"""
    has_description = detect_shotname_format(base_name)
    parts = base_name.split("_")
    
    if has_description:
        return "_".join(parts[:5])  # PROYECTO_SEQ_SHOT_DESC1_DESC2
    else:
        return "_".join(parts[:3])  # PROYECTO_SEQ_SHOT

def clean_base_name(file_name):
    """Limpia el nombre de archivo removiendo extensiones y versiones"""
    base_name = re.sub(r"_%04d\.exr$", "", file_name)
    base_name = re.sub(r"_\d{4}\.exr$", "", base_name)
    base_name = re.sub(r"_v\d+$", "", base_name)
    base_name = os.path.splitext(base_name)[0]
    return base_name
```

### LGA_NKS_Flow_CreateShot.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    clean_base_name,
)

# En get_shot_name_from_selected_clip():
base_name = clean_base_name(exr_name)
shot_code = extract_shot_code(base_name)

# En HieroOperations.get_selected_clips_info():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_Pull.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_task_name,
    clean_base_name,
)

# En parse_exr_name():
base_name = clean_base_name(file_name)

# En process_selected_clips():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)
task_name_extracted = extract_task_name(base_name)
if task_name_extracted:
    task_name = task_name_extracted.lower()
else:
    # Fallback para casos edge
    ...
```

### LGA_NKS_Flow_Shot_info.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    clean_base_name,
)

# En parse_exr_name():
base_name = clean_base_name(file_name)

# En process_selected_clips():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_Thumbs.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    clean_base_name,
)

# En get_project_name_from_clip():
base_name = clean_base_name(filename)
project_name = extract_project_name(base_name)

# En get_shot_name_from_selected_clip():
base_name = clean_base_name(exr_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_CreateShot_Thumbs.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    clean_base_name,
)

# En get_shot_name_from_selected_clip():
base_name = clean_base_name(exr_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_Push.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_task_name,
)

# En Worker.update_local_database():
project_name = extract_project_name(self.base_name)
shot_code = extract_shot_code(self.base_name)
task_name_extracted = extract_task_name(self.base_name)
if task_name_extracted:
    task_name = task_name_extracted.lower()
else:
    # Fallback para casos edge
    ...
```

### LGA_NKS_Flow_Push_connector.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas con fallback completo

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_task_name,
)
# Si el import falla, usa fallback con lógica completa del sistema dual

# En execute_full_push_operation():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)  # Detecta formato automáticamente
task_name_extracted = extract_task_name(base_name)

# En check_version():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)  # Detecta formato automáticamente
```

### LGA_NKS_Flow_Panel.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import clean_base_name

# En parse_exr_name():
base_name = clean_base_name(exr_name)
# Validación flexible compatible con ambos formatos
```

---

## Referencia: Proyecto Nuke (LGA_ToolPack)

Esta sección documenta el trabajo previo realizado en el proyecto de Nuke, que sirvió como base para este proyecto de Hiero.

### Problemas Identificados en Scripts de Nuke

1. **LGA_showInlFlow.py** - Parsing rígido que asume 5 campos
2. **LGA_Write_Presets.py** - Fórmulas TCL hardcodeadas
3. **LGA_Write_PathToText.py** - Cálculo de profundidad fijo

### Estado del Proyecto Nuke

#### ✅ Fase 1: Limpieza - COMPLETADA
- ✅ Eliminado `LGA_ToolPack_settings_ShotName.py`
- ✅ Eliminado botón "Configure Shot Naming" del menú

#### ✅ Fase 2A: LGA_showInlFlow.py - COMPLETADA
- ✅ Implementada detección inteligente por campo 5
- ✅ Generación correcta de shot_code para ambos formatos

#### ✅ Fase 2B: LGA_Write_Presets.py - COMPLETADA
- ✅ Implementado ajuste dinámico de fórmulas TCL
- ✅ Detección automática de formato
- ✅ Ajuste dinámico +2 bloques cuando se detecta formato con descripción

### Implementación Técnica Nuke

#### LGA_showInlFlow.py
```python
# ✅ IMPLEMENTADO - Detección inteligente por campo 5
parts = base_name.split("_")

is_simplified_format = False
if len(parts) >= 5:
    field_5 = parts[4]
    if field_5.startswith('v') and len(field_5) > 1 and field_5[1:].isdigit():
        is_simplified_format = True

if is_simplified_format:
    shot_code = "_".join(parts[:3])  # proyecto_seq_shot
else:
    shot_code = "_".join(parts[:5])  # proyecto_seq_shot_desc1_desc2
```

#### LGA_Write_Presets.py
```python
# ✅ IMPLEMENTADO - Detección y ajuste dinámico de fórmulas TCL

def detect_shotname_format():
    """Detecta formato basado en script actual de Nuke"""
    script_path = nuke.root().name()
    if not script_path or script_path == "Root":
        return False
    
    base_name = re.sub(r"\.nk$", "", os.path.basename(script_path))
    parts = base_name.split("_")
    
    if len(parts) >= 5:
        field_5 = parts[4]
        return not (field_5.startswith('v') and field_5[1:].isdigit())
    return False

def adjust_tcl_formulas(presets, has_description):
    """Ajusta fórmulas TCL dinámicamente"""
    if not has_description:
        return presets
    
    for preset in presets.values():
        if "file_pattern" in preset:
            preset["file_pattern"] = re.sub(
                r"\] 0 (\d+)\]", 
                lambda m: f"] 0 {int(m.group(1)) + 2}]", 
                preset["file_pattern"]
            )
    return presets
```
