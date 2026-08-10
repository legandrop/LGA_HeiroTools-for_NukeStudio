> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Plan de Implementación: Creación Automática del Soft Effect Frame_Only

## Objetivo

Implementar una funcionalidad en el script `LGA_NKS_FrameNumber.py` que verifique la existencia de un track llamado `BurnIn` y, en caso de que no contenga un soft effect llamado `Frame_Only`, lo cree con todas las propiedades necesarias.

### Funcionalidad Requerida

Si cuando se activa el script existe un track llamado `BurnIn` pero **no tiene un soft effect llamado `Frame_Only`**, debemos crearlo con las mismas propiedades que un `Frame_Only` existente, y con la misma duración que cualquier otro soft effect que esté en ese track llamado `BurnIn`.

## Pasos de Implementación

### Paso 1: Exploración ✅ COMPLETADO

**Script creado:** `LGA_NKS_FrameNumber_Explore.py`

Este script captura todas las propiedades del soft effect `Frame_Only` existente:
- Propiedades del `EffectTrackItem` (timeline, enabled, etc.)
- Todas las propiedades del nodo (121 knobs con sus valores)
- Información de duración y posición en el timeline
- Referencia de otros soft effects en el track

### Paso 2: Creación del Soft Effect ✅ COMPLETADO Y VALIDADO

**Script creado:** `LGA_NKS_FrameNumber_Create.py`

Este script:
- ✅ **Independiente**: Puede ejecutarse solo para pruebas
- ✅ **Auxiliar**: Está preparado para ser llamado desde el script maestro `LGA_NKS_FrameNumber.py` cuando no exista el soft effect
- ✅ **Función exportable**: Expone `create_frame_only_effect(seq=None, track=None)` para uso externo
- ✅ **Validado**: Funciona correctamente creando efectos con la duración adecuada

**Funcionalidad Implementada:**
1. ✅ Buscar el track `BurnIn` en la secuencia activa
2. ✅ Verificar si existe el soft effect `Frame_Only`
3. ✅ Si no existe:
   - ✅ Obtener la duración de otros soft effects en el track usando `get_track_duration_from_other_effects()`
   - ✅ Crear el efecto usando `track.createEffect()` con dos métodos:
     - **Método preferido**: `cloneFrom=existing_text2_effect` - Clona desde un efecto Text2 existente preservando todas las propiedades
     - **Método alternativo**: `effectType='Text2'` - Crea un nuevo efecto Text2 y configura todas las propiedades manualmente
   - ✅ Configurar todas las propiedades capturadas en el Paso 1 (42 propiedades configuradas exitosamente)
   - ✅ Configurar timeline In/Out según la duración obtenida de otros efectos
   - ✅ Configurar lifetime del nodo para que coincida con el timeline

**Resultados de las Pruebas:**
- ✅ Los efectos se crean correctamente con la duración adecuada (obtenida de otros efectos en el track)
- ✅ El método `cloneFrom` preserva todas las propiedades automáticamente
- ✅ El método `effectType` crea el efecto y configura todas las propiedades manualmente
- ✅ Ambos métodos funcionan correctamente y crean efectos con `timelineIn` y `timelineOut` correctos

### Paso 3: Integración 🔜 PENDIENTE

Una vez que el script de creación funcione correctamente, se integrará en `LGA_NKS_FrameNumber.py`:
- Al inicio del script, verificar si existe el soft effect
- Si no existe, llamar a la función de creación
- Continuar con el flujo normal del script

---

## Resultados de la Exploración

A continuación se muestran los resultados completos obtenidos del script de exploración:

### Propiedades del EffectTrackItem

```
Nombre: Frame_Only
Enabled: True
Timeline In: 0
Timeline Out: 461
Duración: 461 frames
Track: BurnIn
Tiene error: False
toString(): EffectTrackItem('Frame_Only', SubTrackItem('Text1( subTrackIndex=4, timelineIn=0, timelineOut=461 )'))
```

### Propiedades del Nodo

```
Nombre del nodo: Frame_Only
Clase del nodo: Text2
Total de knobs: 121
```

### Knobs Importantes Capturados

Los knobs más relevantes para recrear el efecto son:

#### Texto y Mensaje
- `message`: `"Frame: 1049"` (Multiline_Eval_String_Knob)
- `box`: `(280.5599795074472, 372.4884323840888, 767.5303935074476, 436.68261568408855)` (BBox_Knob)
- `xjustify`: `"left"` (Enumeration_Knob)
- `yjustify`: `"top"` (Enumeration_Knob)

#### Fuente
- `font`: `0.0` (FreeType_Knob)
- `font_size`: `91.0` (Array_Knob)
- `font_width`: `97.0` (Array_Knob)
- `font_height`: `85.0` (Array_Knob)
- `global_font_scale`: `0.9` (Array_Knob)

#### Color
- `color`: `[1.0, 0.7991074323654175, 0.0, 1.0]` (AColor_Knob) - Amarillo/naranja

#### Fondo
- `enable_background`: `True` (Boolean_Knob)
- `background_color`: `[0.0, 0.0, 0.0, 1.0]` (AColor_Knob) - Negro
- `background_opacity`: `0.94` (Array_Knob)
- `background_border_x`: `10.0` (Array_Knob)
- `background_border_y`: `5.0` (Array_Knob)

#### Sombras
- `enable_shadows`: `True` (Boolean_Knob)
- `shadow_color`: `[0.0, 0.0, 0.0, 1.0]` (AColor_Knob) - Negro
- `shadow_opacity`: `1.0` (Array_Knob)
- `shadow_angle`: `270.0` (Array_Knob)
- `shadow_distance`: `1.0` (Array_Knob)
- `shadow_softness`: `0.0` (Array_Knob)
- `shadow_size`: `1.0` (Array_Knob)

#### Transformaciones
- `translate`: `(0.0, 0.0)` (XY_Knob)
- `rotate`: `0.0` (Double_Knob)
- `scale`: `[1.0, 1.0]` (WH_Knob)
- `matrix`: `{0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1}` (Transform2d_Knob)

#### Lifetime
- `lifetimeStart`: `0.0` (Array_Knob)
- `lifetimeEnd`: `461.0` (Array_Knob)
- `useLifetime`: `True` (Boolean_Knob)

### Otros Soft Effects en el Track (Referencia de Duración)

```
- Frame2: In=0, Out=461, Duration=461
- Reso2: In=0, Out=461, Duration=461
- Fps: In=0, Out=461, Duration=461
- Drive2: In=0, Out=461, Duration=461
```

**Nota importante:** Todos los soft effects en el track tienen la misma duración (461 frames), desde el inicio (0) hasta el final (461). El nuevo `Frame_Only` debe crearse con esta misma duración.

---

## Notas Técnicas

### Script Auxiliar

El script `LGA_NKS_FrameNumber_Create.py` está diseñado para:
- Ser ejecutable de forma independiente para pruebas
- Ser importable como módulo desde el script maestro
- Exponer una función principal `create_frame_only_effect()` que puede ser llamada desde otros scripts

### Integración Futura

El script está listo para integrarse en `LGA_NKS_FrameNumber.py`. La integración se realizará de la siguiente manera:

```python
# Al inicio de print_box_values(), después de buscar el track y antes de buscar el efecto
if not target_clip:
    # Intentar crear el soft effect si no existe
    try:
        from LGA_NKS_ViewerTL.LGA_NKS_FrameNumber_Create import create_frame_only_effect
        created_effect = create_frame_only_effect(seq, target_track)
        if created_effect:
            target_clip = created_effect
            debug_print(f"✅ Soft effect '{CLIP_NAME}' creado exitosamente")
        else:
            debug_print("❌ No se pudo crear el soft effect 'Frame_Only'.")
            return
    except Exception as e:
        debug_print(f"❌ Error al crear el soft effect: {e}")
        return
```

**Ubicación de la integración:**
- Después de buscar el track `BurnIn`
- Después de buscar el soft effect `Frame_Only` en `subTrackItems()`
- Si no se encuentra, llamar a `create_frame_only_effect()`
- Si se crea exitosamente, continuar con el flujo normal del script

---

## Estado del Proyecto

- ✅ Paso 1: Exploración completada
- ✅ Paso 2: Creación del script completada y **VALIDADA** ✅
  - Script funciona correctamente
  - Crea efectos con duración adecuada
  - Configura todas las propiedades correctamente
  - Listo para integración
- ⏳ Paso 3: Integración (pendiente - listo para implementar)

## Notas sobre el Script de Creación

### Método de Creación Implementado

El script `LGA_NKS_FrameNumber_Create.py` usa `track.createEffect()` que es el método correcto según la exploración:

**Signatura de `createEffect()`:**
```python
createEffect(effectType=None, cloneFrom=None, copyFrom=None, trackItem=None, 
             timelineIn=None, timelineOut=None, subTrackIndex=None)
```

**Estrategia de Creación:**

✅ **COMPORTAMIENTO IMPLEMENTADO:**
- El script **SIEMPRE crea un efecto nuevo** usando `effectType='Text2'`
- **NO clona** otros efectos existentes (como "Frame1")
- Crea un efecto completamente nuevo e independiente llamado "Frame_Only"
- Configura manualmente todas las 42 propiedades capturadas en la exploración
- Configura el nombre del efecto y del nodo como "Frame_Only"

**Método de Creación:**
1. **Creación Nueva (`effectType='Text2'`):**
   - Usa `track.createEffect(effectType='Text2', timelineIn=..., timelineOut=...)`
   - Crea un efecto completamente nuevo e independiente
   - Configura todas las propiedades manualmente desde `EFFECT_PROPERTIES`
   - **Ventaja**: Crea un efecto nuevo, no una copia de otro efecto existente

**Nota:** Se eliminó la lógica de clonación (`cloneFrom`) para evitar crear copias de otros efectos. El script ahora siempre crea un efecto nuevo.

**Configuración de Duración:**
- Obtiene la duración de otros soft effects en el track usando `get_track_duration_from_other_effects()`
- Usa esa duración para `timelineIn` y `timelineOut` al crear el efecto
- Configura también el `lifetime` del nodo para que coincida

**Propiedades Configuradas:**
- ✅ 42 propiedades configuradas exitosamente
- ⚠️ El knob `font` se omite (usa valor por defecto del nodo, ya que requiere configuración especial)
- ✅ Todas las demás propiedades (texto, color, fondo, sombras, transformaciones, etc.) se configuran correctamente

### Notas Técnicas

- **Eliminación de efectos**: La eliminación de efectos mediante script tiene limitaciones en la API de Hiero, pero esto no afecta la funcionalidad principal ya que el objetivo es crear efectos, no eliminarlos.
- **Undo/Redo**: El script usa `project.beginUndo()` y `project.endUndo()` para que las operaciones sean reversibles.
- **Manejo de errores**: El script incluye manejo robusto de errores y mensajes de debug detallados.

---

## Avances Realizados

### ✅ Completado

1. **Script de Exploración** (`LGA_NKS_FrameNumber_Explore.py`):
   - Captura todas las propiedades del soft effect existente
   - Genera información detallada en formato JSON
   - Funciona correctamente

2. **Script de Creación** (`LGA_NKS_FrameNumber_Create.py`):
   - ✅ Crea efectos correctamente usando `track.createEffect()`
   - ✅ **SIEMPRE crea un efecto nuevo** (no clona otros efectos)
   - ✅ Usa la duración correcta de otros efectos en el track
   - ✅ Configura todas las propiedades (42 exitosas)
   - ✅ Funciona de forma independiente y como módulo auxiliar
   - ✅ Corregido: Eliminada la lógica de clonación que creaba copias de otros efectos

3. **Scripts de Exploración de API**:
   - `LGA_H-Explore_Create_EffectTrackItem.py` - Exploró cómo crear EffectTrackItem
   - `LGA_H-Explore_createEffect.py` - Exploró cómo usar `track.createEffect()`
   - Ambos scripts proporcionaron información valiosa sobre la API de Hiero

### 🔄 Pendiente

1. **Integración en Script Maestro**:
   - Integrar `create_frame_only_effect()` en `LGA_NKS_FrameNumber.py`
   - Probar el flujo completo end-to-end
   - Validar que funciona en diferentes escenarios

### 📝 Notas Adicionales

- La eliminación de efectos mediante script tiene limitaciones en la API de Hiero, pero esto no afecta la funcionalidad principal
- El script de creación está completamente funcional y listo para producción
- Todas las propiedades importantes se configuran correctamente
- El método de clonación es preferido porque preserva automáticamente todas las propiedades

---

**Nota:** Este documento será eliminado una vez que la implementación esté completa y validada.

