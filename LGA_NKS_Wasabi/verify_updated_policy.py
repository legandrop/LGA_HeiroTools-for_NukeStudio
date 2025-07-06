import os
import sys

# Agregar la ruta actual al sys.path para que Python encuentre las dependencias locales
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import boto3
from boto3 import Session
import json
from botocore.exceptions import ClientError


def verify_policy_updated():
    """Verificar que la política se actualizó con el contenido correcto"""
    print("🔍 === VERIFICACIÓN DE POLÍTICA ACTUALIZADA ===\n")

    # Verificar credenciales
    if not os.getenv("WASABI_ADMIN_KEY") or not os.getenv("WASABI_ADMIN_SECRET"):
        print("❌ Variables de entorno no configuradas")
        return False

    try:
        # Crear cliente IAM
        session = Session()
        iam = session.client(
            "iam",
            aws_access_key_id=os.getenv("WASABI_ADMIN_KEY"),
            aws_secret_access_key=os.getenv("WASABI_ADMIN_SECRET"),
            endpoint_url="https://iam.wasabisys.com",
            region_name="us-east-1",
        )

        # Parámetros
        policy_name = "TestPoli_policy"
        account_id = "100000152728"
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        # Contenido esperado
        expected_policy = {
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
                            "s3:prefix": [
                                "",
                                "103/",
                                "103/ETDM_3003_0090_DeAging_Cocina/*",
                            ]
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

        print(f"=== Verificando Política: {policy_name} ===")

        # Obtener la política
        policy_response = iam.get_policy(PolicyArn=policy_arn)
        policy = policy_response["Policy"]

        print(f"✅ Política encontrada: {policy['PolicyName']}")
        print(f"   ARN: {policy['Arn']}")
        print(f"   Versión por defecto: {policy['DefaultVersionId']}")
        print(f"   Última actualización: {policy['UpdateDate']}")

        # Obtener el contenido actual
        version_response = iam.get_policy_version(
            PolicyArn=policy_arn, VersionId=policy["DefaultVersionId"]
        )

        current_policy = version_response["PolicyVersion"]["Document"]

        print("\n📄 CONTENIDO ACTUAL DE LA POLÍTICA:")
        print("=" * 50)
        print(json.dumps(current_policy, indent=2, ensure_ascii=False))

        print("\n📄 CONTENIDO ESPERADO:")
        print("=" * 50)
        print(json.dumps(expected_policy, indent=2, ensure_ascii=False))

        # Verificar elementos clave
        print("\n🔍 VERIFICACIÓN DETALLADA:")
        print("=" * 50)

        success = True

        # Verificar Version
        if current_policy.get("Version") == expected_policy.get("Version"):
            print("✅ Version: Correcto")
        else:
            print(
                f"❌ Version: Esperado '{expected_policy.get('Version')}', encontrado '{current_policy.get('Version')}'"
            )
            success = False

        # Verificar número de statements
        current_statements = current_policy.get("Statement", [])
        expected_statements = expected_policy.get("Statement", [])

        if len(current_statements) == len(expected_statements):
            print(f"✅ Número de statements: {len(current_statements)}")
        else:
            print(
                f"❌ Número de statements: Esperado {len(expected_statements)}, encontrado {len(current_statements)}"
            )
            success = False

        # Verificar cada statement
        for i, (current_stmt, expected_stmt) in enumerate(
            zip(current_statements, expected_statements)
        ):
            print(f"\n📋 Statement {i+1}:")

            # Verificar Effect
            if current_stmt.get("Effect") == expected_stmt.get("Effect"):
                print(f"  ✅ Effect: {current_stmt.get('Effect')}")
            else:
                print(
                    f"  ❌ Effect: Esperado '{expected_stmt.get('Effect')}', encontrado '{current_stmt.get('Effect')}'"
                )
                success = False

            # Verificar Action
            current_actions = current_stmt.get("Action", [])
            expected_actions = expected_stmt.get("Action", [])

            # Normalizar a lista si es string
            if isinstance(current_actions, str):
                current_actions = [current_actions]
            if isinstance(expected_actions, str):
                expected_actions = [expected_actions]

            if set(current_actions) == set(expected_actions):
                print(f"  ✅ Actions: {current_actions}")
            else:
                print(
                    f"  ❌ Actions: Esperado {expected_actions}, encontrado {current_actions}"
                )
                success = False

            # Verificar Resource
            current_resources = current_stmt.get("Resource", [])
            expected_resources = expected_stmt.get("Resource", [])

            # Normalizar a lista si es string
            if isinstance(current_resources, str):
                current_resources = [current_resources]
            if isinstance(expected_resources, str):
                expected_resources = [expected_resources]

            if set(current_resources) == set(expected_resources):
                print(f"  ✅ Resources: {current_resources}")
            else:
                print(
                    f"  ❌ Resources: Esperado {expected_resources}, encontrado {current_resources}"
                )
                success = False

            # Verificar Condition si existe
            if "Condition" in expected_stmt:
                if "Condition" in current_stmt:
                    if current_stmt["Condition"] == expected_stmt["Condition"]:
                        print(f"  ✅ Condition: Correcto")
                    else:
                        print(f"  ❌ Condition: No coincide")
                        print(f"    Esperado: {expected_stmt['Condition']}")
                        print(f"    Encontrado: {current_stmt['Condition']}")
                        success = False
                else:
                    print(f"  ❌ Condition: Falta en la política actual")
                    success = False

        # Verificar que el usuario tiene la política asignada
        print(f"\n👤 VERIFICANDO ASIGNACIÓN AL USUARIO 'TestPoli':")
        print("=" * 50)

        try:
            user_policies = iam.list_attached_user_policies(UserName="TestPoli")
            attached_policies = user_policies.get("AttachedPolicies", [])

            policy_attached = False
            for policy in attached_policies:
                if policy["PolicyArn"] == policy_arn:
                    policy_attached = True
                    print(f"✅ Política asignada al usuario TestPoli")
                    break

            if not policy_attached:
                print(f"❌ Política NO asignada al usuario TestPoli")
                success = False

        except Exception as e:
            print(f"❌ Error verificando asignación: {e}")
            success = False

        # Resultado final
        print("\n" + "=" * 60)
        print("📊 RESULTADO FINAL")
        print("=" * 60)

        if success:
            print("🎉 ¡VERIFICACIÓN EXITOSA!")
            print("✅ La política se actualizó correctamente con el contenido esperado")
            print("✅ La política está asignada al usuario TestPoli")
            print(
                "✅ Todos los permisos para vfx-etdm están configurados correctamente"
            )
        else:
            print("❌ VERIFICACIÓN FALLIDA")
            print("La política no coincide con el contenido esperado")

        return success

    except Exception as e:
        print(f"❌ Error general: {e}")
        return False


if __name__ == "__main__":
    verify_policy_updated()
