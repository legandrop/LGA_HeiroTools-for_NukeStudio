"""
____________________________________________________________________

  LGA_NKS_Flow_Status_Config v1.02 | Lega

  Fuente unica de los estados de Task de Flow para HieroTools: codigo,
  nombre visible, color de clip, tag de XYplorer y en que contexto
  (studio/client) el estado existe.

  Antes esto vivia duplicado en cuatro lugares (`status_translation` en
  Flow_Push y en Flow_Push_connector, `task_status_dict` en Flow_Push y en
  Flow_Pull) mas la lista de botones del Flow Panel. Las copias se
  desincronizaron: colores distintos para el mismo estado y botones que
  empujaban codigos que el sitio de Flow del contexto activo no acepta.

  Los dos sitios de Flow NO tienen la misma lista de estados:

    solo studio (wanka) : rev_su, revcha, revjua, revjav
    solo client (projb)  : revprd
    en los dos          : el resto, incluido pubsh (OK for Delivery)

  Empujar un codigo que el sitio no tiene falla con
  "'xxx' is not a valid status", asi que los botones se filtran por contexto.
  El CATALOGO en cambio no se filtra nunca: es solo para mostrar y pintar, y
  la DB local puede tener codigos sincronizados desde el otro sitio. Filtrarlo
  haria desaparecer esas filas sin ningun aviso.

  El ORDEN de los estados es el mismo que el del sg_status_list de Flow, y
  los nombres tambien, salvo las divergencias declaradas en
  docs/Docu_Flow_Estados_Colores.md.

  v1.02: NOTE_CAPABLE_CODES + is_note_capable: los estados que piden nota en el
         push y mandan la Version a `vwd` salen de aca. Estaban hardcodeados en
         cinco listas iguales que ya se habian desincronizado (`revhld` faltaba
         en la del conector y `revprd` en las cinco).
  v1.01: Se elimina el boton Rev Dir Den (empujaba el mismo rev_di que Rev Dir).
         La cola de entrega pasa a pubsh -> check -> apr, con apr como FINAL, y
         apr se muestra "Delivery Apr" en vez de "Delivery OK", que era casi
         identico al "OK for Delivery" de pubsh. El orden de PUSH_BUTTONS y de
         los CODES_BY_MODE acompana al de Flow y al de PipeSync (revjua antes
         que revjav). Nombres del catalogo alineados con Flow. revprd toma el
         mismo tag de XYplorer que rev_di.
  v1.00: Version inicial.
____________________________________________________________________

"""

MODE_STUDIO = "studio"
MODE_CLIENT = "client"

BOTH = (MODE_STUDIO, MODE_CLIENT)
STUDIO_ONLY = (MODE_STUDIO,)
CLIENT_ONLY = (MODE_CLIENT,)


# ---------------------------------------------------------------------------
# Catalogo de estados de Task
# ---------------------------------------------------------------------------
# code -> (nombre visible, color de clip, tag de XYplorer)
#
# Superset de los dos sitios de Flow, mas codigos historicos que pueden seguir
# apareciendo en data vieja (wts, enviad, rev, vwd). NO se filtra por contexto.
#
# Los colores son los `bg_color` reales de Flow salvo donde se aclara.
TASK_STATUS_CATALOG = {
    "noread": ("Not ready", "#000000", None),
    "wts": ("Waiting to start", "#000000", None),
    "ready": ("Ready to start", "#8a8a8a", None),
    "progre": ("In progress", "#7d4cff", None),
    # Estado de SHOT, no de task. Nunca lo empuja el Flow Panel, pero aparece en
    # la DB y sin entrada se mostraba el codigo crudo.
    "plylst": ("In playlist", "#99c153", None),
    "corr": ("Corrections", "#2e77d4", "Corrections"),
    "rev_su": ("Review Sebas", "#bd7f9f", "Rev_Sup"),
    "revcha": ("Review Charly", "#a9909d", "Rev_Sup"),
    # Codigo interno largo de PipeSync que aparecio en data sincronizada.
    "review_charly": ("Review Charly", "#a9909d", "Rev_Sup"),
    "revjua": ("Review Juano", "#7F4B69", "Rev_Sup"),
    "revjav": ("Review Javi", "#9c3e5e", "Rev_Sup"),
    "revleg": ("Review Lega", "#69135e", "Rev_Lega"),
    "revhld": ("Review Hold", "#9E6A15", "Rev Hold"),
    # Review Prod solo existe en projb. Flow lo trae en #D7F2B1, pero ese lima
    # tiene MAS luminancia que el gris de noread (#d3d3d3) y en un clip chico se
    # lee como blanco; PipeSync ya lo bajo a #8CBF3F por el mismo motivo.
    # Comparte el tag de XYplorer con Review Dir.
    "revprd": ("Review Prod", "#8CBF3F", "ReviewDir"),
    "rev_di": ("Review Dir", "#B5DB4B", "ReviewDir"),
    # Cola de entrega: pubsh -> check -> apr. `apr` es el FINAL, lo da el cliente.
    # Se llamaba "Delivery OK", casi identico al "OK for Delivery" de pubsh, que es
    # el primero: las mismas palabras en los dos extremos opuestos.
    "pubsh": ("OK for Delivery", "#50BFC7", "Approved"),
    "check": ("Delivered", "#38A138", "Approved"),
    "apr": ("Delivery Apr", "#266612", "Approved"),
    # `pbshed` ya no esta en ningun sg_status_list: en projb lo reemplazo `check`.
    # Queda en el catalogo por si aparece en data vieja.
    "pbshed": ("Delivered", "#52c233", "Approved"),
    "omit": ("Omited", "#244c19", "Approved"),
    "enviad": ("Enviado", "#000000", "Approved"),
    "rev": ("Pending Review", "#000000", None),
    "vwd": ("Viewed", "#000000", None),
}


# ---------------------------------------------------------------------------
# Botones de push del Flow Panel
# ---------------------------------------------------------------------------
# (label, code, color de clip, contextos)
#
# El label es la clave con la que viaja el push hasta el conector, asi que tiene
# que salir de aca y no escribirse a mano en cada archivo.
#
# El ORDEN es el mismo que el del `sg_status_list` de Flow y el de los dropdowns
# de PipeSync, para que las tres listas se lean igual.
#
# Los labels de los botones van cortos ("Rev Sebas") porque el panel es angosto;
# el nombre completo del estado esta en el catalogo de arriba.
#
# `color = None` significa "el del catalogo".
PUSH_BUTTONS = [
    ("Corrections", "corr", None, BOTH),
    ("Rev Sebas", "rev_su", None, STUDIO_ONLY),
    ("Rev Charly", "revcha", None, STUDIO_ONLY),
    ("Rev Juano", "revjua", None, STUDIO_ONLY),
    ("Rev Javi", "revjav", None, STUDIO_ONLY),
    ("Rev Lega", "revleg", None, BOTH),
    ("Rev Hold", "revhld", None, BOTH),
    ("Rev Prod", "revprd", None, CLIENT_ONLY),
    ("Rev Dir", "rev_di", None, BOTH),
    ("OK for Delivery", "pubsh", None, BOTH),
    ("Delivered", "check", None, BOTH),
    ("Delivery Apr", "apr", None, BOTH),
]

# Alias historicos de labels que ya no se dibujan pero que pueden llegar desde
# una llamada vieja o un log. Se mantienen para que el push no quede mudo.
# Ojo: "Delivery Ok" era `check` y "Delivery OK" era `apr` — se diferenciaban solo
# por la capitalizacion. Ese es justamente el motivo del renombre a "Delivery Apr".
LEGACY_LABEL_ALIASES = {
    "Corrs_Lega": "revleg",
    "Approved": "apr",
    "Delivery OK": "apr",
    "Delivery Approved": "apr",
    "Delivery Ok": "check",
    "Delivery Checked": "check",
    "Rev Dir Den": "rev_di",
}


# ---------------------------------------------------------------------------
# Codigos validos por contexto
# ---------------------------------------------------------------------------
# Espejo exacto del `sg_status_list` de cada sitio, verificado con
# `sg.schema_field_read(entity, "sg_status_list")`. Escribir un codigo que no
# esta en la lista del sitio falla con "'xxx' is not a valid status", asi que
# todo dropdown o boton que ESCRIBA estado tiene que filtrar por aca.
#
# Ojo: `revleg` en projb se llama "Review Sup" y es el unico reviewer del sitio.
# Las listas de Shot son identicas en los dos; las de Task se diferencian solo en
# los reviewers por persona (studio) y en `revprd` (client).
TASK_STATUS_CODES_BY_MODE = {
    MODE_STUDIO: (
        "noread", "omit", "ready", "progre", "corr",
        "rev_su", "revcha", "revjua", "revjav", "revleg", "revhld",
        "rev_di", "pubsh", "check", "apr",
    ),
    MODE_CLIENT: (
        "noread", "omit", "ready", "progre", "corr",
        "revleg", "revhld", "revprd",
        "rev_di", "pubsh", "check", "apr",
    ),
}

SHOT_STATUS_CODES_BY_MODE = {
    MODE_STUDIO: (
        "noread", "omit", "ready", "progre", "plylst", "pubsh", "check", "apr",
    ),
    MODE_CLIENT: (
        "noread", "omit", "ready", "progre", "plylst", "pubsh", "check", "apr",
    ),
}


# Estados de review "por persona": marcan que el clip esta esperando la revision
# de alguien concreto, y por eso el Pull vuelve a habilitar esos clips en el
# timeline. Quedan afuera rev_di y revhld, que no apuntan a nadie del equipo.
# Superset de los dos contextos: se matchea por color de clip, asi que un codigo
# del otro sitio simplemente no aparece.
PERSONAL_REVIEW_CODES = (
    "rev_su",
    "revcha",
    "review_charly",
    "revjua",
    "revjav",
    "revleg",
    "revprd",
)


# Estados que abren el dialogo de nota en el push y que ademas de la Task ponen
# la Version en `vwd` (vista). Los dos efectos van SIEMPRE juntos: si un estado
# pide nota es porque alguien va a mirar esa version.
#
# Esto estaba hardcodeado en CINCO listas iguales (cuatro en Flow_Push y una en
# el conector) y se desincronizo igual que `status_translation` antes de la
# v1.05 del conector: `revhld` estaba en las cuatro de Flow_Push pero no en la
# del conector, asi que el push abria el dialogo, el usuario escribia la nota y
# el conector la descartaba devolviendo success sin un solo warning. `revprd`
# no estaba en ninguna de las cinco.
#
# Ojo `rev_su`: NO va aca. Es el unico estado de review que no lleva nota y que
# pone la Version en `rev`, no en `vwd`.
#
# Superset de los dos contextos, como PERSONAL_REVIEW_CODES: un codigo del otro
# sitio no llega nunca, porque el panel ya filtro los botones por contexto.
NOTE_CAPABLE_CODES = (
    "corr",
    "revcha",
    "revjua",
    "revjav",
    "revleg",
    "revhld",
    "revprd",
    "rev_di",
)


def is_note_capable(code):
    """True si ese estado pide nota en el push y manda la Version a `vwd`."""
    return code in NOTE_CAPABLE_CODES


def _normalize_mode(mode):
    return MODE_CLIENT if str(mode or "").strip().lower() == MODE_CLIENT else MODE_STUDIO


def get_task_status_dict():
    """
    Catalogo completo code -> (nombre, color, tag). Sin filtrar por contexto.

    Reemplaza al `task_status_dict` que estaba duplicado en Pull y Push. Se
    devuelve una copia porque los callers historicos lo guardan como atributo de
    instancia y podrian mutarlo.
    """
    return dict(TASK_STATUS_CATALOG)


def get_status_info(code):
    """(nombre, color, tag) de un codigo, o None si no esta en el catalogo."""
    return TASK_STATUS_CATALOG.get(code)


def get_status_color(code, default="#000000"):
    info = TASK_STATUS_CATALOG.get(code)
    return info[1] if info else default


def get_task_status_codes(mode):
    """Codigos de Task validos en el sitio de Flow de ese contexto."""
    return TASK_STATUS_CODES_BY_MODE[_normalize_mode(mode)]


def get_shot_status_codes(mode):
    """Codigos de Shot validos en el sitio de Flow de ese contexto."""
    return SHOT_STATUS_CODES_BY_MODE[_normalize_mode(mode)]


def filter_states_for_mode(states, mode, entity="task"):
    """
    Filtra una lista de tuplas `(label, code, ...)` dejando solo los codigos que
    el sitio del contexto acepta, conservando el orden original.
    """
    valid = (
        get_shot_status_codes(mode)
        if entity == "shot"
        else get_task_status_codes(mode)
    )
    return [state for state in states if state[1] in valid]


def get_personal_review_colors():
    """Colores de clip (minusculas) de los estados de review por persona."""
    return {get_status_color(code).lower() for code in PERSONAL_REVIEW_CODES}


def get_push_buttons(mode):
    """
    Botones de estado que corresponden al contexto: lista de dicts con
    `label`, `code` y `color` (el color de clip ya resuelto).
    """
    mode = _normalize_mode(mode)
    buttons = []
    for label, code, color_override, contexts in PUSH_BUTTONS:
        if mode not in contexts:
            continue
        buttons.append(
            {
                "label": label,
                "code": code,
                "color": color_override or get_status_color(code),
            }
        )
    return buttons


def get_status_translation(mode=None):
    """
    label -> codigo de Flow.

    Sin `mode` devuelve TODOS los labels (mas los alias historicos): es lo que
    necesitan Push y el conector, que reciben un label ya elegido por el panel y
    solo tienen que traducirlo. Filtrarlo ahi convertiria un contexto mal leido
    en un push mudo en vez de un error de Flow explicito.
    """
    if mode is None:
        translation = {label: code for label, code, _, _ in PUSH_BUTTONS}
        translation.update(LEGACY_LABEL_ALIASES)
        return translation
    return {button["label"]: button["code"] for button in get_push_buttons(mode)}
