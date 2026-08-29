"""
____________________________________________________________________

  LGA_NKS_BurnIn_Blink v1.00 | Lega

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

  v1.00: Version inicial.
____________________________________________________________________
"""

import os

KERNEL_NAME = "LGARoundedPanels"
KERNEL_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "LGA_RoundedPanels.blink"
)

FIELDS = ("clip", "res", "frame", "tc", "cspace", "fps")


def _log(message):
    try:
        import LGA_NKS_BurnIn_Logic as bi_logic

        bi_logic._log("[Blink] " + message)
    except Exception:
        pass


def _bindings():
    """Sufijo del knob del kernel -> expresion sobre los knobs del padre."""
    binds = {}
    for f in FIELDS:
        binds["%s_x" % f] = "parent.bi_%s_x*width" % f
        binds["%s_y" % f] = "parent.bi_%s_y*height" % f
        binds["%s_w" % f] = "parent.bi_%s_w*width" % f
        binds["%s_h" % f] = "parent.bi_%s_h*height" % f
        binds["%s_on" % f] = "parent.bi_%s_on*parent.bi_%s_bg" % (f, f)
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


def setup(node):
    """Punto de entrada del onCreate del BlinkScript interno del gizmo."""
    try:
        if _compile_kernel(node):
            _bind_params(node)
    except Exception as exc:
        _log("ERROR en setup: {}".format(exc))
