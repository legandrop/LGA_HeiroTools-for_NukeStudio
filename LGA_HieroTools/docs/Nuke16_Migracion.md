> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Plan de migración Nuke 15 → Nuke 16 (PySide2 → PySide6) - Hiero Panels

## Estrategia
- Capa de compatibilidad `LGA_QtAdapter_HieroTools.py` con funciones helper avanzadas similar a ToolPacks
- Funciones helper automatizan cambios de API Qt5/Qt6: `horizontal_advance()`, `primary_screen_geometry()`, `set_layout_margin()`
- Reemplazar imports PySide2 → `LGA_QtAdapter_HieroTools` en todos los paneles
- Mantener compatibilidad con Nuke 15 mediante try/except
- Actualizar APIs Qt5 deprecadas si es necesario

## Paneles Principales (requieren migración completa)

### Paneles de UI principales
- [x] `LGA_NKS_ClipColor_Panel.py` — Panel de colores de clips (PySide2.QtWidgets, PySide2.QtGui)
- [x] `LGA_NKS_Edit_Panel.py` — Panel de herramientas de edición (PySide2.QtWidgets, PySide2.QtGui, PySide2.QtCore)
- [x] `LGA_NKS_Assignee_Panel.py` — Panel de asignación de usuarios Flow (PySide2.QtWidgets, PySide2.QtGui, PySide2.QtCore)
- [x] `LGA_NKS_Coordination_Panel.py` — Panel de producción Flow (PySide2.QtWidgets, PySide2.QtGui, PySide2.QtCore)
- [x] `LGA_NKS_Flow_Panel.py` — Panel principal Flow (PySide2.QtWidgets, PySide2.QtGui, PySide2.QtCore)
- [x] `LGA_NKS_Review_Panel.py` — Panel de revisión (PySide2.QtWidgets, PySide2.QtGui, PySide2.QtCore)
- [x] `LGA_NKS_ViewerTL_Panel.py` — Panel de viewer (PySide2.QtWidgets, PySide2.QtGui, PySide2.QtCore)
- [x] `LGA_NKS_NoFPT_Panel.py` — Panel Flow alternativo (PySide2.QtWidgets, PySide2.QtGui)

### Archivos adicionales migrados (scripts auxiliares)
- [x] `LGA_NKS_Shortcuts.py` — Atajos de teclado (migrado a LGA_QtAdapter_HieroTools)
- [x] `z_clear_outpoint_workaround.py` — Workaround para timeline viewer (migrado a LGA_QtAdapter_HieroTools)
- [x] `z_version_everywhere.py` — Versionado de clips (migrado a LGA_QtAdapter_HieroTools)

## Scripts de Funcionalidad (requieren migración Qt)

### LGA_NKS/ - Scripts básicos
- [x] `LGA_NKS_CheckProjectVersions.py` — Verificación de versiones (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_OpenInNukeX.py` — Abrir en NukeX (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_Compare_Versions.py` — Comparar versiones (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)

### LGA_NKS_Edit/ - Scripts de edición
- [x] `LGA_NKS_Reconnect.py` — Reconexión de media (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_SelfReplaceClip.py` — Reemplazo de clips (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_MatchVerToEXR.py` — Matching de versiones (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_CompareVerToEditref.py` — Comparación con EditRef (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_CompareEXR_to_aPlate.py` — Comparación EXR aPlate (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_CreateNewTrack.py` — Creación de tracks (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_mediaMissingFrames.py` — Frames faltantes (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_Trim_In.py` — Recorte IN (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_Trim_Out.py` — Recorte OUT (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_FixColorspaces.py` — Corrección de colorspaces (sin Qt directo)

### LGA_NKS_Flow/ - Scripts de Flow
- [x] `LGA_NKS_Flow_Pull.py` — Pull de tasks Flow (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QRunnable, QThreadPool)
- [x] `LGA_NKS_Flow_Push.py` — Push de estados Flow (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_Flow_Assign_Assignee.py` — Asignación de usuarios (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_Flow_Assignee.py` — Obtener asignados (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QRunnable, QThreadPool)
- [x] `LGA_NKS_Flow_Clear_Assignees.py` — Limpiar asignados (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_Flow_Shot_info.py` — Información de shots (migrado a LGA_QtAdapter_HieroTools - QShortcut fix)
- [x] `LGA_NKS_Flow_ReviewPic.py` — Captura de review (migrado Qt)
- [x] `LGA_NKS_Flow_NamingUtils.py` — Utilidades de naming (sin Qt)
- [x] `LGA_NKS_Flow_CreateShot_Thumbs.py` — Creación de thumbnails (migrado Qt)

### LGA_NKS_Coordination_Panel_py/ - Scripts de producción Flow
- [x] `LGA_NKS_Flow_CreateShot.py` — Crear shots Flow (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_Flow_ModifyShot.py` — Modificar shots Flow (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_Flow_ShowInFlow.py` — Mostrar en Flow (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QRunnable, QThreadPool)
- [x] `LGA_NKS_Flow_Thumbs.py` — Thumbnails Flow (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_Flow_ShotPriority.py` — Prioridad de shots (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_FileManagerS3_Download.py` — Descarga FileManagerS3 (sin Qt - solo subprocess)
- [x] `LGA_NKS_FileManagerS3_Upload.py` — Subida FileManagerS3 (sin Qt - solo subprocess)
- [x] `LGA_NKS_FileManagerS3_OpenPath.py` — Abrir ruta FileManagerS3 (sin Qt - solo subprocess)

## ✅ **MIGRACIÓN COMPLETA - LGA_NKS_Coordination_Panel_py**
**8/8 archivos completamente migrados:**
- `LGA_NKS_Flow_CreateShot.py` ✅
- `LGA_NKS_Flow_ModifyShot.py` ✅
- `LGA_NKS_Flow_ShowInFlow.py` ✅
- `LGA_NKS_Flow_Thumbs.py` ✅
- `LGA_NKS_Flow_ShotPriority.py` ✅
- `LGA_NKS_FileManagerS3_Download.py` ✅ (sin Qt - solo subprocess)
- `LGA_NKS_FileManagerS3_Upload.py` ✅ (sin Qt - solo subprocess)
- `LGA_NKS_FileManagerS3_OpenPath.py` ✅ (sin Qt - solo subprocess)

### LGA_NKS_ViewerTL/ - Scripts de timeline/viewer
- [x] `LGA_NKS_Timeline_Refresh_Wrap.py` — Refresh timeline (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [ ] `LGA_NKS_FrameNumber.py` — Números de frame (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)
- [x] `LGA_NKS_PrevNext_Rev.py` — Navegación revisión (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_InOut_Editref.py` — EditRef IN/OUT (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton)
- [x] `LGA_NKS_Reduce_SeqWin.py` — Reducir secuencia (sin Qt directo)
- [x] `LGA_NKS_SnapShot.py` — Captura de pantalla (sin Qt directo)

### LGA_NKS_Wasabi/ - Scripts de Wasabi
- [x] `LGA_NKS_Wasabi_PolicyAssign.py` — Asignación de políticas Wasabi (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QRunnable, QThreadPool)
- [x] `LGA_NKS_Wasabi_PolicyUnassign.py` — Eliminación de políticas Wasabi (QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar)

## Archivos que NO necesitan migración

### Utilidades y configuración
- [x] `LGA_NKS_Shortcuts.py` — Atajos de teclado (migrado a LGA_QtAdapter_HieroTools)
- [x] `LGA_NKS_Utils/LGA_NKS_StyleUtils.py` — Utilidades de estilos (sin Qt)
- [x] `LGA_NKS_Utils/LGA_NKS_GetClip.py` — Utilidades de clips (migrado Qt + fix IndexError)
- [x] `LGA_NKS_Utils/README_StyleUtils.md` — Documentación
- [x] `LGA_NKS_Flow_Task_Config.py` — Configuración de tasks Flow (sin Qt)
- [x] `LGA_NKS_Flow_Users.json` — Configuración de usuarios (JSON)
- [x] `LGA_NKS_Panel_Style_Guide.md` — Guía de estilos
- [x] `LGA_NKS_Hilos_Hiero.md` — Documentación de hilos

### Scripts sin Qt
- [x] `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3.md` — Documentación
- [x] `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.md` — Documentación
- [x] `LGA_NKS_Wasabi/LGA_NKS_Wasabi_README.md` — Documentación
- [x] `LGA_NKS_Wasabi/verify_policy_assign.py` — Script de verificación (sin Qt)
- [x] `LGA_NKS_Wasabi/verify_policy_created.py` — Script de verificación (sin Qt)
- [x] `LGA_NKS_Wasabi/verify_updated_policy.py` — Script de verificación (sin Qt)
- [x] `LGA_NKS_Wasabi/wasabi_policy_utils.py` — Utilidades Wasabi (sin Qt)
- [x] `LGA_NKS_Edit/LGA_NKS_MatchVerToEXR.md` — Documentación

### Archivos adicionales migrados durante testing
- [x] `LGA_NKS_Utils/LGA_NKS_GetClip.py` — Utilidades de clips (migrado Qt + fix IndexError cuando no hay clips seleccionados)

### Building Blocks (archivos legacy)
- [x] Todos los archivos en `+Building_Blocks/` — Scripts antiguos no usados

### Dependencias externas
- [x] `shotgun_api3/` — API de ShotGrid (externa)
- [x] `LGA_NKS_Wasabi/boto3/` — AWS SDK (externa)
- [x] `LGA_NKS_Wasabi/botocore/` — AWS SDK core (externa)

## Pasos sugeridos para migración

1. **`LGA_QtAdapter_HieroTools.py`** en `Python/Startup/` incluye funciones helper avanzadas:
   - `horizontal_advance(metrics, text)` - ancho de texto compatible Qt5/Qt6
   - `primary_screen_geometry(pos)` - geometría de pantalla con fallback robusto
   - `set_layout_margin(layout, margin)` - márgenes de layout compatibles Qt5/Qt6

2. **Migrar paneles principales** (orden recomendado):
   - Empezar con paneles simples como `LGA_NKS_ClipColor_Panel.py`
   - Continuar con `LGA_NKS_ViewerTL_Panel.py`
   - Luego paneles complejos como `LGA_NKS_Flow_Panel.py`

3. **Migrar scripts de funcionalidad**:
   - Reemplazar imports PySide2 → `LGA_QtAdapter_HieroTools`
   - Revisar uso de APIs deprecated (QApplication, QThreadPool, etc.)
   - Los scripts que usan QRunnable/QThreadPool ya están preparados

4. **Probar en Nuke 15 y 16**:
   - Verificar que los paneles se cargan correctamente
   - Probar funcionalidades básicas
   - Revisar que los estilos y tooltips funcionan

## Consideraciones especiales

### QRunnable y QThreadPool
Los scripts que usan hilos (`LGA_NKS_Flow_Pull.py`, `LGA_NKS_Wasabi_PolicyAssign.py`, etc.) ya están preparados para ambas versiones ya que estas clases no cambiaron entre PySide2/6.

### QApplication global
Muchos scripts crean QApplication. En PySide6 puede haber cambios en el manejo de instancias globales.

### QFont y QFontMetrics
Algunos scripts pueden usar APIs de fuente que cambiaron.

### Cambios en jerarquía de widgets del Timeline
**Problema identificado:** La estructura interna de widgets del timeline cambió significativamente entre Nuke 15 y 16.

**Ejemplo con `LGA_NKS_ScrollTo_TopTrack.py`:**
- **Nuke 15:** Scrollbar horizontal en `QSplitter → QWidget → QAbstractScrollArea → qt_scrollarea_hcontainer`
- **Nuke 16:** Scrollbar vertical (¡no horizontal!) en `QSplitter → QWidget → QAbstractScrollArea → qt_scrollarea_vcontainer`

**Solución implementada:** Lógica híbrida que detecta automáticamente la versión y busca el scrollbar en la ubicación correcta:
- Detecta valores "sospechosos" (positivos cuando deberían ser negativos)
- Cambia automáticamente a método alternativo específico para cada versión
- En Nuke 16 busca en `vcontainer` en lugar de `hcontainer`

**Lección aprendida:** No asumir que la orientación del scrollbar (horizontal vs vertical) se mantiene entre versiones. Hacer pruebas exhaustivas de jerarquía de widgets.

### Problema resuelto: API del Undo System
**Problema identificado:** En versiones recientes, `project.undoStack()` ya no existe.

**Ejemplo con `LGA_NKS_Edit_Panel.py`:**
- **❌ Código problemático (API antigua):**
  ```python
  project.beginUndo("Operation")
  try:
      # do something
  finally:
      if project.undoStack().canEnd():  # AttributeError!
          project.endUndo()
  ```

- **✅ Código correcto (context manager):**
  ```python
  with project.beginUndo("Operation"):
      # do something  # begin/end manejado automáticamente
  ```

**Solución implementada:** Cambiar todas las funciones para usar el context manager `with project.beginUndo("name"):`.

### Problema resuelto: Threading initialization timing en Nuke 16
**Problema identificado:** En Nuke 16 (PySide6), el `QThreadPool` global no está disponible inmediatamente al inicio, causando que los workers no se ejecuten.

**Síntoma:** El panel funciona cuando se recarga con el botón, pero no al abrir Nuke por primera vez.

**Causa:** El sistema de threading de Qt/PySide6 requiere inicialización completa antes de poder usar threads.

**Solución implementada:** Agregar delay de inicialización usando `QTimer.singleShot()`:

```python
# En el constructor del panel, en lugar de:
self.start_scan()

# Usar:
QtCore.QTimer.singleShot(500, self.start_scan)  # 500ms delay
```

**Resultado:** El threading funciona correctamente en Nuke 16 después de esperar a que Qt esté completamente inicializado.

### Problema resuelto: Incompatibilidad SIP/PySide2 al usar hiero.ui.mainWindow() como parent de QDialog

**Problema identificado:** En PySide2 (Nuke 15), el objeto devuelto por `hiero.ui.mainWindow()` es un wrapper SIP de Hiero cuyo tipo interno no es compatible con el sistema de tipos de PySide2 cuando se pasa como `parent` al constructor de `QDialog` o `QWidget`. Esto genera el error "QWidget: Must construct a QApplication before a QWidget" aunque QApplication exista y esté activa.

**Comportamiento diferenciado:**
- **Nuke 15 (PySide2):** `QDialog(hiero.ui.mainWindow())` → crash con "QWidget: Must construct a QApplication before a QWidget"
- **Nuke 16 (PySide6):** `QDialog(hiero.ui.mainWindow())` → funciona correctamente (conversión de tipos más robusta en Qt6)

**Ejemplo con `LGA_NKS_TaskSelectionDialog.py` y `LGA_NKS_TaskMismatchDialog.py`:**
- **❌ Código problemático:**
  ```python
  parent = hiero.ui.mainWindow()
  dialog = QDialog(parent)  # Crash en PySide2
  ```

- **✅ Código correcto (usa PYSIDE_VER del adaptador):**
  ```python
  from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import PYSIDE_VER
  def _get_hiero_main_window():
      if PYSIDE_VER < 6:
          return None  # Evitar incompatibilidad SIP/PySide2
      # ... obtener window solo en PySide6
  ```

**Solución implementada:** En `_get_hiero_main_window()` de `LGA_NKS_TaskSelectionDialog.py`, retornar `None` cuando `PYSIDE_VER < 6`, usando `PYSIDE_VER` del adaptador `LGA_QtAdapter_HieroTools`. Los diálogos se crean sin parent en PySide2 (seguro y funcional) y con parent en PySide6 (correcto y bien parentado).

**Lección aprendida:** Nunca pasar `hiero.ui.mainWindow()` como parent de QWidget/QDialog en código que deba funcionar con PySide2. Usar siempre `PYSIDE_VER` para condicionar este comportamiento.

### Problema resuelto: QShortcut movido entre módulos en PySide6
**Problema identificado:** `QShortcut` se movió de `QtWidgets` a `QtGui` en PySide6.

**Ejemplo con `LGA_NKS_Flow_Shot_info.py`:**
- **❌ Código problemático:**
  ```python
  from PySide6.QtWidgets import QShortcut  # No existe en PySide6
  ```
- **✅ Código correcto:**
  ```python
  from LGA_QtAdapter_HieroTools import QtGui, QShortcut
  # QShortcut ya está disponible desde el adapter
  ```

**Solución implementada:** Usar directamente las clases del adapter `LGA_QtAdapter_HieroTools` que maneja automáticamente estas diferencias.

## Estado actual
- [x] `LGA_QtAdapter_HieroTools.py` creado con funciones helper avanzadas (`horizontal_advance`, `primary_screen_geometry`, `set_layout_margin`)
- [x] Todos los paneles principales migrados (8/8)
- [x] Scripts básicos LGA_NKS/ migrados (3/3)
- [x] Scripts LGA_NKS_Edit/ migrados (8/8)
- [x] Scripts LGA_NKS_ViewerTL/ migrados (5/6)
- [x] Scripts auxiliares migrados (4/4)
- [x] APIs problemáticas corregidas (undo system, scrollbar hierarchy)
- [x] Todos los scripts completados - migración Qt finalizada
