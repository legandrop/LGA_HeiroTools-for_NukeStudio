"""
____________________________________________________________________

  LGA_NKS_TaskHistoryBand v1.01 | Lega

  Franja colapsable "Task history" del panel Show Flow Info.
  Port de `FlowNotesPopover::buildAssignmentHistoryBand` (PipeSync).

  Arranca colapsada con chips; click en chevron/titulo expande el grafico
  de nodos. La barra horizontal de chips va AFUERA del scroll (debajo del
  header, indentada bajo los chips).

  Usado por:
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py

  v1.01: Los chips y los nodos llevan la fuente del pack (apply_ui_font);
         sin eso salian con la del host. El elidido del nombre se mide
         despues de aplicarla, no antes.
  v1.00: Version inicial.
____________________________________________________________________

"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Optional

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtGui, QtWidgets
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import apply_ui_font
from LGA_NKS_Shared.LGA_NKS_TaskAssignmentHistory import (
    PersonHistory,
    Span,
    currently_active,
    persons_from_spans,
)

try:
    from LGA_NKS_Shared.LGA_tooltip_helper import set_rich_tooltip
except Exception:  # pragma: no cover - entorno sin helper
    def set_rich_tooltip(widget, html):  # type: ignore
        widget.setToolTip(html.replace("<br>", "\n").replace("<br/>", "\n"))


Qt = QtCore.Qt
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QScrollArea = QtWidgets.QScrollArea
QScrollBar = QtWidgets.QScrollBar
QSizePolicy = QtWidgets.QSizePolicy
QColor = QtGui.QColor
QPainter = QtGui.QPainter
QPen = QtGui.QPen
QBrush = QtGui.QBrush
QFontMetrics = QtGui.QFontMetrics
QTimer = QtCore.QTimer

_MONTHS_SHORT = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


def history_date(dt: Optional[datetime]) -> str:
    """Fecha corta absoluta para la franja (sin frases relativas)."""
    if dt is None:
        return "?"
    day = dt.date() if hasattr(dt, "date") else dt
    base = f"{day.day} {_MONTHS_SHORT[day.month]}"
    if day.year == datetime.now().year:
        return base
    return f"{base} {day.year % 100:02d}"


class TaskHistoryChip(QWidget):
    """Mini chip: borde del color, circulito lleno/hueco + nombre."""

    kHeight = 24
    kDotSize = 8
    kMaxNameWidth = 110

    def __init__(self, name, color, active, parent=None):
        super(TaskHistoryChip, self).__init__(parent)
        self.setObjectName("flowTaskHistoryChip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(self.kHeight)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        color_name = color.name() if hasattr(color, "name") else str(color)
        radius = self.kHeight // 2
        self.setStyleSheet(
            f"QWidget#flowTaskHistoryChip {{"
            f"  background-color: transparent;"
            f"  border: 1px solid {color_name};"
            f"  border-radius: {radius}px;"
            f"}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 0, 8, 0)
        layout.setSpacing(5)

        dot = QLabel(self)
        dot.setObjectName("flowTaskHistoryChipDot")
        dot.setFixedSize(self.kDotSize, self.kDotSize)
        half = self.kDotSize / 2.0
        if active:
            dot.setStyleSheet(
                f"background-color: {color_name}; border: none; border-radius: {half}px;"
            )
        else:
            dot.setStyleSheet(
                f"background-color: transparent; border: 1.5px solid {color_name}; "
                f"border-radius: {half}px;"
            )
        layout.addWidget(dot, 0, Qt.AlignVCenter)

        name_label = QLabel(self)
        name_label.setObjectName("flowTaskHistoryChipName")
        name_label.setStyleSheet(
            f"color: {color_name}; background: transparent; border: none; "
            f"font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(name_label, 0, Qt.AlignVCenter)

        # La fuente del pack va al final, con los hijos ya creados. El elidido
        # se mide DESPUES: con la fuente del host el corte del nombre no
        # coincidia con lo que despues se dibujaba.
        apply_ui_font(self)
        metrics = QFontMetrics(name_label.font())
        name_label.setText(metrics.elidedText(name, Qt.ElideRight, self.kMaxNameWidth))


class TaskHistoryHeaderRow(QWidget):
    """Fila clickeable: chevron + titulo. on_toggle es un callable."""

    def __init__(self, parent=None):
        super(TaskHistoryHeaderRow, self).__init__(parent)
        self.on_toggle = None  # type: Optional[Callable[[], None]]
        self.setObjectName("flowTaskHistoryToggle")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_toggle:
            self.on_toggle()
            event.accept()
            return
        super(TaskHistoryHeaderRow, self).mousePressEvent(event)


class TaskHistoryNode(QWidget):
    """Nodo del grafico expandido: circulito + nombre + rango + dias."""

    kNodeWidth = 134
    kDotSize = 13
    kDotTop = 14
    kMinHeight = 84

    def __init__(
        self,
        name,
        range_text,
        days_text,
        color,
        active,
        draw_line_left,
        draw_line_right,
        parent=None,
    ):
        super(TaskHistoryNode, self).__init__(parent)
        self._color = QColor(color) if not isinstance(color, QColor) else color
        self._active = active
        self._line_left = draw_line_left
        self._line_right = draw_line_right
        self.setObjectName("flowTaskHistoryNode")
        self.setFixedWidth(self.kNodeWidth)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, self.kDotTop + self.kDotSize + 9, 4, 0)
        layout.setSpacing(2)

        name_label = QLabel(self)
        name_label.setObjectName("flowTaskHistoryName")
        name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        name_label.setStyleSheet(f"color: {self._color.name()};")
        name_label.setToolTip(name)
        layout.addWidget(name_label)

        range_label = QLabel(range_text, self)
        range_label.setObjectName("flowTaskHistoryRange")
        range_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.addWidget(range_label)

        days_label = QLabel(days_text, self)
        days_label.setObjectName("flowTaskHistoryDays")
        days_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        days_label.setVisible(bool(days_text))
        layout.addWidget(days_label)
        layout.addStretch()

        if not active:
            range_label.setStyleSheet("color: #5f5f5f;")
            days_label.setStyleSheet("color: #565656;")
            effect = QtWidgets.QGraphicsOpacityEffect(name_label)
            effect.setOpacity(0.62)
            name_label.setGraphicsEffect(effect)

        # Igual que en el chip: primero la fuente del pack sobre los hijos ya
        # creados, y recien despues se mide el elidido del nombre.
        apply_ui_font(self)
        metrics = QFontMetrics(name_label.font())
        name_label.setText(metrics.elidedText(name, Qt.ElideRight, self.kNodeWidth - 10))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center_x = self.width() // 2
        center_y = self.kDotTop + self.kDotSize // 2
        radius = self.kDotSize // 2
        gap = radius + 5

        painter.setPen(QPen(QColor(0x3A, 0x3A, 0x3A), 1))
        if self._line_left:
            painter.drawLine(0, center_y, center_x - gap, center_y)
        if self._line_right:
            painter.drawLine(center_x + gap, center_y, self.width(), center_y)

        painter.setPen(QPen(self._color, 2))
        painter.setBrush(QBrush(self._color) if self._active else Qt.NoBrush)
        painter.drawEllipse(
            center_x - radius + 1,
            center_y - radius + 1,
            self.kDotSize - 2,
            self.kDotSize - 2,
        )


def build_assignment_history_band(spans: List[Span], accent_color_fn, parent=None):
    """Construye la franja Task history. accent_color_fn(name) -> QColor/#hex."""
    if not spans:
        return None

    ordered: List[PersonHistory] = persons_from_spans(spans, history_date)
    if not ordered:
        return None

    band = QWidget(parent)
    band.setObjectName("flowTaskHistory")
    band.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    band_layout = QVBoxLayout(band)
    band_layout.setContentsMargins(16, 12, 8, 12)
    band_layout.setSpacing(6)

    active_count = sum(1 for p in ordered if p.active)

    header = QWidget(band)
    header.setObjectName("flowTaskHistoryHeader")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(10)

    toggle_hit = TaskHistoryHeaderRow(header)
    toggle_layout = QHBoxLayout(toggle_hit)
    toggle_layout.setContentsMargins(0, 0, 0, 0)
    toggle_layout.setSpacing(6)

    chevron = QLabel(toggle_hit)
    chevron.setObjectName("flowTaskHistoryChevron")
    chevron.setFixedSize(12, 12)
    chevron.setAlignment(Qt.AlignCenter)
    chevron.setText("▶")
    chevron.setStyleSheet("color: #8a8a8a; font-size: 9px; background: transparent;")
    chevron.setAttribute(Qt.WA_TransparentForMouseEvents)
    toggle_layout.addWidget(chevron, 0, Qt.AlignVCenter)

    title = QLabel(toggle_hit)
    title.setObjectName("flowTaskHistoryTitle")
    title.setTextFormat(Qt.RichText)
    past_count = len(ordered) - active_count
    title.setText(
        "<span style='color: #d8d8d8; font-weight: 700;'>Task history</span>"
        f"<span style='color: #8a8a8a;'>&nbsp;&nbsp;{active_count} active"
        f"&nbsp;&nbsp;|&nbsp;&nbsp;{past_count} past</span>"
    )
    title.setAttribute(Qt.WA_TransparentForMouseEvents)
    toggle_layout.addWidget(title, 0, Qt.AlignVCenter)

    header_layout.addWidget(toggle_hit, 0, Qt.AlignLeft | Qt.AlignVCenter)

    k_chips_bar_h = 10
    chips_scroll = QScrollArea(header)
    chips_scroll.setObjectName("flowTaskHistoryChipsScroll")
    chips_scroll.setWidgetResizable(True)
    chips_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    chips_scroll.setFixedHeight(TaskHistoryChip.kHeight)
    chips_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    chips_scroll.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    chips_scroll.setAutoFillBackground(False)
    chips_scroll.viewport().setAutoFillBackground(False)

    chips_host = QWidget(chips_scroll)
    chips_host.setObjectName("flowTaskHistoryChips")
    chips_layout = QHBoxLayout(chips_host)
    chips_layout.setContentsMargins(0, 0, 0, 0)
    chips_layout.setSpacing(6)
    chips_layout.addStretch(1)

    for person in ordered:
        color = accent_color_fn(person.name)
        chip = TaskHistoryChip(person.name, color, person.active, chips_host)
        set_rich_tooltip(chip, "Activo" if person.active else "Inactivo")
        chips_layout.addWidget(chip, 0, Qt.AlignVCenter)

    chips_scroll.setWidget(chips_host)
    header_layout.addWidget(chips_scroll, 1, Qt.AlignVCenter)
    band_layout.addWidget(header)

    bar_row = QWidget(band)
    bar_row.setObjectName("flowTaskHistoryChipsBarRow")
    bar_row.setVisible(False)
    bar_row_layout = QHBoxLayout(bar_row)
    bar_row_layout.setContentsMargins(0, 0, 0, 0)
    bar_row_layout.setSpacing(10)

    bar_indent = QWidget(bar_row)
    bar_indent.setFixedHeight(1)
    bar_indent.setFixedWidth(0)
    bar_row_layout.addWidget(bar_indent, 0)

    chips_bar = QScrollBar(Qt.Horizontal, bar_row)
    chips_bar.setObjectName("flowTaskHistoryChipsBar")
    chips_bar.setFixedHeight(k_chips_bar_h)
    bar_row_layout.addWidget(chips_bar, 1)
    band_layout.addWidget(bar_row)

    chips_inner_bar = chips_scroll.horizontalScrollBar()

    def sync_chips_bar():
        collapsed = chips_scroll.isVisible()
        maximum = chips_inner_bar.maximum() if chips_inner_bar else 0
        need_bar = collapsed and maximum > 0
        bar_row.setVisible(need_bar)
        if not need_bar or not chips_inner_bar:
            return
        bar_indent.setFixedWidth(max(0, toggle_hit.width()))
        chips_bar.setRange(chips_inner_bar.minimum(), maximum)
        chips_bar.setPageStep(chips_inner_bar.pageStep())
        chips_bar.setSingleStep(chips_inner_bar.singleStep())
        if chips_bar.value() != chips_inner_bar.value():
            chips_bar.setValue(chips_inner_bar.value())

    chips_inner_bar.rangeChanged.connect(lambda *_: sync_chips_bar())
    chips_inner_bar.valueChanged.connect(
        lambda v: chips_bar.setValue(v) if chips_bar.value() != v else None
    )
    chips_bar.valueChanged.connect(
        lambda v: chips_inner_bar.setValue(v)
        if chips_inner_bar and chips_inner_bar.value() != v
        else None
    )
    QTimer.singleShot(0, sync_chips_bar)

    scroll = QScrollArea(band)
    scroll.setObjectName("flowTaskHistoryScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    scroll.setAutoFillBackground(False)
    scroll.viewport().setAutoFillBackground(False)
    scroll.setVisible(False)

    nodes_host = QWidget(scroll)
    nodes_host.setObjectName("flowTaskHistoryNodes")
    nodes_layout = QHBoxLayout(nodes_host)
    nodes_layout.setContentsMargins(0, 0, 8, 4)
    nodes_layout.setSpacing(0)

    now = datetime.now()
    for i, person in enumerate(ordered):
        unknown = "…"
        if person.active:
            span_start = person.active_since
            span_end = now
            range_text = f"{history_date(person.active_since) if person.active_since else unknown} – Ahora"
        else:
            span_start = person.first_from
            span_end = person.last_to
            frm = history_date(person.first_from) if person.first_from else unknown
            to = history_date(person.last_to) if person.last_to else unknown
            range_text = frm if frm == to else f"{frm} – {to}"

        days_text = ""
        if span_start is not None and span_end is not None:
            whole_days = (span_end.date() - span_start.date()).days
            days_text = "1 día" if whole_days <= 1 else f"{whole_days} días"

        color = accent_color_fn(person.name)
        node = TaskHistoryNode(
            person.name,
            range_text,
            days_text,
            color,
            person.active,
            i > 0,
            i < len(ordered) - 1,
            nodes_host,
        )
        tip = (
            "Asignado a esta task en este momento."
            if person.active
            else "Estuvo asignado a esta task y ya no lo esta."
        )
        if len(person.periods) > 1:
            tip += "\n\nPeriodos:\n  - " + "\n  - ".join(person.periods)
        node.setToolTip(tip)
        nodes_layout.addWidget(node, 0, Qt.AlignTop)

    nodes_layout.addStretch()
    scroll.setWidget(nodes_host)
    # La fuente del pack sobre la franja entera (header, chips y nodos ya
    # existen) y antes de medir el alto del grafico: el sizeHint sale de la
    # metrica de la fuente, y con la del host quedaba calculado sobre otra.
    apply_ui_font(band)
    content_h = max(nodes_host.sizeHint().height(), TaskHistoryNode.kMinHeight)
    scroll.setFixedHeight(content_h + 14)
    band_layout.addWidget(scroll)

    def toggle():
        expanding = not scroll.isVisible()
        scroll.setVisible(expanding)
        chips_scroll.setVisible(not expanding)
        if expanding:
            bar_row.setVisible(False)
        else:
            sync_chips_bar()
        chevron.setText("▼" if expanding else "▶")
        if band.parentWidget() and band.parentWidget().layout():
            band.parentWidget().layout().activate()
        band.updateGeometry()

    toggle_hit.on_toggle = toggle
    return band


def assignee_title_text(spans: List[Span], fallback: str = "") -> str:
    """Texto de assignees activos para el titulo, o fallback si no hay historial."""
    names = currently_active(spans)
    if names:
        return ", ".join(names)
    return (fallback or "").strip()
