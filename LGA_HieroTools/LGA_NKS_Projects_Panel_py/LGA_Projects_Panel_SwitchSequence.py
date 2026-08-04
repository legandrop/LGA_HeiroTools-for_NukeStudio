"""
____________________________________________________________________

  LGA_NKS_Projects_Panel_SwitchSequence v2.31 | Lega

  Hiero / Nuke Studio - Switch V3: HÍBRIDO OPTIMIZADO + LIMPIEZA TOTAL + CROSS-PROJECT

  🎯 SOLUCIÓN GANADORA FINAL:
  - Velocidad optimizada + Estado completo del viewer
  - NO crea duplicados + Mantiene viewer settings completos
  - ✅ Playhead: Preservado automáticamente por Hiero
  - ✅ Gain/Gamma/Saturation: Transferidos desde viewer anterior
  - ✅ UI: Redimensiona ventana + Scroll al top track
  - ✅ CIERRE EQUILIBRADO: Cierra viewer + timeline originales (método refresh)
  - ✅ CROSS-PROJECT: Cambia entre proyectos automáticamente

  ✅ CONFIRMADO: Funciona perfectamente - velocidad 0.63s con cierre equilibrado + cross-project.

  INTEGRACIÓN EN PANEL DE PROYECTOS:
  from switch_sequence_v3_final import switch_to_sequence_hybrid

  v2.31: Fix del switch lento: ahora cierra el viewer + timeline viejos ANTES de abrir la secuencia nueva (flag CLOSE_BEFORE_OPEN). Abriendo primero, la destruccion competia con los hilos de IO de la media recien abierta y esperaba entre 3.5s y 13.7s. Cerrando primero, 0.46s. Se captura y restaura el playhead a mano, porque openInTimeline lo preservaba leyendolo del viewer previo.

  v2.30: Diagnostico del cierre lento: _process_events ahora mide por separado sendPostedEvents(DeferredDelete) y processEvents, para saber si los segundos se van en la destruccion real del widget o en lo que esa destruccion desencadena. Agregado flag SWITCH_DIAGNOSTIC_SPLIT_CLOSE (off) para atribuir el costo a viewer o timeline.

  v2.29: Agregado logging diagnostico del cierre real de viewers/timelines: snapshots de widgets, medicion de eventos Qt/DeferredDelete y espera post-switch para detectar donde tarda Hiero.

  v2.28: Fix: el check "Ya activa" ahora compara también el proyecto. Antes, si dos proyectos abiertos tenían una secuencia con el mismo nombre (ej: "101" en PROJALT y en PROJA), el switch hacia el proyecto incorrecto era ignorado porque el nombre coincidía con la secuencia activa de otro proyecto.
  v2.27: Desactiva el Frame Number del ViewerTL al finalizar cada cambio de secuencia
  v2.26: Reinicia el log en cada cambio de timeline e inyecta el logger del Projects Panel en scripts shared
  v2.25: Agregado timeline pre-cleanup sobre la secuencia nueva.
         Elimina tracks NukeVFX y extiende BurnIn antes de los ajustes finales de UI.
  v2.24: Flag opcional para cerrar viewers + timelines viejos (deja solo el nuevo)
  v2.23: Flag opcional para cerrar TODOS los timelines viejos (deja solo el nuevo)
  v2.22: Apertura con duplicado y cierre simultáneo de viewer + timeline originales (método refresh)
  v2.21: Mejorada lógica de versiones: búsqueda en anteúltimo bloque y priorización de sufijos (_Mac)
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import time
import importlib.util
import os
from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging import (
    DEBUG,
    DEBUG_CONSOLE,
    DEBUG_LOG,
    debug_print,
    reset_debug_log,
)

# Si True, cierra TODOS los viewers + timelines viejos y deja solo el nuevo
CLOSE_ALL_TIMELINES = True

# Orden del switch. Con True cierra el viewer + timeline viejos ANTES de abrir
# la secuencia nueva.
#
# Abriendo primero (False, comportamiento histórico), la destrucción del par
# viejo compite con los hilos de IO que están leyendo la media recién abierta y
# se queda esperándolos: entre 3.5s y 13.7s medidos, erráticos y sin relación
# con el tamaño del timeline. Cerrando primero, la misma destrucción cuesta
# 0.46s sobre una secuencia de 129 trackItems.
#
# Se deja el flag para poder volver al orden viejo sin revertir el código.
CLOSE_BEFORE_OPEN = True

# Logging diagnostico post-switch. Mide si Qt/Hiero siguen procesando cierres
# despues de que las llamadas Python ya retornaron.
SWITCH_DIAGNOSTIC_LOG_WIDGETS = True

# Diagnostico: destruye viewer y timeline originales por separado en vez de
# simultaneamente, para saber cual de los dos se come los segundos.
# ROMPE el "cierre equilibrado" que el codigo mantiene a proposito, asi que
# queda apagado por defecto. Prender solo para medir.
SWITCH_DIAGNOSTIC_SPLIT_CLOSE = False

SWITCH_CLEANUP_WAIT_TIMEOUT = 8.0
SWITCH_CLEANUP_WAIT_INTERVAL = 0.10
SWITCH_CLEANUP_LOG_INTERVAL = 0.50

# Qt import (según entorno)
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt


def _process_events(label=None, send_deferred_delete=False):
    """
    Procesa eventos de Qt para estabilidad y devuelve el tiempo consumido.

    Mide por separado las dos fases, que cuestan cosas distintas:
      - sendPostedEvents(DeferredDelete): destruccion REAL de lo agendado con
        deleteLater(). Aca es donde Hiero libera el timeline/viewer viejo.
      - processEvents(): lo que esa destruccion desencadena (repaint, relayout)
        mas la cola normal de eventos.
    Antes se median juntas y no se sabia cual de las dos se comia los segundos.
    """
    deferred_elapsed = 0.0
    events_elapsed = 0.0

    if QtCore:
        try:
            if send_deferred_delete and hasattr(QtCore, "QEvent"):
                deferred_start = time.time()
                QtCore.QCoreApplication.sendPostedEvents(
                    None, QtCore.QEvent.DeferredDelete
                )
                deferred_elapsed = time.time() - deferred_start

            events_start = time.time()
            QtCore.QCoreApplication.processEvents()
            events_elapsed = time.time() - events_start
        except Exception:
            pass

    elapsed = deferred_elapsed + events_elapsed
    if label:
        debug_print(
            f"   [QtEvents] {label}: {elapsed:.3f}s | "
            f"deferredDelete={deferred_elapsed:.3f}s | "
            f"processEvents={events_elapsed:.3f}s"
        )
    return elapsed


def _safe_widget_value(widget, attr_name, default=""):
    try:
        value = getattr(widget, attr_name)
        return value() if callable(value) else value
    except Exception:
        return default


def _snapshot_switch_widgets():
    """Captura estado compacto de viewers y timelines de Hiero."""
    snapshot = {"viewers": [], "timelines": [], "active_sequence": None}
    try:
        active_seq = hiero.ui.activeSequence()
        snapshot["active_sequence"] = active_seq.name() if active_seq else None
    except Exception as e:
        snapshot["active_sequence"] = f"<error:{e}>"

    try:
        app = QtWidgets.QApplication.instance()
        if not app:
            return snapshot

        for widget in app.allWidgets():
            try:
                class_name = (
                    widget.metaObject().className()
                    if hasattr(widget, "metaObject")
                    else str(type(widget))
                )
                is_viewer = "Foundry::Storm::UI::Viewer" in class_name
                is_timeline = "TimelineEditor" in class_name
                if not is_viewer and not is_timeline:
                    continue

                seq_name = None
                if is_timeline:
                    try:
                        seq = widget.sequence() if hasattr(widget, "sequence") else None
                        seq_name = seq.name() if seq else None
                    except Exception as e:
                        seq_name = f"<error:{e}>"

                entry = {
                    "object": _safe_widget_value(widget, "objectName", ""),
                    "title": _safe_widget_value(widget, "windowTitle", ""),
                    "visible": _safe_widget_value(widget, "isVisible", False),
                    "enabled": _safe_widget_value(widget, "isEnabled", False),
                    "class": class_name,
                    "seq": seq_name,
                }
                if is_viewer:
                    snapshot["viewers"].append(entry)
                else:
                    snapshot["timelines"].append(entry)
            except Exception:
                continue
    except Exception as e:
        snapshot["error"] = str(e)

    return snapshot


def _format_widget_entry(entry):
    title = entry.get("title") or "<sin titulo>"
    obj = entry.get("object") or "<sin objectName>"
    visible = "visible" if entry.get("visible") else "hidden"
    enabled = "enabled" if entry.get("enabled") else "disabled"
    seq = entry.get("seq")
    seq_part = f" | seq={seq}" if seq else ""
    return f"{title} | obj={obj} | {visible}/{enabled}{seq_part}"


def _log_widget_snapshot(label, snapshot=None):
    if not SWITCH_DIAGNOSTIC_LOG_WIDGETS:
        return snapshot
    snapshot = snapshot or _snapshot_switch_widgets()
    debug_print(
        f"   [Widgets] {label}: active={snapshot.get('active_sequence')} | "
        f"viewers={len(snapshot.get('viewers', []))} | "
        f"timelines={len(snapshot.get('timelines', []))}"
    )
    for entry in snapshot.get("viewers", []):
        debug_print(f"   [Widgets]   viewer: {_format_widget_entry(entry)}")
    for entry in snapshot.get("timelines", []):
        debug_print(f"   [Widgets]   timeline: {_format_widget_entry(entry)}")
    if snapshot.get("error"):
        debug_print(f"   [Widgets]   error: {snapshot['error']}")
    return snapshot


def _pending_widget_names(widget_names):
    pending = []
    if not widget_names:
        return pending
    target_names = set(name for name in widget_names if name)
    snapshot = _snapshot_switch_widgets()
    for group_name in ("viewers", "timelines"):
        for entry in snapshot.get(group_name, []):
            obj_name = entry.get("object")
            if obj_name in target_names:
                pending.append((group_name[:-1], entry))
    return pending


def _wait_for_scheduled_widget_cleanup(widget_names, timeout, interval, log_interval):
    """
    Espera diagnostica: procesa eventos Qt hasta que desaparezcan los widgets
    agendados con deleteLater(), o hasta timeout.
    """
    target_names = sorted(set(name for name in widget_names if name))
    if not target_names:
        debug_print("   [CleanupWait] Sin widgets agendados para esperar")
        return 0.0, True, []

    debug_print(
        f"   [CleanupWait] Esperando cierre real de {len(target_names)} widgets: {target_names}"
    )
    start = time.time()
    next_log = 0.0
    pending = _pending_widget_names(target_names)

    while pending and (time.time() - start) < timeout:
        elapsed = time.time() - start
        if elapsed >= next_log:
            pending_names = [
                f"{kind}:{entry.get('title') or '<sin titulo>'}|{entry.get('object')}"
                for kind, entry in pending
            ]
            debug_print(
                f"   [CleanupWait] +{elapsed:.2f}s pendientes={len(pending)} {pending_names}"
            )
            next_log = elapsed + log_interval

        _process_events("cleanup wait tick", send_deferred_delete=True)
        if interval > 0:
            time.sleep(min(interval, 0.05))
        pending = _pending_widget_names(target_names)

    elapsed = time.time() - start
    ok = not pending
    if ok:
        debug_print(f"   [CleanupWait] Widgets cerrados realmente en {elapsed:.2f}s")
    else:
        pending_names = [
            f"{kind}:{entry.get('title') or '<sin titulo>'}|{entry.get('object')}"
            for kind, entry in pending
        ]
        debug_print(
            f"   [CleanupWait] TIMEOUT {elapsed:.2f}s | siguen pendientes={pending_names}",
            level="warning",
        )
    return elapsed, ok, pending


def _get_viewer_state(viewer):
    """Captura estado del viewer (gain/gamma/saturation para transferir, sin time)."""
    if not viewer:
        return None
    try:
        return {
            "gain": viewer.gain(),
            "gamma": viewer.gamma(),
            "saturation": viewer.saturation(),
        }
    except Exception:
        return None


def _apply_viewer_settings(viewer, state):
    """Aplica ajustes del viewer (gain/gamma/saturation) - playhead lo maneja Hiero automáticamente."""
    if not viewer or not state:
        return
    try:
        # Aplicamos gain/gamma/saturation - el playhead lo preserva Hiero automáticamente
        if "gain" in state:
            viewer.setGain(state["gain"])
        if "gamma" in state:
            viewer.setGamma(state["gamma"])
        if "saturation" in state:
            viewer.setSaturation(state["saturation"])
    except Exception:
        pass


def _get_available_luts(player):
    """Devuelve lista de LUTs disponibles si el player lo soporta."""
    if not player:
        return None
    try:
        if hasattr(player, "LUTs"):
            luts = player.LUTs()
            if isinstance(luts, (list, tuple, set)):
                return list(luts)
    except Exception:
        return None
    return None


def _apply_rec709_if_available(viewer):
    """
    Aplica LUT ACES/Rec.709 solo si existe.
    Si no se puede verificar disponibilidad, intenta setearlo y valida.
    """
    if not viewer:
        return False
    try:
        player = viewer.player()
        if not player:
            return False

        target_lut = "ACES/Rec.709"
        available_luts = _get_available_luts(player)
        if available_luts is not None and target_lut not in available_luts:
            debug_print(f"   ├── LUT '{target_lut}' no disponible, se mantiene actual")
            return False

        previous_lut = None
        try:
            previous_lut = player.LUT()
        except Exception:
            previous_lut = None

        try:
            player.setLUT(target_lut)
        except Exception as e:
            debug_print(f"   ├── Error al setear LUT '{target_lut}': {e}")
            return False

        try:
            current_lut = player.LUT()
        except Exception:
            current_lut = None

        if current_lut and current_lut != target_lut:
            if previous_lut:
                try:
                    player.setLUT(previous_lut)
                except Exception:
                    pass
            debug_print(
                f"   ├── LUT '{target_lut}' no aplicado (actual: {current_lut})"
            )
            return False

        debug_print(f"   ├── LUT aplicado: {target_lut}")
        return True
    except Exception as e:
        debug_print(f"   ├── Error aplicando LUT Rec.709: {e}")
        return False


def _get_current_playhead():
    """
    Posición actual del playhead, o None si no se puede leer.

    Solo hace falta con CLOSE_BEFORE_OPEN: openInTimeline preservaba el playhead
    leyéndolo del viewer previo, y con el orden nuevo ese viewer ya está cerrado
    cuando se abre la secuencia nueva.
    """
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            return None
        return viewer.time()
    except Exception:
        return None


def _restore_playhead(playhead):
    """Reposiciona el playhead en el viewer nuevo. No falla si no se puede."""
    if playhead is None:
        return False
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            return False

        actual = viewer.time()
        if actual == playhead:
            debug_print(f"   [Playhead] Ya estaba en {playhead}")
            return True

        viewer.setTime(playhead)
        debug_print(f"   [Playhead] Restaurado: {actual} -> {playhead}")
        return True
    except Exception as e:
        debug_print(f"   [Playhead] No se pudo restaurar: {e}")
        return False


def _get_current_viewer_object_name():
    """Obtiene objectName del viewer activo actual."""
    try:
        current_viewer = hiero.ui.currentViewer()
        if not current_viewer:
            return None
        current_window = current_viewer.window()
        if current_window and hasattr(current_window, "objectName"):
            return current_window.objectName()
    except Exception:
        return None
    return None


def _get_current_timeline_object_name():
    """Obtiene objectName del timeline activo actual."""
    try:
        active_seq = hiero.ui.activeSequence()
        if not active_seq:
            return None
        current_timeline = hiero.ui.getTimelineEditor(active_seq)
        if not current_timeline:
            return None
        current_window = current_timeline.window()
        if current_window and hasattr(current_window, "objectName"):
            return current_window.objectName()
    except Exception:
        return None
    return None


def _close_old_viewer_and_timeline_safe(old_viewer_object_name, old_timeline_object_name):
    """
    Cierra viewer + timeline originales de forma SEGURA usando deleteLater().
    Mantiene el equilibrio delicado de Hiero cerrando ambos simultáneamente.
    """
    if not old_viewer_object_name and not old_timeline_object_name:
        return 0, 0, []

    closed_viewers = 0
    closed_timelines = 0
    scheduled_widget_names = []

    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets

        app = QtWidgets.QApplication.instance()
        if not app:
            return 0, 0, []

        widgets_to_close = []

        for widget in app.allWidgets():
            try:
                obj_name = widget.objectName() if hasattr(widget, "objectName") else ""
                if not obj_name:
                    continue

                class_name = (
                    widget.metaObject().className()
                    if hasattr(widget, "metaObject")
                    else ""
                )

                if (
                    old_viewer_object_name
                    and obj_name == old_viewer_object_name
                    and "Foundry::Storm::UI::Viewer" in class_name
                ):
                    widgets_to_close.append(("viewer", widget))

                if (
                    old_timeline_object_name
                    and obj_name == old_timeline_object_name
                    and "TimelineEditor" in class_name
                ):
                    widgets_to_close.append(("timeline", widget))

            except Exception:
                continue

        # Cierre simultáneo para mantener equilibrio
        for widget_type, widget in widgets_to_close:
            try:
                obj_name = widget.objectName() if hasattr(widget, "objectName") else ""
                widget.deleteLater()
                if obj_name:
                    scheduled_widget_names.append(obj_name)
                if widget_type == "viewer":
                    closed_viewers += 1
                elif widget_type == "timeline":
                    closed_timelines += 1
            except Exception:
                continue

            # Modo diagnostico: fuerza la destruccion de cada widget por
            # separado para atribuir el costo a uno u otro.
            if SWITCH_DIAGNOSTIC_SPLIT_CLOSE:
                _process_events(
                    f"close original {widget_type} ({obj_name})",
                    send_deferred_delete=True,
                )

        _process_events("close originals immediate", send_deferred_delete=True)

    except Exception:
        return closed_viewers, closed_timelines, scheduled_widget_names

    return closed_viewers, closed_timelines, scheduled_widget_names


def _close_all_other_viewers_and_timelines_safe(
    current_viewer_object_name, current_timeline_object_name
):
    """
    Cierra TODOS los viewers + timelines viejos dejando solo los actuales.
    Usa deleteLater() para evitar crashes en Hiero 16 y mantener equilibrio delicado.
    """
    if not current_viewer_object_name and not current_timeline_object_name:
        return 0, 0, []

    closed_viewers = 0
    closed_timelines = 0
    scheduled_widget_names = []

    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets

        app = QtWidgets.QApplication.instance()
        if not app:
            return 0, 0, []

        widgets_to_close = []

        for widget in app.allWidgets():
            try:
                obj_name = widget.objectName() if hasattr(widget, "objectName") else ""
                if not obj_name:
                    continue

                class_name = (
                    widget.metaObject().className()
                    if hasattr(widget, "metaObject")
                    else ""
                )

                if "Foundry::Storm::UI::Viewer" in class_name:
                    if "contactsheet" in obj_name.lower():
                        continue
                    if current_viewer_object_name and obj_name != current_viewer_object_name:
                        widgets_to_close.append(("viewer", widget))

                if "TimelineEditor" in class_name:
                    if current_timeline_object_name and obj_name != current_timeline_object_name:
                        widgets_to_close.append(("timeline", widget))

            except Exception:
                continue

        for widget_type, widget in widgets_to_close:
            try:
                obj_name = widget.objectName() if hasattr(widget, "objectName") else ""
                widget.deleteLater()
                if obj_name:
                    scheduled_widget_names.append(obj_name)
                if widget_type == "viewer":
                    closed_viewers += 1
                elif widget_type == "timeline":
                    closed_timelines += 1
            except Exception:
                continue

        _process_events("close all old widgets immediate", send_deferred_delete=True)

    except Exception:
        return closed_viewers, closed_timelines, scheduled_widget_names

    return closed_viewers, closed_timelines, scheduled_widget_names


def _collect_viewers():
    """Devuelve lista de viewers Qt (Foundry::Storm::UI::Viewer) con título y visibilidad."""
    viewers = []
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets

        all_widgets = QtWidgets.QApplication.instance().allWidgets()
        for widget in all_widgets:
            try:
                class_name = (
                    widget.metaObject().className()
                    if hasattr(widget, "metaObject")
                    else str(type(widget))
                )
                if "Foundry::Storm::UI::Viewer" in class_name:
                    title = (
                        widget.windowTitle() if hasattr(widget, "windowTitle") else ""
                    )
                    visible = (
                        widget.isVisible() if hasattr(widget, "isVisible") else False
                    )
                    viewers.append(
                        {"widget": widget, "title": title, "visible": visible}
                    )
            except Exception:
                continue
    except Exception:
        pass
    return viewers


def _pick_target_by_title(items, target_sequence_name):
    """Selecciona un item cuyo título coincida, priorizando los visibles."""
    visible_matches = [
        v for v in items if v.get("title") == target_sequence_name and v.get("visible")
    ]
    if visible_matches:
        return visible_matches[0]
    name_matches = [v for v in items if v.get("title") == target_sequence_name]
    if name_matches:
        return name_matches[0]
    return None


def _pick_target_viewer(viewers, target_sequence_name):
    return _pick_target_by_title(viewers, target_sequence_name)


def _collect_timelines():
    """Devuelve lista de timelines Qt (TimelineEditor) con título, visibilidad y secuencia asociada (si disponible)."""
    timelines = []
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets

        all_widgets = QtWidgets.QApplication.instance().allWidgets()
        for widget in all_widgets:
            try:
                class_name = (
                    widget.metaObject().className()
                    if hasattr(widget, "metaObject")
                    else str(type(widget))
                )
                # Distintos nombres observados para timelines
                if "TimelineEditor" in class_name or "Timeline" in class_name:
                    title = (
                        widget.windowTitle() if hasattr(widget, "windowTitle") else ""
                    )
                    visible = (
                        widget.isVisible() if hasattr(widget, "isVisible") else False
                    )
                    seq_name = None
                    try:
                        seq = widget.sequence() if hasattr(widget, "sequence") else None
                        if seq:
                            seq_name = seq.name()
                    except Exception:
                        seq_name = None
                    timelines.append(
                        {
                            "widget": widget,
                            "title": title,
                            "visible": visible,
                            "seq_name": seq_name,
                        }
                    )
            except Exception:
                continue
    except Exception:
        pass
    return timelines


def _cleanup_viewers_aggressive(target_sequence_name):
    """
    Cierra TODOS los viewers excepto el correspondiente a la secuencia objetivo.
    - Mantiene únicamente el primer viewer con windowTitle == target_sequence_name (el activo).
    - Cierra duplicados y cualquier otro viewer/timeline residual.
    - Loggea estado antes/después para diagnóstico.
    """
    viewers = _collect_viewers()
    closed = []
    kept = []
    target_viewer = _pick_target_viewer(viewers, target_sequence_name)

    for entry in viewers:
        widget = entry["widget"]
        title = entry.get("title", "") or "<sin título>"
        visible = entry.get("visible", False)

        if target_viewer and widget == target_viewer["widget"]:
            kept.append(title)
            continue

        try:
            widget.deleteLater()
            _process_events()
            closed.append(title)
        except Exception:
            continue

    debug_print(
        f"   ├── Viewers antes: {len(viewers)} | cerrados: {len(closed)} | mantenidos: {len(kept)}"
    )
    if kept:
        debug_print(f"   │   Mantenidos: {kept}")
    if closed:
        debug_print(f"   │   Cerrados: {closed}")

    return len(closed), len(kept), kept, closed


def _cleanup_timelines_aggressive(target_sequence_name, target_seq_obj=None):
    """
    Cierra timelines (TimelineEditor) que no correspondan a la secuencia objetivo.
    Mantiene los timelines cuya secuencia asociada o título coincida con la secuencia objetivo.
    No cierra timelines de secuencia desconocida (para evitar dejar la UI sin timeline si no podemos determinar).
    """
    timelines = _collect_timelines()
    target_timeline = _pick_target_by_title(timelines, target_sequence_name)
    closed = []
    kept = []
    skipped = []

    for entry in timelines:
        widget = entry["widget"]
        title = entry.get("title", "") or "<sin título>"
        seq_name = entry.get("seq_name")

        # Mantener timelines que correspondan a la secuencia objetivo (por nombre de secuencia o por título)
        if (target_timeline and widget == target_timeline["widget"]) or (
            seq_name == target_sequence_name
        ):
            kept.append(title)
            continue

        # Si no podemos determinar la secuencia, no lo cerramos para no dejar la UI en gris
        if seq_name is None:
            skipped.append(title)
            continue

        try:
            widget.deleteLater()
            _process_events()
            closed.append(title)
        except Exception:
            continue

    debug_print(
        f"   ├── Timelines antes: {len(timelines)} | cerrados: {len(closed)} | mantenidos: {len(kept)} | omitidos (desconocidos): {len(skipped)}"
    )
    if kept:
        debug_print(f"   │   Timelines mantenidos: {kept}")
    if closed:
        debug_print(f"   │   Timelines cerrados: {closed}")
    if skipped:
        debug_print(f"   │   Timelines omitidos (seq desconocida): {skipped}")

    return len(closed), len(kept), kept, closed, skipped


def _focus_target_viewer(target_sequence_name):
    """Intenta enfocar el viewer de la secuencia objetivo después de la limpieza."""
    viewers = _collect_viewers()
    target = _pick_target_viewer(viewers, target_sequence_name)
    if not target:
        debug_print(
            f"   ├── No se encontró viewer para '{target_sequence_name}' tras limpieza"
        )
        return
    widget = target["widget"]
    try:
        widget.show()
        widget.raise_()
        widget.activateWindow()
        _process_events()
        debug_print(f"   ├── Viewer enfocado: {target_sequence_name}")
    except Exception:
        debug_print(f"   ├── No se pudo enfocar viewer '{target_sequence_name}'")


def import_script(script_name):
    """Importa script shared usado por Switch Sequence."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(base_dir, "LGA_NKS_Shared", script_name + ".py")

    if os.path.exists(script_path):
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "set_debug_handler"):
            module.set_debug_handler(debug_print)
        elif hasattr(module, "debug_print"):
            module.debug_print = debug_print
        if hasattr(module, "DEBUG"):
            module.DEBUG = DEBUG
        return module
    return None


def reduce_sequence_window(timeline_editor=None):
    """Reduce panel izquierdo del timeline."""
    try:
        reduce_module = import_script("LGA_NKS_Reduce_SeqWin")
        if reduce_module:
            reduce_module.main(timeline_editor)
            return True
    except Exception:
        pass
    return False


def scroll_to_top_track(timeline_editor=None):
    """Hace scroll al track superior."""
    try:
        scroll_module = import_script("LGA_NKS_ScrollTo_TopTrack")
        if scroll_module:
            scroll_module.main(timeline_editor)
            return True
    except Exception:
        pass
    return False


def disable_frame_number_on_active_sequence():
    """
    Deshabilita el soft effect Frame_Only del track BurnIn en la secuencia activa.
    No crea ni reposiciona el efecto; solo fuerza el overlay de frame a estado off.
    """
    try:
        seq = hiero.ui.activeSequence()
    except Exception as e:
        debug_print(f"   Frame Number off: no se pudo obtener secuencia activa: {e}")
        return False

    if not seq:
        debug_print("   Frame Number off: no hay secuencia activa")
        return False

    try:
        from LGA_NKS_ViewerTL_Panel_py.LGA_NKS_FrameNumber import (
            find_frame_only_effect,
        )
    except Exception as e:
        debug_print(f"   Frame Number off: no se pudo importar helper: {e}")
        return False

    target_track = None
    try:
        for track in seq.videoTracks():
            if track.name() == "BurnIn":
                target_track = track
                break
    except Exception as e:
        debug_print(f"   Frame Number off: error leyendo tracks: {e}")
        return False

    if not target_track:
        debug_print("   Frame Number off: track BurnIn no encontrado")
        return False

    try:
        frame_effect = find_frame_only_effect(target_track, "Frame_Only")
    except Exception as e:
        debug_print(f"   Frame Number off: error buscando Frame_Only: {e}")
        return False

    if not frame_effect:
        debug_print("   Frame Number off: efecto Frame_Only no encontrado")
        return False

    try:
        is_enabled = (
            frame_effect.isEnabled() if hasattr(frame_effect, "isEnabled") else True
        )
    except Exception:
        is_enabled = True

    if not is_enabled:
        debug_print("   Frame Number off: ya estaba desactivado")
        return True

    try:
        if hasattr(frame_effect, "setEnabled"):
            frame_effect.setEnabled(False)
            debug_print("   Frame Number off: Frame_Only desactivado")
            return True
    except Exception as e:
        debug_print(f"   Frame Number off: error desactivando Frame_Only: {e}")
        return False

    debug_print("   Frame Number off: Frame_Only no soporta setEnabled")
    return False


def switch_to_sequence_hybrid(target_sequence_name, target_project=None):
    """
    Switch HÍBRIDO V3 PERFECTO: Mejor que v4 + LIMPIEZA TOTAL + CROSS-PROJECT
    - Velocidad del v2 + Estado completo del v1
    - Sin duplicados + Mantiene viewer settings completos
    - ✅ Playhead: Preservado automáticamente por Hiero
    - ✅ Gain/Gamma/Saturation: Transferidos desde viewer anterior
    - ✅ UI: Redimensiona ventana + Scroll al top track
    - ✅ CIERRE EQUILIBRADO: Cierra viewer + timeline originales (método refresh)
    - ✅ OPCIONAL: Cierra TODOS los timelines viejos (flag CLOSE_ALL_TIMELINES)
    - ✅ CROSS-PROJECT: Cambia entre proyectos automáticamente
    """
    reset_debug_log()
    total_start = time.time()
    _log_widget_snapshot("inicio switch")
    debug_print(f"🔄 Switch híbrido a '{target_sequence_name}'...")

    # 1. Verificar proyectos
    projects = hiero.core.projects()
    if not projects:
        debug_print("❌ Error: No hay proyectos abiertos")
        return False

    # 2. Buscar la secuencia en el proyecto especificado o en todos los proyectos
    target_seq = None

    if target_project:
        # Buscar en el proyecto específico
        try:
            sequences = target_project.sequences()
            for seq in sequences:
                try:
                    if seq.name() == target_sequence_name:
                        target_seq = seq
                        debug_print(
                            f"   ├── Secuencia encontrada en proyecto: {target_project.name()}"
                        )
                        break
                except Exception:
                    continue
        except Exception:
            pass
    else:
        # Búsqueda legacy: buscar en todos los proyectos disponibles
        for proj in projects:
            try:
                sequences = proj.sequences()
                for seq in sequences:
                    try:
                        if seq.name() == target_sequence_name:
                            target_seq = seq
                            if proj != projects[0]:
                                debug_print(
                                    f"   ├── Secuencia encontrada en proyecto: {proj.name()}"
                                )
                            break
                    except Exception:
                        continue
                if target_seq:
                    break
            except Exception:
                continue

    if not target_seq:
        debug_print(f"❌ Error: Secuencia '{target_sequence_name}' no encontrada")
        return False

    # 2. Verificar si ya estamos en la secuencia (OPTIMIZACIÓN)
    active_seq = None
    try:
        active_seq = hiero.ui.activeSequence()
    except Exception:
        active_seq = None

    if active_seq and active_seq.name() == target_sequence_name:
        # Si hay un proyecto objetivo, verificar que la secuencia activa pertenece al mismo proyecto.
        # Dos proyectos distintos pueden tener secuencias con el mismo nombre (ej: "101" en PROJALT y en PROJA).
        if target_project is not None:
            try:
                active_project = active_seq.project()
                if active_project != target_project:
                    debug_print(
                        f"   ├── '{target_sequence_name}' activa pero en otro proyecto "
                        f"({active_project.name()} ≠ {target_project.name()}), continuando switch..."
                    )
                    # No retornar: el switch debe seguir adelante hacia el proyecto correcto
                else:
                    debug_print("✅ Ya activa - sin cambios")
                    return True
            except Exception as _e:
                debug_print(f"   ├── No se pudo comparar proyectos ({_e}), continuando switch...")
                # En caso de error comparando, procedemos con el switch para no quedar bloqueados
        else:
            debug_print("✅ Ya activa - sin cambios")
            return True

    # 3. Capturar ajustes del viewer ACTUAL (gain/gamma para transferir)
    step_start = time.time()
    current_viewer = hiero.ui.currentViewer()
    viewer_state = _get_viewer_state(current_viewer) if current_viewer else None
    viewer_capture_time = time.time() - step_start

    # 4. Capturar viewer + timeline actuales ANTES de duplicar (método refresh)
    old_viewer_object_name = _get_current_viewer_object_name()
    old_timeline_object_name = _get_current_timeline_object_name()
    debug_print(
        f"   [Targets] Original viewer={old_viewer_object_name} | "
        f"timeline={old_timeline_object_name}"
    )

    # 5 y 6. Abrir la nueva y cerrar la vieja.
    #
    # El ORDEN es lo que decide la velocidad del switch. Abriendo primero, la
    # destruccion del par viejo tiene que sincronizarse con los hilos de IO que
    # estan leyendo la media recien abierta, y se queda esperandolos: medido
    # entre 3.5s y 13.7s, sin relacion con el tamano del timeline. Cerrando
    # primero no hay con que competir: 0.46s sobre una secuencia de 129 items.
    #
    # El playhead se captura y se restaura a mano porque openInTimeline lo
    # preservaba leyendolo del viewer previo, que con este orden ya no existe.

    def _abrir_secuencia_nueva():
        """Abre la secuencia objetivo y verifica que el cambio ocurrio."""
        debug_print("   [Stage] openInTimeline: inicio")
        hiero.ui.openInTimeline(target_seq)
        _process_events("despues de openInTimeline")

        activa = hiero.ui.activeSequence()
        if not (activa and activa.name() == target_sequence_name):
            debug_print("❌ Error: Secuencia no cambió correctamente")
            return None
        return activa

    def _cerrar_par_original():
        """Cierra viewer + timeline originales. Devuelve (viewers, timelines, agendados)."""
        try:
            cerrados_v, cerrados_t, agendados = _close_old_viewer_and_timeline_safe(
                old_viewer_object_name, old_timeline_object_name
            )
            debug_print(f"   [DeleteLater] Originales agendados: {agendados}")
            debug_print(
                f"   ├── Cerrados originales: viewers={cerrados_v}, timelines={cerrados_t}"
            )
            return cerrados_v, cerrados_t, agendados
        except Exception as e:
            debug_print(f"   ├── Error cerrando viewer/timeline originales: {e}")
            return 0, 0, []

    new_active = None
    open_time = 0
    close_time = 0

    if CLOSE_BEFORE_OPEN:
        # Playhead del viewer viejo, antes de destruirlo
        playhead_original = _get_current_playhead()
        debug_print(f"   [Playhead] Original: {playhead_original}")

        step_start = time.time()
        closed_viewers, closed_timelines, scheduled_original_names = (
            _cerrar_par_original()
        )
        close_time = time.time() - step_start
        _log_widget_snapshot("despues deleteLater originales (pre-apertura)")

        step_start = time.time()
        try:
            new_active = _abrir_secuencia_nueva()
            if new_active is None:
                return False
        except Exception as e:
            debug_print(f"❌ Error abriendo secuencia: {e}")
            return False
        open_time = time.time() - step_start
        _log_widget_snapshot("despues openInTimeline")

        # Restaurar el playhead: sin viewer previo, Hiero no tiene de donde sacarlo
        _restore_playhead(playhead_original)
    else:
        # Orden histórico: abrir y después cerrar. Mucho más lento, se conserva
        # solo para poder volver atrás si el orden nuevo diera problemas.
        step_start = time.time()
        try:
            new_active = _abrir_secuencia_nueva()
            if new_active is None:
                return False
        except Exception as e:
            debug_print(f"❌ Error abriendo secuencia: {e}")
            return False
        open_time = time.time() - step_start
        _log_widget_snapshot("despues openInTimeline")

        step_start = time.time()
        closed_viewers, closed_timelines, scheduled_original_names = (
            _cerrar_par_original()
        )
        close_time = time.time() - step_start
        _log_widget_snapshot("despues deleteLater originales")

    new_timeline = hiero.ui.getTimelineEditor(new_active) if new_active else None

    # 7. Ejecutar pre-cleanup sobre la secuencia nueva antes de ajustes finales de UI
    step_start = time.time()
    try:
        precleanup_module = import_script("LGA_NKS_Timeline_PreCleanup")
        if precleanup_module:
            debug_print("   [Stage] Timeline pre-cleanup: inicio")
            precleanup_result = precleanup_module.main()
            debug_print(f"   ├── Timeline pre-cleanup: {precleanup_result}")
        else:
            debug_print("   ├── No se pudo importar LGA_NKS_Timeline_PreCleanup")
    except Exception as e:
        debug_print(f"   ├── Error ejecutando timeline pre-cleanup: {e}")
    precleanup_time = time.time() - step_start

    # 8. Aplicar ajustes del viewer anterior (gain/gamma) - playhead ya está correcto
    viewer_restore_time = 0
    if viewer_state:
        step_start = time.time()
        new_viewer = hiero.ui.currentViewer()
        if new_viewer:
            _apply_viewer_settings(new_viewer, viewer_state)
        viewer_restore_time = time.time() - step_start

    # 9. Enfocar viewer objetivo tras cierre (para evitar pantallas grises)
    debug_print("   [Stage] Focus target viewer: inicio")
    _focus_target_viewer(target_sequence_name)
    _log_widget_snapshot("despues focus target viewer")

    # 10. Redimensionar ventana del timeline (como v4)
    step_start = time.time()
    debug_print("   [Stage] UI reduce: inicio")
    reduce_success = reduce_sequence_window(new_timeline)
    reduce_time = time.time() - step_start
    debug_print(f"   [Stage] UI reduce: fin | ok={reduce_success} | {reduce_time:.3f}s")

    # 11. Scrollear al top track (como v4)
    step_start = time.time()
    debug_print("   [Stage] UI scroll: inicio")
    scroll_success = scroll_to_top_track(new_timeline)
    scroll_time = time.time() - step_start
    debug_print(f"   [Stage] UI scroll: fin | ok={scroll_success} | {scroll_time:.3f}s")

    # 12. Cerrar TODOS los viewers + timelines viejos si el flag está activo
    close_all_widgets_time = 0
    scheduled_extra_names = []
    if CLOSE_ALL_TIMELINES:
        step_start = time.time()
        current_viewer_object_name = _get_current_viewer_object_name()
        current_timeline_object_name = _get_current_timeline_object_name()
        debug_print(
            f"   [Targets] Current keep viewer={current_viewer_object_name} | "
            f"timeline={current_timeline_object_name}"
        )
        closed_extra_viewers, closed_extra_timelines, scheduled_extra_names = (
            _close_all_other_viewers_and_timelines_safe(
                current_viewer_object_name, current_timeline_object_name
            )
        )
        debug_print(f"   [DeleteLater] Extras agendados: {scheduled_extra_names}")
        close_all_widgets_time = time.time() - step_start
        debug_print(
            f"   ├── Close ALL old viewers: {closed_extra_viewers} cerrados"
        )
        debug_print(
            f"   ├── Close ALL old timelines: {closed_extra_timelines} cerrados"
        )

        _log_widget_snapshot("despues deleteLater close all")

    # 13. Aplicar LUT Rec.709 si existe (evita reset a sRGB)
    rec709_time = 0
    rec709_applied = False
    step_start = time.time()
    try:
        rec709_applied = _apply_rec709_if_available(hiero.ui.currentViewer())
    except Exception as e:
        debug_print(f"   ├── Error aplicando LUT Rec.709: {e}")
    rec709_time = time.time() - step_start

    # 14. Forzar Frame Number apagado tras el cambio de secuencia
    frame_number_off_time = 0
    frame_number_off_result = False
    step_start = time.time()
    try:
        frame_number_off_result = disable_frame_number_on_active_sequence()
    except Exception as e:
        debug_print(f"   Frame Number off: error inesperado: {e}")
    frame_number_off_time = time.time() - step_start

    # 15. Espera diagnostica post-event-loop: confirma cierre real de widgets
    cleanup_wait_time, cleanup_wait_ok, cleanup_pending = (
        _wait_for_scheduled_widget_cleanup(
            scheduled_original_names + scheduled_extra_names,
            SWITCH_CLEANUP_WAIT_TIMEOUT,
            SWITCH_CLEANUP_WAIT_INTERVAL,
            SWITCH_CLEANUP_LOG_INTERVAL,
        )
    )
    _log_widget_snapshot("final post cleanup wait")

    # 16. Resultado final
    total_time = time.time() - total_start
    debug_print(f"✅ Switch híbrido perfecto completado en {total_time:.2f}s")
    debug_print(f"   ├── Viewer capture: {viewer_capture_time:.3f}s")
    debug_print(f"   ├── Sequence open: {open_time:.3f}s")
    debug_print(
        f"   ├── Close originals (viewer+timeline): {close_time:.3f}s"
        f" | orden={'cierre primero' if CLOSE_BEFORE_OPEN else 'apertura primero'}"
    )
    debug_print(f"   ├── Timeline pre-cleanup: {precleanup_time:.3f}s")
    debug_print(f"   ├── Viewer settings apply: {viewer_restore_time:.3f}s")
    debug_print(f"   ├── UI reduce: {reduce_time:.3f}s")
    debug_print(f"   ├── UI scroll: {scroll_time:.3f}s")
    debug_print(
        f"   ├── Rec.709 apply: {rec709_time:.3f}s | applied={rec709_applied}"
    )
    debug_print(
        f"   Frame Number off: {frame_number_off_time:.3f}s | result={frame_number_off_result}"
    )
    if CLOSE_ALL_TIMELINES:
        debug_print(
            f"   ├── Close ALL old viewers+timelines: {close_all_widgets_time:.3f}s"
        )
    debug_print(f"   └── Total: {total_time:.2f}s")

    debug_print(
        f"   [Summary] Post-event cleanup wait: {cleanup_wait_time:.3f}s | "
        f"ok={cleanup_wait_ok} | pending={len(cleanup_pending)}"
    )

    return True
