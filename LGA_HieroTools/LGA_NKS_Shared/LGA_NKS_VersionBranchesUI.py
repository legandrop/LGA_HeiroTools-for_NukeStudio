"""
____________________________________________________________________

  LGA_NKS_VersionBranchesUI v1.00 | Lega

  Capa de presentacion de las ramas de versiones: icono, colores y
  textos. La logica de ramas vive en LGA_NKS_VersionBranching.py; aca
  solo esta como se muestran.

  El icono es el mismo SVG que usa PipeSync en el VersionsWidget, y los
  colores son los mismos tres: verde = cabeza de su rama, rojo = atras
  dentro de su rama, gris = rama sin conflicto. Que las dos apps se vean
  igual es el punto: son los mismos shots.

  Los textos salen de TOOLTIPS[idioma] y no del widget, para que la
  migracion a tooltips bilingues sea un cambio de datos.

  v1.00: Version inicial.
____________________________________________________________________
"""

import os

from LGA_QtAdapter_HieroTools import svg_icon, svg_pixmap


# Mismos colores que statusColor() en VersionsWidget.cpp de PipeSync.
BRANCH_COLOR_CONFLICT = "#F44336"  # atras dentro de su propia rama
BRANCH_COLOR_CURRENT = "#4CAF50"  # cabeza de su rama
BRANCH_COLOR_NEUTRAL = "#ADADAD"  # rama sin comparacion posible

_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
BRANCH_ICON_FILE = os.path.join(_ICONS_DIR, "version_branches.svg")

# Idioma de los tooltips. Unico lugar a tocar cuando se hagan bilingues.
LANGUAGE = "es"

TOOLTIPS = {
    "es": {
        "branches_title": "Este shot tiene {count} ramas de version",
        "branches_intro": (
            "Cada rama es un compositor trabajando el mismo shot por separado. "
            "La version mas alta de otra rama NO es tu proxima version."
        ),
        "branch_row": "Rama {label}",
        "no_head": "sin version en esta rama",
        "push_other_branches": (
            "Hay otras ramas mas arriba, pero no son tu rama: no bloquean el push."
        ),
        "pull_other_branch_row": (
            "Fila informativa: hay novedad en otra rama. El clip NO se movio."
        ),
        "download_pick_branch": (
            "Elegis que rama bajar. Con el numero o con el mouse; ESC cancela."
        ),
    }
}

# Cache de iconos por color: rasterizar el SVG en cada fila de una tabla
# es caro y el resultado no cambia.
_ICON_CACHE = {}


def tooltip(key, **kwargs):
    """Texto de tooltip por clave, ya formateado. Nunca hardcodear en el widget."""
    table = TOOLTIPS.get(LANGUAGE) or TOOLTIPS["es"]
    text = table.get(key, "")
    if not text:
        return ""
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return text


def branch_icon(color=BRANCH_COLOR_NEUTRAL, logical_size=16):
    """QIcon del SVG de ramas teñido. None si QtSvg no esta disponible."""
    cache_key = (str(color), int(logical_size))
    if cache_key not in _ICON_CACHE:
        _ICON_CACHE[cache_key] = svg_icon(
            BRANCH_ICON_FILE, logical_size=logical_size, color=color
        )
    return _ICON_CACHE[cache_key]


def branch_pixmap(color=BRANCH_COLOR_NEUTRAL, logical_size=16):
    """QPixmap del SVG de ramas teñido. None si QtSvg no esta disponible."""
    return svg_pixmap(BRANCH_ICON_FILE, logical_size=logical_size, color=color)


def _cell(text, color=None):
    if color:
        return "<span style='color:{0}'>{1}</span>".format(color, text)
    return str(text)


def branches_tooltip_html(branches, intro_key="branches_intro"):
    """Tooltip HTML con una fila por rama y sus fuentes.

    branches: lista de dicts
      {'label': 'v100', 'cells': [('NKS', 'v103', '#4CAF50'), ('Flow', 'v103', None)]}
    """
    if not branches:
        return ""

    rows = [
        "<div style='padding:8px 12px'>",
        "<div style='color:#E8E8E8'><b>{0}</b></div>".format(
            tooltip("branches_title", count=len(branches))
        ),
        "<div style='color:#888888'>{0}</div><br>".format(tooltip(intro_key)),
        "<table cellspacing='0' cellpadding='0'>",
    ]

    for branch in branches:
        rows.append(
            "<tr><td colspan='4'><span style='color:#E8E8E8'><b>{0}</b></span></td></tr>".format(
                tooltip("branch_row", label=branch.get("label", "v?"))
            )
        )
        cells = branch.get("cells") or []
        row = ["<tr>"]
        for source, value, color in cells:
            row.append(
                "<td width='46'><span style='color:#ADADAD'>{0}</span></td>"
                "<td width='60'>{1}</td>".format(source, _cell(value, color))
            )
        row.append("</tr>")
        rows.append("".join(row))

    rows.append("</table></div>")
    return "".join(rows)
