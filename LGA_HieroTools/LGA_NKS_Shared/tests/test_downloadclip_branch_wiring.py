"""Pruebas del cableado de ramas en Download Clip.

Carga el modulo real LGA_NKS_FileManager_DownloadClip.py (sin Hiero, sin Qt y
sin red) con FileManager mockeado, y verifica la cadena completa:
entries -> ramas -> plan -> intents -> argumentos del CLI.

Cubre lo que no cubren los tests de los helpers: que las piezas esten
efectivamente conectadas entre si.

Correr:  python test_downloadclip_branch_wiring.py
"""

import importlib.util
import os
import shutil
import sys
import tempfile


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
TOOLS_DIR = os.path.dirname(SHARED_DIR)
for candidate in (SHARED_DIR, TOOLS_DIR):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import LGA_NKS_BranchDownloadPlan as plan  # noqa: E402


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _load_downloadclip():
    path = os.path.join(
        TOOLS_DIR, "LGA_NKS_Coordination_Panel_py", "LGA_NKS_FileManager_DownloadClip.py"
    )
    spec = importlib.util.spec_from_file_location("dlclip_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEQ_PARENT = "T:/VFX-ERSO/060/ERSO_060_010/comp/4_publish"
SEQ_MEDIA = SEQ_PARENT + "/ERSO_060_010_comp_v012/ERSO_060_010_comp_v012.%04d.exr"


def _entry(**overrides):
    entry = {
        "clip": None,
        "clip_name": "ERSO_060_010_comp",
        "file_path": SEQ_MEDIA,
        "is_single_file": False,
        "target_local": SEQ_PARENT + "/ERSO_060_010_comp_v012",
        "parent_local": SEQ_PARENT,
        "local_versions": [12],
        "versions": {12: "ERSO_060_010_comp_v012", 14: "ERSO_060_010_comp_v014"},
        "target_version": 12,
        "error": None,
    }
    entry.update(overrides)
    return entry


def run():
    dlclip = _load_downloadclip()

    launched = []

    def fake_launch(folder_paths, file_paths, notify_dir, download_latest, mode_label):
        launched.append(
            {
                "folders": list(folder_paths),
                "files": list(file_paths),
                "latest": download_latest,
                "mode": mode_label,
            }
        )
        return True

    dlclip._launch_filemanager = fake_launch
    temp_intents = tempfile.mkdtemp(prefix="lga_test_intents_")
    dlclip.get_intent_dir = lambda: temp_intents

    try:
        # Una sola rama: no se pregunta nada y se baja su cabeza con --download
        # (ruta explicita), no con --download-latest.
        launched.clear()
        dlclip._apply_branch_scan([_entry()])
        _expect(len(launched) == 1, f"Debe lanzar una vez, lanzo {len(launched)}")
        _expect(launched[0]["latest"] is False, "No debe usar --download-latest")
        _expect(
            launched[0]["folders"] == [SEQ_PARENT + "/ERSO_060_010_comp_v014"],
            f"Debe bajar la cabeza v014: {launched[0]['folders']}",
        )

        intent = plan.read_intent(temp_intents, launched[0]["folders"][0])
        _expect(intent is not None, "Debe escribir el intent para el watcher")
        _expect(intent["version"] == 14, f"Intent con version equivocada: {intent}")
        _expect(intent["switch"] is True, "El clip debe subir a la cabeza de su rama")
        _expect(
            intent["clip_path"] == SEQ_MEDIA,
            "El intent debe recordar la ruta original del clip",
        )

        # Listado fallido: fallback al --download-latest de FileManager, con la
        # ruta actual del clip.
        launched.clear()
        dlclip._apply_branch_scan([_entry(error="sin credenciales", versions={})])
        _expect(len(launched) == 1, "El fallback tiene que lanzar igual")
        _expect(launched[0]["latest"] is True, "El fallback usa --download-latest")
        _expect(
            launched[0]["mode"] == "LATEST-FALLBACK",
            f"Modo inesperado: {launched[0]['mode']}",
        )

        # Ya estando en la cabeza igual se baja (comportamiento historico del
        # boton: click siempre descarga), pero sin dialogo.
        launched.clear()
        dlclip._apply_branch_scan(
            [
                _entry(
                    versions={12: "ERSO_060_010_comp_v012"},
                    local_versions=[12],
                )
            ]
        )
        _expect(len(launched) == 1, "Estando al dia igual se baja")
        _expect(
            launched[0]["folders"] == [SEQ_PARENT + "/ERSO_060_010_comp_v012"],
            f"Debe bajar la propia version: {launched[0]['folders']}",
        )

        # Sin parent_local no se puede armar la ruta: se saltea ese clip en vez
        # de reventar la descarga de todos.
        launched.clear()
        dlclip._apply_branch_scan([_entry(parent_local=None)])
        _expect(not launched, "Sin parent_local no debe lanzar nada")
    finally:
        shutil.rmtree(temp_intents, ignore_errors=True)


if __name__ == "__main__":
    run()
    print("test_downloadclip_branch_wiring: OK")
