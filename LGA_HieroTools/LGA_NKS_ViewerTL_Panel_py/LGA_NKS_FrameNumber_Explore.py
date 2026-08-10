"""
____________________________________________________________________

  LGA_NKS_FrameNumber_Explore v1.00 | Lega

  Script de exploración para capturar todas las propiedades
  del soft effect 'Frame_Only' en el track 'BurnIn'

  Este script captura:
  - Propiedades del EffectTrackItem (timeline, enabled, etc.)
  - Todas las propiedades del nodo (knobs y valores)
  - Información de duración y posición en el timeline
  - Cualquier otra propiedad relevante para recrear el efecto
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import json

# ============================
# Configuración
# ============================

TRACK_NAME = "BurnIn"
CLIP_NAME = "Frame_Only"
DEBUG = False

# ============================
# Funciones Auxiliares
# ============================


def debug_print(*message):
    if DEBUG:
        print(*message)


def safe_get_value(obj, attr, default=None):
    """Obtiene un valor de forma segura, retornando default si falla."""
    try:
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if callable(value):
                return value()
            return value
        return default
    except Exception as e:
        debug_print(f"⚠️ Error obteniendo {attr}: {e}")
        return default


def get_knob_info(node, knob_name):
    """Obtiene información detallada de un knob."""
    try:
        knob = node[knob_name]
        value = knob.value()

        knob_info = {
            "name": knob_name,
            "value": value,
            "value_type": str(type(value).__name__),
            "class_name": (
                knob.__class__.__name__ if hasattr(knob, "__class__") else "Unknown"
            ),
        }

        # Intentar obtener información adicional del knob
        try:
            if hasattr(knob, "label"):
                knob_info["label"] = knob.label()
        except:
            pass

        try:
            if hasattr(knob, "tooltip"):
                knob_info["tooltip"] = knob.tooltip()
        except:
            pass

        try:
            if hasattr(knob, "visible"):
                knob_info["visible"] = knob.visible()
        except:
            pass

        try:
            if hasattr(knob, "enabled"):
                knob_info["enabled"] = knob.enabled()
        except:
            pass

        # Para valores complejos, intentar serializar
        try:
            if isinstance(value, (list, tuple)):
                knob_info["value_serialized"] = list(value)
            elif isinstance(value, dict):
                knob_info["value_serialized"] = dict(value)
            else:
                knob_info["value_serialized"] = str(value)
        except:
            knob_info["value_serialized"] = str(value)

        return knob_info
    except Exception as e:
        return {"name": knob_name, "error": str(e)}


# ============================
# Función Principal
# ============================


def explore_frame_only_effect():
    """
    Explora y captura todas las propiedades del soft effect 'Frame_Only'.
    """
    debug_print("=" * 80)
    debug_print("🔍 EXPLORACIÓN DEL SOFT EFFECT 'Frame_Only'")
    debug_print("=" * 80)

    # Obtener la secuencia activa
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("❌ No se encontró una secuencia activa.")
        return None

    # Buscar el track especificado
    target_track = None
    for track in seq.videoTracks():
        if track.name() == TRACK_NAME:
            target_track = track
            break

    if not target_track:
        debug_print(f"❌ No se encontró el track '{TRACK_NAME}'.")
        return None

    # Buscar el soft effect 'Frame_Only'
    target_effect = None

    # Usar subTrackItems() para acceder a los soft effects
    items = target_track.subTrackItems()
    if not items:
        debug_print(f"❌ El track '{TRACK_NAME}' no tiene items.")
        return None

    # Buscar en los soft effects del track
    for item in items:
        effect_item = item[0]
        if isinstance(effect_item, hiero.core.EffectTrackItem):
            if effect_item.name() == CLIP_NAME:
                target_effect = effect_item
                break

    if not target_effect:
        debug_print(
            f"❌ No se encontró el soft effect '{CLIP_NAME}' en el track '{TRACK_NAME}'."
        )
        debug_print(f"\nSoft effects encontrados en el track:")
        for item in items:
            effect_item = item[0]
            if isinstance(effect_item, hiero.core.EffectTrackItem):
                debug_print(f"  - Soft Effect: {effect_item.name()}")
        return None

    debug_print(f"\n✅ Soft effect '{CLIP_NAME}' encontrado!")
    debug_print("=" * 80)

    # ============================
    # Capturar propiedades del EffectTrackItem
    # ============================
    debug_print("\n📋 PROPIEDADES DEL EffectTrackItem:")
    debug_print("-" * 80)

    effect_properties = {}

    # Propiedades básicas
    effect_properties["name"] = safe_get_value(target_effect, "name", "Unknown")
    debug_print(f"  Nombre: {effect_properties['name']}")

    effect_properties["enabled"] = safe_get_value(target_effect, "isEnabled", True)
    debug_print(f"  Enabled: {effect_properties['enabled']}")

    effect_properties["timeline_in"] = safe_get_value(target_effect, "timelineIn", None)
    debug_print(f"  Timeline In: {effect_properties['timeline_in']}")

    effect_properties["timeline_out"] = safe_get_value(
        target_effect, "timelineOut", None
    )
    debug_print(f"  Timeline Out: {effect_properties['timeline_out']}")

    if (
        effect_properties["timeline_in"] is not None
        and effect_properties["timeline_out"] is not None
    ):
        effect_properties["duration"] = (
            effect_properties["timeline_out"] - effect_properties["timeline_in"]
        )
        debug_print(f"  Duración: {effect_properties['duration']} frames")

    # Propiedades adicionales del EffectTrackItem
    try:
        effect_properties["source_in"] = target_effect.sourceIn()
        debug_print(f"  Source In: {effect_properties['source_in']}")
    except:
        pass

    try:
        effect_properties["source_out"] = target_effect.sourceOut()
        debug_print(f"  Source Out: {effect_properties['source_out']}")
    except:
        pass

    try:
        effect_properties["track_name"] = (
            target_effect.parentTrack().name() if target_effect.parentTrack() else None
        )
        debug_print(f"  Track: {effect_properties['track_name']}")
    except:
        pass

    try:
        effect_properties["has_error"] = target_effect.nodeHasError()
        debug_print(f"  Tiene error: {effect_properties['has_error']}")
    except:
        pass

    try:
        effect_properties["to_string"] = target_effect.toString()
        debug_print(f"  toString(): {effect_properties['to_string']}")
    except:
        pass

    # ============================
    # Capturar propiedades del nodo
    # ============================
    debug_print("\n📋 PROPIEDADES DEL NODO:")
    debug_print("-" * 80)

    node = None
    try:
        node = target_effect.node()
    except Exception as e:
        debug_print(f"❌ Error obteniendo el nodo: {e}")
        return effect_properties

    if not node:
        debug_print("❌ No se pudo obtener el nodo asociado al effect.")
        return effect_properties

    node_properties = {}

    # Información básica del nodo
    try:
        node_properties["node_name"] = node.name()
        debug_print(f"  Nombre del nodo: {node_properties['node_name']}")
    except:
        pass

    try:
        node_properties["node_class"] = node.Class()
        debug_print(f"  Clase del nodo: {node_properties['node_class']}")
    except:
        pass

    # Obtener todos los knobs
    debug_print(f"\n📦 KNOBS DEL NODO (Total: {len(node.knobs())}):")
    debug_print("-" * 80)

    knobs_info = {}
    for knob_name in node.knobs():
        knob_info = get_knob_info(node, knob_name)
        knobs_info[knob_name] = knob_info

        # Imprimir información del knob
        debug_print(f"\n  🔹 {knob_name}:")
        debug_print(f"     Valor: {knob_info.get('value', 'N/A')}")
        debug_print(f"     Tipo: {knob_info.get('value_type', 'N/A')}")
        debug_print(f"     Clase: {knob_info.get('class_name', 'N/A')}")

        if "label" in knob_info:
            debug_print(f"     Label: {knob_info['label']}")
        if "tooltip" in knob_info:
            debug_print(f"     Tooltip: {knob_info['tooltip']}")
        if "visible" in knob_info:
            debug_print(f"     Visible: {knob_info['visible']}")
        if "enabled" in knob_info:
            debug_print(f"     Enabled: {knob_info['enabled']}")

    node_properties["knobs"] = knobs_info

    # ============================
    # Información de otros soft effects en el track (para duración)
    # ============================
    debug_print("\n📋 OTROS SOFT EFFECTS EN EL TRACK (para referencia de duración):")
    debug_print("-" * 80)

    other_effects = []
    for item in items:
        effect_item = item[0]
        if isinstance(effect_item, hiero.core.EffectTrackItem):
            if effect_item.name() != CLIP_NAME:
                effect_info = {
                    "name": effect_item.name(),
                    "timeline_in": safe_get_value(effect_item, "timelineIn", None),
                    "timeline_out": safe_get_value(effect_item, "timelineOut", None),
                }
                if (
                    effect_info["timeline_in"] is not None
                    and effect_info["timeline_out"] is not None
                ):
                    effect_info["duration"] = (
                        effect_info["timeline_out"] - effect_info["timeline_in"]
                    )
                other_effects.append(effect_info)
                debug_print(
                    f"  - {effect_info['name']}: In={effect_info['timeline_in']}, Out={effect_info['timeline_out']}, Duration={effect_info.get('duration', 'N/A')}"
                )

    # ============================
    # Compilar información completa
    # ============================
    complete_info = {
        "effect_properties": effect_properties,
        "node_properties": node_properties,
        "other_effects_reference": other_effects,
        "track_name": TRACK_NAME,
        "effect_name": CLIP_NAME,
    }

    debug_print("\n" + "=" * 80)
    debug_print("✅ EXPLORACIÓN COMPLETA")
    debug_print("=" * 80)

    # Intentar guardar en JSON para referencia
    try:
        json_output = json.dumps(complete_info, indent=2, default=str)
        debug_print("\n📄 INFORMACIÓN EN FORMATO JSON:")
        debug_print("-" * 80)
        print(json_output)
    except Exception as e:
        debug_print(f"\n⚠️ No se pudo serializar a JSON: {e}")
        debug_print("La información está disponible en el objeto retornado.")

    return complete_info


# Ejecutar la función
if __name__ == "__main__":
    result = explore_frame_only_effect()
    if result:
        debug_print("\n✅ Script completado exitosamente.")
    else:
        debug_print("\n❌ Script completado con errores.")
