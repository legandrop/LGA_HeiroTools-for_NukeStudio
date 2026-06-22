"""
____________________________________________________________________

  LGA_import_shots_bulk v1.02 | Lega

  Bulk Import: importar varios shots al timeline en una sola operacion,
  en orden alfabetico, como si se importaran uno por uno.

  v1.02: Sidebar muestra rutas T:/VFX-* y N:/VFX-*; columnas Type y Date
         Modified ajustan ancho por contenido con mínimos configurables.
  v1.01: Browser mas grande, seleccion gris configurable y sidebar ampliado
         con accesos VFX-* detectados en las raices T: y N:.
  v1.00: Browser Qt con seleccion multiple de carpetas y simulacion del
         layout final para el preview combinado del Bulk Import.
         Fix follow-up: expone la carpeta actual del browser al confirmar para
         persistirla en settings (evita reabrir dentro del shot seleccionado).

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


# ✅✅💾⚠️ Color de selección de carpetas en el browser.
SHOT_BROWSER_SELECTION_BG_COLOR = "#b4b4b4"
SHOT_BROWSER_SELECTION_TEXT_COLOR = "#202020"

# ✅✅💾⚠️ Tamaño inicial del browser de selección.
SHOT_BROWSER_WIDTH = 900
SHOT_BROWSER_HEIGHT = 760

# ✅✅💾⚠️ Ancho fijo del panel izquierdo de shortcuts.
SHOT_BROWSER_SIDEBAR_WIDTH = 175

# ✅✅💾⚠️ Anchos mínimos de columnas del browser.
SHOT_BROWSER_TYPE_COLUMN_MIN_WIDTH = 130
SHOT_BROWSER_DATE_COLUMN_MIN_WIDTH = 175


# ── Logger inyectable (mismo patron que los demas modulos auxiliares) ──────────
def _default_print(*args, **kwargs):
    pass


debug_print = _default_print
_last_browser_directory = ""


def set_debug_print(fn):
    """El script principal inyecta su debug_print para unificar el logging."""
    global debug_print
    debug_print = fn


def get_last_browser_directory():
    """Último directorio visible en el browser al aceptar selección."""
    return _last_browser_directory


class _ShotBrowserSidebarDelegate(QtWidgets.QStyledItemDelegate):
    """Conserva iconos y muestra shortcuts VFX como `T:/VFX-MOR`."""

    def __init__(self, labels_by_path, parent=None):
        super(_ShotBrowserSidebarDelegate, self).__init__(parent)
        self._labels_by_path = labels_by_path

    @staticmethod
    def _index_url(index):
        # QUrlModel usa Qt.UserRole + 1 para la URL en QFileDialog no nativo.
        value = index.data(QtCore.Qt.UserRole + 1)
        if isinstance(value, QtCore.QUrl):
            return value
        if value:
            try:
                return QtCore.QUrl(value)
            except Exception:
                pass
        return None

    def initStyleOption(self, option, index):
        super(_ShotBrowserSidebarDelegate, self).initStyleOption(option, index)
        url = self._index_url(index)
        if url is None:
            return
        path = url.toLocalFile().replace("\\", "/").rstrip("/").lower()
        label = self._labels_by_path.get(path)
        if label:
            option.text = label


def _discover_vfx_sidebar_urls():
    """Retorna (urls, labels) para carpetas VFX-* de T:/ y N:/."""
    urls = []
    labels = {}
    for drive in ("T:", "N:"):
        root_path = drive + "/"
        root_info = QtCore.QFileInfo(root_path)
        if not root_info.exists() or not root_info.isDir():
            debug_print("Shot browser sidebar: drive %s no disponible" % drive)
            continue
        root = QtCore.QDir(root_path)
        infos = root.entryInfoList(
            ["VFX-*"],
            QtCore.QDir.Dirs | QtCore.QDir.NoDotAndDotDot,
            QtCore.QDir.Name | QtCore.QDir.IgnoreCase,
        )
        for info in infos:
            path = info.absoluteFilePath().replace("\\", "/").rstrip("/")
            url = QtCore.QUrl.fromLocalFile(path)
            urls.append(url)
            labels[path.lower()] = "%s/%s" % (drive, info.fileName())
    return urls, labels


def _configure_shot_browser_sidebar(dlg, labels_by_path):
    """Aplica el ancho fijo configurable al sidebar de shortcuts."""
    sidebar = dlg.findChild(QtWidgets.QListView, "sidebar")
    if sidebar is None:
        debug_print("Shot browser sidebar: QListView 'sidebar' no encontrado",
                    level="warning")
        return

    current_width = max(1, int(sidebar.width()))
    target_width = max(1, int(SHOT_BROWSER_SIDEBAR_WIDTH))
    sidebar.setMinimumWidth(target_width)
    sidebar.setMaximumWidth(target_width)
    delegate = _ShotBrowserSidebarDelegate(labels_by_path, sidebar)
    sidebar.setItemDelegate(delegate)
    # Mantener referencia explícita por compatibilidad con bindings viejos.
    sidebar._lga_sidebar_delegate = delegate
    debug_print(
        "Shot browser sidebar: current_w=%d configured_w=%d shortcuts=%d"
        % (current_width, target_width, len(labels_by_path))
    )


def _configure_shot_browser_columns(dlg):
    """Autoajusta Type/Date Modified y aplica mínimos para evitar recortes."""
    tree = dlg.findChild(QtWidgets.QTreeView, "treeView")
    if tree is None:
        # Fallback: el tree principal suele ser el único con varias columnas.
        for candidate in dlg.findChildren(QtWidgets.QTreeView):
            if candidate.model() is not None and candidate.model().columnCount() > 1:
                tree = candidate
                break
    if tree is None or tree.model() is None:
        debug_print("Shot browser columns: treeView no encontrado", level="warning")
        return

    model = tree.model()
    configured = []
    for column in range(model.columnCount()):
        header_text = str(
            model.headerData(column, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
            or ""
        ).strip()
        normalized = header_text.lower()
        minimum = None
        if normalized in ("type", "tipo"):
            minimum = SHOT_BROWSER_TYPE_COLUMN_MIN_WIDTH
        elif (
            "date modified" in normalized
            or "modified" in normalized
            or "fecha de modificación" in normalized
            or "fecha de modificacion" in normalized
        ):
            minimum = SHOT_BROWSER_DATE_COLUMN_MIN_WIDTH
        if minimum is None:
            continue

        tree.resizeColumnToContents(column)
        content_width = int(tree.columnWidth(column))
        header_width = int(
            tree.fontMetrics().horizontalAdvance(header_text)
        ) + 28
        target = max(minimum, content_width, header_width)
        tree.setColumnWidth(column, target)
        configured.append(
            "%s[col=%d content=%d header=%d min=%d target=%d]"
            % (header_text, column, content_width, header_width, minimum, target)
        )

    debug_print(
        "Shot browser columns: %s"
        % (" | ".join(configured) if configured else "Type/Date no detectadas")
    )


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
    dlg.resize(SHOT_BROWSER_WIDTH, SHOT_BROWSER_HEIGHT)
    dlg.setStyleSheet(
        dlg.styleSheet()
        + """
        QListView::item:selected,
        QTreeView::item:selected {
            background-color: %s;
            color: %s;
        }
        QListView::item:selected:!active,
        QTreeView::item:selected:!active {
            background-color: %s;
            color: %s;
        }
        """
        % (
            SHOT_BROWSER_SELECTION_BG_COLOR,
            SHOT_BROWSER_SELECTION_TEXT_COLOR,
            SHOT_BROWSER_SELECTION_BG_COLOR,
            SHOT_BROWSER_SELECTION_TEXT_COLOR,
        )
    )
    if initial_dir:
        dlg.setDirectory(initial_dir)

    # Mantener los shortcuts estándar y sumar proyectos VFX de T:/ y N:/.
    vfx_urls, sidebar_labels = _discover_vfx_sidebar_urls()
    sidebar_urls = list(dlg.sidebarUrls())
    seen_urls = {
        url.toString().lower()
        for url in sidebar_urls
    }
    for url in vfx_urls:
        key = url.toString().lower()
        if key not in seen_urls:
            sidebar_urls.append(url)
            seen_urls.add(key)
    dlg.setSidebarUrls(sidebar_urls)

    # El ancho real del sidebar solo está disponible después del primer layout.
    QtCore.QTimer.singleShot(
        0, lambda: _configure_shot_browser_sidebar(dlg, sidebar_labels)
    )
    # Primer layout + carga inicial del QFileSystemModel. Dos pasadas cubren
    # tanto el header inmediato como contenido que aparece de forma asíncrona.
    QtCore.QTimer.singleShot(0, lambda: _configure_shot_browser_columns(dlg))
    QtCore.QTimer.singleShot(350, lambda: _configure_shot_browser_columns(dlg))
    debug_print(
        "Shot browser: requested_size=%dx%d selection_bg=%s selection_text=%s "
        "sidebar_urls=%d vfx_shortcuts=%d labels=%s type_min=%d date_min=%d"
        % (
            SHOT_BROWSER_WIDTH,
            SHOT_BROWSER_HEIGHT,
            SHOT_BROWSER_SELECTION_BG_COLOR,
            SHOT_BROWSER_SELECTION_TEXT_COLOR,
            len(sidebar_urls),
            len(vfx_urls),
            sorted(sidebar_labels.values()),
            SHOT_BROWSER_TYPE_COLUMN_MIN_WIDTH,
            SHOT_BROWSER_DATE_COLUMN_MIN_WIDTH,
        )
    )

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

    global _last_browser_directory
    try:
        _last_browser_directory = (
            dlg.directory().absolutePath().replace("\\", "/").rstrip("/")
        )
    except Exception as exc:
        _last_browser_directory = ""
        debug_print(
            "pick_shot_folders: no se pudo leer current dir → %s" % exc,
            level="warning",
        )

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
    debug_print(
        "pick_shot_folders: %d carpeta(s) current_dir='%s' → %s"
        % (len(folders), _last_browser_directory or "", folders)
    )
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
