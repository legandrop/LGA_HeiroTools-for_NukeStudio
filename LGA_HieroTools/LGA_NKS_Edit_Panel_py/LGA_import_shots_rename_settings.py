"""
____________________________________________________________________

  LGA_import_shots_rename_settings v1.02 | Lega

  Persistencia de configuracion para la seccion Rename.
  INI: %APPDATA%\\LGA\\HieroTools\\ImportShotsRename.ini

  Changelog:
  - v1.02: El dialogo "Guardar preset" migra al modulo de estilo
           LGA_UI_Style_HieroTools: Style.FORM + BTN_PRIMARY/BTN_SECONDARY
           y tokens en vez del QSS propio. El ambar #d9a441 del titulo se
           deja: es la identidad de esta familia de dialogos y no tiene
           token equivalente.
  - v1.01: Agrega persistencia y presets de Prefix/Suffix.

____________________________________________________________________
"""

import configparser
import os
import sys
from pathlib import Path

CONFIG_DIR_NAME = "LGA"
CONFIG_SUBDIR_NAME = "HieroTools"
CONFIG_FILE_NAME = "ImportShotsRename.ini"

SEC_SR1 = "SearchReplace1"
SEC_SR2 = "SearchReplace2"
SEC_PREFIX = "Prefix"
SEC_SUFFIX = "Suffix"
SEC_DELIM = "Delimiter"
SEC_PADDING = "Padding"

DEFAULTS_SR = {
    "search": "",
    "replace": "",
    "case_sensitive": "false",
}
DEFAULTS_TEXT = {
    "text": "",
}
DEFAULTS_DELIM = {
    "char": "_",
}
DEFAULTS_PADDING = {
    "digits": "4",
}


def _user_config_root():
    if sys.platform.startswith("win"):
        v = os.getenv("APPDATA")
        if v:
            return v
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.path.expanduser("~/.config")


def get_settings_path():
    return (
        Path(_user_config_root())
        / CONFIG_DIR_NAME
        / CONFIG_SUBDIR_NAME
        / CONFIG_FILE_NAME
    )


def _ensure_dir(path_obj):
    path_obj.parent.mkdir(parents=True, exist_ok=True)


def _read_cfg(path_obj):
    cfg = configparser.ConfigParser()
    if path_obj.exists():
        cfg.read(str(path_obj), encoding="utf-8")
    return cfg


def _write_cfg(cfg, path_obj):
    _ensure_dir(path_obj)
    with open(str(path_obj), "w", encoding="utf-8") as fh:
        cfg.write(fh)


def load_settings():
    cfg = _read_cfg(get_settings_path())

    def _section(sec, defaults):
        out = dict(defaults)
        if cfg.has_section(sec):
            for k, v in cfg[sec].items():
                out[k] = v
        return out

    return {
        "sr1": _section(SEC_SR1, DEFAULTS_SR),
        "sr2": _section(SEC_SR2, DEFAULTS_SR),
        "prefix": _section(SEC_PREFIX, DEFAULTS_TEXT),
        "suffix": _section(SEC_SUFFIX, DEFAULTS_TEXT),
        "delimiter": _section(SEC_DELIM, DEFAULTS_DELIM),
        "padding": _section(SEC_PADDING, DEFAULTS_PADDING),
    }


def save_settings(data):
    cfg_path = get_settings_path()
    cfg = _read_cfg(cfg_path)

    mapping = {
        "sr1": SEC_SR1,
        "sr2": SEC_SR2,
        "prefix": SEC_PREFIX,
        "suffix": SEC_SUFFIX,
        "delimiter": SEC_DELIM,
        "padding": SEC_PADDING,
    }
    for key, sec_name in mapping.items():
        if key not in data:
            continue
        if not cfg.has_section(sec_name):
            cfg.add_section(sec_name)
        for k, v in data[key].items():
            cfg.set(sec_name, str(k), str(v))

    _write_cfg(cfg, cfg_path)


# ── Presets de rename ─────────────────────────────────────────────────────────

PRESET_FIELDS = (
    "sr1_search",
    "sr1_replace",
    "sr1_case",
    "sr2_search",
    "sr2_replace",
    "sr2_case",
    "prefix",
    "suffix",
    "delim",
    "digits",
)


def load_rename_presets():
    """Lee secciones [RenamePreset_N] del INI y devuelve lista de dicts.

    Cada preset: {"name": str, "sr1_search": ..., ..., "delim": "_", "digits": "4"}.
    """
    cfg = _read_cfg(get_settings_path())
    presets = []
    i = 0
    while cfg.has_section("RenamePreset_%d" % i):
        sec = "RenamePreset_%d" % i
        d = {"name": cfg.get(sec, "name", fallback="Preset %d" % i)}
        for k in PRESET_FIELDS:
            d[k] = cfg.get(sec, k, fallback="")
        presets.append(d)
        i += 1
    return presets


def save_rename_presets(presets):
    """Reescribe todas las secciones [RenamePreset_N] con la lista dada."""
    p = get_settings_path()
    cfg = _read_cfg(p)
    for sec in list(cfg.sections()):
        if sec.lower().startswith("renamepreset_"):
            cfg.remove_section(sec)
    for i, preset in enumerate(presets):
        sec = "RenamePreset_%d" % i
        cfg.add_section(sec)
        cfg.set(sec, "name", str(preset.get("name", "Preset %d" % i)))
        for k in PRESET_FIELDS:
            cfg.set(sec, k, str(preset.get(k, "")))
    _write_cfg(cfg, p)


def show_save_rename_preset_dialog(parent=None):
    """Diálogo para nombrar un preset de rename. Devuelve str (nombre) o None."""
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

    header_row = QtWidgets.QHBoxLayout()
    title_lbl = QtWidgets.QLabel("Guardar preset de rename")
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

    name_prompt = QtWidgets.QLabel("Nombre del preset:")
    name_prompt.setStyleSheet("font-size:11px;")
    layout.addWidget(name_prompt)

    line = QtWidgets.QLineEdit()
    line.setPlaceholderText("Ej: Plates v01")
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
