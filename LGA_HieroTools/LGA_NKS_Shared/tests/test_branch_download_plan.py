"""Pruebas del plan de descarga por ramas y del listado de Wasabi.

El listado S3 se inyecta con un fake: no toca red ni credenciales.

Correr:  python test_branch_download_plan.py
"""

import os
import shutil
import sys
import tempfile


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_BranchDownloadPlan as plan  # noqa: E402
import LGA_NKS_S3VersionLister as lister  # noqa: E402


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


# ── fixtures ─────────────────────────────────────────────────────────────────

SEQ_PARENT = "T:/VFX-ERSO/060/ERSO_060_010/comp/4_publish"
SEQ_TARGET = SEQ_PARENT + "/ERSO_060_010_comp_v012"
SEQ_MEDIA = SEQ_TARGET + "/ERSO_060_010_comp_v012.%04d.exr"

MOV_PARENT = "T:/VFX-ERSO/060/ERSO_060_010/comp/3_review"
MOV_MEDIA = MOV_PARENT + "/ERSO_060_010_comp_v012.mov"


def _fake_lister(folders=None, files=None, calls=None):
    def _lister(bucket, prefix):
        if calls is not None:
            calls.append((bucket, prefix))
        return list(folders or []), list(files or [])

    return _lister


def _entry_secuencia(remote_versions, local_versions, target_version=12):
    versions = {
        number: f"ERSO_060_010_comp_{plan.format_version(number)}"
        for number in remote_versions
    }
    entry = {
        "clip_name": "ERSO_060_010_comp",
        "file_path": SEQ_MEDIA,
        "is_single_file": False,
        "parent_local": SEQ_PARENT,
        "target_name": f"ERSO_060_010_comp_{plan.format_version(target_version)}",
        "target_version": target_version,
        "versions": versions,
        "local_versions": list(local_versions),
    }
    entry["branches"] = plan.build_clip_branches(entry)
    return entry


# ── listado remoto ───────────────────────────────────────────────────────────


def test_lister_secuencia_filtra_familia():
    calls = []
    result = lister.list_family_versions(
        SEQ_TARGET,
        is_single_file=False,
        lister=_fake_lister(
            folders=[
                "ERSO_060_010_comp_v010",
                "ERSO_060_010_comp_v012",
                "ERSO_060_010_comp_v103",
                "ERSO_060_010_roto_v200",  # otra familia
                "referencias",  # sin version
            ],
            files=["ERSO_060_010_comp_v999.mov"],  # archivos no cuentan para secuencia
            calls=calls,
        ),
    )
    _expect(result.get("ok"), f"El listado debe resolver: {result.get('error')}")
    _expect(
        sorted(result["versions"]) == [10, 12, 103],
        f"Versiones mal filtradas: {sorted(result['versions'])}",
    )
    _expect(result["target_version"] == 12, "Version del target")
    _expect(result["parent_local"] == SEQ_PARENT, "Padre local")
    _expect(len(calls) == 1, "Debe listar una sola vez")
    # El prefijo remoto arranca despues de la carpeta VFX-*.
    _expect(
        calls[0][1] == "060/ERSO_060_010/comp/4_publish",
        f"Prefijo remoto inesperado: {calls[0][1]}",
    )


def test_lister_archivo_unico_mira_archivos():
    result = lister.list_family_versions(
        MOV_MEDIA,
        is_single_file=True,
        lister=_fake_lister(
            folders=["ERSO_060_010_comp_v500"],  # carpetas no cuentan para .mov
            files=[
                "ERSO_060_010_comp_v012.mov",
                "ERSO_060_010_comp_v103.mov",
                "ERSO_060_010_comp_v103.mp4",  # otra extension = otra familia
            ],
        ),
    )
    _expect(result.get("ok"), f"El listado debe resolver: {result.get('error')}")
    _expect(
        sorted(result["versions"]) == [12, 103],
        f"Versiones mal filtradas: {sorted(result['versions'])}",
    )


def test_lister_sin_token_de_version():
    result = lister.list_family_versions(
        MOV_PARENT + "/sin_version.mov", is_single_file=True, lister=_fake_lister()
    )
    _expect(not result.get("ok"), "Sin _v### no se puede resolver ramas")


def test_lister_ruta_sin_vfx():
    result = lister.list_family_versions(
        "C:/temp/ERSO_060_010_comp_v012.mov",
        is_single_file=True,
        lister=_fake_lister(),
    )
    _expect(not result.get("ok"), "Una ruta sin VFX-* no resuelve bucket")


def test_lister_error_de_red_no_revienta():
    def _boom(bucket, prefix):
        raise RuntimeError("timeout")

    result = lister.list_family_versions(SEQ_TARGET, is_single_file=False, lister=_boom)
    _expect(not result.get("ok"), "Un error de red debe volver como ok=False")
    _expect("timeout" in result.get("error", ""), "El error debe explicar la causa")


# ── opciones del dialogo ─────────────────────────────────────────────────────


def test_una_sola_rama_no_ofrece_opciones():
    entry = _entry_secuencia(remote_versions=[10, 12], local_versions=[10, 12])
    options = plan.aggregate_branch_options([entry])
    _expect(len(options) == 1, f"Debe haber una sola rama, hay {len(options)}")
    _expect(options[0]["is_current_branch"], "Y es la del clip")


def test_dos_ramas_ordenadas_y_marcadas():
    entry = _entry_secuencia(remote_versions=[10, 12, 100, 103], local_versions=[10, 12])
    options = plan.aggregate_branch_options([entry])
    _expect(len(options) == 2, f"Debe haber 2 ramas, hay {len(options)}")
    _expect(options[0]["label"] == "v000", f"Primera rama: {options[0]['label']}")
    _expect(options[1]["label"] == "v100", f"Segunda rama: {options[1]['label']}")
    _expect(options[0]["is_current_branch"], "La rama del clip es la primera")
    _expect(not options[0]["has_news"], "La rama del clip esta al dia")
    _expect(options[1]["has_news"], "La rama 100 es novedad")
    _expect(plan.option_summary(options[1]) == "v103", "Resumen de la rama 100")


def test_opciones_unen_varios_clips():
    a = _entry_secuencia(remote_versions=[12, 103], local_versions=[12])
    b = _entry_secuencia(remote_versions=[12, 205], local_versions=[12])
    options = plan.aggregate_branch_options([a, b])
    labels = [option["label"] for option in options]
    _expect(labels == ["v000", "v100", "v200"], f"Labels inesperados: {labels}")
    _expect(len(options[0]["heads"]) == 2, "La rama comun tiene los dos clips")
    _expect(len(options[1]["heads"]) == 1, "La rama 100 solo esta en el primer clip")


# ── plan de descarga ─────────────────────────────────────────────────────────


def test_plan_todas_las_ramas():
    entry = _entry_secuencia(remote_versions=[12, 103], local_versions=[12])
    result = plan.plan_downloads([entry], plan.SELECTION_ALL)
    _expect(len(result["folder_paths"]) == 2, "Debe bajar las dos cabezas")
    _expect(not result["file_paths"], "Una secuencia no va por --download-file")
    _expect(
        result["folder_paths"][1].endswith("ERSO_060_010_comp_v103"),
        f"Ruta resuelta inesperada: {result['folder_paths'][1]}",
    )

    # Con "todas", el clip solo sube dentro de su propia rama.
    switches = [intent for intent in result["intents"] if intent["switch"]]
    _expect(len(switches) == 1, "Solo un intent debe pedir cambio de version")
    _expect(switches[0]["version"] == 12, "Y es la cabeza de la rama del clip")


def test_plan_rama_explicita_sube_el_clip():
    entry = _entry_secuencia(remote_versions=[12, 103], local_versions=[12])
    result = plan.plan_downloads([entry], "v100")
    _expect(len(result["folder_paths"]) == 1, "Solo la rama elegida")
    _expect(len(result["intents"]) == 1, "Un solo intent")
    intent = result["intents"][0]
    _expect(intent["switch"], "Eligiendo una rama explicita el clip se mueve ahi")
    _expect(intent["version"] == 103, "A la cabeza de esa rama")
    _expect(intent["clip_path"] == SEQ_MEDIA, "El intent recuerda el clip original")


def test_plan_archivo_unico_usa_file_paths():
    entry = {
        "clip_name": "ERSO_060_010_comp",
        "file_path": MOV_MEDIA,
        "is_single_file": True,
        "parent_local": MOV_PARENT,
        "target_name": "ERSO_060_010_comp_v012",
        "target_version": 12,
        "versions": {12: "ERSO_060_010_comp_v012.mov", 103: "ERSO_060_010_comp_v103.mov"},
        "local_versions": [12],
    }
    entry["branches"] = plan.build_clip_branches(entry)
    result = plan.plan_downloads([entry], plan.SELECTION_ALL)
    _expect(len(result["file_paths"]) == 2, "Los .mov van por --download-file")
    _expect(not result["folder_paths"], "Y no por --download")


def test_plan_reporta_clips_sin_esa_rama():
    a = _entry_secuencia(remote_versions=[12, 103], local_versions=[12])
    b = _entry_secuencia(remote_versions=[12], local_versions=[12])
    result = plan.plan_downloads([a, b], "v100")
    _expect(len(result["folder_paths"]) == 1, "Solo el clip que tiene esa rama")
    _expect(len(result["skipped"]) == 1, "El otro clip se reporta como salteado")


# ── intents ──────────────────────────────────────────────────────────────────


def test_intents_ida_y_vuelta():
    temp_dir = tempfile.mkdtemp(prefix="lga_intents_")
    try:
        entry = _entry_secuencia(remote_versions=[12, 103], local_versions=[12])
        result = plan.plan_downloads([entry], "v100")
        written = plan.write_intents(temp_dir, result["intents"])
        _expect(len(written) == 1, "Debe escribir un intent")

        target = result["intents"][0]["path"]
        loaded = plan.read_intent(temp_dir, target)
        _expect(loaded is not None, "El intent debe leerse por su ruta")
        _expect(loaded["version"] == 103, "Version del intent")
        _expect(loaded["switch"] is True, "Flag de cambio de version")

        # El watcher recibe la ruta con barras de Windows: debe matchear igual.
        windows_style = target.replace("/", "\\")
        _expect(
            plan.read_intent(temp_dir, windows_style) is not None,
            "El match no debe depender del separador",
        )

        _expect(plan.clear_intent(temp_dir, target), "El intent se borra al consumirlo")
        _expect(
            plan.read_intent(temp_dir, target) is None,
            "Una vez borrado no debe volver a leerse",
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_intent_vencido_se_ignora():
    temp_dir = tempfile.mkdtemp(prefix="lga_intents_")
    try:
        intents = [
            {
                "path": SEQ_TARGET,
                "kind": "folder",
                "clip_path": SEQ_MEDIA,
                "version": 12,
                "switch": True,
            }
        ]
        plan.write_intents(temp_dir, intents)

        # Envejecer el intent a mano por encima del TTL: primero el contenido
        # y despues el mtime, porque escribir el archivo lo vuelve a poner en
        # "ahora" y prune_intents mira el mtime.
        target_file = os.path.join(temp_dir, plan.intent_filename(SEQ_TARGET))
        old = os.path.getmtime(target_file) - plan.INTENT_TTL_SECONDS - 60
        import json

        with open(target_file, "r+", encoding="utf-8") as handle:
            payload = json.load(handle)
            payload["created"] = old
            handle.seek(0)
            handle.truncate()
            json.dump(payload, handle)
        os.utime(target_file, (old, old))

        _expect(
            plan.read_intent(temp_dir, SEQ_TARGET) is None,
            "Un intent vencido no debe usarse",
        )
        _expect(plan.prune_intents(temp_dir) == 1, "prune debe borrar el vencido")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run():
    test_lister_secuencia_filtra_familia()
    test_lister_archivo_unico_mira_archivos()
    test_lister_sin_token_de_version()
    test_lister_ruta_sin_vfx()
    test_lister_error_de_red_no_revienta()
    test_una_sola_rama_no_ofrece_opciones()
    test_dos_ramas_ordenadas_y_marcadas()
    test_opciones_unen_varios_clips()
    test_plan_todas_las_ramas()
    test_plan_rama_explicita_sube_el_clip()
    test_plan_archivo_unico_usa_file_paths()
    test_plan_reporta_clips_sin_esa_rama()
    test_intents_ida_y_vuelta()
    test_intent_vencido_se_ignora()


if __name__ == "__main__":
    run()
    print("test_branch_download_plan: OK")
