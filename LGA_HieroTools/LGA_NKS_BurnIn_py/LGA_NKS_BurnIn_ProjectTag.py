"""
____________________________________________________________________

  LGA_NKS_BurnIn_ProjectTag v1.00 | Lega

  Lectura y escritura del override de config de LGA_BurnIn que viaja
  dentro del proyecto: un tag LGA_BurnIn_Settings en el tagsBin() del
  proyecto, con el JSON en la key tag.lga_burnin_config (las keys de
  metadata de tags DEBEN empezar con "tag.", lo exige Hiero).

  El tag NO lo toca el Clean Project del Edit Panel (ese solo borra
  BinItems sin uso, nunca tags), y se serializa en el .hrox, asi que
  los settings acompanan al proyecto cuando se lo manda a otra persona.

  v1.00: Version inicial.
____________________________________________________________________
"""

import json

import LGA_NKS_BurnIn_Config as bi_config


def _find_tag(project):
    """Busca el tag de settings en el tagsBin del proyecto. None si no esta."""
    import hiero.core

    stack = [project.tagsBin()]
    while stack:
        bin_obj = stack.pop()
        for item in bin_obj.items():
            if isinstance(item, hiero.core.Bin):
                stack.append(item)
            elif isinstance(item, hiero.core.Tag):
                if item.name() == bi_config.PROJECT_TAG_NAME:
                    return item
    return None


def find_project(project_name):
    """Proyecto abierto con ese nombre exacto, o None."""
    import hiero.core

    for proj in hiero.core.projects():
        if proj.name() == project_name:
            return proj
    return None


def read_config_json(project):
    """JSON crudo guardado en el tag del proyecto, o None si no hay."""
    if project is None:
        return None
    tag = _find_tag(project)
    if tag is None:
        return None
    md = tag.metadata()
    if md.hasKey(bi_config.PROJECT_TAG_KEY):
        return md.value(bi_config.PROJECT_TAG_KEY)
    return None


def write_config(project, cfg_dict):
    """Escribe el dict de overrides al tag del proyecto (lo crea si no esta).

    No guarda el proyecto: el .hrox se persiste cuando el usuario guarda.
    Devuelve error o None.
    """
    import hiero.core

    if project is None:
        return "No hay proyecto para escribir el tag"
    try:
        tag = _find_tag(project)
        if tag is None:
            tag = hiero.core.Tag(bi_config.PROJECT_TAG_NAME)
            project.tagsBin().addItem(tag)
        tag.metadata().setValue(
            bi_config.PROJECT_TAG_KEY,
            json.dumps(cfg_dict, ensure_ascii=False, sort_keys=True),
        )
        return None
    except Exception as exc:
        return "No se pudo escribir el tag del proyecto: {}".format(exc)


def remove_config(project):
    """Borra el tag de settings del proyecto si existe. Devuelve error o None."""
    if project is None:
        return "No hay proyecto"
    try:
        tag = _find_tag(project)
        if tag is None:
            return None
        parent = tag.parentBin()
        if parent is not None:
            parent.removeItem(tag)
        return None
    except Exception as exc:
        return "No se pudo borrar el tag del proyecto: {}".format(exc)
