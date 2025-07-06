# LGA NKS Wasabi - Gestión de Políticas IAM

Este módulo permite crear y gestionar políticas de acceso IAM en Wasabi para usuarios específicos, usando boto3 con dependencias locales.

## Archivos Principales

### `TestPoli.py`
**Script principal** para crear/actualizar políticas IAM y asignarlas a usuarios.

**Funcionalidad:**
- Detecta si una política ya existe
- Si existe: actualiza su contenido con una nueva versión
- Si no existe: crea la política desde cero
- Asigna la política al usuario especificado
- Maneja errores de permisos y conexión

**Uso:**
```bash
python TestPoli.py
```

**Configuración requerida:**
- Variables de entorno: `WASABI_ADMIN_KEY` y `WASABI_ADMIN_SECRET`
- Usuario objetivo: `TestPoli`
- Política objetivo: `TestPoli_policy`

**Política configurada:**
Acceso específico al bucket `vfx-etdm` con permisos para:
- Listar todos los buckets (`s3:ListAllMyBuckets`)
- Obtener ubicación de buckets (`s3:GetBucketLocation`)
- Listar contenido del bucket `vfx-etdm` con prefijos específicos
- Acceso completo a la ruta `103/ETDM_3003_0090_DeAging_Cocina/`

### `verify_updated_policy.py`
**Script de verificación** que confirma que la política se creó/actualizó correctamente.

**Funcionalidad:**
- Verifica que la política existe
- Compara el contenido actual vs. el esperado
- Valida que la política está asignada al usuario
- Muestra información detallada de versiones y fechas

**Uso:**
```bash
python verify_updated_policy.py
```

### `verify_policy_created.py`
**Script de verificación general** para políticas existentes.

**Funcionalidad:**
- Verificación básica de políticas
- Útil para diagnóstico general
- Menos específico que `verify_updated_policy.py`

## Dependencias Locales

El módulo incluye todas las dependencias de boto3 en subcarpetas:
- `boto3/` - Cliente AWS/Wasabi
- `botocore/` - Core de boto3
- `dateutil/` - Manejo de fechas
- `jmespath/` - Consultas JSON
- `urllib3/` - Comunicación HTTP
- `s3transfer/` - Transferencias S3
- `six.py` - Compatibilidad Python 2/3

## Configuración

### Variables de Entorno
```powershell
$env:WASABI_ADMIN_KEY = "tu_clave_de_acceso"
$env:WASABI_ADMIN_SECRET = "tu_clave_secreta"
```

### Endpoints Utilizados
- **IAM**: `https://iam.wasabisys.com`
- **S3**: `https://s3.wasabisys.com`
- **Región**: `us-east-1`

## Flujo de Trabajo

1. **Ejecutar** `TestPoli.py` para crear/actualizar la política
2. **Verificar** con `verify_updated_policy.py` que todo funcionó correctamente
3. **Resultado**: Usuario `TestPoli` con acceso controlado al bucket `vfx-etdm`

## Estructura de la Política

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
      "Resource": "arn:aws:s3:::vfx-etdm",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["", "103/", "103/ETDM_3003_0090_DeAging_Cocina/*"]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::vfx-etdm/103/ETDM_3003_0090_DeAging_Cocina",
        "arn:aws:s3:::vfx-etdm/103/ETDM_3003_0090_DeAging_Cocina/*"
      ]
    }
  ]
}
```

## Notas Técnicas

- **Gestión de versiones**: Las políticas se actualizan creando nuevas versiones
- **Manejo de errores**: Incluye fallbacks para problemas de permisos
- **Compatibilidad**: Funciona sin instalación global de boto3
- **Debug**: Variable `DEBUG = True` para mensajes detallados
