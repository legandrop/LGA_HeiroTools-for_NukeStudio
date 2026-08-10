> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Métodos de Selección de Clip en Scripts LGA_NKS

Este documento describe los dos métodos principales utilizados en los scripts para determinar sobre qué clip se está actuando.

**Nota:** Este documento refleja el estado actual de los scripts. No incluye historial de cambios ni logs de actualizaciones.

**Convención de nombres de tracks:** la lógica funcional de nombres del timeline está centralizada en [docs/Docu_Logica_Nombres_Tracks.md](/Users/leg4/.nuke/Python/Startup/docs/Docu_Logica_Nombres_Tracks.md). Este documento se enfoca en selección de clips; la semántica de `_comp_`, `_roto_`, `_cleanup_`, `_compRev_`, `_rotoRev_`, `_cleanupRev_` se documenta allí.

---

## Método 1: Clip Seleccionado (`te.selection()`)

### Descripción
Este método utiliza los clips que están actualmente seleccionados en el timeline de Hiero/Nuke Studio. Se obtiene mediante `te.selection()` donde `te` es el `TimelineEditor` de la secuencia activa.

### Ventajas
- Permite trabajar con múltiples clips a la vez
- El usuario tiene control explícito sobre qué clips procesar
- Funciona independientemente de la posición del playhead

### Desventajas
- Requiere que el usuario seleccione manualmente los clips
- Puede ser menos intuitivo cuando se quiere trabajar con el clip visible en el viewer

### Scripts que usan este método:

#### Scripts de Flow:
- **`LGA_NKS_Flow/LGA_NKS_Flow_Push.py`** - **Método Híbrido:** La función `push_from_selected_clips()` usa el módulo centralizado `LGA_NKS_GetClip` (permite selecciones múltiples). La función legacy `Push_Task_Status()` recibe `base_name` como parámetro (compatible con paneles que usan Método 1).
- **`LGA_NKS_Flow/LGA_NKS_Flow_Pull.py`** (línea 557) - `selected_clips = te.selection()` + usa `TRACK_comp_EXR` para filtrar tracks (v3.30)
- **`LGA_NKS_Flow/LGA_NKS_Flow_Thumbs.py`** (línea 52) - `selected_clips = timeline_editor.selection()`
- **`LGA_NKS_Flow/LGA_NKS_Flow_CreateShot_Thumbs.py`** (línea 70) - `selected_clips = timeline_editor.selection()`
- **`LGA_NKS_Flow/LGA_NKS_Flow_CreateShot.py`** (línea 136) - `selected_clips = timeline_editor.selection()`

#### Paneles:
- [x] **`LGA_NKS_Assignee_Panel.py`** - Usa `get_clips_to_process()` del módulo `LGA_NKS_GetClip` con `prioritize_multiple_selection=True` (método híbrido: selección múltiple prioritaria, playhead para selección simple)
- **`LGA_NKS_Coordination_Panel.py`** - Llama a scripts que usan selección

#### Scripts de NKS:
- **`LGA_NKS/LGA_NKS_Trim_In.py`** (línea 396) - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_Trim_Out.py`** (línea 295) - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_Compare_Versions.py`** (línea 25) - `selected_clips = te.selection()` + usa `TRACK_comp_EXR` para identificar track
- **`LGA_NKS/LGA_NKS_Compare_Versions_OFF.py`** - Usa `TRACK_comp_EXR` para identificar track
- **`LGA_NKS/LGA_NKS_OpenInNukeX.py`** (línea 335) - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_RevealInExplorer.py`** (línea 62) - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_RevealNK_Script.py`** (línea 44) - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_SelfReplaceClip.py`** (línea 164) - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_Reconnect.py`** (línea 94) - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_ON_Clips_OFF_v00-Clips.py`** - Procesa clips seleccionados o todos

#### Paneles de EditTools:
- **`LGA_NKS_Edit_Panel.py`** - Múltiples funciones usan `selected_clips = te.selection()`

---

## Método 2: Clip del Track que coincide con el Playhead (Método Híbrido Inteligente)

### Descripción
Este método obtiene la posición actual del playhead (`viewer.time()`) y busca el clip en el track especificado (por defecto `_comp_`, definido en `TRACK_comp_EXR`) que coincide con esa posición temporal. El clip se encuentra cuando `clip.timelineIn() <= current_time < clip.timelineOut()`.

**⚠️ IMPORTANTE:** El track por defecto ahora se llama `_comp_` (definido en `TRACK_comp_EXR`), anteriormente se llamaba `EXR`.

**Método Híbrido Inteligente Completo:**
1. **Lógica inteligente simple**: Si hay un solo clip seleccionado fuera del track objetivo pero del mismo shot, automáticamente usa el clip del track correcto (SIN mostrar mensaje al usuario)
2. **Lógica inteligente múltiple**: Analiza selecciones múltiples y devuelve exactamente un clip por shot único, priorizando clips del track objetivo
3. **Advertencia selectiva**: Solo muestra advertencia cuando la lógica inteligente NO puede resolver automáticamente el problema
4. **Primero intenta**: Obtener el clip del track especificado (por defecto `_comp_`) en la posición del playhead
5. **Fallback**: Si no encuentra clip en playhead, usa los clips seleccionados

### Ventajas
- **Más intuitivo**: trabaja con el clip visible en el viewer
- **Lógica inteligente silenciosa**: corrige automáticamente selecciones erróneas del mismo shot SIN molestar al usuario con mensajes innecesarios
- **Selección múltiple inteligente**: devuelve exactamente un clip por shot único, eliminando confusión cuando el usuario selecciona múltiples clips del mismo shot
- **Feedback inteligente**: solo muestra advertencias cuando REALMENTE hay un problema que no puede resolverse automáticamente
- No requiere selección manual (aunque tiene fallback inteligente)
- Permite trabajar rápidamente mientras se navega por el timeline
- Ideal para workflows donde siempre se trabaja con el mismo track (configurable mediante `TRACK_comp_EXR`)
- **Soporta selecciones múltiples avanzadas**: Si el script está configurado con `prioritize_multiple_selection=True` o usa `get_clips_to_process()`, aplica lógica inteligente para procesar múltiples shots correctamente

### Desventajas
- **En modo playhead por defecto**: Funciona con un clip a la vez (el clip visible en el viewer)
  - **EXCEPCIÓN**: Si el script permite selecciones múltiples (`prioritize_multiple_selection=True` o `get_clips_to_process()`) y hay múltiples clips seleccionados en el track, procesará todos esos clips en lugar de solo el del playhead
- Requiere que exista un track con el nombre especificado (por defecto `_comp_`, configurable en `TRACK_comp_EXR`)

### Scripts que usan este método:

- [x] **`LGA_NKS_Flow/LGA_NKS_Flow_Shot_info.py`** - Usa módulo centralizado `LGA_NKS_GetClip` con `track_name=None` (NO permite selecciones múltiples)
- [x] **`LGA_NKS_Flow/LGA_NKS_Flow_Push.py`** - Usa módulo centralizado `LGA_NKS_GetClip` con `track_name=None` en función `push_from_selected_clips()` (permite selecciones múltiples, con límite de 4 clips requiere confirmación)
- [x] **`LGA_NKS_Flow/LGA_NKS_Flow_ShowInFlow.py`** - Usa módulo centralizado `LGA_NKS_GetClip` con `track_name=None` (permite selecciones múltiples)
- [x] **`LGA_NKS_Assignee_Panel.py`** - Usa `get_clips_to_process()` del módulo `LGA_NKS_GetClip` con `prioritize_multiple_selection=True` (método híbrido: selección múltiple prioritaria, playhead para selección simple)
- [x] **`LGA_NKS_Flow/LGA_NKS_ReviewPic.py`** - Usa módulo centralizado `LGA_NKS_GetClip` con `track_name=None` (NO permite selecciones múltiples)
- [x] **`LGA_NKS/LGA_NKS_Clip_DisableEXR.py`** - Usa módulo centralizado `LGA_NKS_GetClip` (NO permite selecciones múltiples)
- [x] **`LGA_NKS_Edit/LGA_NKS_CompareEXR_to_aPlate.py`** - Usa módulo centralizado `LGA_NKS_GetClip` (permite selecciones múltiples)
- [x] **`LGA_NKS_Edit/LGA_NKS_CompareVerToEditref.py`** - Usa módulo centralizado `LGA_NKS_GetClip` con método híbrido para buscar clip en track REV (playhead primero, luego selección como fallback)
- [x] **`LGA_NKS/LGA_NKS_InOut_Editref.py`** - Usa módulo centralizado `LGA_NKS_GetClip` con método híbrido para buscar en track EditRef o EditRefClean
- [x] **`LGA_NKS/LGA_NKS_PrevNext_Rev.py`** - Usa módulo centralizado `LGA_NKS_GetClip` con método híbrido para buscar clips EditRef cuando la posición coincide con el playhead

**Leyenda:** 
- [x] = Usa módulo centralizado `LGA_NKS_GetClip`
- [ ] = Implementación manual
- **(permite selecciones múltiples)** = Usa `prioritize_multiple_selection=True` o `get_clips_to_process()` para procesar múltiples clips
- **(NO permite selecciones múltiples)** = Usa `prioritize_multiple_selection=False` (comportamiento por defecto) y procesa solo un clip a la vez

### Scripts que usan TRACK_comp_EXR directamente (no a través del módulo centralizado)

Estos scripts importan `TRACK_comp_EXR` del módulo `LGA_NKS_GetClip` pero hacen comparaciones directas con tracks en lugar de usar las funciones del módulo:

- [x] **`LGA_NKS/LGA_NKS_Compare_Versions.py`** - Importa `TRACK_comp_EXR` y lo usa para buscar el track (v1.2)
- [x] **`LGA_NKS/LGA_NKS_EXRTrack_Difference.py`** - Importa `TRACK_comp_EXR` y lo usa para alternar blend mode (v1.1)
- [x] **`LGA_NKS/LGA_NKS_Compare_Versions_OFF.py`** - Importa `TRACK_comp_EXR` y lo usa para desactivar blend mode

**Nota:** Estos scripts usan selección manual (Método 1) pero también necesitan identificar el track específico por nombre, por lo que importan `TRACK_comp_EXR` para mantener la centralización del nombre del track.

---

## Módulo Utilitario Centralizado: `LGA_NKS_GetClip`

### Ubicación
**`LGA_NKS_Utils/LGA_NKS_GetClip.py`**

Este módulo centraliza la funcionalidad de obtención de clips para evitar duplicación de código y facilitar el mantenimiento. Implementa el método híbrido recomendado.

### ⚠️⚠️⚠️ IMPORTANTE: Cambio de Nombre del Track ⚠️⚠️⚠️

**El track que antes se llamaba "EXR" ahora se llama "_comp_" y está definido en la variable `TRACK_comp_EXR`.**

**Información crítica:**
- **Nombre actual del track:** `_comp_`
- **Variable en el módulo:** `TRACK_comp_EXR = "_comp_"` (en `LGA_NKS_Utils/LGA_NKS_GetClip.py`)
- **Nombre anterior:** `"EXR"` (ya no se usa)
- **Contenido del track:** Contiene los archivos EXR con el render de COMP

**Track compRev:**
- **Nombre actual del track:** `_compRev_`
- **Variable en el módulo:** `TRACK_comp_REV = "_compRev_"` (en `LGA_NKS_Shared/LGA_NKS_GetClip.py`)
- **Nombres anteriores:** `"_rev_"`, `"REV"`, `"_compMov_"` (ya no se usan)
- **Contenido del track:** Contiene los archivos MOV o MXF con el render de COMP

**Es MUY IMPORTANTE verificar en los scripts que modificamos que:**
1. ✅ Usen la variable `TRACK_comp_EXR` del módulo
2. ✅ NO tengan hardcodeado `"EXR"` o cualquier otro nombre de track
3. ✅ Usen `track_name=None` en las llamadas a funciones para respetar `TRACK_comp_EXR`

**Si encuentras código hardcodeado con "EXR" o cualquier otro nombre de track, debe cambiarse para usar `track_name=None` y así respetar el valor actual `_comp_`.**

### ⚠️ IMPORTANTE: Revisar Hardcodeo de Nombre de Track

**Antes de migrar un script al módulo centralizado, es CRÍTICO revisar si tiene hardcodeado el nombre del track.**

**Problema común:**
- Muchos scripts tienen hardcodeado `track_name="EXR"` (o el nombre antiguo) en las llamadas a funciones
- Esto sobrescribe el `TRACK_comp_EXR` del módulo centralizado (actualmente `"_comp_"`)
- El script seguirá buscando en el nombre hardcodeado aunque cambies `TRACK_comp_EXR` a otro valor
- **Actualmente el track se llama `_comp_`, NO `EXR`**

**Solución:**
- **Usar `track_name=None`** o **no pasar el parámetro** para que use `TRACK_comp_EXR` del módulo
- **NO hardcodear** nombres de tracks como `track_name="EXR"` en las llamadas

**Ejemplo incorrecto:**
```python
# ❌ INCORRECTO: Hardcodea "EXR" (nombre antiguo), ignora TRACK_comp_EXR (actualmente "_comp_")
clip = get_clip_to_process(track_name="EXR")
# ❌ INCORRECTO: Hardcodea cualquier nombre, ignora TRACK_comp_EXR
clip = get_clip_to_process(track_name="_comp_")  # Aunque sea el nombre correcto, no debe hardcodearse
```

**Ejemplo correcto:**
```python
# ✅ CORRECTO: Usa TRACK_comp_EXR del módulo
clip = get_clip_to_process(track_name=None)
# O simplemente:
clip = get_clip_to_process()  # None es el valor por defecto
```

**Al migrar scripts existentes:**
1. Buscar todas las llamadas con `track_name="EXR"` o cualquier nombre hardcodeado
2. Cambiarlas a `track_name=None` o eliminar el parámetro
3. Verificar que el script ahora respete `TRACK_comp_EXR` del módulo

### Funciones Disponibles

#### `get_clip_to_process(track_name=None, prioritize_multiple_selection=False)`
**Función principal recomendada** - Implementa el método híbrido inteligente:
1. **Advertencia automática**: Si hay clips seleccionados en tracks que no son el objetivo, muestra mensaje informativo
2. **Lógica inteligente para selección simple**: Si hay un solo clip seleccionado fuera del track objetivo pero del mismo shot, automáticamente usa el clip del track correcto (con mensaje informativo)
3. Si `prioritize_multiple_selection=True` y hay múltiples clips seleccionados en el track, devuelve lista de esos clips
4. Si no, intenta obtener el clip del track especificado en la posición del playhead
5. Si no encuentra, usa el primer clip seleccionado como fallback

**Parámetros:**
- `track_name` (str, optional): Nombre del track a buscar. Si es `None`, usa `TRACK_comp_EXR` (actualmente `"_comp_"`)
- `prioritize_multiple_selection` (bool): Si `True` y hay múltiples clips seleccionados en el track especificado, 
  devuelve lista de esos clips. Si `False` (por defecto), procesa solo un clip a la vez usando playhead primero.

**Cuándo usar `prioritize_multiple_selection=True`:**
- Cuando tu script **permite procesar múltiples clips** a la vez (ej: abrir múltiples URLs, procesar batch)
- Cuando quieres que la selección múltiple tenga prioridad sobre el playhead

**Cuándo usar `prioritize_multiple_selection=False` (por defecto):**
- Cuando tu script **NO permite selecciones múltiples** y procesa solo un clip a la vez
- Cuando quieres priorizar el clip visible en el viewer (playhead)

**Retorna:**
- Clip encontrado, lista de clips (si `prioritize_multiple_selection=True` y hay múltiples), o `None` si no se encuentra ningún clip

**Ejemplos de uso:**
```python
# Track por defecto (TRACK_comp_EXR) - selecciones múltiples NO permitidas
clip = get_clip_to_process(track_name=None)  # o simplemente get_clip_to_process()

# Otro track específico (solo si es necesario)
clip = get_clip_to_process(track_name="REV")

# Permitir selecciones múltiples inteligentes
clips = get_clip_to_process(track_name=None, prioritize_multiple_selection=True)
# Lógica inteligente automática: devuelve exactamente un clip por shot único
# Ej: si seleccionás 5 clips de 3 shots diferentes → devuelve 3 clips óptimos
```

**Comportamiento inteligente:**
- **Selección simple:**
  - ✅ Si seleccionás un clip de otro track pero del mismo shot que el clip visible en `_comp_`, automáticamente usa el clip de `_comp_` (**SIN mensaje**, solo en logs)
  - ⚠️ Si los shots NO coinciden, muestra advertencia explicativa y usa el clip de `_comp_` (playhead)
  - 🔄 Si no hay clip en `_comp_`, usa el clip seleccionado como fallback inteligente

- **Selección múltiple:**
  - 🎯 **Análisis automático**: Se activa cuando hay múltiples clips seleccionados (independientemente del track)
  - ✅ **Un clip por shot**: Devuelve exactamente un clip por shot único (el mejor disponible)
  - 🔄 **Inclusión inteligente**: Incluye shots de otros tracks si no hay correspondencia en `_comp_`
  - 📝 **Logs detallados**: Muestra agrupación por shots y selección final

#### `find_clip_at_playhead_in_track(seq, track_name=None)`
Busca el clip en un track específico que coincide con la posición del playhead.

**Parámetros:**
- `seq`: Secuencia activa de Hiero
- `track_name` (str, optional): Nombre del track. Si es `None`, usa `TRACK_comp_EXR`

**Retorna:**
- Clip encontrado o `None`

#### `get_clips_to_process(track_name=None, prioritize_multiple_selection=False)`
Obtiene los clips a procesar usando el método híbrido. **Siempre devuelve una lista** (puede contener 0, 1 o más clips).

**Recomendado para scripts que procesan múltiples clips.** Usa esta función cuando necesites iterar sobre los clips.

**Características:**
- Muestra advertencia automática cuando hay clips seleccionados en tracks que no son el objetivo
- Filtra por track igual que `get_clip_to_process()`

**Parámetros:**
- `track_name` (str, optional): Nombre del track a buscar. Si es `None`, usa `TRACK_comp_EXR`
- `prioritize_multiple_selection` (bool): Si `True` y hay múltiples clips seleccionados en el track, devuelve lista de esos clips (permite selecciones múltiples)

**Retorna:**
- Lista de clips encontrados (puede estar vacía)

**Ejemplo de uso:**
```python
# Siempre devuelve lista con lógica inteligente aplicada automáticamente
clips = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)
# Aplica analyze_multiple_shots_selection() cuando hay múltiples clips seleccionados

for clip in clips:
    file_path = clip.source().mediaSource().fileinfos()[0].filename()
    # Procesar clip (uno por shot único)...
```

#### `get_selected_clips()`
Obtiene todos los clips seleccionados en el timeline (excluyendo efectos).

**Retorna:**
- Lista de clips seleccionados o lista vacía

#### `get_selected_clips_in_track(seq, track_name=None)`
Obtiene todos los clips seleccionados que pertenecen al track especificado.

**Parámetros:**
- `seq`: Secuencia activa de Hiero
- `track_name` (str, optional): Nombre del track. Si es `None`, usa `TRACK_comp_EXR`

**Retorna:**
- Lista de clips seleccionados en el track especificado (excluyendo efectos) o lista vacía

#### `extract_shot_code_from_clip(clip)`
Extrae el shot code de un clip usando las utilidades de naming compatibles con ambos formatos de nomenclatura.
Maneja errores gracefully si no hay media o el archivo no existe.

**Parámetros:**
- `clip`: Clip de Hiero del cual extraer el shot code

**Retorna:**
- `str`: Shot code extraído o cadena vacía si hay error

#### `analyze_multiple_shots_selection(all_selected_clips, track_name=None)`
Analiza selección múltiple inteligente: devuelve exactamente un clip por shot único.
Prioriza clips del track objetivo, pero incluye shots de otros tracks si no hay correspondencia.

**Parámetros:**
- `all_selected_clips`: Lista de todos los clips seleccionados
- `track_name` (str, optional): Nombre del track objetivo. Si es `None`, usa `TRACK_comp_EXR`

**Retorna:**
- Lista de clips óptimos (uno por shot único)


### Configuración

#### Variables de Configuración

**`TRACK_comp_EXR = "_comp_"`**
- Track por defecto para EXR de COMP
- **CRÍTICO:** Usar `track_name=None` para respetar este valor
- Cambiar aquí afecta a TODOS los scripts que usan `track_name=None`

**`TRACK_comp_REV = "_compRev_"`**
- Track por defecto para MOV/MXF de COMP
- Nombres anteriores: `"_rev_"`, `"REV"`, `"_compMov_"` (ya no se usan)

**`TRACK_roto_EXR = "_roto_"`**
- Track para EXR de la task ROTO

**`TASK_EXR_TRACKS = [TRACK_comp_EXR, TRACK_roto_EXR]`**
- Lista centralizada de todos los tracks de tasks EXR
- Usada por Flow Pull y Flow Push para operar sobre múltiples tasks
- Para agregar una nueva task: solo agregar su track aquí
- **No hardcodear** nombres de tasks en scripts — siempre referenciar esta lista
- Próxima task prevista: `_cleanup_`, que deberá sumarse aquí cuando exista `TRACK_cleanup_EXR`

**`DEBUG = False`**
- Controla mensajes de debug
- Modificar: `import LGA_NKS_GetClip as clip_utils; clip_utils.DEBUG = False`

### Cómo Usar en Nuevos Scripts

**Importación del módulo:**
```python
from pathlib import Path
import sys

# Agregar ruta del módulo utilitario
utils_path = Path(__file__).parent.parent / "LGA_NKS_Utils"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_GetClip import get_clip_to_process, get_clips_to_process
    import LGA_NKS_GetClip as clip_utils
    # Sincronizar debug si es necesario
    clip_utils.DEBUG = DEBUG  # Donde DEBUG es tu variable de debug
```

**Uso en el hilo principal:**

**Para scripts que NO permiten selecciones múltiples:**
```python
# ⚠️ IMPORTANTE: Usar track_name=None para respetar TRACK_comp_EXR del módulo
clip = get_clip_to_process(track_name=None)  # prioritize_multiple_selection=False por defecto

if not clip:
    print("No se encontró clip")
    return

# Procesar clip...
```

**Para scripts que permiten selecciones múltiples:**
```python
# ⚠️ IMPORTANTE: Usar track_name=None para respetar TRACK_comp_EXR del módulo
clips = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)

for clip in clips:
    # Procesar cada clip...
```

**⚠️ IMPORTANTE:** Las funciones de este módulo **deben ejecutarse en el hilo principal** de Hiero. Si tu script usa threading, obtén el clip ANTES de crear el hilo secundario.

---

## Scripts que usan el módulo LGA_NKS_GetClip

### Funciones principales del módulo:

#### `get_clip_to_process(track_name=None, prioritize_multiple_selection=False)`
**Procesamiento de un clip a la vez (método híbrido inteligente)**

- **`LGA_NKS_Flow/LGA_NKS_Flow_Shot_info.py`** - `track_name=None`, `prioritize_multiple_selection=False`
- **`LGA_NKS_Flow/LGA_NKS_ReviewPic.py`** - `track_name=None`, `prioritize_multiple_selection=False`
- **`LGA_NKS/LGA_NKS_Clip_DisableEXR.py`** - `track_name=None`, `prioritize_multiple_selection=False`
- **`LGA_NKS/LGA_NKS_InOut_Editref.py`** - Método híbrido con track EditRef
- **`LGA_NKS/LGA_NKS_PrevNext_Rev.py`** - Método híbrido con track EditRef
- **`LGA_NKS_Edit/LGA_NKS_CompareVerToEditref.py`** - Método híbrido con track REV

#### `get_clips_to_process(track_name=None, prioritize_multiple_selection=False)`
**Procesamiento de múltiples clips (siempre devuelve lista)**

- **`LGA_NKS_Assignee_Panel.py`** - `track_name=None`, `prioritize_multiple_selection=True` (método híbrido prioritario)
- **`LGA_NKS_Flow/LGA_NKS_Flow_ShowInFlow.py`** - `track_name=None`, `prioritize_multiple_selection=True`
- **`LGA_NKS_Flow/LGA_NKS_Flow_Push.py`** - `push_from_selected_clips()` usa `track_name=None`, `prioritize_multiple_selection=True`
- **`LGA_NKS_Edit/LGA_NKS_CompareEXR_to_aPlate.py`** - `track_name=None`, permite selecciones múltiples

### Scripts que importan TRACK_comp_EXR directamente:
**Usan el módulo solo para la variable centralizada, no las funciones:**

- **`LGA_NKS/LGA_NKS_Compare_Versions.py`** - Importa `TRACK_comp_EXR` para identificar track
- **`LGA_NKS/LGA_NKS_EXRTrack_Difference.py`** - Importa `TRACK_comp_EXR` para alternar blend mode
- **`LGA_NKS/LGA_NKS_Compare_Versions_OFF.py`** - Importa `TRACK_comp_EXR` para desactivar blend mode

### Scripts que usan `te.selection()` directamente:
**No usan el módulo centralizado:**

- **`LGA_NKS_Flow/LGA_NKS_Flow_Pull.py`** - `selected_clips = te.selection()` + TRACK_comp_EXR
- **`LGA_NKS_Flow/LGA_NKS_Flow_Thumbs.py`** - `selected_clips = timeline_editor.selection()`
- **`LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`** - `selected_clips = timeline_editor.selection()`
- **`LGA_NKS_Flow/LGA_NKS_Flow_CreateShot_Thumbs.py`** - `selected_clips = timeline_editor.selection()`
- **`LGA_NKS/LGA_NKS_Trim_In.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_Trim_Out.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_Compare_Versions.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_OpenInNukeX.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_RevealInExplorer.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_RevealNK_Script.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_SelfReplaceClip.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_Reconnect.py`** - `selected_clips = te.selection()`
- **`LGA_NKS/LGA_NKS_ON_Clips_OFF_v00-Clips.py`** - Procesa clips seleccionados o todos
- **`LGA_NKS_Edit_Panel.py`** - Múltiples funciones usan `selected_clips = te.selection()`

---

## Recomendación

**Se recomienda usar el módulo utilitario `LGA_NKS_GetClip`** que implementa el Método 2 (playhead en track especificado por `TRACK_comp_EXR`, actualmente `_comp_`) con fallback a selección porque:
- ✅ **Código centralizado**: Evita duplicación y facilita el mantenimiento
- ✅ **Configuración flexible**: Permite cambiar el track por defecto fácilmente
- ✅ **Más intuitivo**: Trabaja con el clip visible en el viewer
- ✅ **Rápido**: Permite trabajar sin necesidad de seleccionar clips manualmente
- ✅ **Compatible**: Mantiene fallback a selección manual cuando es necesario
- ✅ **Consistente**: Comportamiento uniforme en todos los scripts que lo usan

**Para nuevos scripts:** Usa `get_clip_to_process()` del módulo `LGA_NKS_GetClip` en lugar de implementar la lógica manualmente.

---

## Implementación Manual (Solo Referencia)

**No recomendado - usar el módulo `LGA_NKS_GetClip` en su lugar.**

**Obtener playhead:**
```python
viewer = hiero.ui.currentViewer()
current_time = viewer.time()
```

**Buscar clip en track:**
```python
for track in seq.videoTracks():
    if track.name() == "EXR":  # Usar TRACK_comp_EXR
        for clip in track:
            if not isinstance(clip, hiero.core.EffectTrackItem):
                if clip.timelineIn() <= current_time < clip.timelineOut():
                    return clip
```

**Clips seleccionados:**
```python
te = hiero.ui.getTimelineEditor(seq)
selected_clips = te.selection()
```
