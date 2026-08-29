"""
____________________________________________________________________

  LGA_NKS_BurnIn_Panel v1.01 | Lega

  Ventana de LGA BurnIn con el estilo del pack: edita en vivo los
  knobs del efecto seleccionado en el timeline (campos, fondos,
  estilo) y los objetivos de comparacion del proyecto (res/fps), que
  se guardan en el tag del proyecto (viajan en el .hrox) o como
  defaults del usuario en AppData.

  La ventana no toca el render: solo escribe knobs y config. El panel
  de properties de Nuke queda como fallback crudo.

  v1.01: Seccion Layout con la posicion de cada campo en % del
         formato, presets con nombre (guardar/cargar, en el
         BurnIn.json de AppData) y nudge automatico de los efectos
         tras guardar targets (el timeline no re-evalua las
         expresiones python de color hasta que el nodo se ensucia).
  v1.00: Version inicial.
____________________________________________________________________
"""

import json

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Style,
    Color,
    Metric,
    apply_ui_font,
    emphasis,
)

import LGA_NKS_BurnIn_Config as bi_config

FIELDS = (
    ("clip", "Clip name"),
    ("cspace", "Colorspace"),
    ("res", "Resolution"),
    ("frame", "Frame"),
    ("tc", "Timecode"),
    ("fps", "FPS"),
)

# Capa intermedia de tooltips (regla del repo: siempre en castellano y nunca
# hardcodeados en el widget, para la futura migracion bilingue).
TOOLTIPS = {
    "es": {
        "refresh": "Vuelve a buscar el efecto LGA BurnIn en la secuencia activa",
        "field_on": "Muestra u oculta este campo del burn-in",
        "field_bg": "Panel redondeado de fondo detras de este campo",
        "text_color": "Color del texto de todos los campos",
        "bg_color": "Color de los paneles de fondo",
        "text_opacity": "Opacidad del texto",
        "text_scale": "Escala global del texto",
        "bg_opacity": "Opacidad de los paneles de fondo",
        "bg_radius": "Radio de las esquinas de los paneles, en pixeles",
        "text_pad": "Margen interno horizontal del texto dentro de su panel, en pixeles (el vertical lo da el centrado)",
        "res_target": "Resolucion esperada de los plates: 'timeline' o un valor tipo 3840x2160. Si un plate EXR no coincide, RES se pinta de rojo",
        "fps_target": "FPS esperados: 'timeline' o un numero. Si el clip no coincide, FPS se pinta de rojo",
        "save_defaults": "Guarda los objetivos como default del usuario (AppData)",
        "save_project": "Guarda los objetivos en el proyecto: viajan dentro del .hrox",
        "layout_pos": "Posicion del campo en porcentaje del formato (se adapta a cualquier resolucion)",
        "preset_combo": "Presets guardados en AppData",
        "preset_load": "Aplica el preset elegido al efecto",
        "preset_name": "Nombre para guardar el estado actual como preset",
        "preset_save": "Guarda campos, estilo y layout actuales con ese nombre",
    },
}


def _tip(key, lang="es"):
    return TOOLTIPS.get(lang, {}).get(key, "")


class HieroController(object):
    """Acceso al efecto y a la config reales. Se stubbea para el harness."""

    def __init__(self):
        self.node = None
        self.label = "No effect found"
        self.project_name = ""

    def attach(self):
        import hiero.ui

        self.node = None
        self.label = "No LGA BurnIn effect in the active sequence"
        self.project_name = ""
        seq = hiero.ui.activeSequence()
        if seq is None:
            self.label = "No active sequence"
            return False
        self.project_name = seq.project().name()
        for track in seq.videoTracks():
            for sub in track.subTrackItems():
                for item in sub:
                    try:
                        node = item.node()
                    except Exception:
                        continue
                    if node is not None and node.Class() == "LGA_BurnIn":
                        self.node = node
                        self.label = "%s  (track %s)" % (item.name(), track.name())
                        return True
        return False

    def get(self, knob, default=0.0):
        try:
            return self.node[knob].value()
        except Exception:
            return default

    def set(self, knob, value):
        try:
            self.node[knob].setValue(value)
        except Exception:
            pass

    def get_color(self, knob):
        try:
            v = self.node[knob].value()
            return (float(v[0]), float(v[1]), float(v[2]))
        except Exception:
            return (1.0, 1.0, 1.0)

    def set_color(self, knob, rgb):
        try:
            k = self.node[knob]
            for i, c in enumerate(rgb):
                k.setValue(c, i)
            k.setValue(1.0, 3)
        except Exception:
            pass

    def load_targets(self):
        user_data, _error = bi_config.load_user_file()
        import LGA_NKS_BurnIn_ProjectTag as bi_tag

        tag_json = bi_tag.read_config_json(bi_tag.find_project(self.project_name))
        cfg, _warns = bi_config.resolve(user_data, self.project_name, tag_json)
        return str(cfg.get("res_target", "timeline")), str(cfg.get("fps_target", "timeline"))

    def save_targets_project(self, res_target, fps_target):
        import LGA_NKS_BurnIn_ProjectTag as bi_tag

        proj = bi_tag.find_project(self.project_name)
        current = bi_tag.read_config_json(proj)
        try:
            data = json.loads(current) if current else {}
        except Exception:
            data = {}
        data["res_target"] = res_target
        data["fps_target"] = fps_target
        error = bi_tag.write_config(proj, data)
        self._invalidate()
        return error

    def save_targets_defaults(self, res_target, fps_target):
        data, _error = bi_config.load_user_file()
        data.setdefault("default", {})
        data["default"]["res_target"] = res_target
        data["default"]["fps_target"] = fps_target
        error = bi_config.save_user_file(data)
        self._invalidate()
        return error

    def _invalidate(self):
        try:
            import LGA_NKS_BurnIn_Logic as bi_logic

            bi_logic.invalidate_cache()
        except Exception:
            pass

    def nudge_all(self):
        """Ensucia todos los LGA_BurnIn de la secuencia activa.

        MEDIDO en NKS: el timeline no re-evalua las expresiones python de
        color hasta que el nodo cambia; sin esto un target nuevo no pinta.
        """
        try:
            import hiero.ui

            seq = hiero.ui.activeSequence()
            if seq is None:
                return
            for track in seq.videoTracks():
                for sub in track.subTrackItems():
                    for item in sub:
                        try:
                            node = item.node()
                            if node.Class() != "LGA_BurnIn":
                                continue
                            value = node["bi_opacity"].value()
                            node["bi_opacity"].setValue(value - 0.001)
                            node["bi_opacity"].setValue(value)
                        except Exception:
                            continue
        except Exception:
            pass

    def list_presets(self):
        return bi_config.list_presets()

    def load_preset(self, name):
        return bi_config.load_preset(name)

    def save_preset(self, name, preset):
        return bi_config.save_preset(name, preset)


class BurnInPanel(QtWidgets.QDialog):
    """Editor de LGA BurnIn con el estilo del pack."""

    def __init__(self, controller, parent=None):
        super(BurnInPanel, self).__init__(parent)
        self.ctl = controller
        self.setWindowTitle("LGA BurnIn")
        self.setStyleSheet(Style.FORM)
        # Mas ancha que el minimo estandar: la seccion Layout lleva seis
        # columnas (label + X + Y, dos campos por fila).
        self.setMinimumWidth(int(Metric.DIALOG_MIN_WIDTH * 1.3))
        self._loading = True
        self._armar_ui()
        apply_ui_font(self)
        self._cargar_estado()
        self._loading = False

    # -- armado --------------------------------------------------------------
    def _armar_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        margen = Metric.WINDOW_MARGIN
        layout.setContentsMargins(margen, margen, margen, margen)
        layout.setSpacing(Metric.SPACING)

        titulo = QtWidgets.QLabel("LGA BurnIn")
        titulo.setProperty("lgaTitle", True)
        layout.addWidget(titulo)

        layout.addLayout(self._fila_target())
        layout.addWidget(self._grupo_campos())
        layout.addWidget(self._grupo_layout())
        layout.addWidget(self._grupo_estilo())
        layout.addWidget(self._grupo_presets())
        layout.addWidget(self._grupo_proyecto())
        layout.addLayout(self._acciones())

    def _fila_target(self):
        fila = QtWidgets.QHBoxLayout()
        self.lbl_efecto = QtWidgets.QLabel("")
        self.lbl_efecto.setWordWrap(True)
        fila.addWidget(self.lbl_efecto, 1)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setStyleSheet(Style.BTN_SMALL)
        refresh.setToolTip(_tip("refresh"))
        refresh.clicked.connect(self._refrescar)
        fila.addWidget(refresh)
        return fila

    def _grupo_campos(self):
        grupo = QtWidgets.QGroupBox("Fields")
        grid = QtWidgets.QGridLayout(grupo)
        grid.setContentsMargins(
            Metric.SPACING, Metric.SPACING, Metric.SPACING, Metric.SPACING
        )
        grid.setHorizontalSpacing(Metric.SPACING * 3)
        grid.setVerticalSpacing(Metric.SPACING)

        self.chk_on = {}
        self.chk_bg = {}
        mitad = (len(FIELDS) + 1) // 2
        for i, (key, label) in enumerate(FIELDS):
            col = 0 if i < mitad else 2
            row = i % mitad
            chk = QtWidgets.QCheckBox(label)
            chk.setProperty("lgaLabeled", True)
            chk.setToolTip(_tip("field_on"))
            chk.toggled.connect(self._hacer_setter("bi_%s_on" % key))
            grid.addWidget(chk, row, col)
            self.chk_on[key] = chk

            bg = QtWidgets.QCheckBox("bg")
            bg.setProperty("lgaLabeled", True)
            bg.setToolTip(_tip("field_bg"))
            bg.toggled.connect(self._hacer_setter("bi_%s_bg" % key))
            grid.addWidget(bg, row, col + 1)
            self.chk_bg[key] = bg
        grid.setColumnStretch(4, 1)
        return grupo

    def _grupo_layout(self):
        grupo = QtWidgets.QGroupBox("Layout (% of format)")
        grid = QtWidgets.QGridLayout(grupo)
        grid.setContentsMargins(
            Metric.SPACING, Metric.SPACING, Metric.SPACING, Metric.SPACING
        )
        grid.setHorizontalSpacing(Metric.SPACING * 2)
        grid.setVerticalSpacing(Metric.SPACING)

        self.spin_x = {}
        self.spin_y = {}
        mitad = (len(FIELDS) + 1) // 2
        for i, (key, label) in enumerate(FIELDS):
            col = 0 if i < mitad else 3
            row = i % mitad
            grid.addWidget(QtWidgets.QLabel(label), row, col)
            sx = self._spin(0.0, 100.0, 0.5, _tip("layout_pos"))
            sx.setSuffix(" %")
            sx.setMinimumWidth(Metric.BUTTON_HEIGHT * 3)
            sx.valueChanged.connect(self._hacer_setter_pct("bi_%s_x" % key))
            grid.addWidget(sx, row, col + 1)
            self.spin_x[key] = sx
            sy = self._spin(0.0, 100.0, 0.5, _tip("layout_pos"))
            sy.setSuffix(" %")
            sy.setMinimumWidth(Metric.BUTTON_HEIGHT * 3)
            sy.valueChanged.connect(self._hacer_setter_pct("bi_%s_y" % key))
            grid.addWidget(sy, row, col + 2)
            self.spin_y[key] = sy
        grid.setColumnStretch(6, 1)
        return grupo

    def _grupo_presets(self):
        grupo = QtWidgets.QGroupBox("Presets")
        fila = QtWidgets.QHBoxLayout(grupo)
        fila.setContentsMargins(
            Metric.SPACING, Metric.SPACING, Metric.SPACING, Metric.SPACING
        )
        fila.setSpacing(Metric.SPACING)

        self.combo_presets = QtWidgets.QComboBox()
        self.combo_presets.setStyleSheet(Style.COMBO)
        self.combo_presets.setToolTip(_tip("preset_combo"))
        fila.addWidget(self.combo_presets, 1)

        cargar = QtWidgets.QPushButton("Load")
        cargar.setStyleSheet(Style.BTN_SMALL)
        cargar.setToolTip(_tip("preset_load"))
        cargar.clicked.connect(self._cargar_preset)
        fila.addWidget(cargar)

        self.edit_preset = QtWidgets.QLineEdit()
        self.edit_preset.setPlaceholderText("preset name")
        self.edit_preset.setToolTip(_tip("preset_name"))
        fila.addWidget(self.edit_preset, 1)

        guardar = QtWidgets.QPushButton("Save")
        guardar.setStyleSheet(Style.BTN_SMALL)
        guardar.setToolTip(_tip("preset_save"))
        guardar.clicked.connect(self._guardar_preset)
        fila.addWidget(guardar)
        return grupo

    def _grupo_estilo(self):
        grupo = QtWidgets.QGroupBox("Style")
        grid = QtWidgets.QGridLayout(grupo)
        grid.setContentsMargins(
            Metric.SPACING, Metric.SPACING, Metric.SPACING, Metric.SPACING
        )
        grid.setHorizontalSpacing(Metric.SPACING * 2)
        grid.setVerticalSpacing(Metric.SPACING)

        # Columna izquierda: texto. Columna derecha: paneles de fondo.
        grid.addWidget(QtWidgets.QLabel("Text color"), 0, 0)
        self.btn_text_color = self._swatch(_tip("text_color"), self._elegir_text_color)
        grid.addWidget(self.btn_text_color, 0, 1)

        grid.addWidget(QtWidgets.QLabel("Text opacity"), 1, 0)
        self.spin_opacity = self._spin(0.0, 1.0, 0.05, _tip("text_opacity"))
        self.spin_opacity.valueChanged.connect(self._hacer_setter("bi_opacity"))
        grid.addWidget(self.spin_opacity, 1, 1)

        grid.addWidget(QtWidgets.QLabel("Text scale"), 2, 0)
        self.spin_scale = self._spin(0.0, 2.0, 0.05, _tip("text_scale"))
        self.spin_scale.valueChanged.connect(self._hacer_setter("bi_scale"))
        grid.addWidget(self.spin_scale, 2, 1)

        grid.addWidget(QtWidgets.QLabel("Bg color"), 0, 2)
        self.btn_bg_color = self._swatch(_tip("bg_color"), self._elegir_bg_color)
        grid.addWidget(self.btn_bg_color, 0, 3)

        grid.addWidget(QtWidgets.QLabel("Bg opacity"), 1, 2)
        self.spin_bg_opacity = self._spin(0.0, 1.0, 0.05, _tip("bg_opacity"))
        self.spin_bg_opacity.valueChanged.connect(self._hacer_setter("bi_bg_opacity"))
        grid.addWidget(self.spin_bg_opacity, 1, 3)

        grid.addWidget(QtWidgets.QLabel("Bg corner radius"), 2, 2)
        self.spin_radius = self._spin(0.0, 120.0, 1.0, _tip("bg_radius"))
        self.spin_radius.valueChanged.connect(self._hacer_setter("bi_bg_radius"))
        grid.addWidget(self.spin_radius, 2, 3)

        grid.addWidget(QtWidgets.QLabel("Text padding"), 3, 2)
        self.spin_pad = self._spin(0.0, 120.0, 1.0, _tip("text_pad"))
        self.spin_pad.valueChanged.connect(self._hacer_setter("bi_text_pad"))
        grid.addWidget(self.spin_pad, 3, 3)

        grid.setColumnStretch(4, 1)
        return grupo

    def _grupo_proyecto(self):
        grupo = QtWidgets.QGroupBox("Project targets")
        grid = QtWidgets.QGridLayout(grupo)
        grid.setContentsMargins(
            Metric.SPACING, Metric.SPACING, Metric.SPACING, Metric.SPACING
        )
        grid.setHorizontalSpacing(Metric.SPACING * 2)
        grid.setVerticalSpacing(Metric.SPACING)

        self.lbl_proyecto = QtWidgets.QLabel("")
        self.lbl_proyecto.setWordWrap(True)
        grid.addWidget(self.lbl_proyecto, 0, 0, 1, 4)

        grid.addWidget(QtWidgets.QLabel("Plate resolution"), 1, 0)
        self.edit_res = QtWidgets.QLineEdit()
        self.edit_res.setToolTip(_tip("res_target"))
        grid.addWidget(self.edit_res, 1, 1)

        grid.addWidget(QtWidgets.QLabel("FPS"), 1, 2)
        self.edit_fps = QtWidgets.QLineEdit()
        self.edit_fps.setToolTip(_tip("fps_target"))
        grid.addWidget(self.edit_fps, 1, 3)

        hint = QtWidgets.QLabel(
            "Use %s to compare against the sequence, or explicit values "
            "like 3840x2160 / 24." % emphasis("timeline")
        )
        hint.setWordWrap(True)
        grid.addWidget(hint, 2, 0, 1, 4)
        return grupo

    def _acciones(self):
        fila = QtWidgets.QHBoxLayout()
        defaults = QtWidgets.QPushButton("Save Targets as Defaults")
        defaults.setStyleSheet(Style.BTN_SECONDARY)
        defaults.setFixedHeight(Metric.BUTTON_HEIGHT)
        defaults.setToolTip(_tip("save_defaults"))
        defaults.clicked.connect(self._guardar_defaults)
        fila.addWidget(defaults)

        fila.addStretch(1)

        cerrar = QtWidgets.QPushButton("Close")
        cerrar.setStyleSheet(Style.BTN_SECONDARY)
        cerrar.setFixedHeight(Metric.BUTTON_HEIGHT)
        cerrar.clicked.connect(self.reject)
        fila.addWidget(cerrar)

        guardar = QtWidgets.QPushButton("Save Targets to Project")
        guardar.setStyleSheet(Style.BTN_PRIMARY)
        guardar.setFixedHeight(Metric.BUTTON_HEIGHT)
        guardar.setDefault(True)
        guardar.setToolTip(_tip("save_project"))
        guardar.clicked.connect(self._guardar_proyecto)
        fila.addWidget(guardar)
        return fila

    # -- helpers de armado ---------------------------------------------------
    def _spin(self, minimo, maximo, paso, tooltip):
        # Los spinbox van NATIVOS: es la regla del pack (no hay hoja para
        # ellos y un QSS propio los rompe visualmente).
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimo, maximo)
        spin.setSingleStep(paso)
        spin.setDecimals(2)
        spin.setToolTip(tooltip)
        return spin

    def _swatch(self, tooltip, slot):
        # El color que muestra el swatch es DATA (el valor elegido), por eso
        # su background va inline y no sale de una hoja del modulo.
        boton = QtWidgets.QPushButton()
        boton.setFixedSize(Metric.BUTTON_HEIGHT * 2, Metric.BUTTON_HEIGHT - 6)
        boton.setToolTip(tooltip)
        boton.clicked.connect(slot)
        return boton

    def _pintar_swatch(self, boton, rgb):
        # El background es DATA (el color elegido); el borde sale del token.
        color = QtGui.QColor.fromRgbF(*[max(0.0, min(1.0, c)) for c in rgb])
        boton.setStyleSheet(
            "background-color: %s; border: 1px solid %s;"
            % (color.name(), Color.BORDER_STRONG)
        )

    def _hacer_setter(self, knob):
        def _set(value):
            if self._loading:
                return
            self.ctl.set(knob, float(value) if not isinstance(value, bool) else (1.0 if value else 0.0))

        return _set

    def _hacer_setter_pct(self, knob):
        """Setter para los spins de layout: la UI habla en %, el knob en 0-1."""

        def _set(value):
            if self._loading:
                return
            self.ctl.set(knob, float(value) / 100.0)

        return _set

    # -- estado --------------------------------------------------------------
    def _cargar_estado(self):
        self._loading = True
        self.lbl_efecto.setText("Editing: %s" % emphasis(self.ctl.label))
        for key, _label in FIELDS:
            self.chk_on[key].setChecked(bool(self.ctl.get("bi_%s_on" % key, 1.0)))
            self.chk_bg[key].setChecked(bool(self.ctl.get("bi_%s_bg" % key, 1.0)))
        self.spin_opacity.setValue(float(self.ctl.get("bi_opacity", 1.0)))
        self.spin_scale.setValue(float(self.ctl.get("bi_scale", 0.5)))
        self.spin_bg_opacity.setValue(float(self.ctl.get("bi_bg_opacity", 0.65)))
        self.spin_radius.setValue(float(self.ctl.get("bi_bg_radius", 30.0)))
        self.spin_pad.setValue(float(self.ctl.get("bi_text_pad", 28.0)))
        self._pintar_swatch(self.btn_text_color, self.ctl.get_color("bi_color"))
        self._pintar_swatch(self.btn_bg_color, self.ctl.get_color("bi_bg_color"))
        for key, _label in FIELDS:
            self.spin_x[key].setValue(float(self.ctl.get("bi_%s_x" % key, 0.0)) * 100.0)
            self.spin_y[key].setValue(float(self.ctl.get("bi_%s_y" % key, 0.0)) * 100.0)
        self._recargar_presets()

        proyecto = self.ctl.project_name or "-"
        self.lbl_proyecto.setText("Project: %s" % emphasis(proyecto))
        res_t, fps_t = self.ctl.load_targets()
        self.edit_res.setText(res_t)
        self.edit_fps.setText(fps_t)
        self._loading = False

    def _refrescar(self):
        self.ctl.attach()
        self._cargar_estado()

    def _elegir_text_color(self):
        self._elegir_color("bi_color", self.btn_text_color)

    def _elegir_bg_color(self):
        self._elegir_color("bi_bg_color", self.btn_bg_color)

    def _elegir_color(self, knob, boton):
        actual = QtGui.QColor.fromRgbF(*self.ctl.get_color(knob))
        elegido = QtWidgets.QColorDialog.getColor(actual, self, "Pick color")
        if not elegido.isValid():
            return
        rgb = (elegido.redF(), elegido.greenF(), elegido.blueF())
        self.ctl.set_color(knob, rgb)
        self._pintar_swatch(boton, rgb)

    def _recargar_presets(self):
        actual = self.combo_presets.currentText()
        self.combo_presets.clear()
        self.combo_presets.addItems(self.ctl.list_presets())
        if actual:
            idx = self.combo_presets.findText(actual)
            if idx >= 0:
                self.combo_presets.setCurrentIndex(idx)

    def _estado_actual(self):
        """Snapshot de campos + layout + estilo para guardar como preset."""
        fields = {}
        for key, _label in FIELDS:
            fields[key] = {
                "on": self.chk_on[key].isChecked(),
                "bg": self.chk_bg[key].isChecked(),
                "x": round(self.spin_x[key].value() / 100.0, 4),
                "y": round(self.spin_y[key].value() / 100.0, 4),
            }
        estilo = {
            "text_color": list(self.ctl.get_color("bi_color")),
            "bg_color": list(self.ctl.get_color("bi_bg_color")),
            "text_opacity": self.spin_opacity.value(),
            "text_scale": self.spin_scale.value(),
            "bg_opacity": self.spin_bg_opacity.value(),
            "bg_radius": self.spin_radius.value(),
            "text_pad": self.spin_pad.value(),
        }
        return {"fields": fields, "style": estilo}

    def _guardar_preset(self):
        nombre = self.edit_preset.text().strip()
        error = self.ctl.save_preset(nombre, self._estado_actual())
        if error:
            self._avisar(error, "")
            return
        # Exito silencioso: el preset apareciendo seleccionado en el combo
        # es el feedback (un cartel modal aca corta el flujo de trabajo).
        self._recargar_presets()
        idx = self.combo_presets.findText(nombre)
        if idx >= 0:
            self.combo_presets.setCurrentIndex(idx)
        self.edit_preset.clear()

    def _cargar_preset(self):
        nombre = self.combo_presets.currentText()
        if not nombre:
            self._avisar("No preset selected", "")
            return
        preset = self.ctl.load_preset(nombre)
        if not preset:
            self._avisar("Preset '%s' not found" % nombre, "")
            return
        fields = preset.get("fields") or {}
        estilo = preset.get("style") or {}
        for key, _label in FIELDS:
            data = fields.get(key) or {}
            if "on" in data:
                self.chk_on[key].setChecked(bool(data["on"]))
            if "bg" in data:
                self.chk_bg[key].setChecked(bool(data["bg"]))
            if "x" in data:
                self.spin_x[key].setValue(float(data["x"]) * 100.0)
            if "y" in data:
                self.spin_y[key].setValue(float(data["y"]) * 100.0)
        if "text_opacity" in estilo:
            self.spin_opacity.setValue(float(estilo["text_opacity"]))
        if "text_scale" in estilo:
            self.spin_scale.setValue(float(estilo["text_scale"]))
        if "bg_opacity" in estilo:
            self.spin_bg_opacity.setValue(float(estilo["bg_opacity"]))
        if "bg_radius" in estilo:
            self.spin_radius.setValue(float(estilo["bg_radius"]))
        if "text_pad" in estilo:
            self.spin_pad.setValue(float(estilo["text_pad"]))
        if "text_color" in estilo:
            rgb = tuple(estilo["text_color"])[:3]
            self.ctl.set_color("bi_color", rgb)
            self._pintar_swatch(self.btn_text_color, rgb)
        if "bg_color" in estilo:
            rgb = tuple(estilo["bg_color"])[:3]
            self.ctl.set_color("bi_bg_color", rgb)
            self._pintar_swatch(self.btn_bg_color, rgb)
        self.ctl.nudge_all()

    def _guardar_proyecto(self):
        error = self.ctl.save_targets_project(
            self.edit_res.text().strip(), self.edit_fps.text().strip()
        )
        if not error:
            self.ctl.nudge_all()
        self._avisar(error, "Targets saved to the project (travels in the .hrox). Remember to save the project.")

    def _guardar_defaults(self):
        error = self.ctl.save_targets_defaults(
            self.edit_res.text().strip(), self.edit_fps.text().strip()
        )
        if not error:
            self.ctl.nudge_all()
        self._avisar(error, "Targets saved as user defaults.")

    def _avisar(self, error, ok_texto):
        from LGA_NKS_Shared.LGA_NKS_MessageBox import show_error, show_info

        if error:
            show_error(self, "LGA BurnIn", error)
        else:
            show_info(self, "LGA BurnIn", ok_texto)


_panel = None


def show_panel():
    """Punto de entrada: lo llama el boton Open LGA Panel del gizmo."""
    global _panel
    ctl = HieroController()
    ctl.attach()
    _panel = BurnInPanel(ctl)
    apply_ui_font(_panel)
    _panel.show()
    _panel.raise_()
    return _panel
