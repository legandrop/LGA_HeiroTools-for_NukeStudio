"""
______________________________________________________________________

  verify_policy_assign.py - 2024 - Lega
  Verifica que la policy de PolicyAssign se creó correctamente
______________________________________________________________________

"""

import os
import sys
import json

# Agregar la ruta actual al sys.path para que Python encuentre las dependencias locales
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import boto3
from boto3 import Session

# Configuracion
USERNAME = "TestPoli"  # Debe coincidir con el del script principal
DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def verify_policy_content(expected_buckets_and_paths):
    """
    Verifica que la policy contiene los permisos esperados.

    Args:
        expected_buckets_and_paths (list): Lista de tuplas (bucket, folder, subfolder)
    """
    policy_name = f"{USERNAME}_policy"

    # Crear sesion de boto3
    session = Session()
    iam = session.client(
        "iam",
        aws_access_key_id=os.getenv("WASABI_ADMIN_KEY"),
        aws_secret_access_key=os.getenv("WASABI_ADMIN_SECRET"),
        endpoint_url="https://iam.wasabisys.com",
        region_name="us-east-1",
    )

    # Obtener la policy
    account_id = "100000152728"
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

    try:
        # Obtener información de la policy
        policy_response = iam.get_policy(PolicyArn=policy_arn)
        policy_info = policy_response["Policy"]

        debug_print(f"Policy encontrada: {policy_info['PolicyName']}")
        debug_print(f"ARN: {policy_info['Arn']}")
        debug_print(f"Fecha de creación: {policy_info['CreateDate']}")
        debug_print(f"Versión por defecto: {policy_info['DefaultVersionId']}")

        # Obtener el documento de la policy
        version_response = iam.get_policy_version(
            PolicyArn=policy_arn, VersionId=policy_info["DefaultVersionId"]
        )

        policy_document = version_response["PolicyVersion"]["Document"]

        debug_print("\n=== CONTENIDO DE LA POLICY ===")
        debug_print(json.dumps(policy_document, indent=2, ensure_ascii=False))

        # Verificar contenido específico
        statements = policy_document.get("Statement", [])

        # Verificar statement básico (ListAllMyBuckets)
        basic_statement = None
        list_bucket_statements = []
        s3_action_statements = []

        for statement in statements:
            actions = statement.get("Action", [])
            if isinstance(actions, list):
                if (
                    "s3:ListAllMyBuckets" in actions
                    and "s3:GetBucketLocation" in actions
                ):
                    basic_statement = statement
                elif "s3:ListBucket" in actions:
                    list_bucket_statements.append(statement)
                elif "s3:*" in actions:
                    s3_action_statements.append(statement)
            elif actions == "s3:ListBucket":
                list_bucket_statements.append(statement)
            elif actions == "s3:*":
                s3_action_statements.append(statement)

        debug_print(f"\n=== VERIFICACIÓN DE CONTENIDO ===")
        debug_print(f"Statement básico encontrado: {'✓' if basic_statement else '✗'}")
        debug_print(f"Statements de ListBucket: {len(list_bucket_statements)}")
        debug_print(f"Statements de s3:*: {len(s3_action_statements)}")

        # Verificar cada bucket y path esperado
        for bucket_name, folder_path, subfolder_path in expected_buckets_and_paths:
            debug_print(
                f"\n--- Verificando {bucket_name}/{folder_path}/{subfolder_path} ---"
            )

            # Buscar statement de ListBucket para este bucket
            bucket_list_statement = None
            for statement in list_bucket_statements:
                if statement.get("Resource") == f"arn:aws:s3:::{bucket_name}":
                    bucket_list_statement = statement
                    break

            if bucket_list_statement:
                prefixes = (
                    bucket_list_statement.get("Condition", {})
                    .get("StringLike", {})
                    .get("s3:prefix", [])
                )
                expected_empty_prefix = ""
                expected_prefix = f"{folder_path}/"
                expected_full_prefix = f"{folder_path}/{subfolder_path}/*"

                debug_print(f"  ListBucket statement: ✓")
                debug_print(
                    f"  Prefijo vacío '': {'✓' if expected_empty_prefix in prefixes else '✗'}"
                )
                debug_print(
                    f"  Prefijo '{expected_prefix}': {'✓' if expected_prefix in prefixes else '✗'}"
                )
                debug_print(
                    f"  Prefijo completo '{expected_full_prefix}': {'✓' if expected_full_prefix in prefixes else '✗'}"
                )
            else:
                debug_print(f"  ListBucket statement: ✗")

            # Buscar statement de s3:* para este path
            expected_resource_base = (
                f"arn:aws:s3:::{bucket_name}/{folder_path}/{subfolder_path}"
            )
            expected_resource_wildcard = (
                f"arn:aws:s3:::{bucket_name}/{folder_path}/{subfolder_path}/*"
            )

            found_resources = False
            for statement in s3_action_statements:
                resources = statement.get("Resource", [])
                if (
                    expected_resource_base in resources
                    and expected_resource_wildcard in resources
                ):
                    found_resources = True
                    break

            debug_print(f"  Recursos s3:*: {'✓' if found_resources else '✗'}")

        # Verificar que la policy está asignada al usuario
        debug_print(f"\n=== VERIFICACIÓN DE ASIGNACIÓN AL USUARIO ===")
        try:
            user_policies = iam.list_attached_user_policies(UserName=USERNAME)
            attached_policies = user_policies["AttachedPolicies"]

            policy_attached = False
            for policy in attached_policies:
                if policy["PolicyName"] == policy_name:
                    policy_attached = True
                    break

            debug_print(
                f"Policy asignada a usuario '{USERNAME}': {'✓' if policy_attached else '✗'}"
            )

            if attached_policies:
                debug_print("Políticas asignadas al usuario:")
                for policy in attached_policies:
                    debug_print(f"  - {policy['PolicyName']} ({policy['PolicyArn']})")

        except Exception as e:
            debug_print(f"Error verificando asignación de usuario: {e}")

        return True

    except Exception as e:
        debug_print(f"Error verificando policy: {e}")
        return False


def main():
    """
    Función principal de verificación.
    """
    debug_print("=== Verificando Policy de PolicyAssign ===")

    # Verificar variables de entorno
    if not os.getenv("WASABI_ADMIN_KEY") or not os.getenv("WASABI_ADMIN_SECRET"):
        debug_print(
            "ERROR: Las variables de entorno WASABI_ADMIN_KEY y WASABI_ADMIN_SECRET deben estar configuradas."
        )
        return

    # Paths esperados basados en las rutas de testing
    expected_paths = [
        ("vfx-etdm", "103", "ETDM_3003_0100_DeAging_Cocina"),
        ("vfx-etdm", "101", "ETDM_1000_0010_DeAging_Atropella"),
    ]

    success = verify_policy_content(expected_paths)

    if success:
        debug_print("\n=== VERIFICACIÓN COMPLETADA ===")
    else:
        debug_print("\n=== VERIFICACIÓN FALLÓ ===")


if __name__ == "__main__":
    main()
