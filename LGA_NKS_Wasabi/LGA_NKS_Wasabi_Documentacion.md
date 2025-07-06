# LGA NKS Wasabi - Gestión Automática de Políticas IAM

Este módulo automatiza la creación y gestión de políticas de acceso IAM en Wasabi basándose en los clips seleccionados en Hiero.

## Scripts Principales

### `LGA_NKS_Wasabi_PolicyAssign.py`
**Script principal** que se ejecuta desde Hiero para crear/actualizar políticas IAM automáticamente.

**Funcionalidad:**
- Obtiene rutas de clips seleccionados en el timeline de Hiero
- Parsea las rutas para extraer bucket, carpeta y subcarpeta
- Detecta si la política ya existe y la actualiza sin duplicar permisos
- Crea nueva política si no existe
- Asigna la política al usuario especificado

**Configuración:**
- `USERNAME = "TestPoli"` - Variable para cambiar el usuario objetivo
- Nombre de política: `{USERNAME}_policy`
- Requiere variables de entorno: `WASABI_ADMIN_KEY` y `WASABI_ADMIN_SECRET`

**Uso:**
1. Seleccionar clips en el timeline de Hiero
2. Ejecutar el script desde el panel de Flow
3. El script procesará automáticamente las rutas y creará/actualizará los permisos

**Ejemplo de procesamiento:**
```
Ruta: T:\VFX-ETDM\103\ETDM_3003_0100_DeAging_Cocina\_input\archivo.exr
Resultado: Acceso al bucket 'vfx-etdm' carpeta '103/ETDM_3003_0100_DeAging_Cocina'
```

### `verify_policy_assign.py`
**Script de verificación** que confirma que las políticas se crearon correctamente.

**Funcionalidad:**
- Verifica que la política existe en Wasabi
- Compara el contenido actual vs. el esperado
- Valida que la política está asignada al usuario
- Muestra información detallada de permisos y versiones

**Uso:**
```bash
python verify_policy_assign.py
```

**Verificaciones realizadas:**
- Existencia de la política
- Permisos básicos de S3 (ListAllMyBuckets, GetBucketLocation)
- Permisos específicos de bucket y carpetas
- Asignación correcta al usuario

## Dependencias

El módulo incluye todas las dependencias de boto3 en subcarpetas locales:
- `boto3/` - Cliente AWS/Wasabi
- `botocore/` - Core de boto3
- `dateutil/`, `jmespath/`, `urllib3/`, `s3transfer/`, `six.py` - Dependencias auxiliares

## Configuración de Variables de Entorno

```powershell
$env:WASABI_ADMIN_KEY = "tu_clave_de_acceso"
$env:WASABI_ADMIN_SECRET = "tu_clave_secreta"
```

## Endpoints Utilizados

- **IAM**: `https://iam.wasabisys.com`
- **S3**: `https://s3.wasabisys.com`
- **Región**: `us-east-1`

## Estructura de Política Generada

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListAllMyBuckets", "s3:GetBucketLocation"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::bucket-name",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["", "carpeta/", "carpeta/subcarpeta/*"]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::bucket-name/carpeta/subcarpeta",
        "arn:aws:s3:::bucket-name/carpeta/subcarpeta/*"
      ]
    }
  ]
}
```
