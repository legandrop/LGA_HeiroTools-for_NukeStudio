> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_NKS_Flow_CreateShot v1.34

Script para crear shots en ShotGrid/Flow Production Tracking basado en clips seleccionados en Hiero/Nuke Studio.

**v1.34:** Creación automática de estructura de carpetas por task. Integración con módulo `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py` que crea automáticamente todas las subcarpetas necesarias para cada task habilitada (2D y 3D) siguiendo la jerarquía definida del pipeline.

## Descripción General

Script para crear shots en ShotGrid/Flow Production Tracking basado en clips seleccionados en Hiero/Nuke Studio.

**Cambio importante en v1.2:** Ya no usa templates predefinidos. Crea shots y tasks manualmente para mayor control y flexibilidad.

**Cambio importante en v1.27:** Sistema modular y DRY para crear múltiples tasks. Agregar nuevas tasks es extremadamente fácil.

**Cambio importante en v1.28:** Todas las tasks del pipeline agregadas con sus colores específicos.

**Cambio importante en v1.29:** UI compacta - Tasks deshabilitadas ocupan solo 1 línea sin mostrar campos ni divisores.

**Cambio importante en v1.30:** Reducción automática del 30% en tiempo estimado antes de subirse a Flow.

**Cambio importante en v1.31:** Migración al método híbrido centralizado de selección de clips con soporte para selección múltiple.

## Funcionalidades

### ✅ UI Compacta y Eficiente (v1.29)
- **Tasks deshabilitadas ocupan 1 línea:** Checkbox + nombre solamente
- **Sin divisores ni campos cuando está deshabilitada:** Máxima optimización de espacio vertical
- **Expansión dinámica:** Al habilitar una task, aparecen todas sus columnas y el divisor
- **Checkbox a la izquierda:** Diseño más intuitivo y compacto
- **12 tasks caben en pantalla:** Gracias al diseño compacto

### ✅ Sistema Modular de Tasks (v1.27)
- Código completamente refactorizado para ser DRY (Don't Repeat Yourself)
- Agregar nuevas tasks es tan simple como agregar una línea a `AVAILABLE_TASKS`
- UI generada dinámicamente desde configuración
- Creación de tasks en ShotGrid completamente genérica
- Show/hide dinámico de columnas según checkbox de cada task

### ✅ Tasks Disponibles (v1.28)

Todas las tasks del pipeline están disponibles con sus colores específicos:

| # | Task | Color | Pipeline Step | Por Defecto |
|---|------|-------|---------------|-------------|
| 1 | **Comp** | 🔵 Azul | Comp | ✅ Habilitada |
| 2 | **Roto** | 🔵 Azul | Roto | ❌ Deshabilitada |
| 3 | **Cleanup** | 🔵 Cyan | Cleanup | ❌ Deshabilitada |
| 4 | **DMP** | 🟡 Amarillo | DMP | ❌ Deshabilitada |
| 5 | **Model** | 🟠 Naranja | Model | ❌ Deshabilitada |
| 6 | **Retopo** | 🟠 Naranja | Retopo | ❌ Deshabilitada |
| 7 | **Rigging** | 🟢 Verde | Rigging | ❌ Deshabilitada |
| 8 | **Shaders** | 🟢 Verde | Shaders | ❌ Deshabilitada |
| 9 | **Match Move** | 🟣 Morado | Match Move | ❌ Deshabilitada |
| 10 | **Animation** | 🟠 Naranja | Animation | ❌ Deshabilitada |
| 11 | **FX** | 🟣 Magenta | FX | ❌ Deshabilitada |
| 12 | **Lighting** | 🟢 Verde | Lighting | ❌ Deshabilitada |

**Nota importante:** El orden de las tasks en la UI coincide exactamente con el orden en ShotGrid. Los colores también son exactos según los pipeline steps configurados.

### ✅ Creación de Shots sin Templates
- Crea shots directamente sin depender de templates predefinidos
- Genera automáticamente las tasks habilitadas con estado "noread"
- Mayor control sobre la creación de tasks
- Compatible con cualquier proyecto

### ✅ Sistema de Nomenclatura Dual
- **Formato con descripción:** `PROYECTO_SEQ_SHOT_DESC1_DESC2`
- **Formato simplificado:** `PROYECTO_SEQ_SHOT`
- Detección automática del formato basado en el campo 5 del nombre

### ✅ Características Avanzadas
- Creación de thumbnails automática desde Hiero
- Configuración de estados de shot y task
- Copia de descripción del shot a las tasks
- Reducción automática del 30% en tiempo estimado (v1.30)
- Interfaz gráfica intuitiva
- Procesamiento en segundo plano

### ✅ Creación Automática de Carpetas (v1.33) 🚀
- **Estructura jerárquica completa:** Crea automáticamente todas las subcarpetas necesarias por task
- **Tasks 2D y 3D:** Soporte completo para ambas jerarquías (comp, roto, cleanup, DMP directamente en SHOTNAME/, tasks 3D bajo SHOTNAME/3D/)
- **Detección inteligente:** Verifica existencia de carpetas antes de crearlas
- **Logging detallado:** Muestra exactamente qué carpetas se crean y cuáles ya existían
- **Normalización de paths:** Manejo consistente de rutas para evitar conflictos
- **Integración completa:** Funciona tanto en creación como en modificación de shots

## Uso del Script

### En Hiero/Nuke Studio

**Método 1: Usando el playhead (recomendado)**
1. **Posicionar el playhead** sobre el clip en el track `_comp_` que quieres procesar
2. **Ejecutar script:** `LGA_NKS_Flow_CreateShot.py`
3. **Configurar opciones** en el diálogo
4. **Hacer clic en "Create Shot"**
5. **Monitorear progreso** en la ventana de estado

**Método 2: Selección múltiple**
1. **Seleccionar múltiples clips** en el track `_comp_` del timeline
2. **Ejecutar script:** `LGA_NKS_Flow_CreateShot.py`
3. **Configurar opciones** en el diálogo (se aplicarán a todos los clips seleccionados)
4. **Hacer clic en "Create Shot"**
5. **Monitorear progreso** en la ventana de estado

**Nota:** El script usa el método híbrido centralizado:
- Si hay múltiples clips seleccionados en el track `_comp_`, procesa todos ellos
- Si no hay selección múltiple, usa el clip del playhead en el track `_comp_`
- Si no hay clip en el playhead, usa el primer clip seleccionado como fallback

### Resultado

Para cada clip seleccionado:
- Se crea un shot en ShotGrid (si no existe)
- Se crean todas las tasks habilitadas (ej: Comp, Roto)
- Cada task se crea con su pipeline step correspondiente
- Se asignan los reviewers seleccionados como `task_reviewers`
- Se aplica reducción del 30% al tiempo estimado antes de subirlo
- Se sube thumbnail desde Hiero
- Se actualizan estados según configuración
- **Se crea automáticamente la estructura de carpetas** para cada task habilitada (ver sección "Estructura de Carpetas Automática")
- Tasks deshabilitadas no se crean (ni en ShotGrid ni carpetas)
- Si el shot ya existía en Flow, se muestra un mensaje informativo y se lanza automáticamente Modify Shot (selección única) o se cancela mostrando la lista de shots existentes (selección múltiple)

## Modify Shot

**Archivo:** `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`

Complementa a Create Shot y permite ajustar un shot existente conservando sus estados actuales:

1. **Carga de información:** Consulta Flow para traer la descripción, secuencia y tasks reales del shot (solo admite un clip).
2. **UI compartida:** Reutiliza la misma ventana compacta de Create Shot; las tasks existentes aparecen tildadas y bloqueadas, las nuevas se configuran igual que en Create Shot.
3. **Modificaciones inteligentes:**
   - Tasks que siguen tildadas → se dejan intactas (no se tocan estados, tiempos ni reviewers)
   - Tasks que se destildaron → se eliminan del shot en Flow
   - Tasks nuevas tildadas → se crean con pipeline step, reviewers, descripción y estimados (con reducción del 30%)
   - **Se crea automáticamente la estructura de carpetas** para las nuevas tasks agregadas
   - Si la descripción del shot cambió, se actualiza tanto en el shot como en todas las tasks restantes
4. **Estados intocables:** Nunca cambia el estado del shot ni el de las tasks existentes; solo agrega/quita tasks y sincroniza la descripción.

## Configuración del Usuario

### Diálogo de Configuración

#### Configuración del Shot (3 columnas)
- **Thumbnail + Description:** Vista previa del shot y campo de texto para descripción
- **Sequence:** Campo de entrada para nombre de secuencia
- **Shot status:** ☑️ Ready to start (checkbox)
- **Priority:** ☑️ High (checkbox)

#### Configuración de Tasks (5 columnas por task)

Cada task tiene su propia fila con:

- **[NOMBRE TASK]:** ☑️ (habilitar/deshabilitar creación de esta task)
- **Est. Days:** Campo numérico para tiempo estimado (0-99.9)
  - ⚠️ **Nota importante:** El valor ingresado se reduce automáticamente un 30% antes de subirse a Flow (ej: 1 día → 0.7 días)
- **Status:** ☑️ Ready to start (estado inicial de la task)
- **Description:** ☑️ copy from shot (copiar descripción del shot)
- **Reviewers:** Checkboxes horizontales (solo nombres en UI)
  - ☑️ Lega
  - ☑️ Sebas
  - ☑️ Juano
  - ☑️ Javi

**Comportamiento (v1.29 - Diseño Compacto):**
- **Task DESHABILITADA (☐):**
  - Solo muestra: `☐ [NOMBRE TASK]` en 1 línea
  - No muestra separador
  - No muestra columnas de configuración
  - Ocupa espacio mínimo
  
- **Task HABILITADA (☑):**
  - Muestra separador
  - Muestra: `☑ [NOMBRE TASK]`
  - Muestra todas las columnas: Est. Days, Status, Description, Reviewers
  - Ocupa ~3 líneas

- **Comp:** Habilitada por defecto (muestra columnas)
- **Todas las demás:** Deshabilitadas por defecto (solo 1 línea cada una)

#### Ejemplo Visual de la UI (v1.29) - Diseño Compacto

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Flow | Shot Creation                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│  Configuración del Shot (3 columnas):                                         │
│  [Thumbnail]  [Description]  │  [Sequence]  │  [Status + Priority]           │
├──────────────────────────────────────────────────────────────────────────────┤
│  ☑ 🔵 COMP                                                                    │
│      Est.Days [2] │ Status ☑Ready │ Desc ☑copy │ Rev: ☑Lega ☑Sebas ☑Juano ☑Javi │
│  (HABILITADA - muestra separador + todas las columnas)                       │
├──────────────────────────────────────────────────────────────────────────────┤
│  ☐ 🔵 ROTO                                                                    │
│  ☐ 🔵 CLEANUP                                                                 │
│  ☐ 🟡 DMP                                                                     │
│  ☐ 🟠 MODEL                                                                   │
│  ☐ 🟠 RETOPO                                                                  │
│  ☐ 🟢 RIGGING                                                                 │
│  ☐ 🟢 SHADERS                                                                 │
│  ☐ 🟣 MATCH MOVE                                                              │
│  ☐ 🟠 ANIMATION                                                               │
│  ☐ 🟣 FX                                                                      │
│  ☐ 🟢 LIGHTING                                                                │
│  (DESHABILITADAS - solo checkbox + nombre, sin separador ni columnas)        │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Ventajas del Diseño Compacto (v1.29):**
- ✅ Tasks deshabilitadas ocupan **1 línea** cada una
- ✅ Sin separadores cuando está deshabilitada = más espacio
- ✅ Sin columnas visibles cuando está deshabilitada = UI limpia
- ✅ Las 12 tasks caben en pantalla sin scroll
- ✅ Checkbox a la izquierda = más intuitivo
- ✅ Colores de pipeline steps visibles siempre

### Estados de Task

| Estado | Descripción |
|--------|-------------|
| `noread` | Estado inicial (creado por defecto) |
| `ready` | Listo para comenzar trabajo |
| `ip` | En progreso |
| `rev` | En revisión |
| `apr` | Aprobado |

## Estructura de Carpetas Automática

### Jerarquía por Task

El script crea automáticamente la siguiente estructura de carpetas cuando se habilita cada task:

#### Tasks 2D (Directorio del Shot)
```
SHOTNAME/
├── comp/
│   ├── 0_assets/            # Assets compartidos
│   ├── 1_projects/           # Scripts de Nuke (comp_v001.nk, comp_v002.nk, ...)
│   ├── 2_prerenders/        # Prerenders intermedios
│   ├── 3_review/            # Videos de review (comp_v001.mov, comp_v002.mov, ...)
│   └── 4_publish/           # Publicaciones EXR (subcarpetas: comp_v001/, comp_v002/, ...)
├── roto/
│   ├── 0_assets/            # Assets compartidos
│   ├── 1_projects/           # Scripts de Nuke (roto_v001.nk, roto_v002.nk, ...)
│   ├── 2_prerenders/        # Prerenders intermedios
│   ├── 3_review/            # Videos de review (roto_v001.mov, roto_v002.mov, ...)
│   └── 4_publish/           # Publicaciones EXR (subcarpetas: roto_v001/, roto_v002/, ...)
├── cleanup/
│   ├── 0_assets/            # Assets compartidos
│   ├── 1_projects/           # Scripts de Nuke (cleanup_v001.nk, cleanup_v002.nk, ...)
│   ├── 2_prerenders/        # Prerenders intermedios
│   ├── 3_review/            # Videos de review (cleanup_v001.mov, cleanup_v002.mov, ...)
│   └── 4_publish/           # Publicaciones EXR (subcarpetas: cleanup_v001/, cleanup_v002/, ...)
└── DMP/
    ├── 0_assets/            # Assets compartidos
    ├── 1_projects/           # Proyectos DMP (DMP_v001.mb, DMP_v002.mb, ...)
    ├── 2_prerenders/        # Prerenders intermedios
    ├── 3_review/            # Videos de review (DMP_v001.mov, DMP_v002.mov, ...)
    └── 4_publish/           # Publicaciones (archivos: DMP_v001.mb, DMP_v002.mb, ...)
```

#### Tasks 3D (Subdirectorio 3D/)
```
SHOTNAME/
└── 3D/
    ├── 1_matchMove/
    │   ├── 0_assets/        # Assets compartidos
    │   ├── 1_projects/       # Proyectos Match Move (matchmove_v001.mb, matchmove_v002.mb, ...)
    │   ├── 2_prerenders/    # Prerenders intermedios
    │   ├── 3_review/        # Videos de review (matchmove_v001.mov, matchmove_v002.mov, ...)
    │   └── 4_publish/       # Publicaciones (archivos: matchmove_v001.mb, matchmove_v002.mb, ...)
    ├── 2_model/
    │   ├── 0_assets/        # Assets compartidos
    │   ├── 1_projects/       # Proyectos Modelado (model_v001.mb, model_v002.mb, ...)
    │   ├── 2_prerenders/    # Prerenders intermedios
    │   ├── 3_review/        # Videos de review (model_v001.mov, model_v002.mov, ...)
    │   └── 4_publish/       # Publicaciones (archivos: model_v001.mb, model_v002.mb, ...)
    ├── 3_retopo/
    │   ├── 0_assets/        # Assets compartidos
    │   ├── 1_projects/       # Proyectos Retopo (retopo_v001.mb, retopo_v002.mb, ...)
    │   ├── 2_prerenders/    # Prerenders intermedios
    │   ├── 3_review/        # Videos de review (retopo_v001.mov, retopo_v002.mov, ...)
    │   └── 4_publish/       # Publicaciones (archivos: retopo_v001.mb, retopo_v002.mb, ...)
    ├── 4_rigging/
    │   ├── 0_assets/        # Assets compartidos
    │   ├── 1_projects/       # Proyectos Rigging (rigging_v001.mb, rigging_v002.mb, ...)
    │   ├── 2_prerenders/    # Prerenders intermedios
    │   ├── 3_review/        # Videos de review (rigging_v001.mov, rigging_v002.mov, ...)
    │   └── 4_publish/       # Publicaciones (archivos: rigging_v001.mb, rigging_v002.mb, ...)
    ├── 5_shaders/
    │   ├── 0_assets/        # Assets compartidos
    │   ├── 1_projects/       # Proyectos Shaders (shaders_v001.mb, shaders_v002.mb, ...)
    │   ├── 2_prerenders/    # Prerenders intermedios
    │   ├── 3_review/        # Videos de review (shaders_v001.mov, shaders_v002.mov, ...)
    │   └── 4_publish/       # Publicaciones (archivos: shaders_v001.mb, shaders_v002.mb, ...)
    ├── 6_animation/
    │   ├── 0_assets/        # Assets compartidos
    │   ├── 1_projects/       # Proyectos Animación (animation_v001.mb, animation_v002.mb, ...)
    │   ├── 2_prerenders/    # Prerenders intermedios
    │   ├── 3_review/        # Videos de review (animation_v001.mov, animation_v002.mov, ...)
    │   └── 4_publish/       # Publicaciones (archivos: animation_v001.mb, animation_v002.mb, ...)
    ├── 7_fx/
    │   ├── 0_assets/        # Assets compartidos
    │   ├── 1_projects/       # Proyectos FX (fx_v001.mb, fx_v002.mb, ...)
    │   ├── 2_prerenders/    # Prerenders intermedios
    │   ├── 3_review/        # Videos de review (fx_v001.mov, fx_v002.mov, ...)
    │   └── 4_publish/       # Publicaciones (archivos: fx_v001.mb, fx_v002.mb, ...)
    └── 8_lighting/
        ├── 0_assets/        # Assets compartidos
        ├── 1_projects/       # Proyectos Lighting (lighting_v001.mb, lighting_v002.mb, ...)
        ├── 2_prerenders/    # Prerenders intermedios
        ├── 3_review/        # Videos de review (lighting_v001.mov, lighting_v002.mov, ...)
        └── 4_publish/       # Publicaciones EXR (subcarpetas: lighting_v001/, lighting_v002/, ...)

```

### Comportamiento del Sistema

- **Verificación previa:** Antes de crear carpetas, verifica si ya existen (no duplica)
- **Logging detallado:** Muestra exactamente qué carpetas se crean y cuáles ya existían usando `debug_print()`
- **Normalización de paths:** Maneja rutas de forma consistente (Windows/Unix compatible)
- **Creación recursiva:** Crea automáticamente todos los directorios padre necesarios con `os.makedirs(exist_ok=True)`
- **Integración automática:** 
- En `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`: Se ejecuta después de crear el shot y las tasks
- En `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`: Se ejecuta cuando se agregan nuevas tasks a shots existentes
- **Cálculo de path base:** El `shot_base_path` se calcula como 4 niveles arriba del archivo EXR del clip usando `HieroOperations.calculate_shot_base_path()`

### Ejemplo de Output en Logs

```
🏗️  Creando estructura de carpetas para shot: /project/seq/shot_001
📋 Tasks a procesar: Comp, Model, Lighting
🔧 Procesando task: Comp
✅ Carpeta creada: /project/seq/shot_001/comp/0_assets
✅ Carpeta creada: /project/seq/shot_001/comp/1_projects
📁 Carpeta ya existe: /project/seq/shot_001/comp/2_prerenders
✅ Carpeta creada: /project/seq/shot_001/comp/3_review
✅ Carpeta creada: /project/seq/shot_001/comp/4_publish
🎯 Resumen de carpetas:
   ✅ Creadas: 4
   📁 Existentes: 1
```

## Arquitectura del Código

### Estructura Principal

**Archivo principal:** `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`

```
LGA_NKS_Flow_CreateShot.py
├── AVAILABLE_TASKS (configuración de tasks disponibles)
├── Conexión ShotGrid
├── Funciones de Thumbnail
├── Clases de UI (ShotConfigDialog, FlowStatusWindow)
├── ShotGridManager (lógica de negocio)
│   └── create_shot() - Crea shot y llama a creación de carpetas
├── HieroOperations (operaciones en Hiero)
│   └── calculate_shot_base_path() - Calcula path base del shot (4 niveles arriba del archivo)
├── Worker (procesamiento en background)
└── Integración con LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py
    └── create_folders_for_shot_tasks() - Crea estructura de carpetas automáticamente
```

**Integración:** Después de crear el shot y las tasks en ShotGrid, el script calcula el `shot_base_path` desde el archivo EXR del clip y llama automáticamente a `create_folders_for_shot_tasks()` para crear todas las carpetas necesarias.

### Módulo de Carpetas

**Archivo:** `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`

Módulo dedicado a la creación automática de estructura de carpetas. Se integra automáticamente con `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py` y `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`.

**Funciones principales:**
- `create_folders_for_shot_tasks(shot_path, enabled_tasks)` - Función principal de integración, devuelve `(dict, list)` con resumen y logs
- `create_task_folders(shot_base_path, task_names)` - Crea estructura completa para múltiples tasks
- `ensure_folder_exists(folder_path)` - Crea carpeta individual si no existe
- `validate_shot_base_path(shot_base_path)` - Valida permisos y existencia del path base
- `normalize_path(path)` - Normaliza rutas para comparación consistente

**Estructura de datos:**
- `TASK_FOLDER_STRUCTURE` - Diccionario que mapea nombre de task a lista de subcarpetas relativas

**Características:**
- Estructura definida en diccionario para fácil mantenimiento
- Logging integrado compatible con `debug_print()` del sistema
- Validación de permisos y existencia antes de crear
- Normalización automática de rutas (Windows/Unix compatible)
- Verificación previa: solo crea carpetas que no existen

### Cómo Agregar una Nueva Task

**¡Es súper fácil!** Solo necesitas agregar una entrada a `AVAILABLE_TASKS`:

```python
AVAILABLE_TASKS = [
    {
        "name": "Comp",
        "pipeline_step": "Comp",
        "enabled_by_default": True,
        "color": "#3B9ACA",
    },
    {
        "name": "Roto",
        "pipeline_step": "Roto",
        "enabled_by_default": False,
        "color": "#3B9ACA",
    },
    # ¡Agregar tu nueva task aquí! ⬇️
    {
        "name": "Animation",           # Nombre que aparecerá en UI y ShotGrid
        "pipeline_step": "Animation",   # Pipeline step en ShotGrid
        "enabled_by_default": False,    # Checkbox apagado por defecto
        "color": "#CA7A3B",            # Color del pipeline step
    },
]
```

**¡Eso es todo!** El resto del código se encarga automáticamente de:
- Generar la UI con todos los campos
- Aplicar el color específico de la task
- Habilitar/deshabilitar campos según el checkbox
- Crear la task en ShotGrid con el pipeline step correcto
- Asignar reviewers, descripción, días estimados (con reducción del 30%), etc.

**IMPORTANTE:** El `pipeline_step` debe coincidir exactamente con el código del Step en ShotGrid. Si no existe, se mostrará una advertencia pero la task se creará de todos modos (sin pipeline step asignado).

### Funciones Clave

#### `create_task_row(task_config)` ⭐ REFACTORIZADO v1.29
- Genera dinámicamente UI compacta para una task
- **Estructura de 2 niveles:**
  1. Línea header: checkbox + nombre (siempre visible)
  2. Widget columns: todas las columnas (visible solo si habilitada)
- Retorna layout con todos los widgets
- Checkbox a la izquierda del nombre
- Totalmente genérico y reutilizable

#### `toggle_task_fields(task_name, enabled)` ⭐ SIMPLIFICADO v1.29
- **Muestra/oculta** el widget de columnas completo (no solo deshabilita)
- **Muestra/oculta** el separador
- Diseño compacto: tasks deshabilitadas ocupan 1 línea
- Código ultra-simple: solo llamadas a `setVisible()`

#### `create_task_for_shot(...)` ⭐ NUEVO
- Crea una task para un shot de forma completamente genérica
- Busca automáticamente el pipeline step correspondiente
- Aplica toda la configuración (status, descripción, días con reducción del 30%, reviewers)
- Reutilizable para cualquier tipo de task

#### `create_shot(project_id, shot_code, shot_config, thumbnail_path=None)`
- Crea shot sin template
- Itera sobre todas las tasks habilitadas y las crea dinámicamente
- Sube thumbnail si está disponible

#### `find_tasks_for_shot(shot_id, shot_config)`
- Busca tasks existentes del shot
- Actualiza estados según configuración
- Copia descripciones si está habilitado

## Campos ShotGrid Utilizados

### Entidad Shot
- `code`: Código del shot
- `description`: Descripción
- `sg_sequence`: Secuencia padre
- `sg_status_list`: Estado del shot
- `sg_prioridad`: Prioridad del shot ("high" si activado, opcional)
- `project`: Proyecto

### Entidad Task
- `content`: Nombre de la task ("Comp")
- `entity`: Shot padre
- `step`: Pipeline step (asignado automáticamente según la task)
- `sg_status_list`: Estado de la task
- `sg_description`: Descripción (opcional, puede copiarse del shot)
- `sg_estdias`: Tiempo estimado en días (opcional, solo si > 0)
  - ⚠️ **Nota:** El valor ingresado por el usuario se reduce automáticamente un 30% antes de subirse a Flow (ej: 1 día ingresado → 0.7 días en Flow)
- `task_reviewers`: Lista de usuarios asignados como reviewers
- `project`: Proyecto

### Entidad Step (Pipeline Steps)
- `code`: Código del step (ej: "Comp", "Animation", "Lighting")
- **Nota:** Los pipeline steps son entidades globales en ShotGrid y no están asociados a proyectos específicos

## Sistema de Logging

### Variables de Debug
```python
DEBUG = False  # Cambiar a True para debug detallado
```

### Sistema de Logging Seguro para Hilos
El script utiliza un sistema de logging seguro para entornos multi-hilo que evita conflictos con la GUI de Hiero:

- **Acumulación en memoria:** Los mensajes de debug se acumulan en una lista durante el procesamiento en hilos separados
- **Impresión diferida:** Los logs se imprimen solo al finalizar la operación, evitando crashes por acceso concurrente a la consola
- **Señales seguras:** Utiliza señales Qt para coordinar la impresión de logs entre hilos

### Niveles de Log
- **INFO:** Operaciones normales
- **DEBUG:** Detalles técnicos (solo con DEBUG=True, se imprime al final)
- **ERROR:** Errores críticos

## Compatibilidad

### Versiones Soportadas
- **ShotGrid/Flow:** Todas las versiones recientes
- **Hiero/Nuke Studio:** 12.0+
- **Python:** 3.6+

### Proyectos Soportados
- Funciona en cualquier proyecto ShotGrid
- No requiere configuración específica por proyecto
- Compatible con diferentes esquemas de tasks

## Mantenimiento y Troubleshooting

### Logs de Error Comunes

**"No se encontró la secuencia"**
- Verificar que la secuencia existe en ShotGrid
- Revisar permisos de acceso

**"Error al crear el shot"**
- Verificar permisos de creación en ShotGrid
- Revisar campos obligatorios

**"No se pudieron obtener credenciales"**
- Verificar archivo SecureConfig_Reader.py
- Revisar variables de entorno

### Archivos de Configuración

**SecureConfig_Reader.py**
```python
# Debe contener función get_flow_credentials()
# Retorna: sg_url, sg_login, sg_password
```

**LGA_NKS_Flow_NamingUtils.py**
- Funciones de parsing de nombres de archivo
- Detección automática de formato

## Historial de Versiones

### v1.34 - Creación Automática de Carpetas Implementada ⭐
- ✅ **Módulo de carpetas:** `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py` implementado
- ✅ **Integración completa:** Creación automática de estructura de carpetas en CreateShot y ModifyShot
- ✅ **Soporte completo:** Todas las tasks 2D y 3D con sus subcarpetas (0_assets, 1_projects, 2_prerenders, 3_review, 4_publish)
- ✅ **Logging detallado:** Muestra carpetas creadas vs existentes usando sistema de debug_print

### v1.33 - Pre-chequeo Inteligente + Creación Automática de Carpetas ⭐⭐
- ✅ **Pre-chequeo inteligente antes de mostrar UI:**
  - Ventana "Comprobando existencia de los shots en Flow"
  - Selecciones múltiples: se cancela la creación si alguno ya existe y se listan los códigos detectados
  - Selección única: si el shot ya existe se dispara automáticamente Modify Shot
  - Garantiza que Create Shot solo cree entidades nuevas
- ✅ **Creación automática de carpetas por task:**
  - Estructura jerárquica completa para todas las tasks (2D y 3D)
  - Verificación inteligente de existencia antes de crear
  - Logging detallado de carpetas creadas/existentes
  - Normalización automática de paths
  - Integración completa con Create Shot y Modify Shot
- ✅ **Módulo modular:** `LGA_NKS_Flow_CreateShot_Folders.py` para mantenibilidad

### v1.31 - Método Híbrido Centralizado con Selección Múltiple ⭐
- ✅ **Migración al módulo centralizado `LGA_NKS_GetClip`:**
  - Usa `get_clips_to_process()` con `prioritize_multiple_selection=True` para permitir selección múltiple
  - Respeta `TRACK_comp_EXR` del módulo (actualmente `"_comp_"`) usando `track_name=None`
  - Método híbrido: playhead primero, luego selección como fallback
- ✅ **Soporte para selección múltiple:**
  - Si hay múltiples clips seleccionados en el track `_comp_`, procesa todos ellos
  - Si no hay selección múltiple, usa el clip del playhead
  - Más intuitivo y flexible para workflows de producción
- ✅ **Código más mantenible:**
  - Eliminada duplicación de código de selección de clips
  - Centralizado en módulo utilitario compartido
  - Sincronización de debug con el módulo centralizado

### v1.30 - Reducción Automática de Tiempo Estimado ⭐
- ✅ **Reducción automática del 30% en tiempo estimado:**
  - El valor ingresado por el usuario se reduce un 30% antes de subirse a Flow
  - Ejemplo: 1 día ingresado → 0.7 días en Flow
  - Aplicado automáticamente en `create_task_for_shot()`
  - Log de debug muestra el valor original y el valor reducido

### v1.29.1 - Fixes y Ajustes
- ✅ **Restaurados tamaños de fuente originales:**
  - Nombres de tasks: 12px (no 11px)
  - Labels de columnas: tamaños originales
  - Padding restaurado: 5px para checkboxes, 15px para labels
- ✅ **Ventana se ajusta automáticamente:**
  - Método `adjust_window_size()` agregado
  - QTimer para ajuste después de actualización de layout
  - Altura mínima removida para permitir crecimiento dinámico
- ✅ **Fix:** Campos de entrada de días: 80px width (no 70px)

### v1.29 - UI Compacta ⭐⭐
- ✅ **Diseño compacto extremadamente eficiente:**
  - Tasks deshabilitadas: solo checkbox + nombre (1 línea)
  - Tasks habilitadas: checkbox + nombre + todas las columnas + separador
- ✅ **Checkbox movido a la izquierda** del nombre (más intuitivo)
- ✅ **Hide/show dinámico:** Columnas y separadores aparecen solo cuando se habilita la task
- ✅ **Optimización de espacio:** Las 12 tasks caben en pantalla sin scroll
- ✅ **UI limpia:** Sin campos deshabilitados visualmente "grises"
- ✅ **Método `toggle_task_fields()` simplificado:** Solo show/hide de widgets

### v1.28 - Pipeline Completo con Colores ⭐
- ✅ **12 tasks del pipeline agregadas:** Comp, Roto, Cleanup, DMP, Model, Retopo, Rigging, Shaders, Match Move, Animation, FX, Lighting
- ✅ **Colores específicos por task:** Cada task muestra su color de pipeline step en la UI
- ✅ **Sistema de colores implementado:** 
  - 🔵 Azul: Comp, Roto
  - 🔵 Cyan: Cleanup
  - 🟡 Amarillo: DMP
  - 🟠 Naranja: Model, Retopo, Animation
  - 🟢 Verde: Rigging, Shaders, Lighting
  - 🟣 Morado: Match Move
  - 🟣 Magenta: FX
- ✅ **Orden respetado:** Mismo orden que en ShotGrid
- ✅ **Todo funcional:** Todas las tasks se crean con sus pipeline steps correctos

### v1.27 - Sistema Modular de Tasks ⭐
- ✅ **Refactorización completa a código DRY (Don't Repeat Yourself)**
- ✅ **Sistema modular:** Agregar nuevas tasks es tan fácil como agregar una línea
- ✅ **UI dinámica:** Generada automáticamente desde `AVAILABLE_TASKS`
- ✅ **Creación genérica de tasks en ShotGrid**
- ✅ **Task Roto agregada** (deshabilitada por defecto)
- ✅ **Enable/disable dinámico:** Campos se ocultan cuando task está deshabilitada
- ✅ **Estructura de datos mejorada:** `shot_config["tasks"]` con configuración por task
- ✅ **Método `create_task_row()`:** Genera UI dinámicamente
- ✅ **Método `toggle_task_fields()`:** Maneja show/hide de campos
- ✅ **Método `create_task_for_shot()`:** Crea cualquier task de forma genérica
- ✅ **Preparado para el futuro:** Fácil agregar más tasks

### v1.26 - UI Reorganizada para Task Comp
- ✅ Layout reorganizado: 3 columnas para configuración del shot
- ✅ 5 columnas dedicadas para configuración de Task Comp
- ✅ Checkbox de habilitación para Task Comp
- ✅ Reviewers mostrados solo con nombres (sin apellidos) en UI

### v1.25 - Checkbox "High Priority"
- ✅ Agregado checkbox "High Priority" para asignar sg_prioridad="high"

### v1.24 - Mensajes Diferenciados para Shots
- ✅ Shots existentes muestran mensaje de error en rojo
- ✅ Solo shots recién creados cuentan como éxito
- ✅ Mejor feedback visual para el usuario
- ✅ Lógica clara: crear = verde, existente = rojo
- ✅ Task Comp asignada automáticamente al pipeline step "Comp"

### v1.23 - Sistema de Logging Seguro para Hilos
- ✅ Sistema de logging multi-hilo seguro
- ✅ Impresión diferida de debug logs para evitar crashes
- ✅ Señalización Qt para coordinación entre hilos
- ✅ Compatible con procesamiento en background

### v1.22 - Campo de Tiempo Estimado
- ✅ Agregado campo numérico para tiempo estimado en días (0-99.9)
- ✅ Soporte para valores decimales (ej: 12.5)
- ✅ Campo sg_estdias solo se envía si el valor es mayor que 0
- ✅ Validación de entrada con decimales

### v1.21 - Asignación de Reviewers
- ✅ Asigna reviewers a la task usando el campo task_reviewers
- ✅ Eliminada dependencia de templates
- ✅ Creación manual de tasks
- ✅ Asignación automática de reviewers
- ✅ Mayor compatibilidad entre proyectos
- ✅ Documentación completa

### v1.2 - Creación sin Templates
- ✅ Elimina dependencia de templates predefinidos
- ✅ Crea shots y tasks manualmente
- ✅ Mantiene compatibilidad con el workflow existente
- ✅ Funciona en cualquier proyecto

### v1.1 - Sistema Dual de Nomenclatura
- ✅ Detección automática de formato
- ✅ Compatibilidad PROYECTO_SEQ_SHOT_DESC1_DESC2
- ✅ Compatibilidad PROYECTO_SEQ_SHOT

### v1.0 - Versión Inicial
- ✅ Creación básica de shots
- ✅ Template "Template_comp" hardcodeado
- ✅ Solo proyecto LC

## Scripts Relacionados

- **LGA_NKS_Flow_Push.py:** Subida de versiones
- **LGA_NKS_Flow_Pull.py:** Descarga de datos
- **LGA_NKS_Flow_NamingUtils.py:** Utilidades de naming
- **LGA_NKS_Utils/LGA_NKS_GetClip.py:** Módulo centralizado para selección de clips (método híbrido)
- **LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py:** Modificación segura de shots ya existentes

## Conclusión

**v1.31** migra el script al método híbrido centralizado de selección de clips, permitiendo selección múltiple y mejorando la mantenibilidad del código. El script ahora usa el módulo `LGA_NKS_GetClip` que centraliza la lógica de selección de clips, respetando `TRACK_comp_EXR` (actualmente `"_comp_"`) y permitiendo trabajar tanto con el playhead como con selección múltiple.

### Evolución del Script

#### Antes (v1.26)
- Código hardcodeado para cada task
- Solo task Comp disponible
- Agregar una nueva task requería duplicar ~200 líneas de código
- UI generada manualmente
- Propenso a errores y difícil de mantener

#### v1.27 ⭐
- **Código DRY y modular**
- **Agregar nueva task: 1 entrada en `AVAILABLE_TASKS` (~5 líneas)**
- **UI generada dinámicamente**
- **Todo el comportamiento es automático**
- 2 tasks: Comp, Roto

#### v1.28 ⭐⭐
- **12 tasks del pipeline completo**
- **Sistema de colores implementado**
- **Orden y colores respetan ShotGrid exactamente**
- Tasks: Comp, Roto, Cleanup, DMP, Model, Retopo, Rigging, Shaders, Match Move, Animation, FX, Lighting
- Problema: Tasks deshabilitadas ocupaban mucho espacio vertical

#### v1.29 ⭐⭐⭐
- **UI compacta extremadamente eficiente**
- **Tasks deshabilitadas: 1 línea** (checkbox + nombre)
- **Tasks habilitadas: múltiples líneas** (checkbox + nombre + columnas + separador)
- **Las 12 tasks caben en pantalla** sin necesidad de scroll
- **Checkbox a la izquierda** del nombre (más intuitivo)
- **Hide/show dinámico** de columnas y separadores
- **Listo para producción** con interfaz optimizada

#### v1.30 ⭐⭐⭐⭐
- **Reducción automática del 30% en tiempo estimado**
- **Mejora la precisión de estimaciones en Flow**
- **Transparente para el usuario** (ingresa valor original, se reduce automáticamente)

#### v1.31 ⭐⭐⭐⭐⭐
- **Método híbrido centralizado** para selección de clips
- **Soporte para selección múltiple** en el track `_comp_`
- **Código más mantenible** usando módulo utilitario compartido
- **Más intuitivo** para workflows de producción

#### v1.34 ⭐⭐⭐⭐⭐⭐
- **Creación automática de carpetas** por task
- **Módulo modular** `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`
- **Integración completa** con CreateShot y ModifyShot
- **Estructura completa** para todas las tasks 2D y 3D

### Ventajas del Sistema Actual

✅ **Modularidad:** Agregar/modificar tasks es trivial
✅ **Consistencia:** Colores y nombres coinciden con ShotGrid
✅ **Escalabilidad:** 12 tasks funcionan igual que 2
✅ **Mantenibilidad:** Código limpio y DRY
✅ **Flexibilidad:** Habilitar solo las tasks necesarias por shot
✅ **Sin templates:** Funciona en cualquier proyecto
✅ **Precisión:** Reducción automática del 30% mejora estimaciones
✅ **Automatización completa:** Creación automática de carpetas por task
✅ **Estructura organizada:** Jerarquía clara 2D/3D con subcarpetas estandarizadas

Esta versión del script representa una mejora significativa al eliminar dependencias de templates específicos, permitiendo que funcione de manera consistente en cualquier proyecto ShotGrid mientras mantiene toda la funcionalidad original.

La refactorización a código modular asegura que el script sea fácil de mantener y extender en el futuro, sin necesidad de duplicar lógica.
