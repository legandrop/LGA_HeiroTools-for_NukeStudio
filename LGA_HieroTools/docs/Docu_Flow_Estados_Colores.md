> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Estados y Colores de Flow (Shot y Task)

Fuente de verdad de los estados (`sg_status_list`) de **Shot** y **Task** en Flow
(ShotGrid), en los **dos sitios**: `wanka` (contexto studio) y `projbvfx`
(contexto client).

> Los codigos y nombres reales se obtienen consultando Flow directamente:
> `sg.schema_field_read(entity, "sg_status_list")["sg_status_list"]["properties"]["valid_values"]["value"]`
> y la entidad `Status` para nombre y `bg_color`.

**Regla:** los estados en HieroTools se llaman y se ordenan **igual que en Flow**.
Las unicas divergencias de nombre permitidas son las que estan declaradas abajo,
y son porque el nombre de Flow es un nombre interno feo o ambiguo:

| Codigo | Nombre en Flow | Nombre que usamos | Por que |
|---|---|---|---|
| `revleg` | Review Lega (wanka) / **Review Sup** (projb) | Review Lega | en projb el sup es Lega |

## Lo primero que hay que entender: los dos sitios NO tienen la misma lista

Empujar un codigo que el sitio no acepta falla con
`'xxx' is not a valid status`. No se detecta hasta que alguien aprieta el boton.

| | solo en studio (wanka) | solo en client (projbvfx) |
|---|---|---|
| Task | `rev_su`, `revcha`, `revjua`, `revjav` | `revprd` |
| Shot | — | `revprd` no aplica; los Shot son identicos |

Trampas concretas que ya causaron bugs:

- **`revleg` se llama distinto en cada sitio.** En wanka es "Review Lega"; en
  projbvfx es **"Review Sup"**, y es el unico reviewer del sitio.
- **Que una entidad `Status` exista no alcanza.** Lo que Flow valida al escribir
  es la lista de valores validos del campo. `pubsh` existia en los dos sitios y
  no estaba en el campo de wanka: escribirlo fallaba.
- **La cola de entrega es `pubsh` -> `check` -> `apr`**, y `apr` es el FINAL, lo
  da el cliente. Flow la tenia al reves (`apr` en el medio) hasta que se corrigio.
- **`pbshed` ya no se usa.** Era el "entregado" del Shot de projb; se reemplazo
  por `check`, que es el que manda PipeSync.

## Decision de colores

- **Color de clip del timeline:** `TASK_STATUS_CATALOG` en
  `LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py`. Fuente unica: la usan el Flow
  Panel para los botones, el Push y el Pull.
- **Color UI (dropdowns de Create Shot):** paleta propia en
  `ALL_SHOT_STATES` / `ALL_TASK_STATES` de `LGA_NKS_Flow_CreateShot.py`. Es
  deliberadamente distinta de la de los clips.
- **Color de Flow (`bg_color`):** referencia; es de donde salen los hex nuevos.

Los colores del catalogo se eligen para identificar el estado, no pensando en
que arriba va texto. Cada lugar donde se pintan resuelve la legibilidad a su
manera, y son criterios distintos a proposito:

- **Botones del Flow Panel y del Assignee Panel:** el texto es fijo (`#d8d8d8`),
  asi que lo que se ajusta es el FONDO. `ensure_max_luminance()` (en
  `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`) le pone un techo de luminancia de 135
  bajando el brillo pero manteniendo el tono. Se topea **solo el fondo del
  boton**: el `color` que el Push le pasa a `setColor()` sigue siendo el color
  real del estado, porque de ahi sale el color del clip en el timeline.
- **Dropdowns de Create Shot (`ColoredStatusComboBox`):** al reves, el fondo
  queda con el color exacto y lo que se adapta es el TEXTO (negro en fondos
  claros, `#cccccc` en oscuros).
- **Clips del timeline:** sin correccion. El color va tal cual, porque ahi no
  hay texto encima que dependa de el.

Render de los dropdowns (`ColoredStatusComboBox`):
- **Combo cerrado:** fondo del color del estado, texto contrastado (negro en
  fondos claros, `#cccccc` en fondos oscuros), linea vertical + flecha SVG.
- **Popup abierto:** fondo uniforme `#272727`; cada item con una **bolita** del
  color del estado a la izquierda y el nombre en `#cccccc`; hover/seleccion
  aclara la fila (`#3a3a3a`).

## Estados de TASK

| Nombre visible (UI) | Codigo SG | Nombre real en Flow | Color clip | studio | client |
|---|---|---|---|:--:|:--:|
| Not ready | `noread` | Not ready | `#000000` | si | si |
| Omited | `omit` | Omited | `#244c19` | si | si |
| Ready to start | `ready` | Ready to start | `#8a8a8a` | si | si |
| In progress | `progre` | In progress | `#7d4cff` | si | si |
| Corrections | `corr` | Corrections | `#2e77d4` | si | si |
| Review Sebas | `rev_su` | Review Sebas | `#bd7f9f` | si | **no** |
| Review Charly | `revcha` | Review Charly | `#a9909d` | si | **no** |
| Review Juano | `revjua` | Review Juano | `#7F4B69` | si | **no** |
| Review Javi | `revjav` | Review Javi | `#9c3e5e` | si | **no** |
| Review Lega | `revleg` | Review Lega / **Review Sup** en projb | `#69135e` | si | si |
| Review Hold | `revhld` | Review Hold | `#9E6A15` | si | si |
| Review Prod | `revprd` | Review Prod | `#8CBF3F` | **no** | si |
| Review Dir | `rev_di` | Review Dir | `#B5DB4B` | si | si |
| OK for Delivery | `pubsh` | OK for Delivery | `#50BFC7` | si | si |
| Delivered | `check` | Delivered | `#38A138` | si | si |
| Delivery Apr | `apr` | Delivery Apr | `#266612` | si | si |

`revprd` en Flow viene con `bg_color` `#D7F2B1`, pero ese lima tiene mas
luminancia que el gris de `noread` (`#d3d3d3`) y en un clip chico se lee como
blanco. Se usa `#8CBF3F`, el mismo ajuste que ya hizo PipeSync.

## Estados de SHOT

| Nombre visible (UI) | Codigo SG | Nombre real en Flow | studio | client |
|---|---|---|:--:|:--:|
| Not ready | `noread` | Not ready | si | si |
| Omited | `omit` | Omited | si | si |
| Ready to start | `ready` | Ready to start | si | si |
| In progress | `progre` | In progress | si | si |
| In playlist | `plylst` | In playlist | si | si |
| OK for Delivery | `pubsh` | OK for Delivery | si | si |
| Delivered | `check` | Delivered | si | si |
| Delivery Apr | `apr` | Delivery Apr | si | si |

**Default en Create Shot:** `ready` (Ready to start), shot y task.

## Botones de push del Flow Panel

Salen de `PUSH_BUTTONS` y se filtran con `get_push_buttons(mode)`. El **label es
la clave** con la que viaja el push hasta el conector, asi que el label y el
codigo tienen que definirse juntos y en un solo lugar.

| studio (11) | client (8) |
|---|---|
| Corrections, Rev Sebas, Rev Charly, Rev Juano, Rev Javi, Rev Lega, Rev Hold, Rev Dir, OK for Delivery, Delivered, Delivery Apr | Corrections, Rev Lega, Rev Hold, **Rev Prod**, Rev Dir, OK for Delivery, Delivered, Delivery Apr |

El **orden** es el mismo que el del `sg_status_list` de Flow y el de PipeSync.
Los labels de los botones van cortos (`Rev Sebas`) porque el panel es angosto;
el nombre completo del estado esta en el catalogo.

## Que se filtra por contexto y que no

- **Se filtra** todo lo que ESCRIBE estado: botones del Flow Panel y dropdowns
  de Create Shot. Ofrecer un codigo que el sitio no tiene es un error garantizado.
- **NO se filtra** el catalogo que solo MUESTRA o pinta (`TASK_STATUS_CATALOG`).
  La DB local puede tener codigos sincronizados del otro sitio; filtrarlos los
  haria desaparecer de la tabla del Pull sin ningun aviso.

## Prioridad de SHOT (`Shot.sg_prioridad`)

| Codigo SG | Nombre real en Flow |
|-----------|---------------------|
| `high`    | High                |
| `normal`  | Normal              |

## Reviewers de Task

Los reviewers son **asignaciones de personas** a la task (no un estado). En la UI
son checkboxes y se mapean a usuarios de Flow:

| Checkbox UI | Clave interna       | Nombre real en Flow |
|-------------|---------------------|---------------------|
| Lega        | `lega_pugliese`     | Lega Pugliese       |
| Sebas       | `sebas_romano`      | Sebas Romano        |
| Juano       | `juano`             | Juan Olivares       |
| Charly      | `charly_villafane`  | Charly Villafañe    |
| Javi        | `javi_bravo`        | Javi Bravo          |

En contexto client no hay assignees: ver
[Doc_HieroTools_Studio_Client_Context.md](Doc_HieroTools_Studio_Client_Context.md).

## Referencias tecnicas

- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py` — **fuente unica**.
  - `TASK_STATUS_CATALOG` — code -> (nombre, color de clip, tag XYplorer). Superset, sin filtrar.
  - `TASK_STATUS_CODES_BY_MODE`, `SHOT_STATUS_CODES_BY_MODE` — espejo del `sg_status_list` de cada sitio.
  - `PUSH_BUTTONS`, `get_push_buttons(mode)` — botones del Flow Panel por contexto.
  - `get_status_translation(mode=None)` — label -> codigo, para Push y conector.
  - `get_task_status_dict()`, `get_status_info()`, `get_status_color()` — catalogo para mostrar y pintar.
  - `filter_states_for_mode(states, mode, entity)` — filtra listas `(label, code, color)`.
  - `PERSONAL_REVIEW_CODES`, `get_personal_review_colors()` — reviews por persona que el Pull vuelve a habilitar.
- `LGA_HieroTools/LGA_NKS_Flow_Panel.py`
  - `ColorChangeWidget.build_buttons()` — botones fijos + los del contexto.
  - `ColorChangeWidget.on_context_changed()` — rearmado al cambiar de contexto.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
  - `ShotGridManager.__init__` — `task_status_dict` desde el catalogo compartido.
  - `_status_display_from_code()` — nombre visible; `_LEGACY_STATUS_DISPLAY` para codigos de sistemas viejos.
  - `enable_or_disable_clips()` — usa `get_personal_review_colors()`.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py` y
  `LGA_NKS_Flow_Push_connector.py` — `status_translation` desde el modulo compartido.
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
  - `ALL_SHOT_STATES`, `ALL_TASK_STATES` — paleta de dropdown (distinta de la de clips).
  - `get_shot_states()`, `get_task_states()` — filtradas por contexto activo.
  - `ColoredStatusComboBox` — combo con items coloreados.
- `/Users/leg4/Desktop/Codin/LGA_PipeSync_2/src/services/StatusContextPolicy.cpp` —
  el equivalente en PipeSync. Ojo: sus comentarios sobre que codigo existe en que
  sitio estan desactualizados; la verdad es el schema de Flow.
