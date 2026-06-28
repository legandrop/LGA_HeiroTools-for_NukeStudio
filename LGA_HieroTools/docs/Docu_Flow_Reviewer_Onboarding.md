> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Alta/Baja de Reviewers en Flow y HieroTools

Cuando entra o sale un reviewer del estudio hay que actualizar Flow y todos los puntos del codigo que conocen estados, colores, usuarios y botones de review. Charly es el caso de referencia reciente.

## Checklist

1. En Flow/ShotGrid, agregar o quitar el estado de task correspondiente en `Task.sg_status_list`.
2. Definir el codigo SG del estado, el nombre visible y los colores de UI/timeline.
3. Actualizar Create/Modify Shot para que el reviewer exista como checkbox de `task_reviewers`.
4. Actualizar Flow Push para traducir botones/estados de Hiero hacia el codigo SG.
5. Actualizar Flow Pull para reconocer el estado, pintar clips, taggear carpetas y mostrar filas de review del usuario actual.
6. Actualizar Playlist Push/Pull si el reviewer tambien aplica al flujo de playlist.
7. Actualizar ViewerTL para que el usuario tenga botones dinamicos `Prev Rev` / `Next Rev`.
8. Actualizar `PrevNext Rev` para que pueda buscar clips con el color del reviewer.
9. Actualizar la documentacion de estados/reviewers y el changelog general.

## Mapeo actual

| Reviewer | Codigo SG task status | Color timeline | Login/alias principal | Rev type ViewerTL |
|----------|-----------------------|----------------|-----------------------|-------------------|
| Lega     | `revleg`              | `#69135e`      | `lega` / `lega_pugliese` | `lega` |
| Sebas    | `rev_su`              | `#bd7f9f`      | `sebas` / `sebasromano_post` / `sebas_romano` | `sup` |
| Charly   | `revcha`              | `#a9909d`      | `charly` / `charly_villafane` | `charly` |
| Juano    | `revjua`              | `#7F4B69`      | `juano` / `juanolivares` | `juano` |
| Javi     | `revjav`              | `#9c3e5e`      | `javi` / `javi_bravo` | `javi` |

## Referencias tecnicas

- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
  - `TASK_STATES` - lista de estados de task visibles en Create/Modify Shot.
  - `REVIEWER_NAME_BY_KEY` - mapeo de checkbox interno a usuario real de Flow.
  - `resolve_reviewer_ids()` - convierte reviewers de UI a `HumanUser`.
  - `reviewers_config_from_task()` - lee `task_reviewers` desde Flow.
  - `ShotConfigDialog` - crea los checkboxes visibles de reviewers.
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`
  - `ModifyShotWorker` - aplica cambios de estado y reviewers a tasks existentes.
- `LGA_HieroTools/LGA_NKS_Flow_Panel.py`
  - Configuracion de botones de Flow Panel, incluyendo botones `Rev <Reviewer>`.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
  - `status_translation` - traduce labels de botones a codigos SG.
  - `task_status_dict` - colores/tags asociados a estados.
  - Bloques de decision que detectan estados de review para mensajes/tags.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
  - `ShotGridManager.task_status_dict` - colores de clips y tags para pull.
  - `_normalize_flow_login()` - aliases de login del usuario actual.
  - `_current_user_review_status_codes()` - estados que fuerzan filas de review en la tabla.
  - `HieroOperations.enable_or_disable_clips()` - lista de colores de review que habilitan clips.
- `LGA_HieroTools/LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Push.py`
  - `status_translation` y `task_status_dict` - equivalentes de playlist para push.
- `LGA_HieroTools/LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Pull.py`
  - `ShotGridManager.task_status_dict` y `enable_or_disable_clips()` - equivalentes de playlist para pull.
- `LGA_HieroTools/LGA_NKS_ViewerTL_Panel.py`
  - `ViewerPanel.create_dynamic_buttons()` - aliases, colores y botones dinamicos por usuario.
  - `prev_rev_<reviewer>()` / `next_rev_<reviewer>()` - dispatch hacia `LGA_NKS_PrevNext_Rev`.
- `LGA_HieroTools/LGA_NKS_ViewerTL_Panel_py/LGA_NKS_PrevNext_Rev.py`
  - `COLORS` - colores buscados por `rev_type`.
  - `find_clip_with_color()` - navega al clip anterior/siguiente del reviewer.
- `LGA_HieroTools/docs/Docu_Flow_Estados_Colores.md`
  - Documenta estados SG, colores y reviewers activos.
