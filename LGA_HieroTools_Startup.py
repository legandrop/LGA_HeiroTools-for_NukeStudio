import importlib
import os
import sys
import traceback


STARTUP_DIR = os.path.dirname(__file__)
TOOLS_DIR = os.path.join(STARTUP_DIR, "LGA_HieroTools")

if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

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
