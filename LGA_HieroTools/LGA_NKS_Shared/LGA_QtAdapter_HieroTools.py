"""
Compatibilidad Qt para Hiero Panels - Nuke 15/16.

Usado por runtime activo:
- LGA_NKS_Assignee_Panel.py
- LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py
- LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py
- LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py
- LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py
- LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign.py
- LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py
- LGA_NKS_ClipColor_Panel.py
- LGA_NKS_Coordination_Panel.py
- LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py
- LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py
- LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py
- LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py
- LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py
- LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py
- LGA_NKS_Edit_Panel.py
- LGA_NKS_Flow_Panel.py
- LGA_NKS_Projects_Panel.py
- LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py
- LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py
- LGA_NKS_Review_Panel.py
- LGA_NKS_Shared/LGA_NKS_Reduce_SeqWin.py
- LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py
- LGA_NKS_ViewerTL_Panel.py
- LGA_NKS_ViewerTL_Panel_py/LGA_NKS_InOut_Editref.py
- LGA_NKS_ViewerTL_Panel_py/LGA_NKS_PrevNext_Rev.py
- LGA_NKS_ViewerTL_Panel_py/LGA_NKS_SnapShot.py
- LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py

Incluye compatibilidad para:
- QShortcut (movido de QtWidgets a QtGui en Qt6)
- horizontal_advance() para métricas de fuente
- primary_screen_geometry() para geometría de pantalla
- set_layout_margin() para márgenes de layout
- svg_pixmap() / svg_icon() para rasterizar y teñir SVGs (QtSvg opcional)
"""

from typing import Optional

try:  # PySide6 primero (Nuke 16)
    from PySide6 import QtWidgets, QtGui, QtCore
    from PySide6.QtGui import QAction, QShortcut, QGuiApplication
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    PYSIDE_VER = 6
except ImportError:  # PySide2 (Nuke 15)
    from PySide2 import QtWidgets, QtGui, QtCore
    from PySide2.QtCore import Qt

    try:
        from PySide2.QtGui import QAction, QShortcut  # Qt5 a veces lo expone aqui
    except ImportError:
        from PySide2.QtWidgets import QAction, QShortcut  # fallback QtWidgets
    from PySide2.QtGui import QGuiApplication
    from PySide2.QtWidgets import QApplication

    PYSIDE_VER = 2


# QtSvg no viene garantizado en todos los builds de Nuke: si falta, los
# helpers de SVG devuelven None y el llamador cae a su alternativa de texto.
try:
    if PYSIDE_VER == 6:
        from PySide6 import QtSvg
    else:
        from PySide2 import QtSvg
except ImportError:
    QtSvg = None


def horizontal_advance(metrics: QtGui.QFontMetrics, text: str) -> int:
    """
    Ancho de texto compatible (Qt6 usa horizontalAdvance).
    """
    if hasattr(metrics, "horizontalAdvance"):
        return metrics.horizontalAdvance(text)
    return metrics.width(text)


def primary_screen_geometry(pos: Optional[QtCore.QPoint] = None) -> QtCore.QRect:
    """
    Geometry del monitor principal o del monitor bajo pos.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        return QtCore.QRect(0, 0, 1920, 1080)

    screen = None
    if pos is not None and hasattr(QGuiApplication, "screenAt"):
        screen = QGuiApplication.screenAt(pos)
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    geo = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)
    return geo


def set_layout_margin(layout: QtWidgets.QLayout, margin: int) -> None:
    """
    Establecer margen de layout compatible Qt5/Qt6.
    En Qt6 usa setContentsMargins, en Qt5 usa setMargin.
    """
    if hasattr(layout, "setContentsMargins"):
        layout.setContentsMargins(margin, margin, margin, margin)
    else:
        layout.setMargin(margin)


def svg_pixmap(svg_path, logical_size=18, color=None, supersampling=3, inset=1):
    """Rasteriza un SVG a QPixmap y opcionalmente lo tiñe con `color`.

    Misma tecnica que PipeSync (VersionsWidget::refreshBranchIcons): se
    rasteriza a `supersampling`x con un inset real para que el antialias no
    toque el borde, se tiñe con SourceIn y se entrega con devicePixelRatio,
    asi el icono no queda ni recortado ni borroso en pantallas HiDPI.

    Devuelve None si QtSvg no esta disponible o el archivo no existe.
    """
    if QtSvg is None:
        return None

    import os

    if not svg_path or not os.path.exists(str(svg_path)):
        return None

    raster_size = int(logical_size) * int(supersampling)
    if raster_size <= 0:
        return None
    raster_inset = float(inset) * float(supersampling)

    image = QtGui.QImage(
        raster_size, raster_size, QtGui.QImage.Format_ARGB32_Premultiplied
    )
    image.fill(Qt.transparent)

    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        renderer = QtSvg.QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return None
        bounds = QtCore.QRectF(
            raster_inset,
            raster_inset,
            raster_size - (2.0 * raster_inset),
            raster_size - (2.0 * raster_inset),
        )
        renderer.render(painter, bounds)
        if color is not None:
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), QtGui.QColor(color))
    finally:
        painter.end()

    pixmap = QtGui.QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(float(supersampling))
    return pixmap


def svg_icon(svg_path, logical_size=18, color=None, supersampling=3, inset=1):
    """QIcon a partir de un SVG teñido. None si no se pudo rasterizar."""
    pixmap = svg_pixmap(
        svg_path,
        logical_size=logical_size,
        color=color,
        supersampling=supersampling,
        inset=inset,
    )
    if pixmap is None:
        return None
    return QtGui.QIcon(pixmap)


__all__ = [
    "QtWidgets",
    "QtGui",
    "QtCore",
    "QtSvg",
    "QAction",
    "QShortcut",
    "QGuiApplication",
    "Qt",
    "QApplication",
    "PYSIDE_VER",
    "horizontal_advance",
    "primary_screen_geometry",
    "set_layout_margin",
    "svg_pixmap",
    "svg_icon",
]
