"""
______________________________________________________________________

  LGA_NKS_Wasabi_PolicyAssign v0.2 | Lega Pugliese
  Crea y asigna políticas IAM de Wasabi basadas en rutas de clips seleccionados
______________________________________________________________________

"""

import os
import sys
import json
import hiero.core
import hiero.ui

# Agregar la ruta actual al sys.path para que Python encuentre las dependencias locales
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import boto3
from boto3 import Session

# Configuracion
DEBUG = True


def debug_print(*message):
    if DEBUG:
        print(*message)


def parse_path_for_policy(file_path):
    """
    Parsea la ruta del archivo para extraer bucket y carpetas para la policy.

    Args:
        file_path (str): Ruta completa del archivo

    Returns:
        tuple: (bucket_name, folder_path, subfolder_path) o None si no se puede parsear
    """
    try:
        # Normalizar la ruta y dividir en partes
        normalized_path = os.path.normpath(file_path)
        parts = normalized_path.split(os.sep)

        debug_print(f"Ruta original: {file_path}")
        debug_print(f"Partes de la ruta: {parts}")

        # Buscar el indice donde empieza la estructura que nos interesa
        # Descartamos la unidad (T:\ por ejemplo)
        if len(parts) < 4:
            debug_print("Ruta demasiado corta para parsear")
            return None

        # El bucket será la primera carpeta después de la unidad, en minúsculas
        bucket_name = parts[1].lower()  # VFX-ETDM -> vfx-etdm

        # Las dos carpetas siguientes
        folder_path = parts[2]  # 103
        subfolder_path = parts[3]  # ETDM_3003_0090_DeAging_Cocina

        debug_print(f"Bucket: {bucket_name}")
        debug_print(f"Carpeta: {folder_path}")
        debug_print(f"Subcarpeta: {subfolder_path}")

        return bucket_name, folder_path, subfolder_path

    except Exception as e:
        debug_print(f"Error parseando ruta: {e}")
        return None


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
        elif statement.get("Action") == "s3:*" and isinstance(
            statement.get("Resource"), list
        ):
            s3_action_statement = statement

    # Actualizar el statement de ListBucket
    if list_bucket_statement:
        current_prefixes = (
            list_bucket_statement.get("Condition", {})
            .get("StringLike", {})
            .get("s3:prefix", [])
        )
        if new_prefix not in current_prefixes:
            current_prefixes.append(new_prefix)
        if new_full_prefix not in current_prefixes:
            current_prefixes.append(new_full_prefix)
        list_bucket_statement["Condition"]["StringLike"]["s3:prefix"] = current_prefixes
        debug_print(f"Agregados prefijos: {new_prefix}, {new_full_prefix}")

    # Actualizar el statement de s3:*
    if s3_action_statement:
        current_resources = s3_action_statement["Resource"]
        if new_resource_base not in current_resources:
            current_resources.append(new_resource_base)
        if new_resource_wildcard not in current_resources:
            current_resources.append(new_resource_wildcard)
        debug_print(f"Agregados recursos: {new_resource_base}, {new_resource_wildcard}")

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
    """
    if not paths_info:
        debug_print("No hay información de rutas para procesar")
        return

    policy_name = f"{username}_policy"

    # Crear sesion de boto3
    session = Session()
    iam = session.client(
        "iam",
        aws_access_key_id=os.getenv("WASABI_ADMIN_KEY"),
        aws_secret_access_key=os.getenv("WASABI_ADMIN_SECRET"),
        endpoint_url="https://iam.wasabisys.com",
        region_name="us-east-1",
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

    # Procesar cada ruta
    final_policy = None

    for bucket_name, folder_path, subfolder_path in paths_info:
        debug_print(f"Procesando: {bucket_name}/{folder_path}/{subfolder_path}")

        if final_policy is None:
            if policy_arn:
                # Obtener policy existente
                final_policy = get_existing_policy_document(iam, policy_arn)
                if final_policy:
                    # Combinar con nueva información
                    final_policy = merge_policy_statements(
                        final_policy, bucket_name, folder_path, subfolder_path
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
    if policy_arn:
        debug_print(f"Actualizando policy '{policy_name}'...")
        try:
            iam.create_policy_version(
                PolicyArn=policy_arn,
                PolicyDocument=json.dumps(final_policy),
                SetAsDefault=True,
            )
            debug_print(f"Policy '{policy_name}' actualizada.")
        except Exception as e:
            debug_print(f"Error actualizando policy: {e}")
    else:
        debug_print(f"Creando policy '{policy_name}'...")
        try:
            response = iam.create_policy(
                PolicyName=policy_name, PolicyDocument=json.dumps(final_policy)
            )
            policy_arn = response["Policy"]["Arn"]
            debug_print(f"Policy '{policy_name}' creada.")
        except Exception as e:
            debug_print(f"Error creando policy: {e}")
            policy_arn = potential_arn

    # Asignar policy al usuario
    debug_print(f"Asignando policy '{policy_name}' al usuario '{username}'...")
    try:
        iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)
        debug_print(f"Policy '{policy_name}' asignada a '{username}'.")
    except Exception as e:
        debug_print(f"Error asignando policy: {e}")
        if "EntityAlreadyExists" in str(e):
            debug_print("La policy ya estaba asignada al usuario.")


def main(username=None):
    """
    Función principal del script.

    Args:
        username (str): Nombre del usuario de Wasabi. Si no se proporciona, usa "TestPoli" por defecto.
    """
    # Usar TestPoli por defecto si no se proporciona usuario
    if username is None:
        username = "TestPoli"

    debug_print(
        f"=== Iniciando LGA_NKS_Wasabi_PolicyAssign para usuario: {username} ==="
    )

    # Verificar variables de entorno
    if not os.getenv("WASABI_ADMIN_KEY") or not os.getenv("WASABI_ADMIN_SECRET"):
        debug_print(
            "ERROR: Las variables de entorno WASABI_ADMIN_KEY y WASABI_ADMIN_SECRET deben estar configuradas."
        )
        return

    # Obtener rutas de clips seleccionados en Hiero
    file_paths = get_selected_clips_paths()

    # TESTING: Descomentar para usar rutas hardcodeadas (solo para debugging)
    # test_paths = [
    #     r"T:\VFX-ETDM\103\ETDM_3003_0100_DeAging_Cocina\_input\ETDM_3003_0110_DeAging_Cocina_aPlate_v01",
    #     r"T:\VFX-ETDM\101\ETDM_1000_0010_DeAging_Atropella\_input\ETDM_1000_0010_DeAging_Atropella_aPlate_v01",
    # ]
    # debug_print("=== MODO TESTING: Usando rutas hardcodeadas ===")
    # file_paths = test_paths

    if not file_paths:
        debug_print("No se encontraron rutas de archivos para procesar.")
        return

    # Parsear todas las rutas
    paths_info = []
    for file_path in file_paths:
        parsed = parse_path_for_policy(file_path)
        if parsed:
            paths_info.append(parsed)

    if not paths_info:
        debug_print("No se pudieron parsear las rutas.")
        return

    # Crear y gestionar la policy
    create_and_manage_policy(username, paths_info)
    debug_print("=== Script completado ===")


if __name__ == "__main__":
    main()
