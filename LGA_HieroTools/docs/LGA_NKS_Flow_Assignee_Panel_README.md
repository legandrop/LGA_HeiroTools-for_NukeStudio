> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_NKS_Flow_Assignee_Panel - Configuración Dinámica de Usuarios

## Descripción
El panel LGA_NKS_Flow_Assignee_Panel carga dinámicamente la lista de usuarios desde `LGA_NKS_Flow_Users.json` si existe localmente; si no, usa `LGA_NKS_Flow_Users_dist.json` como configuración distribuible, permitiendo agregar, modificar o eliminar usuarios sin necesidad de editar el código fuente.

## Funcionalidades Principales

### 1. Configuración Dinámica de Usuarios
- Los usuarios se cargan desde `Python/Startup/LGA_NKS_Flow_Users.json` si existe localmente
- Si no existe ese archivo local, se usa `Python/Startup/LGA_NKS_Flow_Users_dist.json`
- Cada usuario tiene nombre, color y usuario de Wasabi configurables
- El sistema crea automáticamente el archivo de configuración si no existe

### 2. Funcionalidad Triple de Botones de Usuario
- **Click normal**: Asigna el usuario a la task comp en Flow Production Tracking y actualiza la base de datos local pipesync.db
- **Shift+Click**: Crea/actualiza políticas IAM de Wasabi para el usuario seleccionado
- **Ctrl+Shift+Click**: Abre ventana de gestión de shots asignados en policy de Wasabi

### 3. Funcionalidad Extendida de Clear Assignees
- **Click normal**: Limpia assignees en Flow para las tasks seleccionadas
- **Shift+Click**: Abre una ventana para escanear `pipesync.db` y buscar shots con estado `approved` / `delivery_checked` (incluye aliases DB `apr` y `check`) que todavía estén presentes en policies de Wasabi
- En la ventana se listan coincidencias en formato:
  - `Nombre de policy | Nombre de shot | Estado del shot`
- Todas las filas aparecen con checkbox activo por defecto y el botón **Limpiar policies** elimina las líneas correspondientes en policies para los items seleccionados

## Archivo de Configuración: LGA_NKS_Flow_Users.json / LGA_NKS_Flow_Users_dist.json

```json
{
    "users": [
        {
            "name": "Lega Pugliese",
            "color": "#69135e",
            "wasabi_user": "lega"
        },
        {
            "name": "Sebas Romano", 
            "color": "#bd7f9f",
            "wasabi_user": "Sebastian_Romano"
        },
        {
            "name": "Patricio Barreiro",
            "color": "#19335D",
            "wasabi_user": "Pato_Barreiro"
        },
        {
            "name": "Mariel Falco",
            "color": "#665621",
            "wasabi_user": "mariel"
        }
    ]
}
```

## Cómo Agregar un Nuevo Usuario

1. Abrir el archivo `Python/Startup/LGA_NKS_Flow_Users.json`
2. Agregar un nuevo objeto al array `users`:
   ```json
   {
       "name": "Nuevo Usuario",
       "color": "#ff6600",
       "wasabi_user": "nuevo_usuario"
   }
   ```
3. Guardar el archivo
4. Reiniciar Hiero o recargar el panel

## Cómo Modificar un Usuario Existente

1. Abrir el archivo `LGA_NKS_Flow_Users.json`
2. Modificar el `name` o `color` del usuario deseado
3. Guardar el archivo
4. Reiniciar Hiero o recargar el panel

## Cómo Eliminar un Usuario

1. Abrir el archivo `LGA_NKS_Flow_Users.json`
2. Eliminar el objeto correspondiente al usuario del array `users`
3. Guardar el archivo
4. Reiniciar Hiero o recargar el panel

## Formato de Campos
- **Colores**: Formato hexadecimal (`#69135e`, `#ff6600`, `#19335D`)
- **wasabi_user**: Nombre exacto del usuario en Wasabi (case-sensitive)

## Integración con Wasabi

### Asignación de Políticas (Shift+Click)
Al hacer Shift+Click en un botón de usuario, el panel llama al script de asignación:
- **Función**: `create_wasabi_policy_for_user(wasabi_user)` 
- **Script llamado**: `Python/Startup/LGA_NKS_Wasabi/LGA_NKS_Wasabi_PolicyAssign.py`
- **Parámetro**: El `wasabi_user` configurado en el JSON para ese usuario
- **Interfaz**: El script maneja toda la interfaz (ventana de estado, hilos, etc.)

### Gestión de Shots (Ctrl+Shift+Click)
Al hacer Ctrl+Shift+Click en un botón de usuario, el panel llama al script de gestión:
- **Función**: `unassign_wasabi_policy_for_user(wasabi_user)`
- **Script llamado**: `Python/Startup/LGA_NKS_Wasabi/LGA_NKS_Wasabi_PolicyUnassign.py`
- **Funcionalidad**: Muestra ventana con shots asignados y permite eliminarlos individualmente
- **Interfaz**: Ventana scrolleable con botones de shots y botón "✕" para eliminar

## Funciones Principales

### Scripts de Asignación y Limpieza
Los scripts llamados por los botones principales ahora actualizan tanto Flow Production Tracking como la base de datos local pipesync.db.

**Orden de escritura (regla del pipeline)**: la fuente de verdad es Flow y `pipesync.db` es solo un cache. Nunca se escribe en la DB local antes que en Flow: primero se hace la escritura en Flow, se verifica que haya sido exitosa y recién entonces se replica en la DB. Si la escritura en Flow falla, se aborta sin tocar la DB (queda desactualizada, que se corrige con un Pull, en vez de quedar con información incorrecta).

#### `LGA_NKS_Flow/LGA_NKS_Flow_Assign_Assignee.py`
- Asigna usuario a task comp en Flow y añade asignación en DB local
- Función principal: `assign_assignee_to_task(base_name, user_name)`

#### `LGA_NKS_Flow/LGA_NKS_Flow_Clear_Assignees.py`
- Elimina todos los asignados de task comp en Flow y limpia asignaciones en DB local
- Función principal: `clear_task_assignees_from_base_name(base_name)`

#### `LGA_NKS_Wasabi/LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py`
- Script llamado por **Shift+Click** en **Clear Assignees**
- Escanea la DB local para shots terminados (`approved` / `delivery_checked`)
- Busca coincidencias en policies IAM de Wasabi (`*_policy`)
- Permite limpiar en lote las líneas de policy para shots seleccionados

### `create_wasabi_policy_for_user(wasabi_user)`
- Llama al script de asignación de políticas de Wasabi para usuario específico
- Pasa el parámetro `wasabi_user` al script
- El script se encarga de mostrar ventana de estado y procesamiento
- Ubicación: `Python/Startup/LGA_NKS_Assignee_Panel.py`

### `unassign_wasabi_policy_for_user(wasabi_user)`
- Llama al script de gestión de shots de Wasabi para usuario específico
- Abre ventana con lista de shots asignados en la policy del usuario
- Permite eliminar shots individuales con interfaz visual
- Ubicación: `Python/Startup/LGA_NKS_Assignee_Panel.py`

### `reload_config()`
- Recarga la configuración sin reiniciar Hiero
- Útil para desarrollo y pruebas

## Método de Selección de Clips

El panel utiliza un **método híbrido inteligente filtrado por track** para determinar qué clips procesar, consistente con el resto del sistema:

### Lógica de Selección
1. **Selección múltiple en track objetivo**: Si hay múltiples clips seleccionados en el track `_comp_` (configurable vía `TRACK_comp_EXR`), procesa TODOS esos clips
2. **Playhead para selección simple**: Si hay solo un clip seleccionado en el track objetivo o ninguno, usa la posición del playhead para encontrar el clip en el track `_comp_`

### Comportamiento Específico
- ✅ **Múltiples clips seleccionados en `_comp_`** → Procesa todos los del track `_comp_` (prioridad máxima)
- ✅ **Un clip seleccionado en `_comp_`** → Usa playhead para determinar cuál procesar en track `_comp_`
- ✅ **Sin clips seleccionados en `_comp_`** → Usa playhead como fallback en track `_comp_`
- ⚠️ **Advertencia automática**: Si hay clips seleccionados en otros tracks, muestra mensaje informativo indicando que solo se procesan los del track `_comp_`

### Implementación Técnica
- Utiliza `get_clips_to_process()` del módulo `LGA_NKS_GetClip` con `prioritize_multiple_selection=True`
- Filtra por track igual que otros scripts del sistema
- Muestra advertencia automática cuando hay clips seleccionados en tracks que no son el objetivo
- Sincroniza debug con el módulo utilitario
- Compatible con el sistema de nomenclatura dual (formatos con/sin descripción)

## Estructura del Panel

### Botones Fijos
1. **Get Assignees** - Obtiene los usuarios asignados a la task comp del clip seleccionado
2. **Clear Assignees** - Elimina todos los asignados de la task comp del clip seleccionado

### Botones Dinámicos (Usuarios)
- Se generan automáticamente basándose en el archivo de configuración
- Cada usuario tiene su propio botón con color personalizado
- **Click normal**: Asigna el usuario a la task comp en Flow Production Tracking y actualiza la base de datos local pipesync.db
- **Shift+Click**: Crea/actualiza políticas IAM de Wasabi para el usuario
- **Ctrl+Shift+Click**: Abre ventana de gestión de shots asignados en policy de Wasabi

## Scroll, Columnas y Solapamiento de Botones

Para evitar solapamiento vertical sin romper el reordenamiento de columnas, el panel usa un `QScrollArea` con umbral y un cálculo de columnas basado en el ancho real disponible:

- **Constante**: `SCROLL_OVERLAP_THRESHOLD_PX`
- **Visibilidad**: `SCROLLBAR_VISIBLE` controla si la barra se muestra. **Por defecto está en `False`**: nunca se ve (pero el scroll con la rueda sigue funcionando). En `True` se muestra cuando corresponde desde el inicio del panel.
- **Comportamiento**: si el contenido excede la altura visible por más de ese umbral, se activa el scroll vertical. Si no, se permite una leve compresión sin scroll.
- **Columnas**: el número de columnas se calcula con el ancho mínimo entre `self.width()`, `scroll_area.width()` y `scroll_area.viewport().width()` para evitar anchos “fantasma” que generan columnas extra.

## Sincronización con Base de Datos Local

El panel mantiene sincronizada la información entre Flow Production Tracking y la base de datos SQLite local `pipesync.db`:

- **Get Assignees**: Consulta asignados desde Flow (fuente de verdad absoluta)
- **Clear Assignees**: Elimina asignados en Flow y limpia tabla `task_assignments` en DB local
- **Assign User**: Añade asignado en Flow y actualiza tabla `task_assignments` en DB local

Esta sincronización bidireccional asegura consistencia entre ambas fuentes de datos.

## Limitaciones Actuales y Plan Futuro

### Estado Actual
- El sistema valida en Flow que el shot exista antes de ejecutar cualquier acción y recupera la lista real de tasks asignadas al shot.
- Si solo existe la task **Comp**, se procesa automáticamente como antes (comp sigue siendo la task por defecto).
- Para **Assign** y **Clear** se muestran checkboxes con los mismos colores que `Create/Modify Shot` a fin de elegir en qué tasks aplicar el cambio cuando existen múltiples tasks (Roto, Cleanup, DMP, etc.).
- **Get Assignees** lista en forma automática los asignados de cada task existente (sin pedir selección), de modo que siempre se ve el panorama completo.
- Las selecciones se respetan tanto para una sola toma como para selecciones múltiples (cada shot abre su propia ventana).

### Próximos Pasos
1. Consolidar la configuración de tasks desde un único módulo (`LGA_NKS_Flow_Task_Config.py`) para que todos los paneles compartan colores y orden.
2. Evaluar caching de consultas cuando se procesan muchos shots consecutivos para reducir llamadas repetidas a Flow.
3. Extender la UI para recordar la última selección de tasks por sesión si el flujo de trabajo lo requiere.

**Referencia**: Lista completa de tasks en `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.md` sección "Tasks Disponibles".

## Notas Técnicas
- El archivo de configuración se busca en la misma carpeta que el script del panel
- Si el archivo no existe, se crea automáticamente con la configuración por defecto
- Los errores se muestran en la consola de debug (activar DEBUG = False en el script)
- El sistema es compatible con caracteres Unicode (nombres con acentos, etc.)
- Las funcionalidades de Flow y Wasabi utilizan credenciales seguras desde PipeSync (SecureConfig_Reader)
- Los botones de usuario utilizan `CustomButton` para manejar Shift+Click y Ctrl+Shift+Click
- Las ventanas de Wasabi son no-modales y se cierran manualmente con botón Close 
