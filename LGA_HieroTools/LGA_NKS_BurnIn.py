"""
____________________________________________________________________

  LGA_NKS_BurnIn v1.00 | Lega

  Registra el soft effect LGA_BurnIn en el menu Effects del timeline
  de Hiero/Nuke Studio. El efecto es un gizmo (LGA_NKS_BurnIn_py/
  LGA_BurnIn.gizmo) de solo Text2 que muestra metadata del clip
  visible y pinta en rojo resolucion/fps cuando no coinciden con el
  objetivo del proyecto. La config vive en AppData y el override por
  proyecto en un tag que viaja en el .hrox.

  Mecanismo de registro: QAction con objectName prefijado
  "foundry.timeline.effect." + setData(clase del nodo), via
  hiero.ui.registerAction (patron oficial de custom_soft_effect.py).

  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import sys
import traceback

# Capa intermedia de tooltips (regla del repo: no hardcodear el texto en el
# widget, para que la futura migracion bilingue sea un cambio de datos).
TOOLTIPS = {
    "es": {
        "effect": "Aplica el burn-in de LGA: metadata del clip visible, "
        "con resolucion y fps en rojo si no coinciden con el proyecto",
    },
}


def _tooltip(key, lang="es"):
    return TOOLTIPS.get(lang, {}).get(key, "")


def _register():
    import nuke
    from hiero.ui import registerAction
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui, QAction

    package_dir = os.path.join(os.path.dirname(__file__), "LGA_NKS_BurnIn_py")

    # El paquete entra a sys.path para que las expresiones del gizmo puedan
    # hacer __import__('LGA_NKS_BurnIn_Logic') por nombre pelado, y a los
    # plugin paths de Nuke para que la clase LGA_BurnIn (el .gizmo) exista.
    if package_dir not in sys.path:
        sys.path.insert(0, package_dir)
    nuke.pluginAddPath(package_dir)

    import LGA_NKS_BurnIn_Logic as bi_logic

    action = QAction(QtGui.QIcon("icons:Text.png"), "LGA BurnIn", None)
    action.setObjectName("foundry.timeline.effect.addLGABurnIn")
    action.setToolTip(_tooltip("effect"))
    action.setData("LGA_BurnIn")
    registerAction(action)

    # La config cacheada por proyecto se invalida en los eventos de proyecto:
    # al cargar (los tags ya estan disponibles), al guardar (por si la ventana
    # de settings estampo un override nuevo) y al cerrar.
    from hiero.core import events

    def _on_project_event(event):
        bi_logic.invalidate_cache()

    for event_type in (
        events.EventType.kAfterProjectLoad,
        events.EventType.kAfterProjectSave,
        events.EventType.kAfterProjectClose,
    ):
        events.registerInterest(event_type, _on_project_event)


try:
    _register()
except Exception:
    print("[LGA_NKS_BurnIn] Error registrando el soft effect")
    traceback.print_exc()
