> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Módulo LGA_Projects_Panel_SwitchSequence

## Resumen

Módulo auxiliar que implementa la **solución ganadora V3 Híbrida** para cambiar de secuencia en Hiero con preservación completa de estado del viewer.

## Solución Implementada

### 🎯 **V3 HÍBRIDA - La Mejor Opción**
- ✅ **Velocidad óptima:** 0.49s (más rápido que v4)
- ✅ **Ajustes completos preservados:** Gain/Gamma/Saturation + Playhead automático
- ✅ **Comportamiento nativo:** Reemplaza viewer como Hiero nativo
- ✅ **Sin duplicados:** Duplica y luego cierra viewer+timeline originales
- ✅ **Opcional:** Cierra TODOS los viewers+timelines viejos (flag `CLOSE_ALL_TIMELINES`)
- ✅ **UI completa:** Reduce panel + scroll automático
- ✅ **Logging por switch:** reinicia `DebugPy_ProjectsPanel.log` al inicio de cada cambio de timeline

Ademas, al terminar cada cambio de secuencia, el flujo desactiva el overlay de Frame Number (`Frame_Only`) del track `BurnIn` si estaba enabled. Este apagado no crea ni reposiciona el efecto.

El flujo tambien registra diagnostico post-event-loop para detectar freezes diferidos de Qt/Hiero: snapshots de viewers/timelines, widgets agendados con `deleteLater()`, duracion de `processEvents` / `DeferredDelete`, y una espera final que confirma si los widgets viejos desaparecieron realmente.

## API

### Función Principal

```python
switch_to_sequence(target_sequence_name)
```

**Parámetros:**
- `target_sequence_name` (str): Nombre de la secuencia objetivo

**Retorna:**
- `bool`: True si el cambio fue exitoso, False en caso contrario

**Características:**
- ✅ **Búsqueda inteligente:** Busca la secuencia en TODOS los proyectos abiertos
- ✅ **Cross-project:** Funciona perfectamente con secuencias de cualquier proyecto abierto
- ✅ **Cambio automático:** Cambia automáticamente al proyecto correcto cuando es necesario
- ✅ **Objetos Sequence directos:** Acepta objetos Sequence directamente (más eficiente y cross-project)
- ✅ **Detección de proyecto:** Identifica automáticamente a qué proyecto pertenece la secuencia
- ✅ **Preservación completa:** Gain/Gamma/Saturation + Playhead automático
- ✅ **Optimización UI:** Reduce panel + scroll al top track
- ✅ **Manejo de duplicados:** Duplica y luego cierra viewer+timeline originales (método refresh)
- ✅ **Cierre total de viewers+timelines:** Opcional con `CLOSE_ALL_TIMELINES = True`
- ✅ **Logging detallado:** Tiempos de ejecución y estado de operaciones
- ✅ **Shared logging integrado:** `LGA_NKS_Timeline_PreCleanup.py` y `LGA_NKS_ScrollTo_TopTrack.py` escriben en el mismo log del Projects Panel

## Uso en Panel de Proyectos

### Importación
```python
from LGA_Projects_Panel_SwitchSequence import switch_to_sequence
```

### Integración
```python
def on_sequence_click(self, sequence_name):
    """Manejador de click en secuencia"""
    try:
        success = switch_to_sequence(sequence_name)
        if success:
            print(f"✅ Secuencia '{sequence_name}' cambiada exitosamente")
            # Actualizar UI si es necesario
        else:
            print(f"❌ Error cambiando a secuencia '{sequence_name}'")
    except Exception as e:
        print(f"❌ Error: {e}")
```

## Logging actual

- Logger usado: `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectsPanel_Logging.py`
- Archivo de salida: `logs/DebugPy_ProjectsPanel.log`
- Flags por defecto:
  - `DEBUG = True`
  - `DEBUG_CONSOLE = False`
  - `DEBUG_LOG = True`
- El `.log` se reinicia una sola vez al comienzo de cada `switch_to_sequence_hybrid()`
- Los scripts shared de pre-cleanup y scroll reciben el `debug_print` del Projects Panel cuando son importados desde este flujo
- El switch loguea snapshots `[Widgets]` antes/despues de abrir/cerrar timelines, targets `[Targets]`, widgets agendados `[DeleteLater]`, ticks `[QtEvents]` y una espera `[CleanupWait]` para confirmar si los viewers/timelines viejos desaparecieron realmente
- El resumen final incluye `[Summary] Post-event cleanup wait`, que mide el tiempo posterior a las llamadas Python inmediatas y ayuda a detectar freezes diferidos de Qt/Hiero

## Compatibilidad

- ✅ **Nuke 15/16:** Usa `LGA_QtAdapter_HieroTools` para compatibilidad Qt
- ✅ **Hiero APIs:** Funciona con todas las versiones de Hiero
- ✅ **Fallbacks:** Incluye fallbacks para imports de Qt si el adapter no está disponible

## Configuración

### Flag opcional
- `CLOSE_ALL_TIMELINES = True` → Cierra todos los viewers+timelines viejos dejando solo el nuevo
- `CLOSE_ALL_TIMELINES = False` → Solo cierra viewer+timeline originales (comportamiento base)

### Flags de diagnostico
- `SWITCH_DIAGNOSTIC_LOG_WIDGETS = True` -> activa snapshots detallados de viewers/timelines en el log del Projects Panel
- `SWITCH_CLEANUP_WAIT_TIMEOUT = 8.0` -> maximo de espera diagnostica para verificar cierre real de widgets agendados
- `SWITCH_CLEANUP_WAIT_INTERVAL = 0.10` y `SWITCH_CLEANUP_LOG_INTERVAL = 0.50` -> frecuencia de procesamiento de eventos y de logs de pendientes durante la espera

## Dependencias

### Requeridas
- `hiero.core` y `hiero.ui` (APIs de Hiero)
- Proyecto abierto en Hiero con secuencias

### Opcionales (para UI completa)
- `LGA_NKS_Shared/LGA_NKS_Reduce_SeqWin.py` - Reduce panel izquierdo
- `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py` - Scroll al top track
- `LGA_NKS_Shared/LGA_NKS_Timeline_PreCleanup.py` - Limpieza previa de timeline

## Testing

### Verificación de Funcionalidad
1. Abrir proyecto con múltiples secuencias en Hiero
2. Ajustar viewer: Gain=0.5, Gamma=1.2, posicionar playhead
3. Ejecutar: `switch_to_sequence("nombre_secuencia")`
4. Verificar: Ajustes preservados, playhead correcto, UI optimizada

### Casos de Testing
- ✅ Secuencia ya activa (debe ser no-op)
- ✅ Primer cambio de secuencia
- ✅ Cambios múltiples entre secuencias ya abiertas
- ✅ Proyectos con una sola secuencia
- ✅ Cross-project entre proyectos diferentes

## Arquitectura

### Componentes
1. **Captura de Estado:** `_get_viewer_state()` - Gain/Gamma/Saturation
2. **Lógica Principal:** `switch_to_sequence_hybrid()` - Algoritmo completo
3. **Aplicación de Estado:** `_apply_viewer_settings()` - Restaura ajustes
4. **Frame Number Off:** `disable_frame_number_on_active_sequence()` - Busca `Frame_Only` en `BurnIn` y lo deshabilita sin crear ni reposicionar el efecto
5. **UI Helpers:** `reduce_sequence_window()`, `scroll_to_top_track()`

### Flujo de Ejecución
```
1. Verificar proyectos abiertos
2. Buscar secuencia objetivo
3. Verificar si ya está activa (optimización)
4. Capturar estado del viewer actual (gain/gamma/saturation)
5. Capturar viewer+timeline activos (originales)
6. Capturar playhead del viewer original
7. Cerrar viewer+timeline originales simultáneamente
8. Abrir nueva secuencia
9. Restaurar el playhead
10. Ejecutar pre-cleanup del timeline nuevo
11. Aplicar ajustes preservados
12. Optimizar UI (focus, reduce + scroll)
13. (Opcional) Cerrar TODOS los viewers+timelines viejos si `CLOSE_ALL_TIMELINES = True`
14. Aplicar LUT Rec.709 si existe
15. Desactivar Frame Number (`Frame_Only`) de la secuencia activa
```

### El orden importa: cerrar ANTES de abrir

Los pasos 7 y 8 estuvieron al revés hasta v2.31, y ese orden costaba entre 4 y 15
segundos de UI congelada por switch, de forma errática y sin relación con el
tamaño del timeline.

La causa: destruir el viewer+timeline viejos obliga a sincronizarse con los hilos
de IO que están leyendo la media de la secuencia recién abierta, y la destrucción
se queda esperándolos. Medido dentro de `sendPostedEvents(DeferredDelete)`: 13.7s
en un caso, 3.5s en otro. Los mismos widgets, destruidos sin nada cargando en
paralelo, cuestan 0.46s — incluso sobre una secuencia de 129 trackItems.

Cerrando primero no hay con qué competir. El flag `CLOSE_BEFORE_OPEN` conserva el
orden viejo por si hiciera falta volver atrás.

Dos consecuencias a tener presentes:

- **El playhead ya no se preserva solo.** `openInTimeline` lo hacía leyéndolo del
  viewer previo, que con este orden ya está cerrado. Por eso se captura con
  `_get_current_playhead()` y se repone con `_restore_playhead()`.
- **El cierre sigue siendo simultáneo.** Viewer y timeline se agendan juntos con
  `deleteLater()` y se destruyen en una sola pasada. Separarlos forzando la
  destrucción entre medio crashea Nuke Studio 16 (access violation en
  `QWidget::~QWidget` destruyendo hijos en cascada). Ese "equilibrio delicado" no
  es superstición: está verificado con dump.

## Logs y Debugging

### Output Normal (con debugging de UI)
```
🔄 Switch híbrido a '710-990'...
✅ Switch híbrido perfecto completado en 0.49s
   ├── Viewer capture: 0.000s
   ├── Close originals (viewer+timeline): 0.000s
   ├── Sequence open: 0.470s
   ├── Viewer settings apply: 0.002s
   ├── UI reduce: 0.002s
   ├── UI scroll: 0.001s
   ├── Close ALL old viewers+timelines: 0.000s (solo si CLOSE_ALL_TIMELINES = True)
   └── Total: 0.49s
Track NukeVFX eliminado: VFX-PROJA 1
Effect BurnIn extendido: Frame9 | 5881 -> 4638
Pre-cleanup finalizado | tracks eliminados: 1 | efectos BurnIn ajustados: 4
Usando método original (Nuke 15)
Posicion actual del scrollbar: -336
Scrolled to position -266.
```

### Casos Especiales
- **Ya activa:** `✅ Ya activa - sin cambios`
- **Error:** `❌ Error: Secuencia 'nombre' no encontrada`
- **Proyecto diferente:** `❌ Error: Secuencia '000' no encontrada` (limitación conocida)

## Problemas Conocidos

### ✅ **RESUELTO: Dos proyectos con secuencia del mismo nombre**

**Problema:** Si dos proyectos abiertos tienen secuencias con el mismo nombre (ej: "101" en PROJALT y "101" en PROJA), al clickear "101" de PROJA el switch era ignorado porque el check "Ya activa" comparaba solo el nombre sin considerar el proyecto. Devolvía "✅ Ya activa" aunque la activa fuera la del otro proyecto.

**✅ Solución (v2.28):** El check ahora compara también el proyecto usando `active_seq.project()`. Si el nombre coincide pero el proyecto difiere, el switch continúa hacia el proyecto correcto.

### ✅ **RESUELTO: Cambio entre Proyectos Diferentes**

**Problema original:** La función buscaba secuencias únicamente en el proyecto activo.

**Error anterior:**
```
🔄 Switch híbrido a '000'...
❌ Error: Secuencia '000' no encontrada
```

**✅ Solución implementada y probada:**
- ✅ **Objetos Sequence directos:** La función ahora acepta objetos Sequence directamente
- ✅ **openInTimeline cross-project:** Descubrimos que `hiero.ui.openInTimeline(sequence_obj)` funciona automáticamente incluso cross-project
- ✅ **Cambio automático:** Hiero cambia el proyecto activo automáticamente cuando abres una secuencia de otro proyecto
- ✅ **Sin intervención manual:** Todo funciona automáticamente sin necesidad de cerrar/abrir proyectos

**Resultado actual (probado y funcionando):**
```
🎯 Usando objeto Sequence directamente para '000'
   Proyecto: 'PROJB_SUP_v011'
   📊 Cambiando de proyecto 'PROJF_SUP_v050' → 'PROJB_SUP_v011'
   ✅ openInTimeline maneja el cambio automáticamente
✅ Switch híbrido perfecto completado
```

**Estado:** ✅ **COMPLETAMENTE RESUELTO Y PROBADO EN PRODUCCIÓN** - Funciona perfectamente cross-project, sin duplicados, con cambio automático de proyecto

## Próximos Pasos

Una vez probado y funcionando en la ventana de testing:

1. ✅ **Integrar en panel final** (`LGA_Projects_Panel.py`) - PENDIENTE
2. ✅ **Probar en producción** con casos reales - ✅ COMPLETADO
3. ✅ **Documentar** en documentación completa del panel - ✅ COMPLETADO
4. ✅ **Resolver limitación entre proyectos** - ✅ COMPLETADO (usando objetos Sequence directamente)

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_Projects_Panel_SwitchSequence.py` - `switch_to_sequence_hybrid()`, `disable_frame_number_on_active_sequence()`, `_apply_rec709_if_available()`, `reduce_sequence_window()`, `scroll_to_top_track()`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_ViewerTL_Panel_py\LGA_NKS_FrameNumber.py` - `find_frame_only_effect()`, `print_box_values()`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_NKS_Timeline_PreCleanup.py` - `main()`, `remove_nukevfx_tracks()`, `extend_burnin_to_last_visible()`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_NKS_ScrollTo_TopTrack.py` - `main()`, `scroll_to_position()`

## Referencias historicas

- [`DOCUMENTACION_COMPLETA_SWITCH_SEQUENCE.md`](../exploracion/DOCUMENTACION_COMPLETA_SWITCH_SEQUENCE.md) - Documentación técnica completa
- [`test_sequence_switch_v3.py`](../exploracion/test_sequence_switch_v3.py) - Script de testing original
- [`LGA_QtAdapter_HieroTools.py`](../LGA_QtAdapter_HieroTools.py) - Adapter Qt para compatibilidad
