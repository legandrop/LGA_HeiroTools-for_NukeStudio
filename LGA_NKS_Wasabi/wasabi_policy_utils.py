"""
______________________________________________________________________

  Wasabi Policy Utils v0.5 | Lega Pugliese
  Funciones auxiliares para gestión de políticas IAM de Wasabi
______________________________________________________________________

"""

import os
import json
from boto3 import Session


def debug_print(*message):
    """Función de debug - debe coincidir con la del script principal"""
    DEBUG = True
    if DEBUG:
        print(*message)


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


def read_user_policy_shots(username):
    """
    Lee la policy del usuario y extrae la lista de shots asignados.

    Args:
        username (str): Nombre del usuario

    Returns:
        list: Lista de nombres de shots o None si hay error
    """
    try:
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
        account_id = "100000152728"
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        try:
            policy_document = get_existing_policy_document(iam, policy_arn)
            if not policy_document:
                debug_print(
                    f"No se pudo obtener el documento de la policy {policy_name}"
                )
                return []

            # Extraer shots de la policy
            shots_set = set()

            for statement in policy_document.get("Statement", []):
                if statement.get("Action") == "s3:*":
                    resources = statement.get("Resource", [])
                    if isinstance(resources, list):
                        for resource in resources:
                            # Extraer el nombre del shot de recursos como:
                            # arn:aws:s3:::vfx-etdm/105/ETDM_5021_0020_Chroma_Camioneta
                            # arn:aws:s3:::vfx-etdm/105/ETDM_5021_0020_Chroma_Camioneta/*
                            if resource.startswith("arn:aws:s3:::") and "/" in resource:
                                parts = resource.split("/")
                                if len(parts) >= 3:
                                    # El shot es la ultima parte sin /*
                                    shot_name = parts[-1]
                                    if shot_name and shot_name != "*":
                                        shots_set.add(shot_name)

            shots_list = sorted(list(shots_set))
            debug_print(f"Shots encontrados en policy: {shots_list}")
            return shots_list

        except Exception as e:
            if "NoSuchEntity" in str(e):
                debug_print(f"La policy '{policy_name}' no existe.")
                return []
            else:
                debug_print(f"Error leyendo policy: {e}")
                return None

    except Exception as e:
        debug_print(f"Error en read_user_policy_shots: {e}")
        return None


def remove_shot_from_policy(username, shot_name):
    """
    Elimina un shot específico de la policy del usuario.

    Args:
        username (str): Nombre del usuario
        shot_name (str): Nombre del shot a eliminar

    Returns:
        bool: True si se eliminó exitosamente, False en caso contrario
    """
    try:
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
        account_id = "100000152728"
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        try:
            policy_document = get_existing_policy_document(iam, policy_arn)
            if not policy_document:
                debug_print(
                    f"No se pudo obtener el documento de la policy {policy_name}"
                )
                return False

            # Crear nueva policy sin el shot especificado
            modified = False
            new_policy = policy_document.copy()

            for statement in new_policy.get("Statement", []):
                if statement.get("Action") == "s3:ListBucket":
                    # Remover prefijos relacionados con el shot
                    prefixes = (
                        statement.get("Condition", {})
                        .get("StringLike", {})
                        .get("s3:prefix", [])
                    )
                    new_prefixes = []
                    for prefix in prefixes:
                        if shot_name not in prefix:
                            new_prefixes.append(prefix)
                        else:
                            modified = True
                            debug_print(f"Removiendo prefijo: {prefix}")

                    if new_prefixes != prefixes:
                        statement["Condition"]["StringLike"]["s3:prefix"] = new_prefixes

                elif statement.get("Action") == "s3:*":
                    # Remover recursos relacionados con el shot
                    resources = statement.get("Resource", [])
                    if isinstance(resources, list):
                        new_resources = []
                        for resource in resources:
                            if shot_name not in resource:
                                new_resources.append(resource)
                            else:
                                modified = True
                                debug_print(f"Removiendo recurso: {resource}")

                        if new_resources != resources:
                            statement["Resource"] = new_resources

            if not modified:
                debug_print(
                    f"No se encontraron referencias al shot {shot_name} en la policy"
                )
                return False

            # Gestionar versiones antes de crear una nueva
            if not manage_policy_versions(iam, policy_arn):
                debug_print(
                    "Warning: No se pudieron gestionar las versiones de la policy"
                )

            # Crear nueva version de la policy
            try:
                iam.create_policy_version(
                    PolicyArn=policy_arn,
                    PolicyDocument=json.dumps(new_policy),
                    SetAsDefault=True,
                )
                debug_print(f"Shot {shot_name} eliminado de la policy {policy_name}")
                return True

            except Exception as e:
                debug_print(f"Error actualizando policy: {e}")
                if "LimitExceeded" in str(e):
                    # Intentar gestionar versiones una vez mas como fallback
                    debug_print("Intentando gestionar versiones como fallback...")
                    if manage_policy_versions(iam, policy_arn):
                        try:
                            iam.create_policy_version(
                                PolicyArn=policy_arn,
                                PolicyDocument=json.dumps(new_policy),
                                SetAsDefault=True,
                            )
                            debug_print(
                                f"Shot {shot_name} eliminado de la policy {policy_name} en segundo intento"
                            )
                            return True
                        except Exception as e2:
                            debug_print(f"Error en segundo intento: {e2}")
                            return False
                    else:
                        debug_print("No se pudieron gestionar las versiones")
                        return False
                else:
                    debug_print(f"Error actualizando policy: {e}")
                    return False

        except Exception as e:
            if "NoSuchEntity" in str(e):
                debug_print(f"La policy '{policy_name}' no existe.")
                return False
            else:
                debug_print(f"Error accediendo a la policy: {e}")
                return False

    except Exception as e:
        debug_print(f"Error en remove_shot_from_policy: {e}")
        return False
