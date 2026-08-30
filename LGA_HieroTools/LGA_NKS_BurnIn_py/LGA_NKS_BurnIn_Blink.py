"""
____________________________________________________________________

  LGA_NKS_BurnIn_Blink v1.04 | Lega

  Setup del nodo BlinkScript interno del gizmo LGA_BurnIn. Lo llama el
  onCreate del nodo al instanciarse el efecto en el timeline (y al
  recargar un proyecto). Hace dos cosas, en forma idempotente:

  1. Compila el kernel LGA_RoundedPanels si no esta compilado, usando
     kernelSourceFile + Load: es la UNICA via que compila por script en
     el timeline (recompile.execute() no hace nada ahi; medido, ver
     Docu_SoftEffects_Aprendizajes.md).
  2. Ata cada parametro del kernel a los knobs de layout del gizmo
     padre por expresion (los knobs del kernel recien existen despues
     de compilar, con el nombre del kernel como prefijo, asi que no se
     pueden escribir en el archivo del gizmo).

  v1.04: El pivote pasa a knobs literales del gizmo (bi_<f>_ax/ay),
         escritos por apply_rotation y leidos por el kernel: UNA sola
         fuente para texto y fondo (antes cada uno lo calculaba por su
         lado y podian divergir). Radio default de esquinas 11.
  v1.03: Rotacion por campo CABLEADA: apply_rotation() escribe el
         literal en animation_layers[10] del grupo "root transform" de
         cada Text2 (con el grupo seleccionado), pivote = centro del
         panel, mismo pivote bindeado a ax/ay del kernel (texto y
         fondo giran juntos). _timeline_format() para el formato real
         (por API el gizmo reporta 640x480). VALIDADO en NKS (90/270).
  v1.02: 8 campos (agrega custom1/custom2), alto del panel por campo
         (_h_expr, depende del size), y apply_font() que setea el peso
         de Inter (Regular/SemiBold/Bold) en el bi_font invisible.
  v1.01: Los paneles abrazan al texto: w y x medidos por python
         (panel_geo de la logica, con cache) y h/y por expresion
         compartida con los box de los Text2.
  v1.00: Version inicial.
____________________________________________________________________
"""

import os

KERNEL_NAME = "LGARoundedPanels"
KERNEL_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "LGA_RoundedPanels.blink"
)

FIELDS = ("clip", "cspace", "res", "frame", "tc", "fps", "custom1", "custom2")

# Grados -> radianes para el knob de rotacion por campo (bi_<f>_rot en grados).
_DEG2RAD = 0.017453292519943295


def _log(message):
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic

        bi_logic._log("[Blink] " + message)
    except Exception:
        pass


# Alto del panel y de la caja de texto: MISMA formula en el kernel y en los
# box de los Text2 (generador gen_LGA_BurnIn_gizmo.h_expr), asi el centrado
# vertical es exacto. Base 100 px del Text2 x escala x size del campo x 1.3 de
# interlinea, mas el padding.
def _h_expr(field):
    return (
        "100*parent.bi_scale*parent.bi_%s_size/100*1.3+parent.bi_text_pad" % field
    )


def _py_geo(field, comp):
    return (
        "[python {__import__('LGA_NKS_BurnIn_Logic')"
        ".panel_geo('%s', '%s', nuke.thisParent(), nuke.frame())}]" % (field, comp)
    )


def _bindings():
    """Sufijo del knob del kernel -> expresion sobre los knobs del padre.

    x y w se MIDEN del texto real (python, cacheado); y y h salen de
    expresiones simples compartidas con los box de los Text2.
    """
    binds = {}
    for f in FIELDS:
        binds["%s_x" % f] = _py_geo(f, "x")
        binds["%s_y" % f] = "parent.bi_%s_y*height" % f
        binds["%s_w" % f] = _py_geo(f, "w")
        binds["%s_h" % f] = _h_expr(f)
        binds["%s_on" % f] = "parent.bi_%s_on*parent.bi_%s_bg" % (f, f)
        # Pivote de rotacion (ax, ay): knobs literales del gizmo, escritos por
        # apply_rotation() — LA MISMA fuente que usa el blob del Text2. Si el
        # kernel lo calculara por expresion y el texto por python, cualquier
        # divergencia (formato del stream, medicion) separa el fondo del texto
        # al rotar. Con rot=0 el kernel es la SDF axis-aligned y no se usan.
        binds["%s_ax" % f] = "parent.bi_%s_ax" % f
        binds["%s_ay" % f] = "parent.bi_%s_ay" % f
        binds["%s_rot" % f] = "parent.bi_%s_rot*%s" % (f, _DEG2RAD)
    binds["corner_radius"] = "parent.bi_bg_radius"
    binds["color_r"] = "parent.bi_bg_color.r"
    binds["color_g"] = "parent.bi_bg_color.g"
    binds["color_b"] = "parent.bi_bg_color.b"
    binds["bg_opacity"] = "parent.bi_bg_opacity"
    return binds


def _compile_kernel(node):
    """Compila el kernel via Load si el nodo no lo tiene ya. True si quedo."""
    try:
        if node["kernelName"].value() == KERNEL_NAME:
            return True
    except Exception:
        pass
    try:
        node["kernelSourceFile"].setValue(KERNEL_FILE.replace("\\", "/"))
        node["reloadKernelSourceFile"].execute()
    except Exception as exc:
        _log("ERROR compilando kernel: {}".format(exc))
        return False
    try:
        ok = node["kernelName"].value() == KERNEL_NAME
    except Exception:
        ok = False
    _log("kernel compilado: {}".format("si" if ok else "NO"))
    return ok


def _bind_params(node):
    """Ata los params del kernel (prefijados con el nombre del kernel) al padre."""
    binds = _bindings()
    knob_names = list(node.knobs())
    bound = 0
    for suffix, expr in binds.items():
        target = None
        for name in knob_names:
            if name.endswith(suffix) and name != suffix:
                target = name
                break
            if name == suffix:
                target = name
        if target is None:
            _log("param no encontrado para sufijo '{}'".format(suffix))
            continue
        knob = node[target]
        try:
            if knob.hasExpression():
                continue
        except Exception:
            pass
        try:
            knob.setExpression(expr)
            bound += 1
        except Exception as exc:
            _log("ERROR atando {} -> {}: {}".format(target, expr, exc))
    if bound:
        _log("{} parametros atados al padre".format(bound))


# La fuente del burn-in es Inter (la del pack). El peso se elige con el knob
# bi_weight (enum 0/1/2). El knob font de Text2 es un FreeType_Knob: se setea
# con setValue(family, style), NO acepta un path. Lo maneja apply_font, que
# corre en el onCreate (via setup) y en el knobChanged de bi_weight (registrado
# en LGA_NKS_BurnIn.py). Los Text2 heredan por la expresion [value parent.bi_font].
_WEIGHT_STYLES = ["Regular", "SemiBold", "Bold"]


def _gizmo_of(node):
    """Grupo LGA_BurnIn que contiene a un nodo interno, o None."""
    try:
        import nuke

        full = node.fullName()
        if "." in full:
            return nuke.toNode(full.rsplit(".", 1)[0])
    except Exception:
        pass
    return None


def apply_font(gizmo):
    """Setea el knob bi_font a Inter con el estilo del peso elegido.

    bi_weight es un Enumeration_Knob: value() devuelve el LABEL, que a
    proposito ES el estilo de Inter ('Regular'/'SemiBold'/'Bold').
    """
    if gizmo is None:
        return
    try:
        style = str(gizmo["bi_weight"].value())
    except Exception:
        style = "SemiBold"
    if style not in _WEIGHT_STYLES:
        style = "SemiBold"
    try:
        gizmo["bi_font"].setValue("Inter", style)
    except Exception as exc:
        _log("ERROR seteando bi_font a Inter {}: {}".format(style, exc))


# ── Rotacion por campo ────────────────────────────────────────────────────────
#
# El transform tab del Text2 NO renderiza en soft effects. Lo que SI renderiza
# es el transform del GRUPO "root transform" del propio Text2, serializado en
# el blob animation_layers:
#
#     {1 11 <cx> <cy> <tx> <ty> <sx> <sy> <skewX> <skewY> <ROT> <?>}
#
# La rotacion va en la posicion [10] y tiene que ser un LITERAL (una expresion
# ahi rompe el layer y el texto desaparece; medido). Ademas el grupo tiene que
# estar SELECCIONADO (group_animations ... selected: 0). Mecanismo capturado de
# un Text2 rotado a mano en la UI (tab Groups). Por eso la rotacion no puede
# vivir solo en el .gizmo: la escribe apply_rotation() leyendo bi_<f>_rot, en
# el onCreate (setup) y en el knobChanged (LGA_NKS_BurnIn.py).
#
# El pivote (cx, cy) es el CENTRO del panel del campo (medido por panel_geo),
# el mismo que se bindea a ax/ay del kernel: texto y fondo giran juntos.


def _timeline_format(gizmo):
    """(width, height) del formato del timeline. OJO: gizmo.width()/height()
    por API devuelve el formato default (640x480), NO el del stream (medido);
    el formato real sale de la secuencia activa de Hiero."""
    try:
        import hiero.ui

        fmt = hiero.ui.activeSequence().format()
        return float(fmt.width()), float(fmt.height())
    except Exception:
        try:
            return float(gizmo.width()), float(gizmo.height())
        except Exception:
            return 1920.0, 1080.0


def apply_rotation(gizmo, fields=None):
    """Escribe la rotacion literal de cada campo en su Text2 interno.

    fields: iterable de campos a actualizar (default: todos). Idempotente;
    con rot=0 escribe el layer identidad (pivote indiferente).
    """
    if gizmo is None:
        return
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic
    except Exception:
        return
    fmt_w, fmt_h = _timeline_format(gizmo)
    for f in fields if fields is not None else FIELDS:
        try:
            text_node = gizmo.node("Text_%s" % f.capitalize())
            if text_node is None:
                continue
            rot = float(gizmo["bi_%s_rot" % f].value())
            # Centro del panel = pivote. El ancho sale de panel_geo('w') (mide
            # el texto, no depende del formato); el ancla y el alto se computan
            # aca con el formato REAL (panel_geo('x'/'cx') usa parent.width(),
            # que por API es el default: no sirve fuera del render).
            width = float(bi_logic.panel_geo(f, "w", gizmo, None) or 0.0)
            anchor = float(gizmo["bi_%s_x" % f].value()) * fmt_w
            justify = bi_logic.PANEL_ANCHOR.get(f, "left")
            if justify == "left":
                cx = anchor + width / 2.0
            elif justify == "center":
                cx = anchor
            else:
                cx = anchor - width / 2.0
            scale = float(gizmo["bi_scale"].value())
            size = float(gizmo["bi_%s_size" % f].value())
            pad = float(gizmo["bi_text_pad"].value())
            h = 100.0 * scale * size / 100.0 * 1.3 + pad
            cy = float(gizmo["bi_%s_y" % f].value()) * fmt_h + h / 2.0
            blob = "{1 11 %s %s 0 0 1 1 0 0 %s 0}" % (
                repr(round(cx, 4)), repr(round(cy, 4)), repr(round(rot, 4))
            )
            text_node["group_animations"].fromScript(
                '{0} imported: 0 selected: 0 items: "root transform"'
            )
            text_node["animation_layers"].fromScript(blob)
            # El kernel usa EL MISMO pivote via los knobs bi_<f>_ax/ay.
            try:
                gizmo["bi_%s_ax" % f].setValue(round(cx, 4))
                gizmo["bi_%s_ay" % f].setValue(round(cy, 4))
            except Exception:
                pass
        except Exception as exc:
            _log("ERROR rotando campo {}: {}".format(f, exc))


def nudge(gizmo):
    """Ensucia el gizmo para que el timeline re-renderice (el write por API de
    animation_layers no dispara el re-render solo; medido)."""
    try:
        value = gizmo["bi_opacity"].value()
        gizmo["bi_opacity"].setValue(value - 0.001)
        gizmo["bi_opacity"].setValue(value)
    except Exception:
        pass


def setup(node):
    """Punto de entrada del onCreate del BlinkScript interno del gizmo."""
    try:
        gizmo = _gizmo_of(node)
        if _compile_kernel(node):
            _bind_params(node)
        apply_font(gizmo)
        apply_rotation(gizmo)
    except Exception as exc:
        _log("ERROR en setup: {}".format(exc))
