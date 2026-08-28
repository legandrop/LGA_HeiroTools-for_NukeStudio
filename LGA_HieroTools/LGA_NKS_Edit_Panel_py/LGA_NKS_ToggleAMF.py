"""
____________________________________________________________________

  LGA_NKS_ToggleAMF v1.12 | Lega

  Habilita o deshabilita los soft effects de color que pone Apply AMF
  (OCIOCDLTransform y OCIOFileTransform) que esten bajo el PLAYHEAD, en
  TODOS los tracks de la secuencia.

  Es un TOGGLE del conjunto, no de cada efecto por separado: si queda al
  menos uno habilitado, los apaga todos; si estan todos apagados, los
  enciende. Invertir cada uno dejaria la cadena mezclada -el grade
  prendido y el LMT apagado-, que es lo que no se quiere ver en un plate.

  Como se toca el estado (medido con
  +Building_Blocks/Hiero/Timeline/LGA_H-Explore_ToggleSoftEffect.py):
  `EffectTrackItem.setEnabled()` NO figura en la API documentada de
  Nuke 16 -ni SubTrackItem ni TrackItemBase la listan- pero existe, y es
  la via buena: al llamarla, el knob `disable` del nodo se mueve solo.

  Sobre la velocidad: se recorren los subtracks de cada track y se filtra
  por tiempo con dos comparaciones de int antes de tocar nada mas. La
  clase del nodo -que es lo caro, porque baja al nodo de Nuke- se
  consulta SOLO en los efectos que ya pasaron el filtro de tiempo. En un
  timeline de 40 tracks eso es la diferencia entre mirar todos los
  efectos y mirar los tres que estan abajo del cursor.

  v1.12: Cada corrida escribe su log a logs/DebugPy_LGA_NKS_ToggleAMF.log,
         prendido o no el debug por consola. Sin eso la tool era
         una caja negra cuando no hacia nada.
  v1.11: El debug por consola queda apagado por default.
  v1.10: Pasa a operar sobre el playhead en todos los tracks, en vez de
         sobre los clips seleccionados.
  v1.00: Version inicial.
____________________________________________________________________

"""

import os
import traceback

import hiero.core
import hiero.ui

# ============================
# Configuracion
# ============================

DEBUG = False

# Los mismos tipos que crea LGA_NKS_ApplyAMF. Si alla se suma un efecto
# nuevo a la cadena, hay que sumarlo aca: son las dos puntas de la misma
# herramienta.
EFFECT_TYPES = frozenset(("OCIOCDLTransform", "OCIOFileTransform"))

# La corrida SIEMPRE deja su log, este o no prendido el debug por consola.
LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "DebugPy_LGA_NKS_ToggleAMF.log"
)

_LOG_LINES = []


def debug_print(*message):
    """Acumula para el .log y, si DEBUG, ademas escribe en la consola."""
    linea = " ".join(str(m) for m in message)
    _LOG_LINES.append(linea)
    if DEBUG:
        print(linea)


def _volcar_log():
    """Escribe el log de la corrida, pisando el anterior. Nunca rompe la tool."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass
    del _LOG_LINES[:]


def _safe_name(obj):
    try:
        return obj.name()
    except Exception:
        return repr(obj)


# ============================
# Busqueda por playhead
# ============================


def get_playhead_time():
    """Frame del playhead, o None si no hay viewer activo."""
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            return None
        return viewer.time()
    except Exception as e:
        debug_print("[WARN] No se pudo leer el playhead: %s" % e)
        return None


def find_amf_effects_at_playhead(seq, tiempo):
    """Efectos de Apply AMF bajo el playhead, en todos los tracks.

    El orden de los filtros es a proposito: primero el rango de tiempo,
    que son dos comparaciones de enteros, y recien despues la clase del
    nodo, que obliga a bajar al nodo de Nuke. Al reves se pagaria ese
    costo por cada efecto del timeline y no por los pocos que estan bajo
    el cursor.
    """
    efectos = []
    for track in seq.videoTracks():
        try:
            sub_tracks = track.subTrackItems()
        except Exception:
            continue
        for sub_track in sub_tracks:
            # subTrackItems() devuelve una tupla por subtrack
            items = sub_track if isinstance(sub_track, (list, tuple)) else (sub_track,)
            for item in items:
                try:
                    # 1) el filtro barato primero
                    if not (item.timelineIn() <= tiempo <= item.timelineOut()):
                        continue
                    # 2) recien ahora, lo caro
                    if not isinstance(item, hiero.core.EffectTrackItem):
                        continue
                    node = item.node()
                    if node is not None and node.Class() in EFFECT_TYPES:
                        efectos.append(item)
                except Exception:
                    # un item invalidado no puede frenar el barrido entero
                    continue
    return efectos


# ============================
# Toggle
# ============================


def toggle_effects(efectos):
    """Apaga todos si hay alguno encendido; si no, los enciende."""
    hay_encendido = False
    for effect in efectos:
        try:
            if effect.isEnabled():
                hay_encendido = True
                break
        except Exception:
            continue

    # Con al menos uno encendido, el toggle apaga: unifica hacia abajo.
    objetivo = not hay_encendido

    ok = 0
    for effect in efectos:
        try:
            effect.setEnabled(objetivo)
            ok += 1
        except Exception as e:
            debug_print("    [ERROR] %s: %s" % (_safe_name(effect), e))
            debug_print(traceback.format_exc())

    return ok, objetivo


# ============================
# Entrada
# ============================


def _main_interno():
    debug_print("\n" + "=" * 70)
    debug_print("  LGA_NKS_ToggleAMF - efectos de Apply AMF bajo el playhead")
    debug_print("=" * 70)

    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("[ERROR] No hay secuencia activa.")
        return

    tiempo = get_playhead_time()
    if tiempo is None:
        debug_print("[ERROR] No hay viewer activo: no se puede saber donde esta el playhead.")
        return

    efectos = find_amf_effects_at_playhead(seq, tiempo)
    debug_print("  playhead : frame %s" % tiempo)
    debug_print("  efectos  : %d bajo el playhead" % len(efectos))

    if not efectos:
        mensaje = (
            "No AMF soft effects under the playhead.\n\n"
            "Move the playhead over a shot that already has them (Apply AMF)."
        )
        debug_print("[ERROR] Sin efectos AMF bajo el playhead.")
        try:
            from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

            show_warning(hiero.ui.mainWindow(), "Toggle AMF", mensaje)
        except Exception as e:
            debug_print("[WARN] No se pudo mostrar el cartel: %s" % e)
        return

    project = seq.project()
    if project:
        project.beginUndo("Toggle AMF")
    try:
        ok, objetivo = toggle_effects(efectos)
    finally:
        if project:
            project.endUndo()

    if DEBUG:
        for effect in efectos:
            try:
                debug_print(
                    "    %-20s %-24s isEnabled=%s"
                    % (effect.node().Class(), _safe_name(effect), effect.isEnabled())
                )
            except Exception:
                pass

    debug_print("\n" + "=" * 70)
    debug_print(
        "  RESUMEN: %d de %d efecto(s) %s"
        % (ok, len(efectos), "habilitados" if objetivo else "deshabilitados")
    )
    debug_print("=" * 70 + "\n")


def main():
    """Envoltorio: corra bien o falle, la corrida SIEMPRE deja su log."""
    try:
        _main_interno()
    except Exception:
        debug_print("[ERROR] Excepcion no atrapada:")
        debug_print(traceback.format_exc())
        raise
    finally:
        _volcar_log()


if __name__ == "__main__":
    main()
