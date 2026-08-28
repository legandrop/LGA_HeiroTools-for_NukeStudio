"""
____________________________________________________________________

  LGA_import_shots_settings v1.03 | Lega

  Persistencia de configuracion y presets para LGA_import_shots.
  INI: %APPDATA%\\LGA\\HieroTools\\ImportShots.ini

  v1.03: El dialogo "Guardar preset" migra al modulo de estilo
         LGA_UI_Style_HieroTools: Style.FORM + BTN_PRIMARY/BTN_SECONDARY
         y tokens en vez del QSS propio. El ambar #d9a441 del titulo se
         deja: es la identidad de esta familia de dialogos y no tiene
         token equivalente.
  v1.02: Guarda la ultima carpeta de shot elegida para usarla como ruta
         inicial del file browser en futuras sesiones.
  v1.01: Agrega settings persistentes de UI para mostrar/ocultar tabs
         Rename/Transcode y el boton Open Queue.

____________________________________________________________________
"""

import configparser
import os
import sys
from pathlib import Path

# ── Constantes de ruta ────────────────────────────────────────────────────────

CONFIG_DIR_NAME    = "LGA"
CONFIG_SUBDIR_NAME = "HieroTools"
CONFIG_FILE_NAME   = "ImportShots.ini"

SEC_CODEC = "Codec"
SEC_RES   = "Resolution"
SEC_ORIG  = "Originals"
SEC_UI    = "UI"

DEFAULTS_CODEC = {
    "dwaa":       "true",
    "channels":   "all",
    "filter":     "lanczos3",
}
DEFAULTS_RES = {
    "preset_index": "0",
    "custom_w":     "2048",
    "custom_h":     "1152",
    "keep_ar":      "true",
    "match_dim":    "0",
    "deana":        "false",
    "deana_par":    "2.0",
    "even_dims":    "true",
}
DEFAULTS_ORIG = {
    "move":   "false",
    "delete": "false",
}
DEFAULTS_UI = {
    "advanced_tabs": "false",
    "last_shot_directory": "",
}

# Presets built-in (primera vez que se abre la herramienta).
# "original" y "timeline" son hardcoded en la UI y NO se guardan en el INI.
DEFAULT_PRESETS = [
    {"name": "2K — 2048×1152",  "w": 2048, "h": 1152},
    {"name": "UHD — 3840×2160", "w": 3840, "h": 2160},
    {"name": "4K — 4096×2304",  "w": 4096, "h": 2304},
    {"name": "Custom...",        "special": "custom"},
]


# ── Rutas ─────────────────────────────────────────────────────────────────────

def _user_config_root():
    if sys.platform.startswith("win"):
        v = os.getenv("APPDATA")
        if v:
            return v
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.path.expanduser("~/.config")


def get_settings_path():
    """Retorna el Path al archivo ImportShots.ini."""
    return (Path(_user_config_root()) / CONFIG_DIR_NAME
            / CONFIG_SUBDIR_NAME / CONFIG_FILE_NAME)


def _ensure_dir(p):
    p.parent.mkdir(parents=True, exist_ok=True)


def _read_cfg(p):
    """Lee el INI si existe y retorna un ConfigParser."""
    cfg = configparser.ConfigParser()
    if p.exists():
        cfg.read(str(p), encoding="utf-8")
    return cfg


def _write_cfg(cfg, p):
    """Escribe el ConfigParser al disco."""
    _ensure_dir(p)
    with open(str(p), "w", encoding="utf-8") as f:
        cfg.write(f)


# ── Settings generales ────────────────────────────────────────────────────────

def load_all_settings():
    """Retorna dict con claves 'codec', 'res', 'originals', 'ui'."""
    cfg = _read_cfg(get_settings_path())

    def _sec(name, defaults):
        d = dict(defaults)
        if cfg.has_section(name):
            for k, v in cfg[name].items():
                d[k] = v
        return d

    return {
        "codec":     _sec(SEC_CODEC, DEFAULTS_CODEC),
        "res":       _sec(SEC_RES,   DEFAULTS_RES),
        "originals": _sec(SEC_ORIG,  DEFAULTS_ORIG),
        "ui":        _sec(SEC_UI,    DEFAULTS_UI),
    }


def save_all_settings(s):
    """Guarda el dict de settings.  Solo modifica las secciones presentes en s."""
    p = get_settings_path()
    cfg = _read_cfg(p)

    mapping = {
        "codec": SEC_CODEC,
        "res": SEC_RES,
        "originals": SEC_ORIG,
        "ui": SEC_UI,
    }
    for key, sec_name in mapping.items():
        if key not in s:
            continue
        if not cfg.has_section(sec_name):
            cfg.add_section(sec_name)
        if key == "codec" and "dwaa_level" not in s[key]:
            cfg.remove_option(sec_name, "dwaa_level")
        if key == "res" and "no_upscale" not in s[key]:
            cfg.remove_option(sec_name, "no_upscale")
        for k, v in s[key].items():
            cfg.set(sec_name, str(k), str(v))

    _write_cfg(cfg, p)


# ── Presets de resolución ─────────────────────────────────────────────────────

def load_res_presets():
    """Retorna la lista de presets de resolución.

    Cada preset es un dict:
      {"name": str, "special": "original"|"custom"}   — preset especial
      {"name": str, "w": int, "h": int}               — preset con dimensiones
    """
    p = get_settings_path()
    cfg = _read_cfg(p)

    presets = []
    i = 0
    while cfg.has_section("ResPreset_%d" % i):
        sec = "ResPreset_%d" % i
        d = {}
        for k, v in cfg[sec].items():
            d[k] = v
        for k in ("w", "h"):
            if k in d:
                try:
                    d[k] = int(d[k])
                except ValueError:
                    pass
        presets.append(d)
        i += 1

    # Filtrar entradas especiales hardcoded que puedan venir de INIs más viejos
    presets = [p for p in presets
               if p.get("special") not in ("original", "custom", "timeline")]

    if not presets:
        presets = [dict(pr) for pr in DEFAULT_PRESETS]
        save_res_presets(presets)

    return presets


def save_res_presets(presets):
    """Guarda la lista de presets al INI (sobrescribe secciones ResPreset_N)."""
    p = get_settings_path()
    cfg = _read_cfg(p)

    for sec in list(cfg.sections()):
        if sec.lower().startswith("respreset_"):
            cfg.remove_section(sec)

    for i, preset in enumerate(presets):
        sec = "ResPreset_%d" % i
        cfg.add_section(sec)
        for k, v in preset.items():
            cfg.set(sec, k, str(v))

    _write_cfg(cfg, p)


def preset_to_tuple(p):
    """Convierte un dict de preset a la tupla (name, preset_val).

    preset_val:
      None       — "Original" (mantener resolución fuente)
      "custom"   — resolución custom (spinboxes)
      (w, h)     — dimensiones fijas
    """
    if "special" in p:
        spec = p["special"]
        return (p["name"], None if spec == "original" else spec)
    return (p["name"], (int(p["w"]), int(p["h"])))


# ── Diálogo "Guardar preset" ──────────────────────────────────────────────────

def show_save_preset_dialog(w, h, parent=None):
    """Abre un diálogo para nombrar un preset de resolución.

    Estilo idéntico al de show_overwrite_warning (Style.FORM, FramelessWindowHint).

    Returns:
        str — nombre introducido por el usuario.
        None — el usuario canceló.
    """
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
    from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color

    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("Guardar preset")
    dlg.setMinimumWidth(380)
    dlg.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
    # Style.FORM cubre fondo, labels, QLineEdit y el separador. El borde va
    # aparte porque la ventana es frameless: sin el, el dialogo se funde con
    # el fondo del host.
    dlg.setStyleSheet(
        Style.FORM + "QDialog { border: 1px solid %s; }" % Color.BORDER_HOVER
    )
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

    layout = QtWidgets.QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(10)

    # Encabezado
    header_row = QtWidgets.QHBoxLayout()
    title_lbl = QtWidgets.QLabel("Guardar preset de resolución")
    # El ambar #d9a441 se DEJA: es el color de identidad de esta familia de
    # dialogos (mismo que show_overwrite_warning) y no un estado del pack.
    title_lbl.setStyleSheet("color:#d9a441; font-size:13px; font-weight:bold;")
    header_row.addWidget(title_lbl)
    header_row.addStretch()
    layout.addLayout(header_row)

    # El separador lo pinta la regla de QFrame HLine de Style.FORM.
    sep = QtWidgets.QFrame()
    sep.setFrameShape(QtWidgets.QFrame.HLine)
    sep.setFixedHeight(1)
    layout.addWidget(sep)

    res_lbl = QtWidgets.QLabel("%d × %d" % (w, h))
    # La resolucion es lo que decide la respuesta: va destacada.
    res_lbl.setStyleSheet(
        "color:%s; font-size:12px; font-weight:bold; margin-top:4px;"
        % Color.TEXT_STRONG
    )
    layout.addWidget(res_lbl)

    name_prompt = QtWidgets.QLabel("Nombre del preset:")
    name_prompt.setStyleSheet("font-size:11px;")
    layout.addWidget(name_prompt)

    line = QtWidgets.QLineEdit()
    line.setPlaceholderText("Ej: DI 2K")
    layout.addWidget(line)

    layout.addSpacing(8)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch()
    btn_cancel = QtWidgets.QPushButton("Cancelar")
    btn_save   = QtWidgets.QPushButton("Guardar")
    btn_cancel.setStyleSheet(Style.BTN_SECONDARY)
    btn_save.setStyleSheet(Style.BTN_PRIMARY)
    btn_save.setEnabled(False)
    btn_row.addWidget(btn_cancel)
    btn_row.addSpacing(8)
    btn_row.addWidget(btn_save)
    layout.addLayout(btn_row)

    line.textChanged.connect(lambda t: btn_save.setEnabled(bool(t.strip())))

    result = [None]

    def _do_save():
        result[0] = line.text().strip()
        dlg.accept()

    btn_cancel.clicked.connect(dlg.reject)
    btn_save.clicked.connect(_do_save)
    line.returnPressed.connect(lambda: _do_save() if btn_save.isEnabled() else None)

    dlg.exec_()
    return result[0]
