"""Pruebas del helper de ramas de versiones.

Correr:  python test_version_branching.py
"""

import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_VersionBranching as vb  # noqa: E402


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def test_gap_rule():
    # El caso canonico documentado en PipeSync: v099 -> v100 NO abre rama.
    _expect(
        vb.split_into_branches([99, 100]) == [[99, 100]],
        "v099 y v100 deben quedar en la misma rama",
    )
    _expect(
        vb.split_into_branches([199, 200]) == [[199, 200]],
        "v199 y v200 deben quedar en la misma rama",
    )
    # Un salto de exactamente 50 SI abre rama (el criterio es >=).
    _expect(
        vb.split_into_branches([1, 51]) == [[1], [51]],
        "Un salto de exactamente 50 debe abrir rama nueva",
    )
    _expect(
        vb.split_into_branches([1, 50]) == [[1, 50]],
        "Un salto de 49 debe quedar en la misma rama",
    )
    _expect(
        vb.split_into_branches([1, 2, 3, 12, 100, 101, 103, 200])
        == [[1, 2, 3, 12], [100, 101, 103], [200]],
        "Tres ramas mal detectadas",
    )


def test_orden_y_duplicados():
    _expect(
        vb.split_into_branches([103, 1, 100, 1, 12]) == [[1, 12], [100, 103]],
        "Debe ordenar y deduplicar antes de partir",
    )
    _expect(vb.split_into_branches([]) == [], "Lista vacia debe dar cero ramas")
    _expect(
        vb.split_into_branches([None, "x", 5]) == [[5]],
        "Los valores no numericos se descartan",
    )


def test_heads():
    versions = [1, 2, 12, 100, 103, 200]
    _expect(vb.branch_heads(versions) == [12, 103, 200], "Cabezas mal calculadas")
    _expect(vb.has_branches(versions), "Debe reportar mas de una rama")
    _expect(not vb.has_branches([1, 2, 3]), "Una sola rama no es 'con ramas'")
    _expect(not vb.has_branches([]), "Sin versiones no hay ramas")


def test_head_of_branch_containing():
    versions = [1, 2, 12, 100, 103]
    # El reemplazo de max(): parado en v002 la cabeza es v012, no v103.
    _expect(
        vb.head_of_branch_containing(versions, 2) == 12,
        "Desde la rama baja la cabeza debe ser 12",
    )
    _expect(
        vb.head_of_branch_containing(versions, 100) == 103,
        "Desde la rama 100 la cabeza debe ser 103",
    )
    # Version que la fuente no conoce: sigue ubicada en su rama.
    _expect(
        vb.head_of_branch_containing([100, 103], 5) == 5,
        "Una version sola en su rama es su propia cabeza",
    )
    _expect(
        vb.head_of_branch_containing([], 7) == 7,
        "Sin lista, la cabeza es la propia version",
    )
    # Ya estando en la cabeza no hay nada mas arriba EN SU rama.
    _expect(
        vb.head_of_branch_containing(versions, 12) == 12,
        "En la cabeza de la rama no debe saltar a otra rama",
    )


def test_latest_versions_per_branch():
    versions = [1, 2, 3, 12, 100, 101, 103]
    _expect(
        vb.latest_versions_per_branch(versions, 1) == {12, 103},
        "1 por rama mal calculado",
    )
    _expect(
        vb.latest_versions_per_branch(versions, 2) == {3, 12, 101, 103},
        "2 por rama mal calculado",
    )
    _expect(
        vb.latest_versions_per_branch(versions, 0) == set(),
        "0 por rama debe devolver vacio",
    )
    _expect(
        vb.latest_versions_per_branch([5], 3) == {5},
        "Pedir mas versiones que las que hay no debe romper",
    )


def test_extract_version_number():
    _expect(vb.extract_version_number("SHOT_010_comp_v012.mov") == 12, "mov")
    _expect(vb.extract_version_number("SHOT_010_comp_v103") == 103, "carpeta")
    _expect(vb.extract_version_number("SHOT_comp_v012 (nota)") == 12, "nombre con nota")
    _expect(vb.extract_version_number("SHOT_comp_v012-alt") == 12, "nombre con guion")
    _expect(vb.extract_version_number("sin version") == -1, "sin token debe dar -1")
    _expect(vb.extract_version_number("sin version", default=0) == 0, "default")
    # En rutas gana el ultimo token: el del archivo, no el de la carpeta.
    _expect(
        vb.extract_version_number("T:/VFX-X/010/comp/4_publish/x_comp_v100/x_comp_v103.exr")
        == 103,
        "En una ruta debe ganar el ultimo _v###",
    )


def test_family_key():
    a = vb.family_key("SHOT_010_comp_v012.mov")
    b = vb.family_key("SHOT_010_comp_v103.mov")
    _expect(a == b, "Dos versiones de la misma serie deben compartir familia")

    _expect(
        vb.family_key("SHOT_010_comp_v012.mov") != vb.family_key("SHOT_010_roto_v012.mov"),
        "Series distintas no deben compartir familia",
    )
    _expect(
        vb.family_key("SHOT_010_comp_v012.mov") != vb.family_key("SHOT_010_comp_v012.exr"),
        "La extension separa familias",
    )
    _expect(
        vb.family_key("SHOT_comp_v012_final") == vb.family_key("SHOT_comp_v103_final"),
        "El sufijo despues de la version debe conservarse en la familia",
    )
    _expect(
        vb.family_key("SHOT_comp_v012_final") != vb.family_key("SHOT_comp_v012"),
        "Un sufijo distinto es otra familia",
    )
    # Secuencias: el token de frames no debe ensuciar la familia.
    _expect(
        vb.family_key("SHOT_comp_v012_%04d.exr") == vb.family_key("SHOT_comp_v103_%04d.exr"),
        "El token %04d no debe separar familias",
    )
    # Rutas completas: solo cuenta el basename.
    _expect(
        vb.family_key("T:/VFX-X/010/SHOT_010_comp_v012.mov") == a,
        "La familia debe salir del basename",
    )
    _expect(
        vb.family_key(r"T:\VFX-X\010\SHOT_010_comp_v012.mov") == a,
        "Barras de Windows deben normalizar igual",
    )
    _expect(
        vb.family_key("T:/VFX-X/010/SHOT_comp_v012/") == vb.family_key("SHOT_comp_v103"),
        "Una carpeta con barra final debe normalizar igual",
    )


def test_group_by_family():
    names = [
        "SHOT_comp_v001.mov",
        "SHOT_comp_v012.mov",
        "SHOT_comp_v100.mov",
        "SHOT_roto_v004.mov",
        "sin_version.mov",
    ]
    groups = vb.group_by_family(names)
    _expect(len(groups) == 2, f"Debe haber 2 familias, hay {len(groups)}")

    comp_key = vb.family_key("SHOT_comp_v001.mov")
    comp_versions = [version for version, _name in groups[comp_key]]
    _expect(comp_versions == [1, 12, 100], "La familia comp debe venir ordenada")
    _expect(
        vb.branch_heads(comp_versions) == [12, 100],
        "La familia comp debe tener dos cabezas",
    )


def test_describe_branches():
    described = vb.describe_branches([1, 2, 12, 100, 103])
    _expect(len(described) == 2, "Debe describir dos ramas")
    _expect(described[0]["label"] == "v000", "La etiqueta es el bloque de centena")
    _expect(described[0]["head"] == 12, "Cabeza de la primera rama")
    _expect(described[1]["label"] == "v100", "Etiqueta de la segunda rama")
    _expect(described[1]["head"] == 103, "Cabeza de la segunda rama")
    _expect(described[1]["versions"] == [100, 103], "Versiones de la segunda rama")
    _expect(vb.describe_branches([]) == [], "Sin versiones no hay ramas descritas")


def test_labels_estables_entre_fuentes():
    # La misma rama tiene que llamarse igual sepa la fuente v100..v103 o solo v103.
    completa = vb.describe_branches([12, 100, 101, 103])
    parcial = vb.describe_branches([12, 103])
    _expect(
        [b["label"] for b in completa] == [b["label"] for b in parcial] == ["v000", "v100"],
        "La etiqueta no debe depender de cuantas versiones vio la fuente",
    )


def test_labels_desambiguados_en_colision():
    # v001 y v060 caen en la misma centena y la regla de 50 las separa:
    # ahi las etiquetas pasan a ser el arranque real de cada rama.
    described = vb.describe_branches([1, 2, 60, 61])
    labels = [branch["label"] for branch in described]
    _expect(labels == ["v001", "v060"], f"Colision mal resuelta: {labels}")
    _expect(len(set(labels)) == len(labels), "Las etiquetas deben ser unicas")


def test_compare_branches_pull():
    # Caso del Pull: Flow tiene la rama 0 hasta v012 y la rama 100 hasta v103.
    # El clip esta en v010 de la rama 0 y no tiene nada de la rama 100.
    branches = vb.compare_branches(
        remote_versions=[1, 5, 12, 100, 103],
        local_versions=[1, 5, 10],
        current_version=10,
    )
    _expect(len(branches) == 2, f"Debe haber 2 ramas, hay {len(branches)}")

    own, other = branches
    _expect(own["is_current_branch"], "La primera rama es la del clip")
    _expect(own["remote_head"] == 12, "Cabeza remota de la rama del clip")
    _expect(own["local_head"] == 10, "Cabeza local de la rama del clip")
    _expect(own["has_news"], "Flow tiene v012 y localmente hay v010: es novedad")

    _expect(not other["is_current_branch"], "La rama 100 no es la del clip")
    _expect(other["remote_head"] == 103, "Cabeza remota de la rama 100")
    _expect(other["local_head"] is None, "No hay nada local de la rama 100")
    _expect(other["has_news"], "Una rama que no tenemos siempre es novedad")
    _expect(other["label"] == "v100", "Etiqueta de la rama ajena")
    _expect(own["label"] == "v000", "Etiqueta de la rama del clip")


def test_compare_branches_sin_novedad():
    # Rama ajena ya bajada completa: no debe generar aviso.
    branches = vb.compare_branches(
        remote_versions=[12, 103],
        local_versions=[12, 103],
        current_version=12,
    )
    _expect(len(branches) == 2, "Dos ramas")
    _expect(not branches[0]["has_news"], "La rama del clip esta al dia")
    _expect(not branches[1]["has_news"], "La rama ajena ya esta bajada")


def test_compare_branches_clip_cuenta_como_local():
    # El clip esta en una version que no figura en la lista local declarada:
    # igual cuenta como bajada, si no todo se reportaria como novedad.
    branches = vb.compare_branches(
        remote_versions=[12],
        local_versions=[],
        current_version=12,
    )
    _expect(len(branches) == 1, "Una sola rama")
    _expect(branches[0]["local_head"] == 12, "El clip cuenta como local")
    _expect(not branches[0]["has_news"], "Estando en la cabeza no hay novedad")


def test_compare_branches_solo_local():
    # Una rama que existe solo en local (todavia no subida) no es novedad.
    branches = vb.compare_branches(
        remote_versions=[12],
        local_versions=[12, 100],
        current_version=12,
    )
    _expect(len(branches) == 2, "Dos ramas")
    _expect(branches[1]["remote_head"] is None, "La rama 100 no esta en la fuente remota")
    _expect(not branches[1]["has_news"], "Sin cabeza remota no hay novedad")


def test_compare_branches_vacio():
    _expect(vb.compare_branches([], []) == [], "Sin versiones no hay ramas")
    solo_clip = vb.compare_branches([], [], current_version=7)
    _expect(len(solo_clip) == 1, "Con solo el clip hay una rama")
    _expect(not solo_clip[0]["has_news"], "Sin fuente remota no hay novedad")


def test_format_version():
    _expect(vb.format_version(7) == "v007", "Padding de 3 digitos por defecto")
    _expect(vb.format_version(103) == "v103", "Tres cifras sin cambios")
    _expect(vb.format_version(7, digits=2) == "v07", "Padding configurable")
    _expect(vb.format_version(None) == "v?", "Valor invalido no debe romper")


def run():
    test_gap_rule()
    test_orden_y_duplicados()
    test_heads()
    test_head_of_branch_containing()
    test_latest_versions_per_branch()
    test_extract_version_number()
    test_family_key()
    test_group_by_family()
    test_describe_branches()
    test_labels_estables_entre_fuentes()
    test_labels_desambiguados_en_colision()
    test_compare_branches_pull()
    test_compare_branches_sin_novedad()
    test_compare_branches_clip_cuenta_como_local()
    test_compare_branches_solo_local()
    test_compare_branches_vacio()
    test_format_version()


if __name__ == "__main__":
    run()
    print("test_version_branching: OK")
