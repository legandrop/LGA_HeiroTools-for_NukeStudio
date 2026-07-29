"""
____________________________________________________________________

  LGA_NKS_Wasabi_PolicyUnassign_CompletedShots v1.02 | Lega

  Limpia policies de Wasabi para shots ya entregados.

  v1.02: Titulo y botones de la ventana con los nombres nuevos de la cola:
         "Delivered" y "Delivery Apr".

  v1.01: Reconoce pubsh (OK for Delivery) como shot terminado, y pbshed por si
         quedo data vieja de erso, que lo usaba antes de pasar a check.
  v1.00: Version inicial.
____________________________________________________________________
"""

import json
import os
import sqlite3
import sys

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtGui, QtWidgets

QApplication = QtWidgets.QApplication
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QCheckBox = QtWidgets.QCheckBox
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QHeaderView = QtWidgets.QHeaderView
QWidget = QtWidgets.QWidget

Qt = QtCore.Qt
QRunnable = QtCore.QRunnable
Slot = QtCore.Slot
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
QObject = QtCore.QObject
QFont = QtGui.QFont

# Mantener el runtime Wasabi autocontenido dentro de Assignees.
current_dir = os.path.dirname(os.path.abspath(__file__))
startup_dir = os.path.dirname(os.path.dirname(__file__))
flow_shared_dir = os.path.join(startup_dir, "LGA_NKS_Shared")

sys.path.insert(0, current_dir)
sys.path.insert(0, flow_shared_dir)

from boto3 import Session
from SecureConfig_Reader import get_s3_credentials
from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_db_path
from wasabi_policy_utils import (
    get_existing_policy_document,
    manage_policy_versions,
    validate_and_repair_policy,
)

DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def get_db_path():
    return get_pipesync_db_path("pipesync.db")


def get_completed_shots_map():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        raise RuntimeError(f"No se encontró pipesync.db en: {db_path}")

    # Estados de shot que cuentan como terminado. Faltaba `pubsh` (OK for
    # Delivery). `pbshed` se acepta solo por data vieja: el Shot de erso lo usaba
    # como "entregado" hasta que se reemplazo por `check`, que es el que manda
    # PipeSync. Sin estos, en Client la ventana salia vacia.
    status_map = {
        "apr": "approved",
        "approved": "approved",
        "check": "delivery_checked",
        "delivery_checked": "delivery_checked",
        "pubsh": "ok_for_delivery",
        "approved_for_delivery": "ok_for_delivery",
        "pbshed": "delivered",
    }
    statuses = tuple(status_map.keys())

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        placeholders = ",".join(["?"] * len(statuses))
        query = f"""
            SELECT shot_name, shot_status
            FROM shots
            WHERE shot_status IN ({placeholders})
            ORDER BY shot_name
        """
        rows = cur.execute(query, statuses).fetchall()
        return {shot_name: status_map.get(status, status) for shot_name, status in rows}
    finally:
        conn.close()


def get_iam_client():
    access_key, secret_key, endpoint, region = get_s3_credentials()
    if not access_key or not secret_key:
        raise RuntimeError("No se pudieron obtener credenciales de Wasabi")

    session = Session()
    return session.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url="https://iam.wasabisys.com",
        region_name=region or "us-east-1",
    )


def iter_local_policies(iam_client):
    marker = None
    while True:
        kwargs = {"Scope": "Local"}
        if marker:
            kwargs["Marker"] = marker
        response = iam_client.list_policies(**kwargs)
        for policy in response.get("Policies", []):
            yield policy
        if not response.get("IsTruncated"):
            break
        marker = response.get("Marker")


def extract_shot_from_resource(resource_arn):
    if not isinstance(resource_arn, str):
        return None
    if not resource_arn.startswith("arn:aws:s3:::"):
        return None
    if "/" not in resource_arn:
        return None

    shot_candidate = resource_arn.rstrip("/").split("/")[-1]
    if shot_candidate == "*" or not shot_candidate:
        return None
    return shot_candidate


def extract_shot_from_prefix(prefix):
    if not isinstance(prefix, str):
        return None
    clean_prefix = prefix.strip()
    if not clean_prefix:
        return None
    clean_prefix = clean_prefix.rstrip("*").rstrip("/")
    if "/" not in clean_prefix:
        return None
    return clean_prefix.split("/")[-1]


def collect_policy_matches(iam_client, completed_shots_map):
    matches = {}
    for policy in iter_local_policies(iam_client):
        policy_name = policy.get("PolicyName", "")
        if not policy_name.endswith("_policy"):
            continue

        policy_arn = policy.get("Arn")
        if not policy_arn:
            continue

        try:
            policy_document = get_existing_policy_document(iam_client, policy_arn)
        except Exception as exc:
            debug_print(f"No se pudo leer {policy_name}: {exc}")
            continue

        if not policy_document:
            continue

        for statement in policy_document.get("Statement", []):
            if statement.get("Action") != "s3:*":
                continue

            resources = statement.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]

            for resource in resources:
                shot_name = extract_shot_from_resource(resource)
                if shot_name in completed_shots_map:
                    key = (policy_arn, shot_name)
                    matches[key] = {
                        "policy_name": policy_name,
                        "policy_arn": policy_arn,
                        "shot_name": shot_name,
                        "shot_status": completed_shots_map[shot_name],
                    }

    return sorted(
        matches.values(),
        key=lambda item: (item["policy_name"].lower(), item["shot_name"].lower()),
    )


def remove_shot_from_policy_document(policy_document, shot_name):
    modified = False
    if not policy_document:
        return policy_document, False

    new_policy = json.loads(json.dumps(policy_document))
    for statement in new_policy.get("Statement", []):
        action = statement.get("Action")

        if action == "s3:ListBucket":
            prefixes = (
                statement.get("Condition", {}).get("StringLike", {}).get("s3:prefix", [])
            )
            if not isinstance(prefixes, list):
                continue

            filtered_prefixes = []
            for prefix in prefixes:
                prefix_shot = extract_shot_from_prefix(prefix)
                if prefix_shot == shot_name:
                    modified = True
                    debug_print(f"Removiendo prefijo: {prefix}")
                else:
                    filtered_prefixes.append(prefix)

            if filtered_prefixes != prefixes:
                if "" not in filtered_prefixes:
                    filtered_prefixes.insert(0, "")
                statement["Condition"]["StringLike"]["s3:prefix"] = filtered_prefixes

        elif action == "s3:*":
            resources = statement.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]
            if not isinstance(resources, list):
                continue

            filtered_resources = []
            for resource in resources:
                resource_shot = extract_shot_from_resource(resource)
                if resource_shot == shot_name:
                    modified = True
                    debug_print(f"Removiendo recurso: {resource}")
                else:
                    filtered_resources.append(resource)

            if filtered_resources != resources:
                statement["Resource"] = filtered_resources

    new_policy = validate_and_repair_policy(new_policy)
    return new_policy, modified


class WorkerSignals(QObject):
    matches_ready = Signal(list)
    clean_finished = Signal(bool, str)
    error = Signal(str)


class ScanWorker(QRunnable):
    def __init__(self):
        super(ScanWorker, self).__init__()
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            completed = get_completed_shots_map()
            iam = get_iam_client()
            matches = collect_policy_matches(iam, completed)
            self.signals.matches_ready.emit(matches)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class CleanWorker(QRunnable):
    def __init__(self, selected_matches):
        super(CleanWorker, self).__init__()
        self.selected_matches = selected_matches
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            iam = get_iam_client()

            shots_by_policy = {}
            name_by_arn = {}
            for match in self.selected_matches:
                policy_arn = match["policy_arn"]
                shots_by_policy.setdefault(policy_arn, set()).add(match["shot_name"])
                name_by_arn[policy_arn] = match["policy_name"]

            updated_policies = 0
            cleaned_shots = 0

            for policy_arn, shots in shots_by_policy.items():
                policy_document = get_existing_policy_document(iam, policy_arn)
                if not policy_document:
                    continue

                policy_document = validate_and_repair_policy(policy_document)
                policy_modified = False
                modified_shot_count = 0

                for shot_name in sorted(shots):
                    policy_document, shot_modified = remove_shot_from_policy_document(
                        policy_document, shot_name
                    )
                    if shot_modified:
                        policy_modified = True
                        modified_shot_count += 1

                if not policy_modified:
                    continue

                if not manage_policy_versions(iam, policy_arn):
                    raise RuntimeError(
                        f"No se pudieron gestionar versiones de {name_by_arn.get(policy_arn, policy_arn)}"
                    )

                iam.create_policy_version(
                    PolicyArn=policy_arn,
                    PolicyDocument=json.dumps(policy_document),
                    SetAsDefault=True,
                )
                updated_policies += 1
                cleaned_shots += modified_shot_count

            self.signals.clean_finished.emit(
                True,
                f"Policies actualizadas: {updated_policies} | Shots limpiados: {cleaned_shots}",
            )
        except Exception as exc:
            self.signals.clean_finished.emit(False, str(exc))


class CompletedShotsPolicyWindow(QDialog):
    def __init__(self, parent=None):
        super(CompletedShotsPolicyWindow, self).__init__(parent)
        self.setWindowTitle("Wasabi Policy Cleanup - Delivered / Delivery Apr")
        self.setModal(False)
        self.setMinimumWidth(980)
        self.resize(980, 520)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._matches = []

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.status_label = QLabel()
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 8px; color: #CCCCCC;")
        font = QFont()
        font.setPointSize(10)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["", "Nombre de policy", "Nombre de shot", "Estado del shot"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)

        self.invert_button = QPushButton("Invertir selección")
        self.invert_button.setEnabled(False)
        self.invert_button.setStyleSheet(
            "QPushButton { background-color: #555555; color: #DDDDDD; border: none; padding: 6px 10px; }"
            "QPushButton:hover { background-color: #6b6b6b; }"
        )
        self.invert_button.clicked.connect(self.invert_selection)
        buttons_layout.addWidget(self.invert_button)

        self.select_approved_button = QPushButton("Seleccionar Delivery Apr")
        self.select_approved_button.setEnabled(False)
        self.select_approved_button.setStyleSheet(
            "QPushButton { background-color: #555555; color: #DDDDDD; border: none; padding: 6px 10px; }"
            "QPushButton:hover { background-color: #6b6b6b; }"
        )
        self.select_approved_button.clicked.connect(self.select_approved)
        buttons_layout.addWidget(self.select_approved_button)

        self.select_delivery_button = QPushButton("Seleccionar Delivered")
        self.select_delivery_button.setEnabled(False)
        self.select_delivery_button.setStyleSheet(
            "QPushButton { background-color: #555555; color: #DDDDDD; border: none; padding: 6px 10px; }"
            "QPushButton:hover { background-color: #6b6b6b; }"
        )
        self.select_delivery_button.clicked.connect(self.select_delivery_ok)
        buttons_layout.addWidget(self.select_delivery_button)

        buttons_layout.addStretch()

        self.clean_button = QPushButton("Limpiar policies")
        self.clean_button.setEnabled(False)
        self.clean_button.setStyleSheet(
            "QPushButton { background-color: #443a91; color: #FFFFFF; border: none; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #774dcb; }"
            "QPushButton:disabled { background-color: #2d2950; color: #999999; }"
        )
        self.clean_button.clicked.connect(self.clean_selected)
        buttons_layout.addWidget(self.clean_button)

    def show_scanning_message(self):
        self.status_label.setText(
            "<span style='color:#CCCCCC;'>Escaneando shots ya entregados en pipesync.db y buscando coincidencias en policies de Wasabi...</span>"
        )

    def _display_status_label(self, internal_status):
        labels = {
            "approved": "Delivery Apr",
            "delivery_checked": "Delivered",
            "ok_for_delivery": "OK for Delivery",
            "delivered": "Delivered",
        }
        return labels.get(internal_status, str(internal_status))

    def show_matches(self, matches):
        self._matches = matches
        self.table.setRowCount(0)

        if not matches:
            self.status_label.setText(
                "<span style='color:#CCCCCC;'>No se encontraron coincidencias entre shots completados y policies de Wasabi.</span>"
            )
            self.clean_button.setEnabled(False)
            self.invert_button.setEnabled(False)
            self.select_approved_button.setEnabled(False)
            self.select_delivery_button.setEnabled(False)
            return

        self.table.setRowCount(len(matches))
        for row, match in enumerate(matches):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 0, checkbox_container)

            policy_item = QTableWidgetItem(match["policy_name"])
            shot_item = QTableWidgetItem(match["shot_name"])
            status_item = QTableWidgetItem(
                self._display_status_label(match["shot_status"])
            )
            self.table.setItem(row, 1, policy_item)
            self.table.setItem(row, 2, shot_item)
            self.table.setItem(row, 3, status_item)

        self.status_label.setText(
            f"<span style='color:#6AB5CA;'>Coincidencias encontradas: {len(matches)}. Seleccioná los items a limpiar y presioná \"Limpiar policies\".</span>"
        )
        self.clean_button.setEnabled(True)
        self.invert_button.setEnabled(True)
        self.select_approved_button.setEnabled(True)
        self.select_delivery_button.setEnabled(True)

    def _iter_row_checkboxes(self):
        for row in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(row, 0)
            if not cell_widget:
                continue
            checkbox = cell_widget.findChild(QCheckBox)
            if checkbox:
                yield row, checkbox

    def invert_selection(self):
        for _, checkbox in self._iter_row_checkboxes():
            checkbox.setChecked(not checkbox.isChecked())

    def select_approved(self):
        for row, checkbox in self._iter_row_checkboxes():
            checkbox.setChecked(self._matches[row]["shot_status"] == "approved")

    def select_delivery_ok(self):
        for row, checkbox in self._iter_row_checkboxes():
            checkbox.setChecked(self._matches[row]["shot_status"] == "delivery_checked")

    def get_selected_matches(self):
        selected = []
        for row in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(row, 0)
            if not cell_widget:
                continue
            checkbox = cell_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                selected.append(self._matches[row])
        return selected

    def clean_selected(self):
        selected = self.get_selected_matches()
        if not selected:
            self.status_label.setText(
                "<span style='color:#C05050;'>No hay filas seleccionadas para limpiar.</span>"
            )
            return

        self.clean_button.setEnabled(False)
        self.status_label.setText(
            f"<span style='color:#CCCCCC;'>Limpiando líneas de policies para {len(selected)} coincidencias seleccionadas...</span>"
        )

        worker = CleanWorker(selected)
        worker.signals.clean_finished.connect(self.on_clean_finished)
        worker.signals.error.connect(self.on_error)
        QThreadPool.globalInstance().start(worker)

    def on_clean_finished(self, success, message):
        if success:
            self.status_label.setText(f"<span style='color:#00ff00;'>{message}</span>")
            # Refrescar resultados para mostrar estado real actual
            self.start_scan()
        else:
            self.status_label.setText(f"<span style='color:#C05050;'>{message}</span>")
            self.clean_button.setEnabled(True)

    def on_error(self, message):
        self.status_label.setText(f"<span style='color:#C05050;'>Error: {message}</span>")
        self.clean_button.setEnabled(True)

    def start_scan(self):
        self.clean_button.setEnabled(False)
        self.invert_button.setEnabled(False)
        self.select_approved_button.setEnabled(False)
        self.select_delivery_button.setEnabled(False)
        self.show_scanning_message()
        scan_worker = ScanWorker()
        scan_worker.signals.matches_ready.connect(self.show_matches)
        scan_worker.signals.error.connect(self.on_error)
        QThreadPool.globalInstance().start(scan_worker)


_window = None


def main():
    global _window
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    _window = CompletedShotsPolicyWindow()
    _window.show()
    _window.start_scan()


if __name__ == "__main__":
    main()
