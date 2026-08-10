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


__all__ = [
    "QtWidgets",
    "QtGui",
    "QtCore",
    "QAction",
    "QShortcut",
    "QGuiApplication",
    "Qt",
    "QApplication",
    "PYSIDE_VER",
    "horizontal_advance",
    "primary_screen_geometry",
    "set_layout_margin",
]
