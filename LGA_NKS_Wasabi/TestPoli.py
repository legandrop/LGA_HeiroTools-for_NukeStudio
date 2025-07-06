import os
import sys

# Agregar la ruta actual al sys.path para que Python encuentre las dependencias locales
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import boto3
from boto3 import Session
import json

# Variable global para activar o desactivar los prints
DEBUG = True


def debug_print(*message):
    if DEBUG:
        print(*message)


def create_and_attach_policy(username, policy_name, policy_document):
    # Crear sesion de boto3 correctamente
    session = Session()
    iam = session.client(
        "iam",
        aws_access_key_id=os.getenv("WASABI_ADMIN_KEY"),
        aws_secret_access_key=os.getenv("WASABI_ADMIN_SECRET"),
        endpoint_url="https://iam.wasabisys.com",
        region_name="us-east-1",  # Wasabi requiere una region
    )

    # 1. Buscar si la policy ya existe
    policy_arn = None
    account_id = "100000152728"  # ID de cuenta conocido
    potential_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

    try:
        # Intentar obtener la policy directamente
        iam.get_policy(PolicyArn=potential_arn)
        policy_arn = potential_arn
        debug_print(f"La policy '{policy_name}' ya existe.")
    except Exception as e:
        if "NoSuchEntity" in str(e):
            debug_print(f"La policy '{policy_name}' no existe.")
        else:
            debug_print(f"Error verificando policy: {e}")
            # Si hay error de permisos, intentar listar
            try:
                existing_policies = iam.list_policies(Scope="Local")["Policies"]
                for policy in existing_policies:
                    if policy["PolicyName"] == policy_name:
                        policy_arn = policy["Arn"]
                        debug_print(
                            f"La policy '{policy_name}' encontrada via listado."
                        )
                        break
            except Exception as list_error:
                debug_print(f"Error listando policies: {list_error}")

    # 2. Si existe, actualizar contenido; si no existe, crearla
    if policy_arn:
        debug_print(f"Actualizando contenido de policy '{policy_name}'...")
        try:
            # Crear nueva version de la policy
            iam.create_policy_version(
                PolicyArn=policy_arn,
                PolicyDocument=json.dumps(policy_document),
                SetAsDefault=True,
            )
            debug_print(f"Policy '{policy_name}' actualizada con nuevo contenido.")
        except Exception as e:
            debug_print(f"Error actualizando policy: {e}")
            debug_print("Intentando continuar con la policy existente...")
    else:
        debug_print(f"Creando policy '{policy_name}'...")
        try:
            response = iam.create_policy(
                PolicyName=policy_name, PolicyDocument=json.dumps(policy_document)
            )
            policy_arn = response["Policy"]["Arn"]
            debug_print(f"Policy '{policy_name}' creada.")
        except Exception as e:
            debug_print(f"Error creando policy: {e}")
            # Si falla crear, intentar obtener ARN construyendo
            account_id = "100000152728"  # ID de cuenta conocido
            policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
            debug_print(f"Usando ARN construido: {policy_arn}")

    # 3. Adjuntar policy al usuario
    debug_print(f"Asignando policy '{policy_name}' al usuario '{username}'...")
    try:
        iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)
        debug_print(f"Policy '{policy_name}' asignada a '{username}'.")
    except Exception as e:
        debug_print(f"Error asignando policy: {e}")
        if "EntityAlreadyExists" in str(e):
            debug_print("La policy ya estaba asignada al usuario.")


# Ejemplo de uso (comentado para que no se ejecute automáticamente)
if __name__ == "__main__":
    # Documento de policy para acceso específico al bucket vfx-etdm
    policy_document = {
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
                "Resource": "arn:aws:s3:::vfx-etdm",
                "Condition": {
                    "StringLike": {
                        "s3:prefix": ["", "103/", "103/ETDM_3003_0090_DeAging_Cocina/*"]
                    }
                },
            },
            {
                "Effect": "Allow",
                "Action": "s3:*",
                "Resource": [
                    "arn:aws:s3:::vfx-etdm/103/ETDM_3003_0090_DeAging_Cocina",
                    "arn:aws:s3:::vfx-etdm/103/ETDM_3003_0090_DeAging_Cocina/*",
                ],
            },
        ],
    }

    # Verificar que las variables de entorno estén configuradas
    if not os.getenv("WASABI_ADMIN_KEY") or not os.getenv("WASABI_ADMIN_SECRET"):
        print(
            "ERROR: Las variables de entorno WASABI_ADMIN_KEY y WASABI_ADMIN_SECRET deben estar configuradas."
        )
        print("Configurar con:")
        print("set WASABI_ADMIN_KEY=tu_clave_de_acceso")
        print("set WASABI_ADMIN_SECRET=tu_clave_secreta")
    else:
        # Ejemplo de uso
        create_and_attach_policy("TestPoli", "TestPoli_policy", policy_document)
        print("Script ejecutado correctamente.")
