> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Trabajo con Hilos en Hiero - Guía de Referencia

Este documento explica cómo trabajar correctamente con hilos en scripts de Hiero/Nuke Studio para evitar bloquear el hilo principal de la UI.

**Nota:** Este documento refleja el estado actual de las mejores prácticas. No incluye historial de cambios ni logs de actualizaciones.

---

## El Problema: Bloqueo del Hilo Principal

Cuando ejecutas operaciones pesadas (conexiones a internet, procesamiento de datos, etc.) en el hilo principal de Hiero, la interfaz se congela y no responde hasta que termine la operación.

### ❌ Código que BLOQUEA (NO hacer):

```python
import threading

def procesar_clip():
    # Obtener clip en hilo principal (correcto)
    clip = get_clip_to_process()
    
    # Crear thread
    result_container = {}
    
    def run_in_thread():
        result_container["result"] = operacion_pesada(clip)
    
    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()  # ❌ BLOQUEA el hilo principal esperando
    
    # Procesar resultado
    resultado = result_container["result"]
```

**Problemas:**
- `thread.join()` bloquea el hilo principal esperando que termine el thread
- Con múltiples clips, se procesan secuencialmente (uno tras otro)
- La UI se congela durante el procesamiento

---

## La Solución: QRunnable y QThreadPool

Usa `QRunnable` y `QThreadPool` de PySide2 para procesamiento asíncrono que no bloquea el hilo principal.

### ✅ Código que NO BLOQUEA (Recomendado):

```python
from PySide2.QtCore import QRunnable, Slot, QThreadPool, Signal, QObject

class WorkerSignals(QObject):
    """Señales para comunicar resultados del worker"""
    result_ready = Signal(object)  # resultado
    error = Signal(str)  # mensaje de error


class MiWorker(QRunnable):
    """Worker para procesar en hilo secundario"""
    
    def __init__(self, datos):
        super(MiWorker, self).__init__()
        self.datos = datos
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        """Ejecuta la operación pesada en hilo secundario"""
        try:
            # Operación pesada aquí (conexión a internet, procesamiento, etc.)
            resultado = operacion_pesada(self.datos)
            self.signals.result_ready.emit(resultado)
        except Exception as e:
            self.signals.error.emit(str(e))


def procesar_clip():
    # Obtener clip en hilo principal (correcto)
    clip = get_clip_to_process()
    
    # Crear worker
    worker = MiWorker(clip)
    
    # Conectar señales para manejar resultados cuando lleguen
    def handle_result(resultado):
        # Manejar resultado en hilo principal
        print(f"Resultado: {resultado}")
    
    def handle_error(error_msg):
        print(f"Error: {error_msg}")
    
    worker.signals.result_ready.connect(handle_result)
    worker.signals.error.connect(handle_error)
    
    # Ejecutar en hilo separado SIN BLOQUEAR
    QThreadPool.globalInstance().start(worker)
    # ✅ La función termina inmediatamente, no espera
```

**Ventajas:**
- No bloquea el hilo principal
- Procesamiento asíncrono
- Múltiples workers pueden ejecutarse en paralelo
- La UI permanece responsive

---

## Patrón Completo: Procesar Múltiples Clips

Cuando necesitas procesar múltiples clips en paralelo:

```python
def procesar_multiples_clips():
    # Obtener clips en hilo principal (correcto)
    clips = get_clips_to_process(track_name="EXR", prioritize_multiple_selection=True)
    
    if not clips:
        return
    
    # Función para manejar resultados cuando lleguen
    def handle_result(resultado, clip_info):
        # Manejar resultado en hilo principal
        file_path, exr_name = clip_info
        print(f"Procesado: {os.path.basename(file_path)}")
        # Abrir URL, mostrar diálogo, etc.
    
    def handle_error(error_msg, clip_info):
        file_path, exr_name = clip_info
        debug_print(f"Error en {os.path.basename(file_path)}: {error_msg}")
    
    # Procesar todos los clips en paralelo
    for clip in clips:
        # Validar clip en hilo principal
        if not clip.source().mediaSource().isMediaPresent():
            continue
        
        fileinfos = clip.source().mediaSource().fileinfos()
        if not fileinfos:
            continue
        
        # Extraer información en hilo principal
        file_path = fileinfos[0].filename()
        exr_name = os.path.basename(file_path)
        clip_info = (file_path, exr_name)
        
        # Crear worker para este clip
        worker = MiWorker(clip_info)
        
        # Conectar señales
        worker.signals.result_ready.connect(
            lambda resultado, info=clip_info: handle_result(resultado, info)
        )
        worker.signals.error.connect(
            lambda error_msg, info=clip_info: handle_error(error_msg, info)
        )
        
        # Ejecutar sin bloquear
        QThreadPool.globalInstance().start(worker)
    
    # ✅ Todos los workers se ejecutan en paralelo
    # ✅ La función termina inmediatamente
    # ✅ Los resultados se manejan cuando llegan vía señales
```

---

## Reglas Importantes

### ✅ HACER:

1. **Obtener datos de Hiero en el hilo principal ANTES del worker:**
   ```python
   # ✅ Correcto
   clip = get_clip_to_process()  # En hilo principal
   fileinfos = clip.source().mediaSource().fileinfos()  # En hilo principal
   worker = MiWorker(fileinfos)  # Pasar datos al worker
   ```

2. **Usar señales para comunicar resultados:**
   ```python
   worker.signals.result_ready.connect(handle_result)
   ```

3. **Manejar UI en el hilo principal:**
   ```python
   def handle_result(resultado):
       # ✅ Abrir diálogos, mostrar mensajes, etc. en hilo principal
       dialog = QDialog()
       dialog.exec_()
   ```

### ❌ NO HACER:

1. **NO usar `thread.join()`:**
   ```python
   # ❌ Incorrecto
   thread.join()  # Bloquea el hilo principal
   ```

2. **NO acceder a objetos de Hiero desde el worker:**
   ```python
   # ❌ Incorrecto
   def run(self):
       clip = get_clip_to_process()  # NO hacer esto en el worker
   ```

3. **NO hacer operaciones pesadas en el hilo principal:**
   ```python
   # ❌ Incorrecto
   def procesar():
       resultado = conexion_internet_pesada()  # Bloquea UI
   ```

---

## Ejemplos de Referencia

### Scripts que implementan correctamente este patrón:

- **`LGA_NKS_Flow/LGA_NKS_Flow_Assignee.py`** - Obtiene asignados de ShotGrid
- **`LGA_NKS_Flow/LGA_NKS_Flow_ShowInFlow.py`** - Abre URLs de tasks en Flow

Ambos usan `QRunnable` y `QThreadPool` y no bloquean el hilo principal.

---

## Estructura Recomendada

```python
from PySide2.QtCore import QRunnable, Slot, QThreadPool, Signal, QObject

# 1. Definir señales
class WorkerSignals(QObject):
    result_ready = Signal(object)
    error = Signal(str)

# 2. Crear worker
class MiWorker(QRunnable):
    def __init__(self, datos):
        super(MiWorker, self).__init__()
        self.datos = datos
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        # Operación pesada aquí
        try:
            resultado = operacion_pesada(self.datos)
            self.signals.result_ready.emit(resultado)
        except Exception as e:
            self.signals.error.emit(str(e))

# 3. Usar el worker
def mi_funcion():
    # Obtener datos en hilo principal
    datos = obtener_datos_hiero()
    
    # Crear worker
    worker = MiWorker(datos)
    
    # Conectar señales
    worker.signals.result_ready.connect(manejar_resultado)
    worker.signals.error.connect(manejar_error)
    
    # Ejecutar sin bloquear
    QThreadPool.globalInstance().start(worker)
```

---

## Resumen

- ✅ Usa `QRunnable` y `QThreadPool` para operaciones pesadas
- ✅ Obtén datos de Hiero en el hilo principal antes del worker
- ✅ Usa señales para comunicar resultados
- ✅ Maneja UI en el hilo principal cuando lleguen los resultados
- ❌ NO uses `thread.join()` - bloquea el hilo principal
- ❌ NO accedas a objetos de Hiero desde el worker

Siguiendo este patrón, tus scripts no bloquearán la UI y funcionarán de forma fluida incluso con múltiples operaciones en paralelo.

