> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# 🚀 Guía del Sistema de Logging Avanzado

## 📋 Descripción General

Esta guía documenta cómo implementar un sistema de logging robusto que escribe exclusivamente a un archivo `.log` sin contaminar la consola. En este repo conviven **dos variantes**: una con timer y limpieza por ejecución, y otra con hora + limpieza diaria.

## 🎯 Características del Sistema

- ✅ **Solo archivo**: No propaga mensajes a consola
- ✅ **Timestamps relativos**: Contador desde 0.000s
- ✅ **Limpieza automática**: Borra el log anterior al iniciar
- ✅ **Encabezado con fecha y hora**: Primera línea en logs por ejecución
- ✅ **Logging asíncrono**: No bloquea la ejecución
- ✅ **Múltiples niveles**: DEBUG, INFO, WARNING, ERROR
- ✅ **Nombres específicos**: `debugPy_NombreScript.log`
- ✅ **Thread-safe**: Funciona en entornos multi-thread

## 🧭 Sistemas de logging en este repo

### ✅ Sistema A: timer + limpieza por ejecución

- **Encabezado**: `Fecha: YYYY-MM-DD HH:MM:SS` al inicio del archivo
- **Formato**: `[0.123s] mensaje`
- **Limpieza**: borra el `.log` en cada ejecución
- **Variante Projects Panel**: durante `switch_to_sequence_hybrid()` el log se reinicia una sola vez al inicio de cada cambio de timeline
- **Scripts que lo usan**:
  - `LGA_NKS_Flow/LGA_NKS_Flow_Pull.py` (log: `debugPy_FlowPull.log`)
  - `LGA_NKS_Flow_Panel.py`
  - `LGA_NKS_Coordination_Panel.py`
  - `LGA_NKS_ViewerTL_Panel.py`
  - `LGA_NKS_Edit_Panel.py`
  - `LGA_NKS_Review_Panel.py`
  - `LGA_NKS_Assignee_Panel.py`
  - `LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py` (log: `debugPy_CreateV000.log`)
  - `LGA_NKS_Edit_Panel_py/LGA_import_shots.py` (log: `debugPy_ImportShots.log`)
  - `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
  - `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`
  - `LGA_NKS_Edit/LGA_NKS_OrganizeProject.py`
  - `LGA_NKS_Edit/LGA_NKS_CleanProject.py`
  - `+Building_Blocks/LGA_NKS_Flow_Pull_DoScan.py`
  - `+Building_Blocks/LGA_NKS_Flow_Pull_BinItem.py`
  - `+Building_Blocks/test_funcion_por_funcion.py`
  - `LGA_NKS_Projects_Panel.py` (log: `DebugPy_ProjectsPanel.log`)
  - `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py`
  - `LGA_NKS_Projects_Panel_py/LGA_NKS_CheckProjectVersions.py`
  - `LGA_NKS_Projects_Panel_py/LGA_NKS_Projects_Panel_Smart_Reload.py`
  - `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py`
  - `LGA_NKS_Shared/LGA_NKS_Timeline_PreCleanup.py` (cuando es invocado desde Projects Panel)
  - `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py` (cuando es invocado desde Projects Panel)

### ✅ Sistema B: hora + limpieza diaria

- **Encabezado**: `Fecha: YYYY-MM-DD` al inicio del archivo
- **Formato**: `[HH:MM:SS] [0.123s] mensaje`
- **Limpieza**: si el log es del día actual, agrega; si es de otro día, lo borra
- **Scripts que lo usan**:
  - `LGA_NKS_Flow/LGA_NKS_Flow_Push.py` (log: `debugPy_FlowPush.log`)
  - `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py`
  - `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py`
  - `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py`
  - `LGA_NKS_Edit/LGA_NKS_Reconnect.py`
  - `LGA_NKS_Edit/LGA_NKS_SelfReplaceClip.py`

## 🧩 Caso especial: Projects Panel

- Helper compartido: `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectsPanel_Logging.py`
- Flags por defecto:
  - `DEBUG = True`
  - `DEBUG_CONSOLE = False`
  - `DEBUG_LOG = True`
- Archivo de salida: `logs/DebugPy_ProjectsPanel.log`
- El `.log` se reinicia al comenzar cada `switch_to_sequence_hybrid()`
- `LGA_NKS_Timeline_PreCleanup.py` y `LGA_NKS_ScrollTo_TopTrack.py` reutilizan ese mismo logger cuando son llamados desde Projects Panel

## 📁 Estructura de Archivos

```
tu_script.py
├── logs/
│   └── debugPy_NombreScript.log  # Archivo de log generado
```

## 🛠️ Implementación Paso a Paso

### 1. Imports Requeridos

```python
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import os
import time
```

### 2. Variables Globales

```python
# Variables para controlar el logging
DEBUG = True           # Master switch: habilita todo el sistema de debug
DEBUG_CONSOLE = False  # Si DEBUG es True, imprime en consola
DEBUG_LOG = True       # Si DEBUG es True, escribe al archivo .log

# Variables del sistema de logging
script_start_time = None
debug_log_listener = None
```

### 3. Formatter Personalizado

```python
class RelativeTimeFormatter(logging.Formatter):
    """Formatter que incluye tiempo relativo desde el inicio del script."""
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        # Calcular tiempo relativo en segundos con 3 decimales
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)
```

### 4. Función de Setup del Logger

```python
def setup_debug_logging(script_name="TuScript"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    # Nombre del archivo basado en el script
    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )

    # Crear directorio si no existe
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # LIMPIAR archivo anterior y escribir encabezado con fecha + hora
    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        print(f"Warning: No se pudo limpiar el log: {e}")

    # Configurar logger con nombre único
    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # 🔑 CLAVE: Desactivar propagación al logger root (consola)
    logger.propagate = False

    # Limpiar handlers existentes
    if logger.handlers:
        logger.handlers.clear()

    # Handler para archivo
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Aplicar formatter personalizado
    formatter = RelativeTimeFormatter("[%(relative_time)s] %(message)s")
    file_handler.setFormatter(formatter)

    # Sistema asíncrono con QueueHandler
    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    # Detener listener anterior si existe
    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    # Iniciar nuevo listener
    debug_log_listener = QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger
```

### 5. Inicialización del Logger

```python
# Inicializar el logger con el nombre de tu script
debug_logger = setup_debug_logging(script_name="TuScript")
```

### 6. Función debug_print Mejorada

```python
def debug_print(*message, level="info"):
    """Función de logging mejorada con switches por consola/archivo."""
    global script_start_time

    # Crear el mensaje
    msg = " ".join(str(arg) for arg in message)

    # Logging a ARCHIVO (siempre que DEBUG y DEBUG_LOG estén activos)
    if DEBUG and DEBUG_LOG:
        # Inicializar tiempo si no está hecho
        if script_start_time is None:
            script_start_time = time.time()

        # Loggear según el nivel
        if level == "debug":
            debug_logger.debug(msg)
        elif level == "warning":
            debug_logger.warning(msg)
        elif level == "error":
            debug_logger.error(msg)
        else:  # info
            debug_logger.info(msg)

    # Logging a CONSOLA (solo si DEBUG y DEBUG_CONSOLE están activos)
    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()

        relative_time = time.time() - script_start_time
        timestamped_msg = f"[{relative_time:.3f}s] {msg}"
        print(timestamped_msg)
```

### 7. Cleanup (Opcional)

```python
def cleanup_logging():
    """Limpia el listener al terminar."""
    global debug_log_listener
    if debug_log_listener:
        try:
            debug_print("Deteniendo listener de logging...")
            debug_log_listener.stop()
            debug_print("Listener detenido")
        except Exception as e:
            debug_print(f"Error en cleanup: {e}", level="error")

# Registrar cleanup automático
try:
    import atexit
    atexit.register(cleanup_logging)
except Exception:
    pass
```

## 🎨 Uso en Tu Código

### Ejemplo Básico

```python
# Al inicio del script
DEBUG = False      # Consola OFF
DEBUG_FILE = True  # Archivo ON

# ... setup del logging ...

def mi_funcion():
    debug_print("Iniciando proceso...")
    try:
        # Tu código aquí
        resultado = operacion_importante()
        debug_print(f"Resultado: {resultado}")
    except Exception as e:
        debug_print(f"Error crítico: {e}", level="error")
        import traceback
        debug_print(f"Traceback: {traceback.format_exc()}", level="error")
```

### Ejemplo Avanzado con Contextos

```python
def procesar_archivo(filepath):
    debug_print(f"=== PROCESANDO: {filepath} ===")

    try:
        debug_print("Verificando archivo...")
        if not os.path.exists(filepath):
            debug_print(f"Archivo no encontrado: {filepath}", level="warning")
            return False

        debug_print("Abriendo archivo...")
        with open(filepath, 'r') as f:
            contenido = f.read()

        debug_print(f"Archivo leído: {len(contenido)} caracteres")
        debug_print("Procesamiento completado", level="info")

        return True

    except Exception as e:
        debug_print(f"ERROR procesando {filepath}: {e}", level="error")
        import traceback
        debug_print(f"Traceback: {traceback.format_exc()}", level="error")
        return False
```

## 📋 Reglas y Mejores Prácticas

### ✅ REGLAS OBLIGATORIAS

1. **Siempre usar `logger.propagate = False`** - Evita salida a consola CMD (Hiero/Nuke)
2. **Nombre único del logger** - Usar `{script_name}_logger`
3. **Limpiar archivo al inicio** - `open(log_file_path, "w")`
4. **Encabezado con fecha y hora** - `Fecha: YYYY-MM-DD HH:MM:SS`
5. **Usar RelativeTimeFormatter** - Timestamps consistentes
6. **QueueHandler + QueueListener** - Logging asíncrono y thread-safe
7. **No agregar StreamHandler** - No usar `basicConfig()` ni handlers a consola

### 🎯 CONVENCIONES RECOMENDADAS

1. **Nombres de archivo**: `debugPy_{ScriptName}.log`
2. **Separadores visuales**: `=== TEXTO ===` para secciones importantes
3. **Niveles apropiados**:
   - `debug`: Detalles técnicos internos
   - `info`: Operaciones normales importantes
   - `warning`: Situaciones no críticas
   - `error`: Errores que requieren atención

4. **Mensajes descriptivos**: Incluir contexto relevante
5. **Logging en puntos críticos**: Inicio/fin de funciones importantes

### 🚫 EVITAR

- ❌ Print statements directos en producción
- ❌ Logging síncrono en operaciones críticas
- ❌ Nombres de logger genéricos
- ❌ No limpiar handlers existentes
- ❌ Olvidar `propagate = False`
- ❌ Usar `basicConfig()` o `StreamHandler` en loggers de archivo

## 🔧 Configuración por Entorno

```python
# Desarrollo
DEBUG = True          # Master ON
DEBUG_CONSOLE = True  # Ver en consola
DEBUG_LOG = True      # También guardar en archivo

# Producción
DEBUG = False         # Master OFF
DEBUG_CONSOLE = False # Consola limpia
DEBUG_LOG = True      # Solo archivo para debugging cuando se active DEBUG
```

## 📊 Ejemplo de Output en Log

```
Fecha: YYYY-MM-DD HH:MM:SS
[0.001s] === INICIANDO SERVIDOR ===
[0.002s] Creando socket TCP...
[0.003s] Socket creado exitosamente
[0.004s] Bind exitoso al puerto 54325
[0.005s] Servidor activo y escuchando
[1.234s] === NUEVA CONEXIÓN RECIBIDA ===
[1.235s] Datos recibidos: 'run_script||archivo.nk'
[1.236s] Comando parseado: 'run_script', Archivo: 'archivo.nk'
[1.237s] Ejecutando script en main thread: archivo.nk
[2.145s] === SCRIPT ABIERTO EXITOSAMENTE ===
```

## 🎯 Checklist de Implementación

- [ ] Imports correctos añadidos
- [ ] Variables `DEBUG` y `DEBUG_FILE` configuradas
- [ ] `RelativeTimeFormatter` implementado
- [ ] `setup_debug_logging()` con `propagate = False`
- [ ] Logger inicializado con nombre único
- [ ] Encabezado con fecha y hora en primera línea
- [ ] `debug_print()` mejorada con niveles
- [ ] Cleanup opcional registrado
- [ ] Probado que NO aparece en consola
- [ ] Verificado que escribe correctamente al `.log`

## 🚀 Implementación Rápida

Para copiar-pegar en cualquier script:

```python
# 1. Pegar imports
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import os
import time

# 2. Pegar variables
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None

# 3. Pegar RelativeTimeFormatter (completo)

# 4. Pegar setup_debug_logging (completo, cambiar script_name)

# 5. Pegar debug_logger = setup_debug_logging(script_name="TuScript")

# 6. Pegar debug_print mejorada (completo)

# 7. Usar: debug_print("Tu mensaje")
```

¡Listo! Sistema de logging profesional implementado. 🎉
