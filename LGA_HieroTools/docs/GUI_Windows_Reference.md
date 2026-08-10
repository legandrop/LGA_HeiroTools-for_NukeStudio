> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Referencia: Cómo Crear Ventanas que se Mantienen Abiertas en Nuke/Hiero

## Problema Común

**Las ventanas creadas con PySide/PyQt en scripts de Nuke/Hiero se abren y se cierran inmediatamente**, apenas se logra ver la ventana por milisegundos.

### ¿Por Qué Sucede?

1. **Recolección de Basura de Python**: Python elimina objetos sin referencias activas
2. **WA_DeleteOnClose por Defecto**: Las ventanas se destruyen automáticamente al cerrar
3. **Falta de Referencia Global**: La variable local se elimina al terminar la función
4. **Event Loop Incorrecto**: Usar `app.exec_()` dentro de Nuke (que ya tiene su propio event loop)

## Soluciones Probadas ✅

### Patrón Principal: Variable Global + WA_DeleteOnClose

#### ✅ Código que FUNCIONA:

```python
from LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt

# 🔑 VARIABLE GLOBAL - CRÍTICA para mantener referencia
_window_instance = None

class MiVentana(QtWidgets.QWidget):  # Usar QWidget, NO QMainWindow/QDialog
    def __init__(self):
        super(MiVentana, self).__init__()
        self.setWindowTitle("Mi Ventana")
        self.setAttribute(Qt.WA_DeleteOnClose, False)  # 🔑 NO se destruye al cerrar

        # Configurar UI...
        layout = QtWidgets.QVBoxLayout(self)
        # ... resto del código

def mostrar_ventana():
    global _window_instance  # 🔑 Usar variable global

    try:
        _window_instance = MiVentana()  # 🔑 Asignar a variable global
        _window_instance.show()
        return _window_instance
    except Exception as e:
        print(f"Error: {e}")
        return None

# Ejecutar
mostrar_ventana()
```

#### ❌ Código que NO FUNCIONA:

```python
def mostrar_ventana_mala():
    ventana = QtWidgets.QWidget()  # ❌ Sin variable global
    ventana.show()
    return ventana  # ❌ Referencia se pierde al terminar la función

# La ventana se cierra inmediatamente porque no hay referencia que la mantenga viva
```

### Alternativa: Registro en Hiero como Acción

```python
import hiero.ui

def mostrar_ventana():
    global _window_instance
    _window_instance = MiVentana()
    _window_instance.show()

def run_script():
    mostrar_ventana()

# Registrar como acción en el menú de Hiero
action = hiero.ui.createMenuAction("Mi Ventana", run_script)
hiero.ui.registerAction(action)

# Agregar al menú
menuBar = hiero.ui.menuBar()
toolsMenu = menuBar.addMenu("Herramientas")
toolsMenu.addAction(action)
```

## Ejemplos Reales que Funcionan

### 1. LGA_NKS_mediaMissingFrames.py

```python
# Variable global
clipMediaInfoWindow = None

class ClipMediaInfo(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ClipMediaInfo, self).__init__(parent)
        # NO setModal, NO setAttribute - funciona igual

def showClipMediaInfo():
    global clipMediaInfoWindow
    clipMediaInfoWindow = ClipMediaInfo()  # Asignación global
    clipMediaInfoWindow.show()
```

### 2. Abrir_ventanita_100px_debajo_del_nodo.py

```python
# Variable global
_window_ref = None

def show_window_below_selected_node():
    global _window_ref

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Ventana")
    dialog.resize(200, 100)
    dialog.show()

    _window_ref = dialog  # 🔑 Referencia global
```

### 3. LGA_NKS_Flow_Assignee.py

```python
class FlowStatusWindow(QtWidgets.QDialog):
    def __init__(self, user_display_name, user_color, operation):
        super(FlowStatusWindow, self).__init__()
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)  # 🔑
        # ... resto del código

# En la función que la crea:
_status_window = FlowStatusWindow(...)
_status_window.show()
```

## Checklist de Verificación

### ✅ Requisitos Mínimos para que Funcione:

- [ ] **Variable Global**: `_mi_ventana = None` al inicio del módulo
- [ ] **Asignación Global**: `_mi_ventana = MiVentana()` en la función
- [ ] **WA_DeleteOnClose**: `self.setAttribute(Qt.WA_DeleteOnClose, False)`
- [ ] **Clase Base**: `QtWidgets.QWidget` (preferido) o `QDialog` con `setModal(False)`
- [ ] **No usar app.exec_()**: Nuke ya maneja el event loop

### 🔍 Diagnóstico si no Funciona:

1. **¿La ventana aparece por milisegundos?**
   - Problema: Falta variable global → Agregar `_ventana_global = None`

2. **¿La ventana se cierra al hacer click fuera?**
   - Problema: Falta `WA_DeleteOnClose` → Agregar `setAttribute(Qt.WA_DeleteOnClose, False)`

3. **¿Usando QMainWindow o QDialog modal?**
   - Problema: Comportamiento inesperado → Cambiar a `QWidget`

4. **¿Usando app.exec_()?**
   - Problema: Congela Nuke → Remover, Nuke ya tiene event loop

## Casos Especiales

### Ventanas Modales Temporales

Para diálogos que SÍ deben cerrarse automáticamente (ej: confirmaciones):

```python
def mostrar_dialogo_temporal():
    dialog = QtWidgets.QDialog()
    dialog.setModal(True)  # Bloquea otras ventanas
    # NO setAttribute(Qt.WA_DeleteOnClose, False) - Se cierra sola
    dialog.exec_()  # OK para diálogos modales temporales
```

### Múltiples Instancias

```python
# Lista global para múltiples ventanas
_ventanas_abiertas = []

def nueva_ventana():
    global _ventanas_abiertas
    ventana = MiVentana()
    _ventanas_abiertas.append(ventana)  # Mantener referencia
    ventana.show()
```

## Errores Comunes y Soluciones

### Error: "Ventana se cierra sola"
**Solución**: Agregar variable global y `WA_DeleteOnClose = False`

### Error: "NameError: name 'Qt' is not defined"
**Solución**: Importar desde `LGA_QtAdapter_HieroTools`, NO directamente de PySide

### Error: "Ventana no responde"
**Solución**: Remover `app.exec_()` - Nuke ya maneja el event loop

### Error: "Ventana bloquea Nuke"
**Solución**: Usar `setModal(False)` o `QWidget` en lugar de `QDialog`

## Referencias

- **LGA_QtAdapter_HieroTools.py**: Adaptador para compatibilidad Nuke 15/16
- **Nuke16_Migracion.md**: Guía de migración Qt
- **LGA_NKS_mediaMissingFrames.py**: Ejemplo perfecto de QWidget + variable global
- **LGA_NKS_Flow_Assignee.py**: Ejemplo de QDialog + WA_DeleteOnClose

---

**Nota**: Este documento se basa en la resolución del problema en `LGA_Projects_Panel_Window.py` siguiendo los patrones de scripts existentes que funcionan correctamente.
