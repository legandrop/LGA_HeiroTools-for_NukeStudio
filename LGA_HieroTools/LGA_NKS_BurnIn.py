"""
____________________________________________________________________

  LGA_NKS_BurnIn v1.04 | Lega

  Registra los soft effects LGA_BurnIn (BlinkScript + Text2, paneles
  redondeados) y LGA_BurnIn_v0 (solo Text2) en el menu Effects del
  timeline de NKS. Muestran metadata del clip visible y pintan en
  rojo resolucion/fps cuando no coinciden con el objetivo del
  proyecto. La config vive en AppData y el override por proyecto en
  un tag que viaja en el .hrox.

  Mecanismo de registro: QAction con objectName prefijado
  "foundry.timeline.effect." + setData(clase del nodo), via
  hiero.ui.registerAction (patron oficial de custom_soft_effect.py).

  v1.04: Refresco del viewer SIN abrir tabs. Tras cualquier cambio de
         un knob bi_* (del panel, de un script o de la UI) se programa
         UN refresh_viewer() diferido (QTimer de 0 ms: una rafaga de
         writes termina en un solo refresh) que descarta los frames
         cacheados del viewer actual (Viewer.flushCache) y le pide que
         se redibuje (hiero.ui.updateViewer). OJO: flushCache ademas
         PAUSA el cacheo (doc de la API), por eso se llama
         resumeCaching() enseguida. El nudge de opacidad sigue como
         respaldo para ensuciar el hash del nodo. Guardia de re-entrada
         en el knobChanged: apply_rotation escribe bi_<f>_ax/ay y el
         nudge escribe bi_opacity, y cada write vuelve a disparar el
         callback. El texto de los custom (bi_<f>_text) tambien
         re-aplica el pivote (cambia el ancho del panel) y los sufijos
         de campo se validan contra FIELDS.
  v1.03: el knobChanged tambien re-aplica la rotacion por campo
         (bi_<f>_rot y todo lo que mueve el pivote: x/y/size, scale,
         text_pad) via apply_rotation() del modulo Blink.
  v1.02: addKnobChanged por nodeClass LGA_BurnIn: al cambiar el peso
         de la fuente (bi_weight) re-aplica apply_font() para que el
         fondo se recalcule con las metricas del nuevo peso de Inter.
  v1.01: Registra LGA_BurnIn (version BlinkScript con paneles
         redondeados) y renombra la version solo-Text2 a LGA_BurnIn_v0.
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
        "effect": "Aplica el burn-in de LGA: metadata del clip visible con "
        "paneles redondeados de fondo; resolucion y fps en rojo si no "
        "coinciden con el proyecto",
        "effect_v0": "Version anterior del burn-in de LGA (solo Text2, "
        "fondos rectangulares nativos)",
    },
}


def _tooltip(key, lang="es"):
    return TOOLTIPS.get(lang, {}).get(key, "")


def _log(message):
    """Log al archivo de la logica (DebugPy_LGA_NKS_BurnIn.log)."""
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic

        bi_logic._log("[Registro] " + message)
    except Exception:
        pass


def _log_once(key, message):
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic

        bi_logic._log_error_once("registro:" + key, message)
    except Exception:
        pass


# ── Refresco del viewer del timeline ─────────────────────────────────────────
#
# Medido en NKS 16: un setValue por API en el gizmo deja al viewer del timeline
# mostrando frames CACHEADOS con el estado anterior; saltar el playhead o
# nuke.clearRAMCache() no alcanzan. La API documentada de hiero.ui trae lo que
# hace falta sin cerrar ni abrir tabs: Viewer.flushCache() ("flush the cache
# on the viewer and pause caching"), Viewer.resumeCaching() y
# hiero.ui.updateViewer(). El detalle de que flushCache PAUSA el cacheo es la
# trampa: sin el resume el viewer deja de cachear para siempre.

# Knobs bi_* que no cambian el render (no disparan refresh).
_KNOBS_SIN_RENDER = ("bi_open_panel",)

_state = {"in_handler": False, "refresh_pending": False}


def refresh_viewer():
    """Fuerza el re-render del frame actual del viewer del timeline sin abrir
    tabs. Devuelve True si pudo flushear el viewer actual. Llamar SIEMPRE desde
    el hilo principal (los metodos del viewer lo exigen)."""
    _state["refresh_pending"] = False
    try:
        import hiero.ui
    except Exception:
        return False
    ok = False
    try:
        viewer = hiero.ui.currentViewer()
        if viewer is not None:
            was_paused = False
            try:
                was_paused = bool(viewer.isCachingPaused())
            except Exception:
                pass
            viewer.flushCache()
            # flushCache pausa el cacheo: se reanuda salvo que YA estuviera
            # pausado por el usuario (se respeta su estado).
            if not was_paused:
                viewer.resumeCaching()
            ok = True
    except Exception as exc:
        _log_once("flush", "viewer.flushCache fallo: {}".format(exc))
    # hiero.ui.updateViewer() pide dos argumentos (medido: "expected 2
    # arguments, got 0"); el flush + el nudge alcanzan para que el viewer
    # vuelva a pedir el frame, asi que no se llama.
    return ok


def schedule_refresh():
    """Programa UN refresh_viewer() para cuando el event loop quede libre: una
    rafaga de writes (el panel escribe varios knobs, apply_rotation escribe
    ax/ay por campo, el nudge escribe dos veces) termina en un solo flush."""
    if _state["refresh_pending"]:
        return
    _state["refresh_pending"] = True
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

        QtCore.QTimer.singleShot(0, refresh_viewer)
    except Exception:
        refresh_viewer()


def _apply_layout_change(gizmo, name):
    """Re-aplica fuente/rotacion segun el knob bi_* que cambio."""
    try:
        import LGA_NKS_BurnIn_Blink as bi_blink
    except Exception:
        return
    if name == "bi_weight":
        # El peso cambia la fuente Y las metricas: re-aplicar ambas y ensuciar
        # el nodo (el bi_font seteado por codigo no siempre invalida solo).
        bi_blink.apply_font(gizmo)
        bi_blink.apply_rotation(gizmo)
        bi_blink.nudge(gizmo)
    elif name.endswith("_rot"):
        # bi_<campo>_rot: reescribir el literal del campo tocado. El write
        # del blob animation_layers no ensucia el nodo solo: nudge.
        field = name[3:-4]
        if field in bi_blink.FIELDS:
            bi_blink.apply_rotation(gizmo, fields=(field,))
            bi_blink.nudge(gizmo)
    elif name.endswith(("_x", "_y", "_size", "_text")):
        # Mover el ancla, el tamano o el texto custom corre el pivote (ancho
        # o centro del panel): re-aplicar el campo (con rot=0 es inocuo).
        field = name[3:].rsplit("_", 1)[0]
        if field in bi_blink.FIELDS:
            bi_blink.apply_rotation(gizmo, fields=(field,))
    elif name in ("bi_scale", "bi_text_pad"):
        # Cambian el alto de TODOS los paneles (y sus centros).
        bi_blink.apply_rotation(gizmo)


def _on_knob_changed():
    """knobChanged de la clase LGA_BurnIn (registrado en _register)."""
    import nuke

    if _state["in_handler"]:
        # Re-entrada: los writes que hace este mismo handler (ax/ay del
        # pivote, el nudge de opacidad) vuelven a disparar el callback.
        return
    n = nuke.thisNode()
    k = nuke.thisKnob()
    if n is None or k is None:
        return
    name = k.name()
    if not name.startswith("bi_") or name in _KNOBS_SIN_RENDER:
        return
    _state["in_handler"] = True
    try:
        _apply_layout_change(n, name)
    except Exception as exc:
        _log("ERROR en knobChanged {}: {}".format(name, exc))
    finally:
        _state["in_handler"] = False
    # Cualquier knob bi_* cambia el render: un solo refresh diferido.
    schedule_refresh()


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

    action_v0 = QAction(QtGui.QIcon("icons:Text.png"), "LGA BurnIn v0", None)
    action_v0.setObjectName("foundry.timeline.effect.addLGABurnInV0")
    action_v0.setToolTip(_tooltip("effect_v0"))
    action_v0.setData("LGA_BurnIn_v0")
    registerAction(action_v0)

    # Un cambio de knob del gizmo (panel, script o UI) re-aplica fuente y
    # rotacion segun corresponda y programa el refresh del viewer.
    nuke.addKnobChanged(_on_knob_changed, nodeClass="LGA_BurnIn")

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
