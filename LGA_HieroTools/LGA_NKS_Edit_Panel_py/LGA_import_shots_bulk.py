"""
____________________________________________________________________

  LGA_import_shots_bulk v1.00 | Lega

  Bulk Import: importar varios shots al timeline en una sola operacion,
  en orden alfabetico, como si se importaran uno por uno.

  v1.00: Browser Qt con seleccion multiple de carpetas y simulacion del
         layout final para el preview combinado del Bulk Import.

  - pick_shot_folders(): browser Qt no-nativo con multi-seleccion de carpetas.
  - simulate_bulk_layout(): simula donde caera cada shot nuevo en el timeline
                            final (para el preview combinado), sin tocarlo.

  La UI y la ejecucion viven en LGA_import_shots.py para reutilizar directamente
  las reglas y widgets de ImportShotDialog sin duplicarlos.

  Modulo puro: no depende de hiero.core directamente. El caller pasa los shots
  existentes (ya recolectados con _collect_timeline_shots) y los shots nuevos.

  Documentacion: docs/LGA_import_shots_bulk_PLAN.md
____________________________________________________________________
"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore


# ── Logger inyectable (mismo patron que los demas modulos auxiliares) ──────────
def _default_print(*args, **kwargs):
    pass


debug_print = _default_print


def set_debug_print(fn):
    """El script principal inyecta su debug_print para unificar el logging."""
    global debug_print
    debug_print = fn


# ══════════════════════════════════════════════════════════════════
#  Browser multi-select de carpetas
# ══════════════════════════════════════════════════════════════════

def pick_shot_folders(initial_dir="", parent=None):
    """
    Abre un QFileDialog NO-nativo que permite seleccionar varias carpetas con
    Shift/Ctrl. El dialogo nativo de Windows no soporta multi-seleccion de
    carpetas; por eso se fuerza DontUseNativeDialog y ExtendedSelection en las
    vistas internas (QListView/QTreeView).

    Retorna lista de rutas (str, con forward slashes). Lista vacia si se cancela.
    """
    dlg = QtWidgets.QFileDialog(parent)
    dlg.setWindowTitle("Seleccionar carpeta(s) de shot — Shift/Ctrl para varias")
    dlg.setFileMode(QtWidgets.QFileDialog.Directory)
    dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
    dlg.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
    if initial_dir:
        dlg.setDirectory(initial_dir)

    # Forzar multi-seleccion en las vistas internas del dialogo Qt.
    try:
        list_view = dlg.findChild(QtWidgets.QListView, "listView")
        if list_view is not None:
            list_view.setSelectionMode(
                QtWidgets.QAbstractItemView.ExtendedSelection
            )
    except Exception as exc:
        debug_print("pick_shot_folders: no se pudo setear listView → %s" % exc,
                    level="warning")
    try:
        tree_view = dlg.findChild(QtWidgets.QTreeView)
        if tree_view is not None:
            tree_view.setSelectionMode(
                QtWidgets.QAbstractItemView.ExtendedSelection
            )
    except Exception as exc:
        debug_print("pick_shot_folders: no se pudo setear treeView → %s" % exc,
                    level="warning")

    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        debug_print("pick_shot_folders: cancelado")
        return []

    # selectedFiles() no siempre conserva la seleccion extendida en PySide.
    # Completarla leyendo los selectionModel de ambas vistas internas.
    selected_paths = list(dlg.selectedFiles())
    for view_type in (QtWidgets.QListView, QtWidgets.QTreeView):
        for view in dlg.findChildren(view_type):
            try:
                model = view.model()
                for index in view.selectionModel().selectedRows(0):
                    path = model.filePath(index)
                    if path:
                        selected_paths.append(path)
            except Exception:
                continue

    folders = []
    for p in selected_paths:
        norm = p.replace("\\", "/").rstrip("/")
        if norm and QtCore.QFileInfo(norm).isDir() and norm not in folders:
            folders.append(norm)
    debug_print("pick_shot_folders: %d carpeta(s) → %s" % (len(folders), folders))
    return folders


# ══════════════════════════════════════════════════════════════════
#  Simulacion del layout combinado
# ══════════════════════════════════════════════════════════════════

def simulate_bulk_layout(existing_shots, new_shots):
    """
    Simula la insercion de varios shots nuevos en el timeline, en orden
    alfabetico, espejando el comportamiento de _find_insert_frame +
    push_clips_right a nivel de shot-master.

    Parametros
    ----------
    existing_shots : list[dict]
        Shots ya en el timeline. Cada uno: {shot_name, timeline_in, timeline_out}.
        (Tipicamente la salida de _collect_timeline_shots).
    new_shots : list[dict]
        Shots a importar. Cada uno debe tener al menos:
        {shot_name, max_frames}. Cualquier otra clave se preserva en el retorno.

    Retorno
    -------
    dict con:
      "placements": list[dict] (una por shot nuevo, en orden alfabetico) con:
          shot_name, max_frames, insert_frame, tl_in, tl_out,
          prev_shot_name, next_shot_name, (+ las claves originales del new_shot)
      "range": dict con el rango acotado del preview combinado:
          first_frame, last_frame  (min tl_in .. max tl_out de los shots nuevos)
      "final_shots": list[dict] (todos los shots — existentes + nuevos — con su
          tl_in/tl_out final, ordenados por tl_in). Cada uno marca is_new=bool.
    """
    # Estado simulado del timeline: copia mutable de los existentes.
    placed = []
    for s in existing_shots:
        placed.append({
            "shot_name": s["shot_name"],
            "tl_in":     int(s["timeline_in"]),
            "tl_out":    int(s["timeline_out"]),
            "is_new":    False,
        })

    # Ordenar los nuevos alfabeticamente (mismo criterio que _find_insert_frame).
    new_sorted = sorted(new_shots, key=lambda x: x["shot_name"].lower())

    placements = []

    for new in new_sorted:
        name = new["shot_name"]
        dur = int(new.get("max_frames") or 0)
        if dur <= 0:
            dur = 100  # fallback identico a main() cuando no hay EXR todavia

        # Posicion alfabetica entre los shots ya colocados.
        placed_alpha = sorted(placed, key=lambda x: x["shot_name"].lower())

        insert_before = None
        for s in placed_alpha:
            if name.lower() < s["shot_name"].lower():
                insert_before = s
                break

        if not placed_alpha:
            # Timeline vacio: el primer shot arranca en 0.
            insert_frame = 0
        elif insert_before is None:
            # Va al final: despues del ultimo clip de todo el timeline simulado.
            insert_frame = max(s["tl_out"] for s in placed) + 1
        else:
            # Va antes de insert_before: ocupa su posicion actual y empuja.
            insert_frame = insert_before["tl_in"]

        tl_in = insert_frame
        tl_out = insert_frame + dur - 1

        # Empujar todos los shots que arrancan en/despues de insert_frame.
        if insert_before is not None:
            for s in placed:
                if s["tl_in"] >= insert_frame:
                    s["tl_in"] += dur
                    s["tl_out"] += dur

        placed.append({
            "shot_name": name,
            "tl_in":     tl_in,
            "tl_out":    tl_out,
            "is_new":    True,
        })

        placements.append({
            **new,
            "shot_name":   name,
            "max_frames":  dur,
            "insert_frame": insert_frame,
            "tl_in":        tl_in,
            "tl_out":       tl_out,
            "prev_shot_name": None,   # se completa abajo
            "next_shot_name": None,
        })

    # Completar prev/next por adyacencia alfabetica en el conjunto final.
    final_alpha = sorted(placed, key=lambda x: x["shot_name"].lower())
    names_alpha = [s["shot_name"] for s in final_alpha]
    for pl in placements:
        try:
            idx = names_alpha.index(pl["shot_name"])
        except ValueError:
            continue
        pl["prev_shot_name"] = names_alpha[idx - 1] if idx > 0 else None
        pl["next_shot_name"] = (
            names_alpha[idx + 1] if idx < len(names_alpha) - 1 else None
        )

    # Rango acotado del preview (solo shots nuevos).
    if placements:
        first_frame = min(pl["tl_in"] for pl in placements)
        last_frame = max(pl["tl_out"] for pl in placements)
    else:
        first_frame, last_frame = 0, 0

    final_shots = sorted(placed, key=lambda x: x["tl_in"])

    debug_print(
        "simulate_bulk_layout: %d nuevos | rango %d-%d" % (
            len(placements), first_frame, last_frame)
    )
    for pl in placements:
        debug_print(
            "  · %s → insert_frame=%d tl=%d-%d (prev=%s next=%s)" % (
                pl["shot_name"], pl["insert_frame"], pl["tl_in"], pl["tl_out"],
                pl["prev_shot_name"] or "-", pl["next_shot_name"] or "-")
        )

    return {
        "placements": placements,
        "range": {"first_frame": first_frame, "last_frame": last_frame},
        "final_shots": final_shots,
    }
