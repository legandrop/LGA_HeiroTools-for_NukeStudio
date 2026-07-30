"""
____________________________________________________________________

  LGA_NKS_VersionBranching v1.00 | Lega

  Ramas de versiones: cuando mas de un compositor trabaja el mismo shot,
  cada uno numera en su propio bloque (rama 0 = v001..v0xx, rama 100 =
  v100..v1xx). Las dos ramas conviven y despues una absorbe el trabajo
  de la otra, asi que el maximo global NO es "la version vigente": cada
  rama tiene su propia cabeza y todas las cabezas son validas a la vez.

  Espejo del modulo de PipeSync (misma regla, mismo gap):
  C:\\Portable\\LGA_PipeSync_2\\src\\utils\\VersionBranching.cpp

  Regla: se ordena la lista, se sacan duplicados, y un salto de BRANCH_GAP
  o mas entre versiones consecutivas abre una rama nueva.
    v099 -> v100  = misma rama (salto 1)
    v012 -> v100  = dos ramas  (salto 88)

  Este modulo trabaja SOLO con enteros a proposito: cada script conserva
  su propio parser de nombres (los formatos varian entre .nk, .mov,
  carpetas de publish y nombres de Version de Flow) y le pasa numeros.
  extract_version_number() existe para el codigo nuevo que no tiene uno.

  v1.00: Version inicial.
____________________________________________________________________
"""

import re


# Salto minimo entre versiones consecutivas que abre una rama nueva.
# Igual que kBranchGap en VersionBranching.h de PipeSync: si se cambia
# aca hay que cambiarlo alla, porque las dos apps miran los mismos shots.
BRANCH_GAP = 50

# Ultimo token _v### / v### del texto. Es el criterio del watcher (el mas
# robusto para rutas, donde puede haber varios _v en el camino).
_VERSION_RE = re.compile(r"_?v(\d{1,4})", re.IGNORECASE)


def extract_version_number(text, default=-1):
    """Numero de version del ultimo token _v###/v### del texto.

    Devuelve `default` si no hay ninguno. Para codigo nuevo: los scripts
    que ya tienen su propio extractor lo conservan.
    """
    matches = list(_VERSION_RE.finditer(str(text or "")))
    if not matches:
        return default
    try:
        return int(matches[-1].group(1))
    except (TypeError, ValueError):
        return default


def format_version(version, digits=3):
    """v012 / v103. PipeSync usa 3 digitos: con ramas de 3 cifras es el
    unico padding que no mezcla v07 con v100 en la misma columna."""
    try:
        return "v{0:0{1}d}".format(int(version), int(digits))
    except (TypeError, ValueError):
        return "v?"


def family_key(name):
    """Clave de familia: nombre sin el token de version, para agrupar una serie.

    Las ramas se calculan SIEMPRE dentro de una familia: dos series
    distintas en la misma carpeta no comparten ramas. Se parte por el
    ULTIMO token de version y se conserva lo que queda de cada lado,
    igual que el `base + "|##|" + sufijo` de PipeSync.
      'SHOT_010_comp_v012.mov'       -> 'shot_010_comp||.mov'
      'SHOT_010_comp_v012_final.mov' -> 'shot_010_comp|_final|.mov'
      'SHOT_010_comp_v012'           -> 'shot_010_comp||'
    """
    raw = str(name or "").strip().replace("\\", "/")
    raw = raw.rstrip("/")
    raw = raw.rsplit("/", 1)[-1]

    extension = ""
    dot = raw.rfind(".")
    if dot > 0:
        candidate = raw[dot:]
        # Solo se trata como extension si no es parte del token de version.
        if not re.match(r"^\.v\d{1,4}$", candidate, re.IGNORECASE):
            extension = candidate.lower()
            raw = raw[:dot]

    # Token de secuencia (%04d, ####) antes de la version: no es parte del nombre.
    raw = re.sub(r"[_.](%0\d*d|#+)$", "", raw)

    matches = list(_VERSION_RE.finditer(raw))
    if not matches:
        return raw.lower() + "||" + extension
    last = matches[-1]
    return raw[: last.start()].lower() + "|" + raw[last.end():].lower() + "|" + extension


def _ordered_unique(versions):
    cleaned = []
    for version in versions or []:
        try:
            cleaned.append(int(version))
        except (TypeError, ValueError):
            continue
    return sorted(set(cleaned))


def split_into_branches(versions, branch_gap=BRANCH_GAP):
    """Parte la lista en ramas. Devuelve lista de listas ascendentes."""
    branches = []
    for version in _ordered_unique(versions):
        if not branches or version - branches[-1][-1] >= branch_gap:
            branches.append([version])
        else:
            branches[-1].append(version)
    return branches


def branch_heads(versions, branch_gap=BRANCH_GAP):
    """Ultima version de cada rama, de rama menor a mayor."""
    return [branch[-1] for branch in split_into_branches(versions, branch_gap)]


def latest_versions_per_branch(versions, count_per_branch, branch_gap=BRANCH_GAP):
    """Set con las ultimas N versiones de cada rama (retencion / descarga)."""
    kept = set()
    try:
        count = int(count_per_branch)
    except (TypeError, ValueError):
        return kept
    if count <= 0:
        return kept
    for branch in split_into_branches(versions, branch_gap):
        kept.update(branch[max(0, len(branch) - count):])
    return kept


def branch_containing(versions, version, branch_gap=BRANCH_GAP):
    """La rama (lista de versiones) donde cae `version`, incluyendola.

    `version` se suma a la lista antes de partir: si el clip esta en una
    version que la fuente consultada todavia no tiene, igual queda ubicado
    en su rama en vez de devolver vacio. Efecto lateral asumido: una
    version intermedia puede unir dos bloques que sin ella quedaban
    separados (v001, v030, v060 = una sola rama), igual que en PipeSync,
    porque la regla mira la lista completa de versiones reales.
    """
    target = extract_version_number(version) if isinstance(version, str) else version
    try:
        target = int(target)
    except (TypeError, ValueError):
        return []

    for branch in split_into_branches(list(versions or []) + [target], branch_gap):
        if target in branch:
            return branch
    return []


def head_of_branch_containing(versions, version, branch_gap=BRANCH_GAP):
    """Cabeza de la rama de `version`. Es el reemplazo de max(versions)
    en todo lo que decide una accion: nunca cruza de rama."""
    branch = branch_containing(versions, version, branch_gap)
    if not branch:
        try:
            return int(version)
        except (TypeError, ValueError):
            return -1
    return branch[-1]


def has_branches(versions, branch_gap=BRANCH_GAP):
    """True si la familia tiene mas de una rama."""
    return len(split_into_branches(versions, branch_gap)) > 1


def branch_label(branch):
    """Etiqueta de una rama por su bloque de centena: 'v000', 'v100', 'v200'.

    Es como se las nombra en produccion ("la rama 0", "la rama 100") y,
    mas importante, es ESTABLE entre fuentes: si Flow conoce v100..v103 y
    Wasabi solo v103, las dos siguen siendo la rama v100. Etiquetar por la
    primera version observada las haria aparecer como ramas distintas
    segun quien conteste.

    La desambiguacion cuando dos ramas caen en la misma centena la hace
    _assign_labels() sobre el conjunto completo.
    """
    if not branch:
        return "v?"
    return format_version((branch[0] // 100) * 100)


def _assign_labels(branches):
    """Etiquetas unicas para un conjunto de ramas.

    Normalmente es la centena; si dos ramas comparten centena (por ejemplo
    v001 y v060, que la regla de 50 separa), las colisionadas pasan a
    etiquetarse por su arranque real.
    """
    labels = [branch_label(branch) for branch in branches]
    positions = {}
    for index, label in enumerate(labels):
        positions.setdefault(label, []).append(index)
    for indexes in positions.values():
        if len(indexes) > 1:
            for index in indexes:
                labels[index] = format_version(branches[index][0])
    return labels


def describe_branches(versions, branch_gap=BRANCH_GAP):
    """Lista de dicts por rama, para UI y tooltips.

    Cada dict: {'label', 'start', 'head', 'versions'}.
    """
    branches = split_into_branches(versions, branch_gap)
    labels = _assign_labels(branches)
    described = []
    for branch, label in zip(branches, labels):
        described.append(
            {
                "label": label,
                "start": branch[0],
                "head": branch[-1],
                "versions": list(branch),
            }
        )
    return described


def compare_branches(
    remote_versions,
    local_versions=None,
    current_version=None,
    branch_gap=BRANCH_GAP,
):
    """Compara una fuente remota contra lo que hay local, rama por rama.

    Es la primitiva de "¿que hay nuevo y donde?": la usa el Pull (Flow vs
    NKS) y el Download Clip (Wasabi vs disco). Las ramas se parten sobre la
    union de las tres entradas, asi una version que solo existe en un lado
    igual queda ubicada.

    Devuelve una lista de dicts, uno por rama:
      label, start, versions, remote_head, local_head,
      is_current_branch, has_news
    `has_news` es True cuando la cabeza remota de esa rama esta por encima
    de la local (o no hay nada local de esa rama).
    """
    remote_set = set(_ordered_unique(remote_versions))
    local_set = set(_ordered_unique(local_versions))

    universe = list(remote_set | local_set)
    current = None
    if current_version is not None:
        try:
            current = int(current_version)
            universe.append(current)
        except (TypeError, ValueError):
            current = None

    branches = split_into_branches(universe, branch_gap)
    labels = _assign_labels(branches)
    compared = []
    for branch, label in zip(branches, labels):
        members = set(branch)
        remote_in = sorted(v for v in remote_set if v in members)
        # El clip cuenta como local: es media que ya tenemos.
        local_in = sorted(v for v in local_set if v in members)
        if current is not None and current in members and current not in local_in:
            local_in.append(current)
            local_in.sort()

        remote_head = remote_in[-1] if remote_in else None
        local_head = local_in[-1] if local_in else None
        compared.append(
            {
                "label": label,
                "start": branch[0],
                "versions": list(branch),
                "remote_versions": remote_in,
                "local_versions": local_in,
                "remote_head": remote_head,
                "local_head": local_head,
                "is_current_branch": current is not None and current in members,
                "has_news": remote_head is not None
                and (local_head is None or remote_head > local_head),
            }
        )
    return compared


def group_by_family(names):
    """Agrupa nombres por familia. Devuelve {family_key: [(version, name)]}.

    Los nombres sin token de version se descartan: no participan de ramas.
    """
    groups = {}
    for name in names or []:
        version = extract_version_number(name)
        if version < 0:
            continue
        groups.setdefault(family_key(name), []).append((version, name))
    for entries in groups.values():
        entries.sort(key=lambda pair: pair[0])
    return groups
