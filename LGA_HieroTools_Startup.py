import importlib
import os
import sys
import traceback


STARTUP_DIR = os.path.dirname(__file__)
TOOLS_DIR = os.path.join(STARTUP_DIR, "LGA_HieroTools")

if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

# La fuente Inter del pack (LGA_NKS_Shared/fonts/) tiene que estar en el
# font-path de Nuke para que el burn-in la renderice SIN instalar nada en la
# maquina del usuario. NUKE_FONT_PATH se lee al ESCANEAR las fuentes (una vez,
# al arrancar), no en runtime; por eso va aca, lo mas temprano posible. Se
# antepone para que el Inter del repo gane sobre un Inter de sistema si existe
# (asi la medicion y el render usan el MISMO Inter en toda maquina).
#
# MEDIDO: Nuke parte NUKE_FONT_PATH por ":" (estilo Unix) incluso en Windows,
# asi que el ":" de la letra de unidad ROMPE el path: getFonts registraba
# "Tools/LGA_NKS_Shared/..." (relativo, invalido) y el render caia a la fuente
# default en silencio. El path va SIN la letra de unidad ("/Users/...", valido
# en Windows contra el drive del proceso) y con barras normales.
_FONTS_DIR = os.path.join(TOOLS_DIR, "LGA_NKS_Shared", "fonts")
if os.path.isdir(_FONTS_DIR):
    _fonts_nuke = os.path.splitdrive(_FONTS_DIR)[1].replace("\\", "/")
    _prev = os.environ.get("NUKE_FONT_PATH", "")
    if _fonts_nuke not in _prev.split(":"):
        os.environ["NUKE_FONT_PATH"] = (
            _fonts_nuke + (":" + _prev if _prev else "")
        )

MODULES = [
    "LGA_NKS_Assignee_Panel",
    "LGA_NKS_BurnIn",
    "LGA_NKS_ClipColor_Panel",
    "LGA_NKS_Coordination_Panel",
    "LGA_NKS_Edit_Panel",
    "LGA_NKS_Flow_Panel",
    "LGA_NKS_Playlist_Panel",
    "LGA_NKS_Projects_Panel",
    "LGA_NKS_Review_Panel",
    "LGA_NKS_Shortcuts",
    "LGA_NKS_ViewerTL_Panel",
    "z_clear_outpoint_workaround",
    "z_version_everywhere",
]

for module_name in MODULES:
    try:
        importlib.import_module(module_name)
    except Exception:
        print("[LGA_HieroTools_Startup] Error loading {}".format(module_name))
        traceback.print_exc()
