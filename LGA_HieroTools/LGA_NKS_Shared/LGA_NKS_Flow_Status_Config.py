"""
____________________________________________________________________

  LGA_NKS_Flow_Status_Config v1.00 | Lega

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
    solo client (erso)  : revprd
    en los dos          : el resto, incluido pubsh (OK for Delivery)

  Empujar un codigo que el sitio no tiene falla con
  "'xxx' is not a valid status", asi que los botones se filtran por contexto.
  El CATALOGO en cambio no se filtra nunca: es solo para mostrar y pintar, y
  la DB local puede tener codigos sincronizados desde el otro sitio. Filtrarlo
  haria desaparecer esas filas sin ningun aviso.

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
    "noread": ("Not Ready To Start", "#000000", None),
    "wts": ("Waiting to start", "#000000", None),
    "ready": ("Ready To Start", "#8a8a8a", None),
    "progre": ("In Progress", "#7d4cff", None),
    # Estado de SHOT, no de task. Nunca lo empuja el Flow Panel, pero aparece en
    # la DB y sin entrada se mostraba el codigo crudo.
    "plylst": ("In Playlist", "#99c153", None),
    "corr": ("Corrections", "#2e77d4", "Corrections"),
    "rev_su": ("Review Sebas", "#bd7f9f", "Rev_Sup"),
    "revcha": ("Review Charly", "#a9909d", "Rev_Sup"),
    # Codigo interno largo de PipeSync que aparecio en data sincronizada.
    "review_charly": ("Review Charly", "#a9909d", "Rev_Sup"),
    "revjua": ("Review Juano", "#7F4B69", "Rev_Sup"),
    "revjav": ("Review Javi", "#9c3e5e", "Rev_Sup"),
    "revleg": ("Review Lega", "#69135e", "Rev_Lega"),
    "revhld": ("Review Hold", "#9E6A15", "Rev Hold"),
    # Review Prod solo existe en erso. Flow lo trae en #D7F2B1, pero ese lima
    # tiene MAS luminancia que el gris de noread (#d3d3d3) y en un clip chico se
    # lee como blanco; PipeSync ya lo bajo a #8CBF3F por el mismo motivo.
    # Comparte el tag de XYplorer con Review Dir.
    "revprd": ("Review Prod", "#8CBF3F", "ReviewDir"),
    "rev_di": ("Review Dir", "#B5DB4B", "ReviewDir"),
    "pubsh": ("OK for Delivery", "#50BFC7", "Approved"),
    "pbshed": ("Delivered", "#52c233", "Approved"),
    "apr": ("Delivery OK", "#266612", "Approved"),
    "check": ("Delivery Checked", "#38A138", "Approved"),
    "omit": ("Omitted", "#244c19", "Approved"),
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
# El ORDEN es el mismo que el del `sg_status_list` de Flow, para que la lista de
# botones y el dropdown de Flow se lean igual. Ojo con `revjav` antes de
# `revjua`: asi esta en Flow.
#
# `color = None` significa "el del catalogo".
PUSH_BUTTONS = [
    ("Corrections", "corr", None, BOTH),
    ("Rev Sebas", "rev_su", None, STUDIO_ONLY),
    ("Rev Charly", "revcha", None, STUDIO_ONLY),
    ("Rev Javi", "revjav", None, STUDIO_ONLY),
    ("Rev Juano", "revjua", None, STUDIO_ONLY),
    ("Rev Lega", "revleg", None, BOTH),
    ("Rev Hold", "revhld", None, BOTH),
    ("Rev Prod", "revprd", None, CLIENT_ONLY),
    ("Rev Dir", "rev_di", None, BOTH),
    ("OK for Delivery", "pubsh", None, BOTH),
    ("Delivery OK", "apr", None, BOTH),
    ("Delivery Checked", "check", None, BOTH),
]

# Alias historicos de labels que ya no se dibujan pero que pueden llegar desde
# una llamada vieja o un log. Se mantienen para que el push no quede mudo.
LEGACY_LABEL_ALIASES = {
    "Corrs_Lega": "revleg",
    "Approved": "apr",
    "Delivery Ok": "check",
    "Delivered": "check",
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
# Ojo con las trampas: `revleg` en erso se llama "Review Sup" y es el unico
# reviewer del sitio; y el estado de shot "entregado" es `check` en wanka pero
# `pbshed` en erso.
TASK_STATUS_CODES_BY_MODE = {
    MODE_STUDIO: (
        "noread", "omit", "ready", "progre", "corr",
        "rev_su", "revcha", "revjav", "revjua", "revleg", "revhld",
        "rev_di", "pubsh", "apr", "check",
    ),
    MODE_CLIENT: (
        "noread", "omit", "ready", "progre", "corr",
        "revleg", "revhld", "revprd",
        "rev_di", "pubsh", "apr", "check",
    ),
}

SHOT_STATUS_CODES_BY_MODE = {
    MODE_STUDIO: (
        "noread", "omit", "ready", "progre", "plylst", "pubsh", "apr", "check",
    ),
    MODE_CLIENT: (
        "noread", "omit", "ready", "progre", "plylst", "pubsh", "pbshed", "apr",
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
