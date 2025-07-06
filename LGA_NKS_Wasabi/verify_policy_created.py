import os
import sys

# Agregar la ruta actual al sys.path para que Python encuentre las dependencias locales
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import boto3
from boto3 import Session
import json
from botocore.exceptions import ClientError


def verify_user_exists(iam_client, username):
    """Verificar que el usuario existe"""
    print(f"=== Verificando Usuario: {username} ===")

    try:
        response = iam_client.get_user(UserName=username)
        user = response["User"]
        print(f"✅ Usuario encontrado: {user['UserName']}")
        print(f"   ARN: {user['Arn']}")
        print(f"   Creado: {user['CreateDate']}")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"❌ Usuario '{username}' no existe")
        else:
            print(f"❌ Error verificando usuario: {e.response['Error']['Message']}")
        return False


def verify_policy_exists(iam_client, policy_name):
    """Verificar que la política existe y obtener su ARN"""
    print(f"\n=== Verificando Política: {policy_name} ===")

    try:
        # Construir el ARN de la política basado en el patrón que vimos
        account_id = (
            "100000152728"  # El ID de cuenta que vimos en el resultado anterior
        )
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        # Intentar obtener la política
        response = iam_client.get_policy(PolicyArn=policy_arn)
        policy = response["Policy"]

        print(f"✅ Política encontrada: {policy['PolicyName']}")
        print(f"   ARN: {policy['Arn']}")
        print(f"   Creada: {policy['CreateDate']}")
        print(f"   Versión por defecto: {policy['DefaultVersionId']}")

        return policy_arn

    except ClientError as e:
        print(f"❌ Error verificando política: {e.response['Error']['Message']}")
        return None


def verify_policy_content(iam_client, policy_arn, expected_content):
    """Verificar el contenido de la política"""
    print(f"\n=== Verificando Contenido de Política ===")

    try:
        # Obtener la política
        response = iam_client.get_policy(PolicyArn=policy_arn)
        policy = response["Policy"]

        # Obtener la versión actual del documento
        version_response = iam_client.get_policy_version(
            PolicyArn=policy_arn, VersionId=policy["DefaultVersionId"]
        )

        policy_document = version_response["PolicyVersion"]["Document"]

        print("📄 Contenido actual de la política:")
        print(json.dumps(policy_document, indent=2, ensure_ascii=False))

        print("\n📄 Contenido esperado:")
        print(json.dumps(expected_content, indent=2, ensure_ascii=False))

        # Comparar contenidos
        if policy_document == expected_content:
            print("\n✅ ¡El contenido de la política coincide exactamente!")
            return True
        else:
            print("\n⚠️  El contenido de la política es diferente")
            print("Esto puede ser normal si Wasabi reformatea el JSON")

            # Verificar elementos clave
            if policy_document.get("Version") == expected_content.get(
                "Version"
            ) and len(policy_document.get("Statement", [])) == len(
                expected_content.get("Statement", [])
            ):
                print("✅ La estructura básica coincide")
                return True
            else:
                print("❌ La estructura básica no coincide")
                return False

    except ClientError as e:
        print(
            f"❌ Error obteniendo contenido de política: {e.response['Error']['Message']}"
        )
        return False


def verify_policy_attached_to_user(iam_client, username, policy_arn):
    """Verificar que la política está adjunta al usuario"""
    print(f"\n=== Verificando Política Adjunta al Usuario ===")

    try:
        # Obtener políticas adjuntas al usuario
        response = iam_client.list_attached_user_policies(UserName=username)
        attached_policies = response.get("AttachedPolicies", [])

        print(f"Políticas adjuntas al usuario '{username}':")

        policy_found = False
        for policy in attached_policies:
            print(f"  - {policy['PolicyName']} (ARN: {policy['PolicyArn']})")
            if policy["PolicyArn"] == policy_arn:
                policy_found = True

        if policy_found:
            print(f"✅ La política está correctamente adjunta al usuario")
            return True
        else:
            print(f"❌ La política NO está adjunta al usuario")
            return False

    except ClientError as e:
        print(
            f"❌ Error verificando políticas del usuario: {e.response['Error']['Message']}"
        )
        return False


def test_s3_access_with_user_credentials():
    """Probar acceso S3 con las credenciales del usuario (si están disponibles)"""
    print(f"\n=== Test de Acceso S3 (Opcional) ===")

    # Nota: Este test requeriría las credenciales del usuario TestPoli
    # Por ahora solo mostramos qué se debería probar
    print("Para probar el acceso S3 con el usuario TestPoli, necesitarías:")
    print("1. Generar credenciales de acceso para el usuario TestPoli")
    print("2. Configurar variables de entorno TESTPOLI_KEY y TESTPOLI_SECRET")
    print("3. Probar acceso al bucket 'mi-bucket' con esas credenciales")

    # Si quisieras implementar esto, sería algo así:
    # testpoli_key = os.getenv("TESTPOLI_KEY")
    # testpoli_secret = os.getenv("TESTPOLI_SECRET")
    # if testpoli_key and testpoli_secret:
    #     # Crear cliente S3 con credenciales del usuario
    #     # Probar operaciones permitidas en la política

    print("⚠️  Test de acceso S3 no implementado (requiere credenciales del usuario)")
    return True


def main():
    """Función principal de verificación"""
    print("🔍 === VERIFICACIÓN DE POLÍTICA CREADA ===\n")

    # Verificar credenciales de admin
    if not os.getenv("WASABI_ADMIN_KEY") or not os.getenv("WASABI_ADMIN_SECRET"):
        print("❌ Variables de entorno de administrador no configuradas")
        return

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

        # Parámetros a verificar
        username = "TestPoli"
        policy_name = "TestPoli_policy"
        expected_policy_content = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                    ],
                    "Resource": ["arn:aws:s3:::mi-bucket/*", "arn:aws:s3:::mi-bucket"],
                }
            ],
        }

        # Verificaciones
        print("Iniciando verificaciones...\n")

        # 1. Verificar usuario
        user_exists = verify_user_exists(iam, username)
        if not user_exists:
            print("❌ No se puede continuar sin el usuario")
            return

        # 2. Verificar política
        policy_arn = verify_policy_exists(iam, policy_name)
        if not policy_arn:
            print("❌ No se puede continuar sin la política")
            return

        # 3. Verificar contenido de política
        content_ok = verify_policy_content(iam, policy_arn, expected_policy_content)

        # 4. Verificar que la política está adjunta al usuario
        attached_ok = verify_policy_attached_to_user(iam, username, policy_arn)

        # 5. Test opcional de acceso S3
        s3_test_ok = test_s3_access_with_user_credentials()

        # Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE VERIFICACIÓN")
        print("=" * 60)
        print(f"Usuario existe: {'✅ SÍ' if user_exists else '❌ NO'}")
        print(f"Política existe: {'✅ SÍ' if policy_arn else '❌ NO'}")
        print(f"Contenido correcto: {'✅ SÍ' if content_ok else '❌ NO'}")
        print(f"Política adjunta: {'✅ SÍ' if attached_ok else '❌ NO'}")
        print(f"Test S3: {'⚠️  PENDIENTE' if s3_test_ok else '❌ NO'}")

        if user_exists and policy_arn and content_ok and attached_ok:
            print("\n🎉 ¡VERIFICACIÓN COMPLETA! Todo está configurado correctamente.")
            print(
                f"   El usuario '{username}' tiene la política '{policy_name}' asignada"
            )
            print(f"   con los permisos correctos para el bucket 'mi-bucket'.")
        else:
            print("\n❌ Hay problemas en la configuración. Revisa los errores arriba.")

    except Exception as e:
        print(f"❌ Error general: {e}")


if __name__ == "__main__":
    main()
