> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_NKS_Flow_Assignee_Panel - Usuarios desde PipeSync

## Descripcion
El panel carga la lista de usuarios desde la **base de datos de PipeSync**, que a su vez
la baja de Flow. No hay ningun archivo de configuracion local que editar: agregar gente,
cambiarle el color o el usuario de Wasabi se hace desde el **tab PROJECTS de PipeSync**,
card `Users & Access`.

## De donde salen los usuarios

```
Flow (sitio Studio)
  HumanUser.sg_pipesync_user_json  ->  { color, wasabi_user, short_name, assignable }
        |  lo edita el Projects tab de PipeSync
        v
pipesync_stats.db  ->  tabla flow_users        (la escribe el sync de PipeSync)
        |
        +--> PipeSync   (colores de assignee en ShotCards, Review y Prod)
        +--> ESTE PANEL (botones de usuario, y los scripts de policies de Wasabi)
```

La fuente de verdad es **Flow**. La DB es solo un cache que PipeSync reescribe entero en
cada sync, y HieroTools la lee en **modo read-only**: nunca escribe ahi.

### Consecuencias practicas

- **Los cambios necesitan un sync de PipeSync.** Si cambias un color en el Projects tab,
  el panel lo toma cuando PipeSync haya sincronizado y vos recargues el panel. PipeSync
  refresca su cache solo al guardar; Hiero lo lee la proxima vez que abre el panel.
- **PipeSync tiene que haber corrido al menos una vez** en esa maquina. Sin
  `pipesync_stats.db` no hay usuarios: el panel se queda **sin botones de usuario** y lo
  deja en el log. **No hay fallback** a una lista compilada — antes lo habia (un JSON
  local mas una config por defecto en el codigo) y el resultado era que la misma persona
  se veia de un color en Hiero y de otro en PipeSync, sin que nadie se enterara.
- **Solo Studio.** El envelope de PipeSync no existe en el sitio Client; ahi los colores
  salen de los Vendor Groups y este panel no se usa.

### Que usuarios aparecen como botones
Los que estan **activos** en Flow y tienen `assignable` en true en su envelope. Alguien
puede tener color y `wasabi_user` sin ser assignable (por ejemplo un producer): no
aparece como boton, pero los scripts de Wasabi lo siguen encontrando, porque buscan por
`wasabi_user` sin filtrar por assignable.

## Funcionalidades Principales

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

## Como se administran los usuarios

**Todo se hace desde PipeSync**, tab `PROJECTS`, card `Users & Access`, en el `…` de la
fila de la persona. La seccion `PipeSync` del dialogo tiene:

| Campo | Que hace |
|---|---|
| `Assignee color` | Color del label del assignee. Se usa como **fondo**, asi que conviene un tono oscuro; el dialogo muestra un preview con el nombre real encima. |
| `Wasabi user` | Nombre de usuario **IAM** de Wasabi (ej. `lega`). Con el se arma la policy `<usuario>_policy`. **No es una credencial**: las access/secret key siguen en el `config.secure` de cada maquina. |
| `Short name` | Nombre corto, opcional. |
| `Assignable` | Si aparece como boton en este panel. |

Para dar de alta a alguien nuevo se lo crea en Flow (o desde el mismo card) y se le
completa esa seccion. Para sacarlo del panel alcanza con destildar `Assignable` o
desactivarlo en Flow — no hace falta borrar nada.

## Formato de Campos
- **Colores**: hexadecimal `#RRGGBB` (`#69135e`, `#19335D`). Se valida al guardar; un
  valor invalido se rechaza en vez de escribirse.
- **wasabi_user**: nombre exacto del usuario en Wasabi (case-sensitive).

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
- Vuelve a leer los usuarios desde `pipesync_stats.db` y reconstruye los botones, sin
  reiniciar Hiero.
- Es lo que hay que usar despues de cambiar algo en el Projects tab de PipeSync y de que
  PipeSync haya sincronizado.

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
- Los usuarios se leen de `pipesync_stats.db` (tabla `flow_users`) en modo read-only. La
  ruta la resuelve `LGA_NKS_PipeSyncPaths.get_pipesync_db_path()`, que apunta SIEMPRE a
  la instalacion estandar de PipeSync, nunca a un build de desarrollo.
- Si la DB no existe o la tabla esta vacia, el panel se queda sin botones de usuario y lo
  deja en el log. No se crea ningun archivo de configuración por defecto.
- Los errores se muestran en la consola de debug (activar DEBUG = False en el script)
- El sistema es compatible con caracteres Unicode (nombres con acentos, etc.)
- Las funcionalidades de Flow y Wasabi utilizan credenciales seguras desde PipeSync (SecureConfig_Reader)
- Los botones de usuario utilizan `CustomButton` para manejar Shift+Click y Ctrl+Shift+Click
- Las ventanas de Wasabi son no-modales y se cierran manualmente con botón Close 

## Referencias tecnicas

### En este repo
- `LGA_NKS_Shared/LGA_NKS_Flow_Users_Config.py`
  - `load_flow_users(assignable_only)`: lee `flow_users` de `pipesync_stats.db`. Con
    `assignable_only=True` (default) devuelve los botones del panel; con `False`, todos.
  - `find_user_by_name()` / `find_user_by_wasabi_user()`: lookup puntual para los scripts.
  - `get_flow_users_db_path()`: ruta de la DB.
  - Aplica la misma precedencia de color que PipeSync: **el color de vendor gana** sobre
    el personal.
- `LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`
  - `get_pipesync_db_path(filename)`: resuelve la instalacion estandar de PipeSync por
    plataforma y contexto, ignorando a proposito el `CachePath` del `config.secure`.
- `LGA_NKS_Assignee_Panel.py`
  - `load_users_from_config()`: carga los usuarios; sin datos devuelve lista vacia.
  - `create_user_buttons()` / `reload_config()`.
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py` y `…_PolicyUnassign.py`
  - `get_user_info_from_config(wasabi_user)`: nombre y color por `wasabi_user`.
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py`, `…_Flow_Assignee.py`,
  `…_Flow_Clear_Assignees.py`
  - `get_user_info_from_config(user_name)`: nombre y color por nombre de Flow.
- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py`
  - `_load_user_colors()` / `_get_user_text_color()`: colores de autor en las notas.

### En el repo de PipeSync (`LGA_PipeSync_2`)
- `Docs/Doc_Assignee_User_Colors.md` — **doc principal de todo este sistema**: el envelope
  de Flow, la tabla `flow_users`, la regla de resolucion de color, el corte Studio/Client
  y la invalidacion del cache.
- `py_scr/get_Flow_info_stats.py::fetch_flow_users()` — el fetch que llena la tabla.
- `py_scr/bootstrap_pipesync_user_field.py` — crea el custom field en Flow. One-shot,
  a mano, solo en el sitio Studio.
- `src/features/settings/components/ProjectSettingsTab.cpp::editPeopleUser()` — el
  dialogo donde se editan color, `wasabi_user`, short name y `assignable`.
