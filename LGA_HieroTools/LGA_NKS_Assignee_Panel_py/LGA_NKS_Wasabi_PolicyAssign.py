"""
____________________________________________________________________

  LGA_NKS_Wasabi_PolicyAssign v1.00 | Lega

  v1.00
  - La carpeta del shot se detecta con is_shot_folder_name() de NamingUtils, que
    valida el vendor code contra la DB de PipeSync, y la secuencia pasa a ser su
    directorio padre. Antes se tomaban los segmentos 0 y 1 del prefijo, o sea por
    profundidad: cualquier clip que no colgara de <secuencia>/<shot> escribia la
    policy sobre un prefijo inexistente, sin error y sin acceso.

  v0.99
  - El nombre y el color del usuario se resuelven por wasabi_user contra la
    DB de PipeSync (tabla flow_users), en vez del JSON local.

  v0.98 (2026-07-21)
  - Propaga errores fail-closed del resolver de buckets con mensajes
    accionables por ruta al preparar la policy.

  v0.97 (2026-07-21)
  - Migra la resolución de bucket/proyecto a LGA_NKS_BucketResolver
    para respetar ProjectBucketOverrides por contexto.

  Crea y asigna políticas IAM de Wasabi basadas en rutas de clips seleccionados
____________________________________________________________________
"""

import os
import sys
import json
import hiero.core
import hiero.ui
# Importar compatibilidad Qt para Hiero Panels
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Shared.LGA_NKS_Flow_Users_Config import find_user_by_wasabi_user

# Reasignar clases para compatibilidad con código existente
QApplication = QtWidgets.QApplication
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton

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

import boto3
from boto3 import Session
from SecureConfig_Reader import get_s3_credentials
from LGA_NKS_BucketResolver import resolve_bucket_from_local_path

# La carpeta del shot se detecta por NOMBRE y no por profundidad de ruta. El helper
# central valida ademas el vendor code contra la DB de PipeSync, que es lo que el
# posicional no podia saber (naming PROYECTO_SEQ_SHOT_VENDOR). Si no se puede importar
# se cae al comportamiento viejo, que sirve mientras el shot este a profundidad 2.
try:
    from LGA_NKS_Flow_NamingUtils import (
        is_shot_folder_name,
        extract_project_name_from_path,
    )
except ImportError:
    is_shot_folder_name = None
    extract_project_name_from_path = None

# Configuracion
DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


# Clase de ventana de estado para mostrar progreso de políticas de Wasabi
class WasabiStatusWindow(QDialog):
    def __init__(self, user_name, user_color, parent=None):
        super(WasabiStatusWindow, self).__init__(parent)
        self.setWindowTitle("Wasabi Policy Status")
        self.setModal(False)  # Cambiar a no modal para evitar problemas
        self.setMinimumWidth(500)

        # Evitar que la ventana se cierre automáticamente
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        # Layout principal
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Etiqueta de estado inicial con formato HTML para múltiples colores
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setTextFormat(Qt.RichText)  # Habilitar formato HTML

        # Mensaje inicial - se actualizará con las rutas reales
        initial_message = (
            f"<div style='text-align: left;'>"
            f"<span style='color: #CCCCCC; '>Habilitando rutas en la policy del usuario </span>"
            f"<span style='color: #CCCCCC; background-color: {user_color}; '>{user_name}</span>"
            f"</div>"
        )

        font = QFont()
        font.setPointSize(10)
        self.status_label.setFont(font)
        self.status_label.setText(initial_message)
        self.status_label.setStyleSheet("padding: 10px;")

        layout.addWidget(self.status_label)

        # Etiqueta para mostrar las rutas que se están procesando
        self.paths_label = QLabel("")
        self.paths_label.setAlignment(Qt.AlignLeft)
        self.paths_label.setWordWrap(True)
        self.paths_label.setTextFormat(Qt.RichText)
        self.paths_label.setStyleSheet("padding: 10px;")
        layout.addWidget(self.paths_label)

        # Etiqueta para mensajes de resultado
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.result_label)

        # Espaciador
        layout.addStretch()

        # Botón de Close
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(
            False
        )  # Deshabilitado hasta que termine el procesamiento
        layout.addWidget(self.close_button)

    def update_paths(self, paths_info):
        """Actualiza la ventana con las rutas reales que se están procesando"""
        paths_html = "<div style='text-align: left;'>"

        for bucket_name, folder_path, subfolder_path in paths_info:
            bucket_path = f"{bucket_name}/{folder_path}/{subfolder_path}"
            paths_html += f"<span style='color: #6AB5CA; '>{bucket_path}</span><br>"

        paths_html += "</div>"
        self.paths_label.setText(paths_html)

    def show_processing_message(self):
        """Muestra el mensaje de procesamiento"""
        processing_html = (
            f"<span style='color: #CCCCCC; '>Procesando clips seleccionados...</span>"
        )
        self.result_label.setText(processing_html)
        self.result_label.setStyleSheet("padding: 10px;")

    def show_success(self, message):
        """Muestra mensaje de éxito en verde"""
        success_html = f"<span style='color: #00ff00; '>{message}</span>"
        self.result_label.setText(success_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.close_button.setEnabled(True)  # Habilitar botón de Close

    def show_error(self, message):
        """Muestra mensaje de error en rojo"""
        error_html = f"<span style='color: #C05050; '>{message}</span>"
        self.result_label.setText(error_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.close_button.setEnabled(True)  # Habilitar botón de Close

    def closeEvent(self, event):
        """
        Manejar el evento de cierre para evitar que se cierre automáticamente.
        Solo se cierra cuando el usuario hace clic en el botón Close o cuando ya terminó el procesamiento.
        """
        if not self.close_button.isEnabled():
            # Si el botón Close está deshabilitado, significa que aún está procesando
            # No permitir cerrar la ventana
            event.ignore()
        else:
            # Si el botón está habilitado, permitir cerrar
            event.accept()


# Clases para procesamiento en hilos
class WasabiWorkerSignals(QObject):
    paths_ready = Signal(list)  # Para enviar las rutas procesadas
    finished = Signal(bool, str)  # success, message
    error = Signal(str)


class WasabiWorker(QRunnable):
    def __init__(self, wasabi_user, status_window):
        super(WasabiWorker, self).__init__()
        self.wasabi_user = wasabi_user
        self.status_window = status_window
        self.signals = WasabiWorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print(
                f"=== Iniciando procesamiento para usuario: {self.wasabi_user} ==="
            )

            # Verificar credenciales de Wasabi desde SecureConfig
            access_key, secret_key, endpoint, region = get_s3_credentials()
            if not access_key or not secret_key:
                self.signals.error.emit(
                    "ERROR: No se pudieron obtener las credenciales de Wasabi desde SecureConfig."
                )
                return

            # Obtener rutas de clips seleccionados en Hiero
            file_paths = get_selected_clips_paths()
            if not file_paths:
                self.signals.error.emit(
                    "No se encontraron rutas de archivos para procesar."
                )
                return

            # Parsear todas las rutas
            paths_info = []
            parse_errors = []
            for file_path in file_paths:
                parsed = parse_path_for_policy(file_path)
                if parsed.get("ok"):
                    paths_info.append(parsed["value"])
                else:
                    parse_errors.append(parsed.get("error") or "Error desconocido de parseo")

            if not paths_info:
                first_error = parse_errors[0] if parse_errors else "No se pudieron parsear las rutas."
                self.signals.error.emit(first_error)
                return

            # Enviar las rutas para actualizar la ventana
            self.signals.paths_ready.emit(paths_info)

            # Crear y gestionar la policy
            create_and_manage_policy(self.wasabi_user, paths_info)

            # Si llegamos aquí, fue exitoso
            self.signals.finished.emit(
                True, f"Policy asignada exitosamente para {self.wasabi_user}"
            )

        except Exception as e:
            debug_print(f"Error en WasabiWorker: {e}")
            self.signals.error.emit(f"Error: {str(e)}")


def parse_path_for_policy(file_path):
    """
    Parsea la ruta del archivo para extraer bucket y carpetas para la policy.

    Args:
        file_path (str): Ruta completa del archivo

    Returns:
        dict: {"ok": bool, "value": tuple|None, "error": str}
    """
    try:
        resolution = resolve_bucket_from_local_path(file_path)
        if not resolution.get("ok"):
            error_message = resolution.get("error") or "No se pudo resolver bucket/prefix."
            debug_print(f"No se pudo resolver bucket/prefix: {error_message}")
            return {
                "ok": False,
                "value": None,
                "error": f"Ruta bloqueada por mapping inválido: {file_path} | {error_message}",
            }

        prefix_parts = list(resolution.get("prefix_parts") or [])
        if len(prefix_parts) < 2:
            message = "Ruta sin suficientes segmentos para folder/subfolder de policy"
            debug_print(message)
            return {
                "ok": False,
                "value": None,
                "error": f"{message}: {file_path}",
            }

        bucket_name = resolution.get("bucket", "")

        # La policy necesita `<secuencia>/<shot>`, y hasta v1.03 eso se tomaba como
        # `prefix_parts[0]` y `[1]`, o sea POSICIONAL: salia bien solo si el clip colgaba
        # exactamente de <proyecto>/<secuencia>/<shot>/... Con un clip suelto bajo la
        # secuencia, un .mov de referencia o una carpeta de supervision, el segundo
        # segmento no es el shot y la policy quedaba escrita sobre un prefijo que no
        # existe -sin ningun error: IAM acepta cualquier string-. El artista quedaba sin
        # acceso y la ventana decia que se habia asignado bien.
        #
        # Ahora el shot se busca POR NOMBRE de atras para adelante, y la secuencia es su
        # directorio padre. Es la misma regla que usa PipeSync, donde la secuencia nunca
        # se infiere del nombre del shot.
        shot_index = -1
        if is_shot_folder_name:
            project_name = (
                extract_project_name_from_path(file_path)
                if extract_project_name_from_path
                else None
            )
            for i in range(len(prefix_parts) - 1, -1, -1):
                if is_shot_folder_name(prefix_parts[i], project_name):
                    shot_index = i
                    break

        if shot_index >= 1:
            folder_path = prefix_parts[shot_index - 1]
            subfolder_path = prefix_parts[shot_index]
        elif len(prefix_parts) == 2 and os.path.splitext(prefix_parts[1])[1]:
            # El segundo segmento es un ARCHIVO, no una carpeta de shot: pasa con un clip
            # suelto colgado de la secuencia. El posicional escribia el prefijo
            # `<secuencia>/<archivo.mov>`, que no existe en el bucket: IAM lo acepta sin
            # chistar, la ventana decia "asignada exitosamente" y el artista se quedaba
            # sin acceso. Es mejor no asignar y decir por que.
            message = (
                "El clip no cuelga de una carpeta de shot, asi que no se puede saber "
                "que prefijo habilitar"
            )
            debug_print(f"{message}: {file_path}")
            return {"ok": False, "value": None, "error": f"{message}: {file_path}"}
        else:
            # Sin helper, o con un nombre de shot que no matchea ningun patron conocido
            # (por ejemplo los que llevan bloques de descripcion, limite documentado de
            # is_shot_folder_name). Se conserva el comportamiento historico, que es
            # correcto en la estructura estandar.
            folder_path = prefix_parts[0]
            subfolder_path = prefix_parts[1]
            if is_shot_folder_name:
                debug_print(
                    "No se reconocio ninguna carpeta de shot por nombre; se usa la "
                    f"profundidad de ruta: {folder_path}/{subfolder_path}"
                )

        debug_print(f"Bucket: {bucket_name}")
        debug_print(f"Carpeta: {folder_path}")
        debug_print(f"Subcarpeta: {subfolder_path}")

        return {"ok": True, "value": (bucket_name, folder_path, subfolder_path), "error": ""}

    except Exception as e:
        debug_print(f"Error parseando ruta: {e}")
        return {
            "ok": False,
            "value": None,
            "error": f"Error parseando ruta '{file_path}': {e}",
        }


def get_selected_clips_paths():
    """
    Obtiene las rutas de los clips seleccionados en Hiero.

    Returns:
        list: Lista de rutas de archivos
    """
    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay una secuencia activa.")
            return []

        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection()

        if len(selected_clips) == 0:
            debug_print("*** No hay clips seleccionados en la pista ***")
            return []

        paths = []
        for shot in selected_clips:
            if isinstance(shot, hiero.core.EffectTrackItem):
                continue

            # Obtener el file path del clip seleccionado
            file_path = (
                shot.source().mediaSource().fileinfos()[0].filename()
                if shot.source().mediaSource().fileinfos()
                else None
            )
            if file_path:
                paths.append(file_path)
                debug_print(f"Ruta encontrada: {file_path}")

        return paths

    except Exception as e:
        debug_print(f"Error obteniendo rutas de clips: {e}")
        return []


def get_existing_policy_document(iam_client, policy_arn):
    """
    Obtiene el documento de policy existente.

    Args:
        iam_client: Cliente IAM de boto3
        policy_arn (str): ARN de la policy

    Returns:
        dict: Documento de policy o None si no existe
    """
    try:
        # Obtener la version por defecto de la policy
        policy_response = iam_client.get_policy(PolicyArn=policy_arn)
        default_version_id = policy_response["Policy"]["DefaultVersionId"]

        # Obtener el documento de la version por defecto
        version_response = iam_client.get_policy_version(
            PolicyArn=policy_arn, VersionId=default_version_id
        )

        policy_document = version_response["PolicyVersion"]["Document"]
        debug_print(f"Policy existente obtenida correctamente")
        return policy_document

    except Exception as e:
        debug_print(f"Error obteniendo policy existente: {e}")
        return None


def manage_policy_versions(iam_client, policy_arn):
    """
    Gestiona las versiones de una policy, eliminando la mas antigua si hay 5 versiones.

    Args:
        iam_client: Cliente IAM de boto3
        policy_arn (str): ARN de la policy

    Returns:
        bool: True si se pudo gestionar correctamente, False en caso contrario
    """
    try:
        # Listar todas las versiones de la policy
        versions_response = iam_client.list_policy_versions(PolicyArn=policy_arn)
        versions = versions_response.get("Versions", [])

        debug_print(f"Policy tiene {len(versions)} versiones")

        # Si hay 5 versiones, necesitamos eliminar la mas antigua (que no sea la default)
        if len(versions) >= 5:
            # Filtrar versiones que no son la default
            non_default_versions = [
                v for v in versions if not v.get("IsDefaultVersion", False)
            ]

            if non_default_versions:
                # Ordenar por fecha de creacion (mas antigua primero)
                non_default_versions.sort(key=lambda x: x.get("CreateDate"))
                oldest_version = non_default_versions[0]

                debug_print(
                    f"Eliminando version mas antigua: {oldest_version['VersionId']}"
                )

                # Eliminar la version mas antigua
                iam_client.delete_policy_version(
                    PolicyArn=policy_arn, VersionId=oldest_version["VersionId"]
                )

                debug_print(
                    f"Version {oldest_version['VersionId']} eliminada correctamente"
                )
            else:
                debug_print("No hay versiones no-default para eliminar")
                return False

        return True

    except Exception as e:
        debug_print(f"Error gestionando versiones de policy: {e}")
        return False


def merge_policy_statements(existing_policy, new_bucket, new_folder, new_subfolder):
    """
    Combina una policy existente con nuevos permisos sin duplicar.

    Args:
        existing_policy (dict): Policy existente
        new_bucket (str): Nombre del bucket
        new_folder (str): Carpeta principal
        new_subfolder (str): Subcarpeta

    Returns:
        dict: Policy combinada
    """
    # Importar las funciones de validación desde wasabi_policy_utils
    from wasabi_policy_utils import validate_and_repair_policy

    # Validar y reparar la policy existente antes de modificarla
    debug_print("Validando policy existente antes de combinar...")
    existing_policy = validate_and_repair_policy(existing_policy)

    # Crear la nueva entrada que queremos agregar
    new_prefix = f"{new_folder}/"
    new_full_prefix = f"{new_folder}/{new_subfolder}/*"
    new_resource_base = f"arn:aws:s3:::{new_bucket}/{new_folder}/{new_subfolder}"
    new_resource_wildcard = f"arn:aws:s3:::{new_bucket}/{new_folder}/{new_subfolder}/*"

    # Buscar el statement de ListBucket para este bucket
    list_bucket_statement = None
    s3_action_statement = None

    for statement in existing_policy["Statement"]:
        if (
            statement.get("Action") == "s3:ListBucket"
            and statement.get("Resource") == f"arn:aws:s3:::{new_bucket}"
        ):
            list_bucket_statement = statement
        elif statement.get("Action") == "s3:*":
            # Verificar si tiene recursos válidos
            resources = statement.get("Resource", [])
            if isinstance(resources, list) and len(resources) > 0:
                s3_action_statement = statement

    # Actualizar el statement de ListBucket
    if list_bucket_statement:
        current_prefixes = (
            list_bucket_statement.get("Condition", {})
            .get("StringLike", {})
            .get("s3:prefix", [])
        )
        # Asegurar que siempre este el prefijo vacio para listar bucket raiz
        if "" not in current_prefixes:
            current_prefixes.append("")
        if new_prefix not in current_prefixes:
            current_prefixes.append(new_prefix)
        if new_full_prefix not in current_prefixes:
            current_prefixes.append(new_full_prefix)
        list_bucket_statement["Condition"]["StringLike"]["s3:prefix"] = current_prefixes
        debug_print(f"Agregados prefijos: '', {new_prefix}, {new_full_prefix}")
    else:
        # Si no existe el statement de ListBucket, crearlo
        new_list_bucket_statement = {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": f"arn:aws:s3:::{new_bucket}",
            "Condition": {
                "StringLike": {"s3:prefix": ["", new_prefix, new_full_prefix]}
            },
        }
        existing_policy["Statement"].append(new_list_bucket_statement)
        debug_print(f"Creado nuevo statement ListBucket para bucket {new_bucket}")

    # Actualizar el statement de s3:*
    if s3_action_statement:
        current_resources = s3_action_statement["Resource"]
        if new_resource_base not in current_resources:
            current_resources.append(new_resource_base)
        if new_resource_wildcard not in current_resources:
            current_resources.append(new_resource_wildcard)
        debug_print(f"Agregados recursos: {new_resource_base}, {new_resource_wildcard}")
    else:
        # Si no existe el statement de s3:*, crearlo
        new_s3_statement = {
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": [new_resource_base, new_resource_wildcard],
        }
        existing_policy["Statement"].append(new_s3_statement)
        debug_print(
            f"Creado nuevo statement s3:* con recursos: {new_resource_base}, {new_resource_wildcard}"
        )

    return existing_policy


def create_policy_document(bucket_name, folder_path, subfolder_path):
    """
    Crea el documento de policy para el bucket y carpetas especificadas.

    Args:
        bucket_name (str): Nombre del bucket
        folder_path (str): Carpeta principal
        subfolder_path (str): Subcarpeta

    Returns:
        dict: Documento de policy
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:ListAllMyBuckets", "s3:GetBucketLocation"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::{bucket_name}",
                "Condition": {
                    "StringLike": {
                        "s3:prefix": [
                            "",
                            f"{folder_path}/",
                            f"{folder_path}/{subfolder_path}/*",
                        ]
                    }
                },
            },
            {
                "Effect": "Allow",
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}/{folder_path}/{subfolder_path}",
                    f"arn:aws:s3:::{bucket_name}/{folder_path}/{subfolder_path}/*",
                ],
            },
        ],
    }


def create_and_manage_policy(username, paths_info):
    """
    Crea o actualiza la policy basada en la información de rutas.

    Args:
        username (str): Nombre del usuario
        paths_info (list): Lista de tuplas (bucket, folder, subfolder)

    Raises:
        Exception: Si hay cualquier error durante el proceso
    """
    if not paths_info:
        debug_print("No hay información de rutas para procesar")
        raise Exception("No hay información de rutas para procesar")

    # A quien tiene `skip_wasabi_policy` NO se le arma policy por shot: son los admins y
    # los que acceden a proyectos completos, y en los dos casos el permiso por shot no le
    # agrega nada. Peor: PipeSync deja de administrar esa policy en cuanto la persona
    # queda marcada asi -su reconciliador filtra por ese flag- y tampoco la borra, o sea
    # que lo que se escriba aca queda concedido para siempre, sin caducar y sin que
    # ninguna UI lo muestre.
    perfil = find_user_by_wasabi_user(username)
    if perfil and perfil.get("skip_wasabi_policy"):
        message = (
            f"{perfil['name']} no lleva policies por shot: su acceso se maneja por "
            "proyecto completo. No se asigno nada."
        )
        debug_print(message)
        raise Exception(message)

    policy_name = f"{username}_policy"

    # Obtener credenciales de Wasabi desde SecureConfig
    access_key, secret_key, endpoint, region = get_s3_credentials()
    if not access_key or not secret_key:
        raise Exception(
            "No se pudieron obtener las credenciales de Wasabi desde SecureConfig"
        )

    # Crear sesion de boto3
    session = Session()
    iam = session.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url="https://iam.wasabisys.com",
        region_name=region or "us-east-1",
    )

    # Verificar si la policy existe
    policy_arn = None
    account_id = "100000152728"
    potential_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

    try:
        iam.get_policy(PolicyArn=potential_arn)
        policy_arn = potential_arn
        debug_print(f"La policy '{policy_name}' ya existe.")
    except Exception as e:
        if "NoSuchEntity" in str(e):
            debug_print(f"La policy '{policy_name}' no existe.")
        else:
            debug_print(f"Error verificando policy: {e}")
            raise Exception(f"Error verificando policy: {e}")

    # Procesar cada ruta
    final_policy = None

    for bucket_name, folder_path, subfolder_path in paths_info:
        debug_print(f"Procesando: {bucket_name}/{folder_path}/{subfolder_path}")

        if final_policy is None:
            if policy_arn:
                # Obtener policy existente
                existing_policy = get_existing_policy_document(iam, policy_arn)
                if existing_policy:
                    # Validar y reparar la policy existente
                    from wasabi_policy_utils import validate_and_repair_policy

                    debug_print("Validando policy existente obtenida...")
                    existing_policy = validate_and_repair_policy(existing_policy)

                    # Combinar con nueva información
                    final_policy = merge_policy_statements(
                        existing_policy, bucket_name, folder_path, subfolder_path
                    )
                else:
                    # Si no se puede obtener, crear nueva
                    final_policy = create_policy_document(
                        bucket_name, folder_path, subfolder_path
                    )
            else:
                # Crear nueva policy
                final_policy = create_policy_document(
                    bucket_name, folder_path, subfolder_path
                )
        else:
            # Combinar con policy existente
            final_policy = merge_policy_statements(
                final_policy, bucket_name, folder_path, subfolder_path
            )

    # Crear o actualizar la policy
    policy_updated = False
    if policy_arn:
        debug_print(f"Actualizando policy '{policy_name}'...")

        # Gestionar versiones antes de crear una nueva
        if not manage_policy_versions(iam, policy_arn):
            debug_print("Warning: No se pudieron gestionar las versiones de la policy")

        try:
            iam.create_policy_version(
                PolicyArn=policy_arn,
                PolicyDocument=json.dumps(final_policy),
                SetAsDefault=True,
            )
            debug_print(f"Policy '{policy_name}' actualizada.")
            policy_updated = True
        except Exception as e:
            debug_print(f"Error actualizando policy: {e}")
            if "LimitExceeded" in str(e):
                # Intentar gestionar versiones una vez mas como fallback
                debug_print("Intentando gestionar versiones como fallback...")
                if manage_policy_versions(iam, policy_arn):
                    try:
                        iam.create_policy_version(
                            PolicyArn=policy_arn,
                            PolicyDocument=json.dumps(final_policy),
                            SetAsDefault=True,
                        )
                        debug_print(
                            f"Policy '{policy_name}' actualizada en segundo intento."
                        )
                        policy_updated = True
                    except Exception as e2:
                        raise Exception(
                            f"Error actualizando policy después de gestionar versiones: {e2}"
                        )
                else:
                    raise Exception(
                        f"Error: No se pudieron gestionar las versiones de la policy '{policy_name}'. {e}"
                    )
            else:
                raise Exception(f"Error actualizando policy: {e}")
    else:
        debug_print(f"Creando policy '{policy_name}'...")
        try:
            response = iam.create_policy(
                PolicyName=policy_name, PolicyDocument=json.dumps(final_policy)
            )
            policy_arn = response["Policy"]["Arn"]
            debug_print(f"Policy '{policy_name}' creada.")
            policy_updated = True
        except Exception as e:
            debug_print(f"Error creando policy: {e}")
            raise Exception(f"Error creando policy: {e}")

    # Solo asignar policy al usuario si se actualizó/creó correctamente
    if policy_updated and policy_arn:
        debug_print(f"Asignando policy '{policy_name}' al usuario '{username}'...")
        try:
            iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)
            debug_print(f"Policy '{policy_name}' asignada a '{username}'.")
        except Exception as e:
            debug_print(f"Error asignando policy: {e}")
            if "EntityAlreadyExists" in str(e):
                debug_print("La policy ya estaba asignada al usuario.")
            else:
                raise Exception(f"Error asignando policy al usuario: {e}")


def get_user_info_from_config(wasabi_user):
    """
    Obtiene nombre y color de una persona a partir de su usuario de Wasabi.

    La fuente es la DB de PipeSync (tabla flow_users), alimentada desde Flow. Si la
    persona no esta ahi, se devuelve el propio wasabi_user y el gris neutro: la policy
    se puede asignar igual, solo se pierde el color en la ventana de estado.

    Returns:
        tuple: (user_name, user_color)
    """
    try:
        user = find_user_by_wasabi_user(wasabi_user)
        if user:
            return user["name"], user["color"]
        debug_print(
            f"'{wasabi_user}' no esta en la DB de PipeSync; se usa el nombre crudo."
        )
        return wasabi_user, "#666666"
    except Exception as e:
        debug_print(f"Error leyendo usuarios de PipeSync: {e}")
        return wasabi_user, "#666666"


# Variable global para mantener referencia a la ventana
_status_window = None


def main(username=None):
    """
    Función principal del script.

    Args:
        username (str): Nombre del usuario de Wasabi. Si no se proporciona, usa "TestPoli" por defecto.
    """
    global _status_window

    # Usar TestPoli por defecto si no se proporciona usuario
    if username is None:
        username = "TestPoli"

    debug_print(
        f"=== Iniciando LGA_NKS_Wasabi_PolicyAssign para usuario: {username} ==="
    )

    # Obtener información del usuario para la ventana
    user_name, user_color = get_user_info_from_config(username)

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Crear y mostrar ventana de estado
    _status_window = WasabiStatusWindow(user_name, user_color)
    _status_window.show()
    _status_window.show_processing_message()  # Mostrar mensaje de procesamiento

    # Crear worker para procesamiento en hilo separado
    worker = WasabiWorker(username, _status_window)

    # Conectar señales
    worker.signals.paths_ready.connect(
        lambda paths_info, window=_status_window: window.update_paths(paths_info)
    )
    worker.signals.finished.connect(
        lambda success, message, window=_status_window: (
            window.show_success(message) if success else window.show_error(message)
        )
    )
    worker.signals.error.connect(
        lambda error_msg, window=_status_window: window.show_error(error_msg)
    )

    # Ejecutar en hilo separado
    QThreadPool.globalInstance().start(worker)

    debug_print("=== Worker iniciado en hilo separado ===")


if __name__ == "__main__":
    main()
