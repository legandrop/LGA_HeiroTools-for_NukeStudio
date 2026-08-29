"""
____________________________________________________________________

  LGA_NKS_BurnIn_Panel v2.00 | Lega

  Editor de LGA BurnIn con el estilo del pack. Rediseno "tabla +
  detalle": una fila por campo (nombre, ON, BG, X, Y, SIZE) con
  drag-sliders estilo Nuke, seleccion multiple de filas, y un bloque
  de detalle que aplica a TODA la seleccion (ancla 3x3 -> X/Y,
  rotacion 0/90/180/270 y el texto de los campos custom). Style
  global (color, peso Inter, opacidades, radio, padding), presets y
  objetivos de comparacion del proyecto (res/fps).

  La ventana solo escribe knobs y config; no toca el render. El panel
  de Properties del gizmo quedo pelado a un solo boton que abre esta.

  La rotacion escribe ademas el literal en los Text2 del efecto via
  LGA_NKS_BurnIn_Blink.apply_rotation (el mecanismo del grupo "root
  transform"; ver Docu_SoftEffects_Aprendizajes.md). Si el viewer no
  refresca solo, el boton Refresh Timeline del ViewerTL lo fuerza.

  v2.01: Rotacion por campo cableada (RotationBar en el detalle,
         aplica a la seleccion; presets guardan/cargan rot).
  v2.00: Rediseno completo. Tabla con drag-sliders (click-drag cambia,
         click escribe) y paint-toggle de checkboxes (click+drag
         tilda/destilda varios). Seleccion multiple + detalle que
         opera sobre la seleccion. Campos custom (texto libre),
         selector de peso Inter, tamano por campo, keep-on-top.
         Reemplaza el diseno por secciones v1.
  v1.01: Layout en %, presets con nombre, nudge tras guardar targets.
  v1.00: Version inicial.
____________________________________________________________________
"""

import json

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import (
    QtWidgets,
    QtGui,
    QtCore,
    Qt,
)
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Style,
    Color,
    Metric,
    apply_ui_font,
    emphasis,
)

import LGA_NKS_BurnIn_Config as bi_config

# (key, etiqueta visible, es_custom). Mismo orden y nombres que el motor
# (LGA_NKS_BurnIn_Blink.FIELDS / gen_LGA_BurnIn_gizmo.ORDER).
FIELDS = (
    ("clip", "Clip name", False),
    ("cspace", "Colorspace", False),
    ("res", "Resolution", False),
    ("frame", "Frame", False),
    ("tc", "Timecode", False),
    ("fps", "FPS", False),
    ("custom1", "Custom 1", True),
    ("custom2", "Custom 2", True),
)

# Presets del ancla 3x3: (X%, Y%) por celda. Fila de arriba = borde superior
# (Y alto), fila de abajo = borde inferior (Y bajo); columnas izq/centro/der.
_ANCHOR_X = (2.0, 50.0, 98.0)
_ANCHOR_Y = (93.0, 50.0, 2.5)

_WEIGHTS = ("Regular", "SemiBold", "Bold")
_ROTATIONS = (0, 90, 180, 270)

# Capa intermedia de tooltips (regla del repo: castellano, nunca hardcodeados
# en el widget, para la futura migracion bilingue).
TOOLTIPS = {
    "es": {
        "refresh": "Vuelve a buscar el efecto LGA BurnIn en la secuencia activa",
        "field_on": "Muestra u oculta este campo (click+drag sobre varios para pintar)",
        "field_bg": "Panel redondeado de fondo detras del campo (click+drag para pintar)",
        "field_x": "Posicion horizontal en % del formato (click-drag cambia, click escribe)",
        "field_y": "Posicion vertical en % del formato (click-drag cambia, click escribe)",
        "field_size": "Tamano del texto de este campo en % (click-drag cambia, click escribe)",
        "field_name": "Click selecciona la fila; Ctrl/Shift para seleccionar varias",
        "anchor": "Manda X/Y de las filas seleccionadas a esa esquina o centro",
        "rotation": "Rota el texto y su fondo de las filas seleccionadas",
        "custom_text": "Texto libre del campo custom seleccionado",
        "weight": "Peso de la fuente Inter (recalcula los fondos)",
        "text_color": "Color del texto de todos los campos",
        "bg_color": "Color de los paneles de fondo",
        "text_opacity": "Opacidad del texto",
        "bg_opacity": "Opacidad de los paneles de fondo",
        "bg_radius": "Radio de las esquinas de los paneles, en pixeles",
        "text_pad": "Margen interno horizontal del texto dentro de su panel, en pixeles",
        "res_target": "Resolucion esperada de los plates: 'timeline' o 3840x2160. Si un plate EXR no coincide, RES se pinta de rojo",
        "fps_target": "FPS esperados: 'timeline' o un numero. Si el clip no coincide, FPS se pinta de rojo",
        "keep_on_top": "Mantiene esta ventana siempre por encima",
        "save_defaults": "Guarda los objetivos como default del usuario (AppData)",
        "save_project": "Guarda los objetivos en el proyecto: viajan dentro del .hrox",
        "preset_combo": "Presets guardados en AppData",
        "preset_load": "Aplica el preset elegido al efecto",
        "preset_name": "Nombre para guardar el estado actual como preset",
        "preset_save": "Guarda campos, estilo y layout actuales con ese nombre",
        "all_on": "Enciende todos los campos",
        "all_off": "Apaga todos los campos",
    },
}


def _tip(key, lang="es"):
    return TOOLTIPS.get(lang, {}).get(key, "")


# ── Widgets custom del pack ───────────────────────────────────────────────────


class PaintController(object):
    """Estado compartido del 'pintado' de checkboxes: un click que EMPIEZA
    sobre un checkbox entra en modo pintar y, mientras se arrastra, tilda o
    destilda con el mismo estado a todos los checkbox que toca el cursor.

    Durante el drag Qt agarra el mouse al checkbox donde se apreto, asi que el
    resto NO recibe eventos: por eso el hit-test se hace a mano contra la lista
    de checkbox registrados, con la posicion global del cursor.
    """

    def __init__(self):
        self.active = False
        self.target = False
        self.boxes = []

    def register(self, box):
        self.boxes.append(box)

    def begin(self, target):
        self.active = True
        self.target = target

    def end(self):
        self.active = False

    def paint_at(self, global_pos):
        if not self.active:
            return
        for box in self.boxes:
            try:
                if not box.isVisible():
                    continue
                top_left = box.mapToGlobal(box.rect().topLeft())
                bottom_right = box.mapToGlobal(box.rect().bottomRight())
                inside = (
                    top_left.x() <= global_pos.x() <= bottom_right.x()
                    and top_left.y() <= global_pos.y() <= bottom_right.y()
                )
                if inside and box.isChecked() != self.target:
                    box.setChecked(self.target)
            except Exception:
                continue


class PaintCheckBox(QtWidgets.QCheckBox):
    """Checkbox que participa del paint-toggle. No lleva QSS propio: hereda la
    hoja de la ventana (Style.FORM); solo agrega el comportamiento de pintado."""

    def __init__(self, controller, parent=None):
        super(PaintCheckBox, self).__init__(parent)
        self._paint = controller
        controller.register(self)

    def mousePressEvent(self, event):
        super(PaintCheckBox, self).mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            # El estado ya cambio en el super: pintamos con el estado NUEVO.
            self._paint.begin(self.isChecked())

    def mouseMoveEvent(self, event):
        super(PaintCheckBox, self).mouseMoveEvent(event)
        if self._paint.active:
            self._paint.paint_at(QtGui.QCursor.pos())

    def mouseReleaseEvent(self, event):
        super(PaintCheckBox, self).mouseReleaseEvent(event)
        self._paint.end()


class DragSlider(QtWidgets.QLineEdit):
    """Numerico estilo Nuke: click-drag horizontal cambia el valor; un click
    simple (sin arrastre) entra en modo escritura. No lleva QSS propio: hereda
    la hoja QLineEdit de la ventana; solo agrega comportamiento y tamano."""

    valueChanged = QtCore.Signal(float)

    def __init__(self, minimo, maximo, decimals, per_px, parent=None):
        super(DragSlider, self).__init__(parent)
        self._min = float(minimo)
        self._max = float(maximo)
        self._dec = int(decimals)
        self._per_px = float(per_px)
        self._value = float(minimo)
        self._dragging = False
        self._moved = False
        self._press_x = 0
        self._press_val = 0.0
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.SizeHorCursor)
        self.setFixedHeight(Metric.ROW_HEIGHT - 2)
        self.editingFinished.connect(self._commit_text)

    def _fmt(self, v):
        return ("%.*f" % (self._dec, v)) if self._dec else ("%d" % int(round(v)))

    def value(self):
        return self._value

    def setValue(self, v, emit=True):
        v = max(self._min, min(self._max, float(v)))
        self._value = v
        self.setText(self._fmt(v))
        if emit:
            self.valueChanged.emit(v)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isReadOnly():
            self._dragging = True
            self._moved = False
            self._press_x = QtGui.QCursor.pos().x()
            self._press_val = self._value
            event.accept()
            return
        super(DragSlider, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            dx = QtGui.QCursor.pos().x() - self._press_x
            if abs(dx) > 2:
                self._moved = True
            self.setValue(self._press_val + dx * self._per_px)
            event.accept()
            return
        super(DragSlider, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            if not self._moved:
                # Click sin arrastre: pasar a modo escritura.
                self.setReadOnly(False)
                self.selectAll()
                self.setFocus(Qt.MouseFocusReason)
            event.accept()
            return
        super(DragSlider, self).mouseReleaseEvent(event)

    def _commit_text(self):
        if self.isReadOnly():
            return
        try:
            self.setValue(float(self.text().replace(",", ".")))
        except ValueError:
            self.setValue(self._value)
        self.setReadOnly(True)

    def focusOutEvent(self, event):
        if not self.isReadOnly():
            self._commit_text()
        super(DragSlider, self).focusOutEvent(event)


class _Clickable(QtWidgets.QFrame):
    """Celda clickeable de un control novedoso (ancla / rotacion). QFrame (no
    QPushButton) a proposito: no hay hoja para estos controles, asi que se
    pintan con tokens Color.* -no hex- y no compiten con Style.BTN_*."""

    clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super(_Clickable, self).__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super(_Clickable, self).mousePressEvent(event)


class AnchorPicker(QtWidgets.QWidget):
    """Grilla 3x3: cada celda manda X/Y de la seleccion a esa esquina/centro."""

    picked = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super(AnchorPicker, self).__init__(parent)
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        self._cells = []
        for r in range(3):
            for c in range(3):
                cell = _Clickable()
                cell.setFixedSize(20, 20)
                x, y = _ANCHOR_X[c], _ANCHOR_Y[r]
                cell.clicked.connect(
                    lambda xx=x, yy=y: self.picked.emit(xx, yy)
                )
                self._paint_cell(cell, False)
                grid.addWidget(cell, r, c)
                self._cells.append((cell, x, y))

    def _paint_cell(self, cell, hot):
        bg = Color.ACCENT if hot else Color.SURFACE_RAISED
        cell.setStyleSheet(
            "background:%s; border-radius:%dpx;" % (bg, Metric.RADIUS_FIELD - 2)
        )

    def highlight(self, x, y):
        for cell, cx, cy in self._cells:
            self._paint_cell(cell, abs(cx - x) < 0.6 and abs(cy - y) < 0.6)


class RotationBar(QtWidgets.QWidget):
    """Segmentado 0/90/180/270: rota texto+fondo de la seleccion."""

    picked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(RotationBar, self).__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._cells = []
        for deg in _ROTATIONS:
            cell = _Clickable()
            cell.setFixedSize(40, Metric.ROW_HEIGHT)
            lay = QtWidgets.QHBoxLayout(cell)
            lay.setContentsMargins(0, 0, 0, 0)
            lbl = QtWidgets.QLabel("%d°" % deg)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background:transparent;")
            lay.addWidget(lbl)
            cell.clicked.connect(lambda d=deg: self.picked.emit(d))
            self._paint_cell(cell, False)
            row.addWidget(cell)
            self._cells.append((cell, deg))
        row.addStretch(1)

    def _paint_cell(self, cell, sel):
        bg = Color.CHECKBOX_ON if sel else Color.CHECKBOX_OFF
        cell.setStyleSheet(
            "background:%s; border:1px solid %s; border-radius:%dpx;"
            % (bg, Color.CHECKBOX_BORDER, Metric.RADIUS_FIELD - 2)
        )

    def highlight(self, deg):
        for cell, d in self._cells:
            self._paint_cell(cell, d == deg)


# ── Acceso al efecto real (stubbeable para el harness) ────────────────────────


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

    def get_text(self, knob, default=""):
        try:
            return str(self.node[knob].value())
        except Exception:
            return default

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

    def get_weight(self):
        try:
            return str(self.node["bi_weight"].value())
        except Exception:
            return "SemiBold"

    def set_weight(self, style):
        try:
            self.node["bi_weight"].setValue(style)
        except Exception:
            pass
        # El fondo depende del peso: re-aplicar la fuente y ensuciar para que
        # el timeline re-mida y re-renderice.
        try:
            import LGA_NKS_BurnIn_Blink as bi_blink

            bi_blink.apply_font(self.node)
        except Exception:
            pass
        self.nudge_all()

    def apply_rotation(self, fields=None):
        """Re-escribe la rotacion literal de los campos en el efecto.

        Llamada directa (ademas del knobChanged del registro) para que la
        rotacion funcione tambien en una sesion donde el registro viejo no
        tenia el branch de bi_<f>_rot.
        """
        try:
            import LGA_NKS_BurnIn_Blink as bi_blink

            bi_blink.apply_rotation(self.node, fields=fields)
        except Exception:
            pass
        self.nudge_all()

    def field_ok(self, field):
        """1.0/0.0 del campo (res/fps) para pintar el nombre en rojo. Ante
        cualquier duda 1.0 (no gritar rojo)."""
        try:
            import LGA_NKS_BurnIn_Logic as bi_logic
            import nuke

            return bi_logic.bi_ok(field, self.node, nuke.frame())
        except Exception:
            return 1.0

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
        """Ensucia todos los LGA_BurnIn de la secuencia activa (el timeline no
        re-evalua las expresiones python hasta que el nodo cambia)."""
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


# ── Ventana ───────────────────────────────────────────────────────────────────


class BurnInPanel(QtWidgets.QDialog):
    """Editor de LGA BurnIn con el estilo del pack (tabla + detalle)."""

    def __init__(self, controller, parent=None):
        super(BurnInPanel, self).__init__(parent)
        self.ctl = controller
        self.paint = PaintController()
        self._loading = True
        self.setWindowTitle("LGA BurnIn")
        self.setStyleSheet(Style.FORM)
        self.setMinimumWidth(int(Metric.DIALOG_MIN_WIDTH * 1.25))
        self._keep_on_top = True
        self._apply_on_top()
        self._armar_ui()
        apply_ui_font(self)
        self._medir_tabla()
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

        layout.addLayout(self._fila_efecto())
        layout.addWidget(self._tabla())
        layout.addWidget(self._detalle())
        layout.addWidget(self._grupo_estilo())
        layout.addWidget(self._grupo_presets())
        layout.addWidget(self._grupo_proyecto())
        layout.addLayout(self._barra_inferior())

    def _fila_efecto(self):
        fila = QtWidgets.QHBoxLayout()
        self.lbl_efecto = QtWidgets.QLabel("")
        self.lbl_efecto.setWordWrap(True)
        fila.addWidget(self.lbl_efecto, 1)
        all_on = QtWidgets.QPushButton("All on")
        all_on.setStyleSheet(Style.BTN_SMALL)
        all_on.setToolTip(_tip("all_on"))
        all_on.clicked.connect(lambda: self._all_fields(True))
        fila.addWidget(all_on)
        all_off = QtWidgets.QPushButton("All off")
        all_off.setStyleSheet(Style.BTN_SMALL)
        all_off.setToolTip(_tip("all_off"))
        all_off.clicked.connect(lambda: self._all_fields(False))
        fila.addWidget(all_off)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setStyleSheet(Style.BTN_SMALL)
        refresh.setToolTip(_tip("refresh"))
        refresh.clicked.connect(self._refrescar)
        fila.addWidget(refresh)
        return fila

    def _tabla(self):
        tabla = QtWidgets.QTableWidget(len(FIELDS), 6, self)
        tabla.setHorizontalHeaderLabels(["Field", "On", "Bg", "X", "Y", "Size"])
        tabla.verticalHeader().setVisible(False)
        tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tabla.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        tabla.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        tabla.setStyleSheet(Style.TABLE)

        self.chk_on = {}
        self.chk_bg = {}
        self.slider_x = {}
        self.slider_y = {}
        self.slider_size = {}
        self.name_items = {}

        for fila, (key, label, _custom) in enumerate(FIELDS):
            item = QtWidgets.QTableWidgetItem(label)
            item.setToolTip(_tip("field_name"))
            item.setData(Qt.UserRole, key)
            tabla.setItem(fila, 0, item)
            self.name_items[key] = item

            tabla.setCellWidget(fila, 1, self._celda_paint(key, "on"))
            tabla.setCellWidget(fila, 2, self._celda_paint(key, "bg"))
            tabla.setCellWidget(fila, 3, self._celda_slider(key, "x", 0.0, 100.0, 1, 0.25))
            tabla.setCellWidget(fila, 4, self._celda_slider(key, "y", 0.0, 100.0, 1, 0.25))
            tabla.setCellWidget(fila, 5, self._celda_slider(key, "size", 10.0, 400.0, 0, 1.0))
            tabla.setRowHeight(fila, Metric.ROW_HEIGHT)

        tabla.horizontalHeader().setStretchLastSection(False)
        tabla.itemSelectionChanged.connect(self._on_selection)
        self.tabla = tabla
        return tabla

    def _celda_paint(self, key, kind):
        chk = PaintCheckBox(self.paint)
        chk.setToolTip(_tip("field_%s" % kind))
        target = self.chk_on if kind == "on" else self.chk_bg
        target[key] = chk
        chk.toggled.connect(self._hacer_setter_bool("bi_%s_%s" % (key, kind)))
        cont = QtWidgets.QWidget()
        cont.setStyleSheet("background: transparent;")
        caja = QtWidgets.QHBoxLayout(cont)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setAlignment(Qt.AlignCenter)
        caja.addWidget(chk)
        return cont

    def _celda_slider(self, key, comp, minimo, maximo, dec, per_px):
        sl = DragSlider(minimo, maximo, dec, per_px)
        sl.setToolTip(_tip("field_%s" % comp))
        store = {"x": self.slider_x, "y": self.slider_y, "size": self.slider_size}[comp]
        store[key] = sl
        if comp == "size":
            sl.valueChanged.connect(self._hacer_setter("bi_%s_size" % key))
        else:
            sl.valueChanged.connect(self._hacer_setter_pct("bi_%s_%s" % (key, comp)))
        cont = QtWidgets.QWidget()
        cont.setStyleSheet("background: transparent;")
        caja = QtWidgets.QHBoxLayout(cont)
        caja.setContentsMargins(3, 0, 3, 0)
        caja.addWidget(sl)
        return cont

    def _detalle(self):
        grupo = QtWidgets.QGroupBox("Selection")
        fila = QtWidgets.QHBoxLayout(grupo)
        fila.setContentsMargins(
            Metric.SPACING, Metric.SPACING, Metric.SPACING, Metric.SPACING
        )
        fila.setSpacing(Metric.SPACING * 2)

        # Ancla 3x3.
        col_anchor = QtWidgets.QVBoxLayout()
        col_anchor.setSpacing(Metric.SPACING // 2)
        lbl_pos = QtWidgets.QLabel("Position")
        col_anchor.addWidget(lbl_pos)
        self.anchor = AnchorPicker()
        self.anchor.setToolTip(_tip("anchor"))
        self.anchor.picked.connect(self._on_anchor)
        col_anchor.addWidget(self.anchor)
        fila.addLayout(col_anchor)

        # Rotacion + texto custom.
        col_right = QtWidgets.QVBoxLayout()
        col_right.setSpacing(Metric.SPACING)
        row_rot = QtWidgets.QHBoxLayout()
        row_rot.setSpacing(Metric.SPACING)
        lbl_rot = QtWidgets.QLabel("Rotation")
        lbl_rot.setFixedWidth(Metric.BUTTON_HEIGHT * 2)
        row_rot.addWidget(lbl_rot)
        self.rotbar = RotationBar()
        self.rotbar.setToolTip(_tip("rotation"))
        self.rotbar.picked.connect(self._on_rotation)
        row_rot.addWidget(self.rotbar)
        row_rot.addStretch(1)
        col_right.addLayout(row_rot)

        row_txt = QtWidgets.QHBoxLayout()
        row_txt.setSpacing(Metric.SPACING)
        self.lbl_custom = QtWidgets.QLabel("Text")
        self.lbl_custom.setFixedWidth(Metric.BUTTON_HEIGHT * 2)
        row_txt.addWidget(self.lbl_custom)
        self.edit_custom = QtWidgets.QLineEdit()
        self.edit_custom.setToolTip(_tip("custom_text"))
        self.edit_custom.textEdited.connect(self._on_custom_text)
        row_txt.addWidget(self.edit_custom, 1)
        col_right.addLayout(row_txt)
        col_right.addStretch(1)
        fila.addLayout(col_right, 1)

        self.grp_detalle = grupo
        return grupo

    def _grupo_estilo(self):
        grupo = QtWidgets.QGroupBox("Style")
        grid = QtWidgets.QGridLayout(grupo)
        grid.setContentsMargins(
            Metric.SPACING, Metric.SPACING, Metric.SPACING, Metric.SPACING
        )
        grid.setHorizontalSpacing(Metric.SPACING * 2)
        grid.setVerticalSpacing(Metric.SPACING)

        grid.addWidget(QtWidgets.QLabel("Text color"), 0, 0)
        self.btn_text_color = self._swatch(_tip("text_color"), self._elegir_text_color)
        grid.addWidget(self.btn_text_color, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Bg color"), 0, 2)
        self.btn_bg_color = self._swatch(_tip("bg_color"), self._elegir_bg_color)
        grid.addWidget(self.btn_bg_color, 0, 3)

        grid.addWidget(QtWidgets.QLabel("Weight"), 1, 0)
        self.combo_weight = QtWidgets.QComboBox()
        self.combo_weight.setStyleSheet(Style.COMBO)
        self.combo_weight.addItems(_WEIGHTS)
        self.combo_weight.setToolTip(_tip("weight"))
        self.combo_weight.currentTextChanged.connect(self._on_weight)
        grid.addWidget(self.combo_weight, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Text opacity"), 1, 2)
        self.slider_opacity = self._detail_slider(0.0, 1.0, 2, 0.01, "text_opacity")
        self.slider_opacity.valueChanged.connect(self._hacer_setter("bi_opacity"))
        grid.addWidget(self.slider_opacity, 1, 3)

        grid.addWidget(QtWidgets.QLabel("Bg opacity"), 2, 0)
        self.slider_bg_opacity = self._detail_slider(0.0, 1.0, 2, 0.01, "bg_opacity")
        self.slider_bg_opacity.valueChanged.connect(self._hacer_setter("bi_bg_opacity"))
        grid.addWidget(self.slider_bg_opacity, 2, 1)
        grid.addWidget(QtWidgets.QLabel("Corner radius"), 2, 2)
        self.slider_radius = self._detail_slider(0.0, 120.0, 0, 1.0, "bg_radius")
        self.slider_radius.valueChanged.connect(self._hacer_setter("bi_bg_radius"))
        grid.addWidget(self.slider_radius, 2, 3)

        grid.addWidget(QtWidgets.QLabel("Padding"), 3, 0)
        self.slider_pad = self._detail_slider(0.0, 120.0, 0, 1.0, "text_pad")
        self.slider_pad.valueChanged.connect(self._hacer_setter("bi_text_pad"))
        grid.addWidget(self.slider_pad, 3, 1)

        grid.setColumnStretch(4, 1)
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

    def _barra_inferior(self):
        fila = QtWidgets.QHBoxLayout()
        self.chk_on_top = QtWidgets.QCheckBox("Keep on top")
        self.chk_on_top.setProperty("lgaLabeled", True)
        self.chk_on_top.setToolTip(_tip("keep_on_top"))
        self.chk_on_top.setChecked(True)
        self.chk_on_top.toggled.connect(self._on_keep_top)
        fila.addWidget(self.chk_on_top)
        fila.addStretch(1)
        defaults = QtWidgets.QPushButton("Save as Defaults")
        defaults.setStyleSheet(Style.BTN_SECONDARY)
        defaults.setFixedHeight(Metric.BUTTON_HEIGHT)
        defaults.setToolTip(_tip("save_defaults"))
        defaults.clicked.connect(self._guardar_defaults)
        fila.addWidget(defaults)
        cerrar = QtWidgets.QPushButton("Close")
        cerrar.setStyleSheet(Style.BTN_SECONDARY)
        cerrar.setFixedHeight(Metric.BUTTON_HEIGHT)
        cerrar.clicked.connect(self.reject)
        fila.addWidget(cerrar)
        guardar = QtWidgets.QPushButton("Save to Project")
        guardar.setStyleSheet(Style.BTN_PRIMARY)
        guardar.setFixedHeight(Metric.BUTTON_HEIGHT)
        guardar.setDefault(True)
        guardar.setToolTip(_tip("save_project"))
        guardar.clicked.connect(self._guardar_proyecto)
        fila.addWidget(guardar)
        return fila

    # -- helpers de armado ---------------------------------------------------
    def _detail_slider(self, minimo, maximo, dec, per_px, tip_key):
        sl = DragSlider(minimo, maximo, dec, per_px)
        sl.setToolTip(_tip(tip_key))
        sl.setMaximumWidth(Metric.BUTTON_HEIGHT * 3)
        return sl

    def _swatch(self, tooltip, slot):
        # El color del swatch es DATA (el valor elegido): background inline.
        boton = QtWidgets.QPushButton()
        boton.setFixedSize(Metric.BUTTON_HEIGHT * 2, Metric.BUTTON_HEIGHT - 6)
        boton.setToolTip(tooltip)
        boton.clicked.connect(slot)
        return boton

    def _pintar_swatch(self, boton, rgb):
        color = QtGui.QColor.fromRgbF(*[max(0.0, min(1.0, c)) for c in rgb])
        boton.setStyleSheet(
            "background-color: %s; border: 1px solid %s;"
            % (color.name(), Color.BORDER_STRONG)
        )

    def _medir_tabla(self):
        tabla = self.tabla
        tabla.resizeColumnsToContents()
        # La columna de nombre estira; ON/BG angostas; X/Y/Size con ancho fijo
        # comodo para el drag-slider. Los checkbox necesitan ~34 px (el padding
        # del ::item de Style.TABLE tambien recorta el cell widget).
        header = tabla.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        tabla.setColumnWidth(1, 34)
        tabla.setColumnWidth(2, 34)
        tabla.setColumnWidth(3, 64)
        tabla.setColumnWidth(4, 64)
        tabla.setColumnWidth(5, 64)
        alto = header.sizeHint().height() + tabla.frameWidth() * 2
        alto += Metric.ROW_HEIGHT * tabla.rowCount()
        tabla.setFixedHeight(alto)

    # -- estado --------------------------------------------------------------
    @staticmethod
    def _num(value, default):
        """Coercion tolerante a float: un preset viejo o un BurnIn.json editado
        a mano puede traer '' / null / una lista; ante eso cae al default en vez
        de tirar (que dejaria _loading pegado y freezearia la ventana)."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _cargar_estado(self):
        # try/finally: si load_targets() u otra llamada tira (alcanzable por
        # Refresh sobre la ventana abierta), _loading NO debe quedar en True o
        # todos los setters de escritura quedan mudos sin aviso.
        self._loading = True
        try:
            self.lbl_efecto.setText("Editing: %s" % emphasis(self.ctl.label))
            for key, _label, _custom in FIELDS:
                self.chk_on[key].setChecked(bool(self.ctl.get("bi_%s_on" % key, 0.0)))
                self.chk_bg[key].setChecked(bool(self.ctl.get("bi_%s_bg" % key, 0.0)))
                self.slider_x[key].setValue(
                    self._num(self.ctl.get("bi_%s_x" % key, 0.0), 0.0) * 100.0, emit=False
                )
                self.slider_y[key].setValue(
                    self._num(self.ctl.get("bi_%s_y" % key, 0.0), 0.0) * 100.0, emit=False
                )
                self.slider_size[key].setValue(
                    self._num(self.ctl.get("bi_%s_size" % key, 100.0), 100.0), emit=False
                )
                self._pintar_nombre(key)
            weight = self.ctl.get_weight()
            idx = self.combo_weight.findText(weight)
            if idx >= 0:
                self.combo_weight.setCurrentIndex(idx)
            self.slider_opacity.setValue(
                self._num(self.ctl.get("bi_opacity", 1.0), 1.0), emit=False
            )
            self.slider_bg_opacity.setValue(
                self._num(self.ctl.get("bi_bg_opacity", 0.65), 0.65), emit=False
            )
            self.slider_radius.setValue(
                self._num(self.ctl.get("bi_bg_radius", 30.0), 30.0), emit=False
            )
            self.slider_pad.setValue(
                self._num(self.ctl.get("bi_text_pad", 28.0), 28.0), emit=False
            )
            self._pintar_swatch(self.btn_text_color, self.ctl.get_color("bi_color"))
            self._pintar_swatch(self.btn_bg_color, self.ctl.get_color("bi_bg_color"))
            self._recargar_presets()
            proyecto = self.ctl.project_name or "-"
            self.lbl_proyecto.setText("Project: %s" % emphasis(proyecto))
            res_t, fps_t = self.ctl.load_targets()
            self.edit_res.setText(res_t)
            self.edit_fps.setText(fps_t)
            self._sync_detalle()
        finally:
            self._loading = False

    def _pintar_nombre(self, key):
        """Nombre del campo en rojo si res/fps no coinciden con el objetivo."""
        item = self.name_items.get(key)
        if item is None:
            return
        color = None
        if key in ("res", "fps") and self.ctl.field_ok(key) < 0.5:
            color = Color.ERROR_TEXT
        if color:
            item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
        else:
            item.setForeground(QtGui.QBrush(QtGui.QColor(Color.TEXT)))

    def _selected_keys(self):
        keys = []
        for item in self.tabla.selectedItems():
            if item.column() == 0:
                key = item.data(Qt.UserRole)
                if key:
                    keys.append(key)
        return keys

    def _sync_detalle(self):
        """Refleja la seleccion en el detalle (ancla, rotacion, texto)."""
        keys = self._selected_keys()
        has = bool(keys)
        self.anchor.setEnabled(has)
        self.rotbar.setEnabled(has)
        if keys:
            first = keys[0]
            x = float(self.ctl.get("bi_%s_x" % first, 0.0)) * 100.0
            y = float(self.ctl.get("bi_%s_y" % first, 0.0)) * 100.0
            self.anchor.highlight(x, y)
            self.rotbar.highlight(
                int(round(float(self.ctl.get("bi_%s_rot" % first, 0.0))))
            )
        else:
            self.anchor.highlight(-1, -1)
            self.rotbar.highlight(-1)
        # El texto custom aparece solo con un unico campo custom seleccionado.
        custom_keys = [k for k in keys if k in ("custom1", "custom2")]
        single_custom = custom_keys[0] if len(keys) == 1 and custom_keys else None
        self.lbl_custom.setEnabled(single_custom is not None)
        self.edit_custom.setEnabled(single_custom is not None)
        self._custom_key = single_custom
        old = self._loading
        self._loading = True
        self.edit_custom.setText(
            self.ctl.get_text("bi_%s_text" % single_custom) if single_custom else ""
        )
        self._loading = old

    # -- eventos -------------------------------------------------------------
    def _on_selection(self):
        if self._loading:
            return
        self._sync_detalle()

    def _on_anchor(self, x, y):
        if self._loading:
            return
        for key in self._selected_keys():
            self.ctl.set("bi_%s_x" % key, x / 100.0)
            self.ctl.set("bi_%s_y" % key, y / 100.0)
            self.slider_x[key].setValue(x, emit=False)
            self.slider_y[key].setValue(y, emit=False)
        self.anchor.highlight(x, y)
        self.ctl.nudge_all()

    def _on_rotation(self, deg):
        if self._loading:
            return
        keys = self._selected_keys()
        for key in keys:
            self.ctl.set("bi_%s_rot" % key, float(deg))
        # Escritura directa del literal en los Text2 (el knobChanged tambien
        # lo hace, pero asi funciona aunque el registro cargado sea viejo).
        self.ctl.apply_rotation(fields=tuple(keys) or None)
        self.rotbar.highlight(deg)

    def _on_custom_text(self, text):
        if self._loading or not getattr(self, "_custom_key", None):
            return
        self.ctl.set("bi_%s_text" % self._custom_key, text)
        self.ctl.nudge_all()

    def _on_weight(self, style):
        if self._loading:
            return
        self.ctl.set_weight(style)

    def _on_keep_top(self, checked):
        self._keep_on_top = bool(checked)
        self._apply_on_top()

    def _apply_on_top(self):
        flags = self.windowFlags()
        if self._keep_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if self.isVisible():
            self.show()

    def _all_fields(self, on):
        for key, _label, _custom in FIELDS:
            self.chk_on[key].setChecked(on)

    def _hacer_setter(self, knob):
        def _set(value):
            if self._loading:
                return
            self.ctl.set(knob, float(value))
            self.ctl.nudge_all()

        return _set

    def _hacer_setter_pct(self, knob):
        def _set(value):
            if self._loading:
                return
            self.ctl.set(knob, float(value) / 100.0)
            self.ctl.nudge_all()

        return _set

    def _hacer_setter_bool(self, knob):
        def _set(value):
            if self._loading:
                return
            self.ctl.set(knob, 1.0 if value else 0.0)
            self.ctl.nudge_all()

        return _set

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
        self.ctl.nudge_all()

    def _recargar_presets(self):
        actual = self.combo_presets.currentText()
        self.combo_presets.clear()
        self.combo_presets.addItems(self.ctl.list_presets())
        if actual:
            idx = self.combo_presets.findText(actual)
            if idx >= 0:
                self.combo_presets.setCurrentIndex(idx)

    def _estado_actual(self):
        fields = {}
        for key, _label, _custom in FIELDS:
            fields[key] = {
                "on": self.chk_on[key].isChecked(),
                "bg": self.chk_bg[key].isChecked(),
                "x": round(self.slider_x[key].value() / 100.0, 4),
                "y": round(self.slider_y[key].value() / 100.0, 4),
                "size": round(self.slider_size[key].value(), 2),
                "rot": round(float(self.ctl.get("bi_%s_rot" % key, 0.0)), 2),
            }
        estilo = {
            "weight": self.combo_weight.currentText(),
            "text_color": list(self.ctl.get_color("bi_color")),
            "bg_color": list(self.ctl.get_color("bi_bg_color")),
            "text_opacity": self.slider_opacity.value(),
            "bg_opacity": self.slider_bg_opacity.value(),
            "bg_radius": self.slider_radius.value(),
            "text_pad": self.slider_pad.value(),
        }
        return {"fields": fields, "style": estilo}

    def _guardar_preset(self):
        nombre = self.edit_preset.text().strip()
        error = self.ctl.save_preset(nombre, self._estado_actual())
        if error:
            self._avisar(error, "")
            return
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
        # try/finally + coercion tolerante: un preset de esquema viejo (v1.xx) o
        # un BurnIn.json editado a mano puede traer valores no numericos; sin
        # esto una excepcion dejaba _loading=True pegado y freezeaba la ventana.
        self._loading = True
        try:
            fields = preset.get("fields") or {}
            estilo = preset.get("style") or {}
            for key, _label, _custom in FIELDS:
                data = fields.get(key) or {}
                if "on" in data:
                    self.chk_on[key].setChecked(bool(data["on"]))
                    self.ctl.set("bi_%s_on" % key, 1.0 if data["on"] else 0.0)
                if "bg" in data:
                    self.chk_bg[key].setChecked(bool(data["bg"]))
                    self.ctl.set("bi_%s_bg" % key, 1.0 if data["bg"] else 0.0)
                if "x" in data:
                    x = self._num(data["x"], 0.0)
                    self.slider_x[key].setValue(x * 100.0, emit=False)
                    self.ctl.set("bi_%s_x" % key, x)
                if "y" in data:
                    y = self._num(data["y"], 0.0)
                    self.slider_y[key].setValue(y * 100.0, emit=False)
                    self.ctl.set("bi_%s_y" % key, y)
                if "size" in data:
                    size = self._num(data["size"], 100.0)
                    self.slider_size[key].setValue(size, emit=False)
                    self.ctl.set("bi_%s_size" % key, size)
                if "rot" in data:
                    self.ctl.set("bi_%s_rot" % key, self._num(data["rot"], 0.0))
            if "weight" in estilo:
                idx = self.combo_weight.findText(str(estilo["weight"]))
                if idx >= 0:
                    self.combo_weight.setCurrentIndex(idx)
                self.ctl.set_weight(str(estilo["weight"]))
            if "text_opacity" in estilo:
                v = self._num(estilo["text_opacity"], 1.0)
                self.slider_opacity.setValue(v, emit=False)
                self.ctl.set("bi_opacity", v)
            if "bg_opacity" in estilo:
                v = self._num(estilo["bg_opacity"], 0.65)
                self.slider_bg_opacity.setValue(v, emit=False)
                self.ctl.set("bi_bg_opacity", v)
            if "bg_radius" in estilo:
                v = self._num(estilo["bg_radius"], 30.0)
                self.slider_radius.setValue(v, emit=False)
                self.ctl.set("bi_bg_radius", v)
            if "text_pad" in estilo:
                v = self._num(estilo["text_pad"], 28.0)
                self.slider_pad.setValue(v, emit=False)
                self.ctl.set("bi_text_pad", v)
            if "text_color" in estilo:
                rgb = tuple(estilo["text_color"])[:3]
                self.ctl.set_color("bi_color", rgb)
                self._pintar_swatch(self.btn_text_color, rgb)
            if "bg_color" in estilo:
                rgb = tuple(estilo["bg_color"])[:3]
                self.ctl.set_color("bi_bg_color", rgb)
                self._pintar_swatch(self.btn_bg_color, rgb)
        finally:
            self._loading = False
        self._sync_detalle()
        # El preset puede traer rotaciones: reescribir los literales.
        self.ctl.apply_rotation()
        self.ctl.nudge_all()

    def _guardar_proyecto(self):
        error = self.ctl.save_targets_project(
            self.edit_res.text().strip(), self.edit_fps.text().strip()
        )
        if not error:
            self.ctl.nudge_all()
        self._avisar(
            error,
            "Targets saved to the project (travels in the .hrox). Remember to save the project.",
        )

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
