"""
Tests del naming con vendor code (PROYECTO_SEQ_SHOT_VENDOR).

Arma una pipesync_stats.db sintetica en un temp dir y apunta ahi el resolver de
rutas, asi que NO depende de que haya una instalacion de PipeSync ni de los
datos reales del estudio.
"""

import json
import os
import sqlite3
import sys
from tempfile import TemporaryDirectory


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_Vendors_Config as vendors_config  # noqa: E402
from LGA_NKS_Flow_NamingUtils import (  # noqa: E402
    clean_base_name,
    extract_shot_code,
    extract_task_name,
    is_shot_folder_name,
)


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _build_db(db_path, proyectos):
    """proyectos: {nombre: [vendor, ...] | None}. None = proyecto sin settings."""
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, project_name TEXT)")
    conn.execute(
        "CREATE TABLE project_settings_cache (project_id INTEGER, settings_json TEXT)"
    )
    for idx, (nombre, vendors) in enumerate(proyectos.items(), start=1):
        conn.execute("INSERT INTO projects VALUES (?, ?)", (idx, nombre))
        if vendors is None:
            continue
        envelope = json.dumps({"project_color": "#112233", "vendors": vendors})
        conn.execute("INSERT INTO project_settings_cache VALUES (?, ?)", (idx, envelope))
    conn.commit()
    conn.close()


def _parse(file_name):
    base = clean_base_name(file_name)
    return extract_shot_code(base), extract_task_name(base)


def _check_naming():
    casos = [
        # (filename, shot_code esperado, task esperada)
        # --- vendor al final del bloque base ---
        ("PROJA_1013_0800_VEN_comp_v000_%04d.exr", "PROJA_1013_0800_VEN", "comp"),
        ("PROJA_1013_0800_VEN_roto_v012_%04d.exr", "PROJA_1013_0800_VEN", "roto"),
        ("PROJA_1013_0800_VEN_v003_%04d.exr", "PROJA_1013_0800_VEN", None),
        (
            "PROJA_1013_0800_VEN_Chroma_Auto_comp_v001_%04d.exr",
            "PROJA_1013_0800_VEN_Chroma_Auto",
            "comp",
        ),
        # vendor sobre base de serie: PROYECTO_TEMP_EP_SEQ_SHOT_VENDOR
        ("PROJA_101_060_010_VEN_comp_v005_%04d.exr", "PROJA_101_060_010_VEN", "comp"),
        # --- REGRESIONES: nada de esto debe cambiar por soportar vendor ---
        # bloque alfabetico despues de dos numeros que NO es vendor: es una task
        ("PROJA_1048_060_Compo_v019_%04d.exr", "PROJA_1048_060", "Compo"),
        ("PROJA_1048_060_v019_%04d.exr", "PROJA_1048_060", None),
        ("PROJA_000_140_comp_v19.exr", "PROJA_000_140", "comp"),
        (
            "PROJA_000_140_Chroma_Auto_comp_v19.exr",
            "PROJA_000_140_Chroma_Auto",
            "comp",
        ),
        ("PROJB_101_060_010_comp_v05.exr", "PROJB_101_060_010", "comp"),
        # vendor adelante (formato historico, se detecta por estructura)
        ("PROJA_VEN_1013_0800_comp_v001_%04d.exr", "PROJA_VEN_1013_0800", "comp"),
        # PROJB esta en la DB SIN vendors cargados, asi que VEN no se reconoce y
        # el nombre degrada al parseo previo (VEN_comp leidos como DESC1_DESC2).
        # No es un bug del parser: es la DB diciendo que ese proyecto no tiene
        # vendors. Se arregla cargando el vendor code en el Projects tab de
        # PipeSync, no adivinando aca.
        ("PROJB_1013_0800_VEN_comp_v001_%04d.exr", "PROJB_1013_0800_VEN_comp", None),
    ]
    for file_name, shot_esperado, task_esperada in casos:
        shot, task = _parse(file_name)
        _expect(
            shot == shot_esperado,
            "{0}: shot_code {1!r}, esperado {2!r}".format(
                file_name, shot, shot_esperado
            ),
        )
        _expect(
            task == task_esperada,
            "{0}: task {1!r}, esperada {2!r}".format(file_name, task, task_esperada),
        )


def _check_shot_folder():
    casos = [
        ("PROJA_1013_0800_VEN", "PROJA", True),
        ("PROJA_1013_0800", "PROJA", True),
        ("PROJA_VEN_1013_0800", "PROJA", True),
        ("PROJA_1013_0800_XXX", "PROJA", False),  # XXX no es vendor conocido
        ("Comp", "PROJA", False),
        ("4_publish", "PROJA", False),
        ("VFX-PROJA", "PROJA", False),
        ("", "PROJA", False),
    ]
    for segmento, proyecto, esperado in casos:
        got = is_shot_folder_name(segmento, proyecto)
        _expect(
            got == esperado,
            "is_shot_folder_name({0!r}) dio {1}, esperado {2}".format(
                segmento, got, esperado
            ),
        )


def _check_sin_db():
    """Sin DB, el naming degrada al comportamiento previo al soporte de vendor."""
    shot, task = _parse("PROJA_1013_0800_VEN_comp_v000_%04d.exr")
    _expect(
        shot == "PROJA_1013_0800_VEN_comp",
        "Sin DB el shot_code deberia degradar, dio {0!r}".format(shot),
    )
    _expect(task is None, "Sin DB la task deberia ser None, dio {0!r}".format(task))


def _check_cache_no_envenena():
    """Un error de lectura no se puede cachear como 'no hay vendors'."""
    original = vendors_config._load_vendors_uncached

    _expect(
        sorted(vendors_config.get_vendor_codes("PROJA")) == ["VEN"],
        "Precondicion: PROJA deberia resolver VEN",
    )

    vendors_config.refresh_vendors_cache()
    vendors_config._load_vendors_uncached = lambda: ({}, False)  # lectura fallida
    try:
        _expect(
            vendors_config.get_vendor_codes("PROJA") == set(),
            "Durante el error no hay datos que devolver",
        )
    finally:
        vendors_config._load_vendors_uncached = original

    _expect(
        sorted(vendors_config.get_vendor_codes("PROJA")) == ["VEN"],
        "Pasado el error, el vendor tiene que volver sin esperar a que cambie la DB",
    )


def _check_stamp_incluye_wal():
    """El stamp tiene que moverse cuando cambia el -wal, no solo el .db."""
    with TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "x.db")
        with open(db_path, "wb") as fh:
            fh.write(b"x")
        antes = vendors_config._db_stamp(db_path)
        with open(db_path + "-wal", "wb") as fh:
            fh.write(b"cambio en el wal")
        despues = vendors_config._db_stamp(db_path)
        _expect(
            antes != despues,
            "El stamp ignora el -wal: un commit de PipeSync pasaria inadvertido",
        )


def _check_imports_coordination_panel():
    """
    Los 5 scripts del panel de coordinacion tienen que dejar TODOS sus imports
    fuera del `except ImportError` del helper de naming.

    Existe porque ya pasó: al insertar ese try/except, el import del launcher de
    FileManagerS3 quedo adentro de la rama de error y las tres tools de Wasabi
    se murieron en silencio (NameError tragado por un except Exception).
    """
    import ast

    panel_dir = os.path.join(
        os.path.dirname(SHARED_DIR), "LGA_NKS_Coordination_Panel_py"
    )
    archivos = [
        "LGA_NKS_FileManagerS3_Upload.py",
        "LGA_NKS_FileManagerS3_Download.py",
        "LGA_NKS_FileManagerS3_OpenPath.py",
        "LGA_NKS_PipeSync_CreatePsync.py",
        "LGA_NKS_PipeSync_OpenPath.py",
    ]
    permitidos = {"LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils"}

    for nombre in archivos:
        ruta = os.path.join(panel_dir, nombre)
        _expect(os.path.exists(ruta), "No existe {0}".format(ruta))
        with open(ruta, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())

        for nodo in ast.walk(tree):
            if not isinstance(nodo, ast.ExceptHandler):
                continue
            for hijo in ast.walk(nodo):
                if isinstance(hijo, ast.ImportFrom) and hijo.module not in permitidos:
                    raise AssertionError(
                        "{0}: el import de {1} quedo dentro de un except".format(
                            nombre, hijo.module
                        )
                    )


def run():
    original_path_fn = vendors_config.get_pipesync_db_path

    _check_stamp_incluye_wal()
    _check_imports_coordination_panel()

    try:
        _run_con_db_sintetica()
    finally:
        # Sin finally, un _expect fallado deja el modulo parcheado al temp dir.
        vendors_config.get_pipesync_db_path = original_path_fn
        vendors_config.refresh_vendors_cache()


def _run_con_db_sintetica():
    with TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "pipesync_stats.db")

        # 1) Sin DB: comportamiento degradado.
        vendors_config.get_pipesync_db_path = lambda filename="pipesync.db": db_path
        vendors_config.refresh_vendors_cache()
        _check_sin_db()

        # 2) Con DB: PROJA tiene vendor, PROJB no, PROJC no tiene settings.
        _build_db(db_path, {"PROJA": ["VEN"], "PROJB": [], "PROJC": None})
        vendors_config.refresh_vendors_cache()

        _expect(
            sorted(vendors_config.get_vendor_codes("PROJA")) == ["VEN"],
            "PROJA deberia tener VEN",
        )
        _expect(
            vendors_config.get_vendor_codes("PROJB") == set(),
            "PROJB esta en la DB sin vendors: no hay que inventarle ninguno",
        )
        _expect(
            sorted(vendors_config.get_vendor_codes("DESCONOCIDO")) == ["VEN"],
            "Un proyecto ausente de la DB usa la union de vendors",
        )
        _expect(
            vendors_config.is_vendor_code("ven", "PROJA"),
            "El lookup de vendor debe ser case-insensitive",
        )

        _check_naming()
        _check_shot_folder()
        _check_cache_no_envenena()


if __name__ == "__main__":
    run()
    print("test_vendor_naming: OK")
