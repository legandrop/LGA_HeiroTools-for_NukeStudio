> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Estados y Colores de Flow (Shot y Task)

Fuente de verdad de los estados (`sg_status_list`) de **Shot** y **Task** en Flow
(ShotGrid), sus nombres visibles en la UI de los paneles, los codigos reales de
Flow, los nombres reales de Flow y el color usado en la UI (dropdowns).

> Los codigos y nombres reales se obtuvieron consultando directamente Flow
> (`sg.schema_field_read(entity, "sg_status_list")` + entidad `Status`).
> Script de verificacion: `+Building_Blocks/LGA_Flow_QueryStates_TEMP.py`.

## Decision de colores

- **Color UI (dropdowns / este MD):** los del PNG de referencia del supervisor.
- **Color de clips del timeline:** los maneja `task_status_dict` en
  `LGA_NKS_Flow_Pull.py` / `LGA_NKS_Flow_Push.py`. **No se tocan** (son
  independientes de los dropdowns).
- **Color de Flow (`bg_color`):** se documenta solo como referencia; no se usa.

Render de los dropdowns (`ColoredStatusComboBox`):
- **Combo cerrado:** fondo del color del estado, texto contrastado (negro en
  fondos claros, `#cccccc` en fondos oscuros), linea vertical + flecha SVG.
- **Popup abierto:** fondo uniforme `#272727`; cada item con una **bolita** del
  color del estado a la izquierda y el nombre en `#cccccc`; hover/seleccion
  aclara la fila (`#3a3a3a`).

## Estados de SHOT (`Shot.sg_status_list`) — 7

| Nombre visible (UI) | Codigo SG | Nombre real en Flow | Color UI | Color Flow (ref) |
|---------------------|-----------|---------------------|----------|------------------|
| Not ready           | `noread`  | Not Ready To Start  | `#d3d3d3` | `#b6b6b6` |
| Omited              | `omit`    | omitted             | `#78b487` | (sin color) |
| Ready to start      | `ready`   | Ready To Start      | `#c2b234` | `#f9fe01` |
| In progress         | `progre`  | In Progress         | `#6443bf` | `#6d00f9` |
| In playlist         | `plylst`  | In Playlist         | `#99c153` | (sin color) |
| Approved            | `apr`     | Approved            | `#244c19` | `#19761b` |
| Delivery Ok         | `check`   | Delivery Checked    | `#52c233` | `#013101` |

**Default en Create Shot:** `ready` (Ready to start).

## Estados de TASK (`Task.sg_status_list`) — 14

| Nombre visible (UI) | Codigo SG | Nombre real en Flow | Color UI | Color Flow (ref) |
|---------------------|-----------|---------------------|----------|------------------|
| Not ready           | `noread`  | Not Ready To Start  | `#d3d3d3` | `#b6b6b6` |
| Omited              | `omit`    | omitted             | `#78b487` | (sin color) |
| Ready to start      | `ready`   | Ready To Start      | `#c2b234` | `#f9fe01` |
| In progress         | `progre`  | In Progress         | `#6443bf` | `#6d00f9` |
| Corrections         | `corr`    | Corrections         | `#2e77d4` | `#0136da` |
| Review Sebas        | `rev_su`  | Review Sup          | `#a65680` | `#fe7db3` |
| Review Charly       | `revcha`  | Review Charly       | `#a9909d` | `#8b0195` |
| Review Juano        | `revjua`  | Review Juano        | `#7f4b69` | `#8b0195` |
| Review Javi         | `revjav`  | review_javi         | `#8f3f72` | `#fe0062` |
| Review Lega         | `revleg`  | RevLega             | `#68135d` | `#6b0170` |
| Review Hold         | `revhld`  | Review Hold         | `#9e6a15` | `#f69b0c` |
| Review Dir          | `rev_di`  | Review Dir          | `#99c153` | `#a2cf00` |
| Approved            | `apr`     | Approved            | `#244c19` | `#19761b` |
| Delivery Ok         | `check`   | Delivery Checked    | `#52c233` | `#013101` |

**Default en Create Shot:** `ready` (Ready to start).

> Nota: el codigo `rev_su` (Flow lo llama "Review Sup") se muestra como
> **"Review Sebas"** en la UI. Es el estado de review del supervisor Sebas.

## Prioridad de SHOT (`Shot.sg_prioridad`) — 2

| Codigo SG | Nombre real en Flow |
|-----------|---------------------|
| `high`    | High                |
| `normal`  | Normal              |

## Reviewers de Task

Los reviewers son **asignaciones de personas** a la task (no un estado). En la UI
son checkboxes (Lega, Sebas, Juano, Charly, Javi) y se mapean a usuarios de Flow:

| Checkbox UI | Clave interna       | Nombre real en Flow |
|-------------|---------------------|---------------------|
| Lega        | `lega_pugliese`     | Lega Pugliese       |
| Sebas       | `sebas_romano`      | Sebas Romano        |
| Juano       | `juano`             | Juan Olivares       |
| Charly      | `charly_villafane`  | Charly Villafañe    |
| Javi        | `javi_bravo`        | Javi Bravo          |

## Referencias tecnicas

- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
  - `ShotConfigDialog` — dialogo de creacion/modificacion (dropdowns de estado).
  - `ColoredStatusComboBox` — combo con items coloreados (texto contrastado).
  - `create_shot()`, `create_task_for_shot()` — escriben `sg_status_list`.
  - `SHOT_STATES`, `TASK_STATES` — listas (nombre_visible, codigo, color) usadas por los dropdowns.
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`
  - `ModifyShotWorker` — aplica cambios de estado de shot y tasks.
  - `LoadShotInfoWorker` — trae shot, tasks y reviewers reales de Flow.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
  - `task_status_dict` — color de los clips del timeline (independiente de los dropdowns).
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
  - `task_status_dict`, `status_translation` — usados por el push de estados.
- `+Building_Blocks/LGA_Flow_QueryStates_TEMP.py` — script de verificacion contra Flow.
