> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA Projects Panel - Smart Reload System
## Sistema Inteligente de Recarga de Panels en Hiero

### 🎯 Objetivo
Crear un sistema que permita **recargar dinámicamente** el panel Projects de Hiero sin perder su estado de docking, preservando la posición exacta donde el usuario lo tenía configurado en su workspace.

### 📁 Arquitectura del Sistema

#### Panel Principal
**Ubicación:** `LGA_NKS_Projects_Panel.py` (raíz)
- Clase `ProjectsPanel` con botón "ReImport"
- Registrado como `"com.lega.ProjectsPanel"`
- Auto-crea panel cuando se importa

#### Script Smart Reload
**Ubicación:** `LGA_Projects_Panel/LGA_NKS_Projects_Panel_Smart_Reload.py`
- Función principal: `smart_reload_panel()`
- Maneja todo el proceso de destrucción y recreación
- Usa método nativo de Hiero para docking

### 🔄 Funcionamiento del Smart Reload

#### 1. Inicio del Proceso
```python
# Usuario hace click en "ReImport" en el panel
def reimport_panel(self):
    # Ejecuta script externo
    script_path = ".../LGA_NKS_Projects_Panel_Smart_Reload.py"
    # Importa y ejecuta main()
```

#### 2. Análisis del Estado Inicial
```python
# Verifica que existe el panel actual
existing_panel = None
for window in wm.windows():
    if window.objectName() == "com.lega.ProjectsPanel":
        existing_panel = window
        break
```

#### 3. Destrucción Inteligente
```python
# Método seguro que funciona:
existing_panel.hide()
existing_panel.deleteLater()

# Espera a que se complete la destrucción
QtCore.QTimer.singleShot(100, lambda: create_new_panel_after_destruction(wm))
```

#### 4. Verificación de Destrucción
```python
# Verifica que el panel anterior se destruyó completamente
projects_count = len([w for w in wm.windows() if w.objectName() == target_object_name])
if projects_count == 0:
    create_new_panel_anyway(wm)
```

#### 5. Creación del Nuevo Panel
```python
# Usa importlib para crear instancia fresca
spec = importlib.util.spec_from_file_location("LGA_NKS_Projects_Panel", script_path)
panel_module = importlib.util.module_from_spec(spec)
panel_module.AUTO_CREATE_PANEL = True  # Activa auto-creación
spec.loader.exec_module(panel_module)
```

#### 6. Docking Inteligente
```python
# Método CRÍTICO: usa el nativo de Hiero
wm = hiero.ui.windowManager()
result = wm.showWindow(panel)  # ← Método correcto
```

### 🎯 Método de Docking: ¿Por qué `wm.showWindow()`?

#### ❌ Métodos Incorrectos Probados:
- `QStackedWidget.insertWidget(index, panel)` → **NO FUNCIONA**
  - Solo inserta en el widget, no integra en sistema de docking
  - Resultado: panel no aparece correctamente dockeado

#### ✅ Método Correcto Encontrado:
- `hiero.ui.windowManager().showWindow(panel)` → **FUNCIONA PERFECTAMENTE**
  - Método nativo de Hiero para mostrar panels dockeados
  - Respeta el workspace guardado del usuario
  - Maneja automáticamente la integración completa

### 🧠 Lógica Inteligente de `wm.showWindow()`

#### Comportamiento Observado:
1. **Respeta el workspace**: Si guardaste tu layout con el panel en cierto lugar, lo mantiene ahí
2. **Inteligente**: Cuando el panel está "fuera de lugar", lo devuelve a la posición "correcta"
3. **No hardcodeado**: No fuerza posiciones específicas, adapta al contexto actual

#### Ejemplo Real:
```
Estado Inicial (movido manualmente):
├── QStackedWidget Count: 3
│   ├── [0] ClipColor
│   ├── [1] Coordination
│   └── [2] Projects ← ¡Fuera de lugar!

Después de wm.showWindow():
├── QStackedWidget Count: 2
│   ├── [0] Project (nativo)
│   └── [1] Projects ← ¡Vuelto al lugar correcto!
```

### 🔍 Estados de Docking en Hiero

#### ✅ Panel Dockeado Correctamente:
- Está dentro de un `QStackedWidget`
- Forma parte de la jerarquía de widgets de Hiero
- Comparte espacio con otros panels en pestañas
- Es visible y funcional

#### ❌ Panel No Dockeado:
- Fuera de la jerarquía de `QStackedWidget`
- No forma parte del layout de Hiero
- Puede estar flotando o oculto
- No integrado en el sistema de docking

### 🧪 Testing y Validación

#### Prueba Básica:
1. Verificar panel existe y está dockeado
2. Hacer click en "ReImport"
3. Confirmar panel reaparece en misma posición
4. Verificar funcionalidad intacta

#### Prueba Avanzada:
1. Mover panel manualmente a otra área
2. Ejecutar reload
3. Confirmar vuelve a posición "correcta" según workspace

### 📊 Resultados de Testing

#### ✅ Éxito Consistente:
```
============================================================
🎉 SMART RELOAD COMPLETADO EXITOSAMENTE
📍 Panel dockeado automáticamente en su posición original
============================================================
```

#### 📈 Métricas:
- ✅ Panel destruido correctamente
- ✅ Nuevo panel creado sin duplicados
- ✅ Docking exitoso con método nativo
- ✅ Posición preservada según workspace
- ✅ Sin efectos secundarios

### 🔧 Troubleshooting

#### Problema: Panel no se destruye
**Síntoma:** Después del reload siguen existiendo 2 panels
**Solución:** Verificar que `deleteLater()` se ejecutó correctamente

#### Problema: Panel no se dockea
**Síntoma:** Panel creado pero no visible en interfaz
**Solución:** Confirmar uso de `wm.showWindow()`, no `insertWidget()`

#### Problema: Panel aparece en lugar equivocado
**Síntoma:** Después del reload está en otra área de la interfaz
**Solución:** Es comportamiento correcto - Hiero lo movió al lugar apropiado

### 🎉 Conclusión

El sistema **Smart Reload** funciona perfectamente usando el método nativo `wm.showWindow()` de Hiero. No requiere hardcodear posiciones ni manipular manualmente los `QStackedWidget`. Hiero maneja inteligentemente el docking basándose en el workspace guardado del usuario.

**Resultado:** Recarga dinámica que preserva la experiencia del usuario y mantiene la integración perfecta con Hiero. ✨
