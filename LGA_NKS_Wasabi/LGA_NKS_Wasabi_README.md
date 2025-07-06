# LGA NKS Wasabi - Gestión Automática de Políticas IAM

Este módulo automatiza la creación y gestión de políticas de acceso IAM en Wasabi basándose en los clips seleccionados en Hiero.

## Scripts Principales

### `LGA_NKS_Wasabi_PolicyAssign.py`
**Script de asignación** que se ejecuta desde Hiero para crear/actualizar políticas IAM automáticamente.

**Funcionalidad:**
- Obtiene rutas de clips seleccionados en el timeline de Hiero
- Parsea las rutas para extraer bucket, carpeta y subcarpeta
- **Valida y repara policies corruptas** antes de modificarlas
- Detecta si la política ya existe y la actualiza sin duplicar permisos
- Crea nueva política si no existe
- Asigna la política al usuario especificado
- Maneja casos donde la policy existente tiene statements inválidos

**Configuración:**
- Recibe el usuario como parámetro en `main(username=None)`
- Por defecto usa "TestPoli" si no se especifica usuario
- Nombre de política: `{username}_policy`
- Requiere variables de entorno: `WASABI_ADMIN_KEY` y `WASABI_ADMIN_SECRET`

**Funciones principales:**
- `merge_policy_statements()`: Combina policies existentes con nuevos permisos
- `create_and_manage_policy()`: Gestiona la creación/actualización de policies

### `LGA_NKS_Wasabi_PolicyUnassign.py`
**Script de gestión** que lee policies existentes y permite eliminar shots específicos de forma visual.

**Funcionalidad:**
- Lee la policy existente del usuario especificado
- **Valida y repara policies corruptas** antes y después de modificarlas
- Extrae automáticamente los nombres de shots desde los recursos S3
- Muestra una ventana con lista scrolleable de shots asignados
- Permite eliminar shots individuales con botón "✕" 
- Actualiza la policy en tiempo real eliminando permisos específicos
- Gestiona automáticamente las versiones de policies (límite de 5)
- **Previene la creación de policies inválidas** al eliminar todos los shots

**Configuración:**
- Recibe el usuario como parámetro en `main(username=None)`
- Por defecto usa "TestPoli" si no se especifica usuario
- Lee política: `{username}_policy`
- Requiere variables de entorno: `WASABI_ADMIN_KEY` y `WASABI_ADMIN_SECRET`

**Funciones principales:**
- `remove_shot_from_policy()`: Elimina un shot específico de la policy

**Uso desde Panel:**
1. Hacer **Ctrl+Shift+Click** en el botón del usuario deseado en el panel LGA_NKS_Flow_Assignee_Panel
2. Se abrirá una ventana mostrando todos los shots asignados al usuario
3. Hacer click en "✕" junto a cualquier shot para eliminarlo de la policy
4. La policy se actualiza automáticamente sin necesidad de reiniciar

**Uso desde PolicyAssign:**
1. Seleccionar clips en el timeline de Hiero
2. Hacer **Shift+Click** en el botón del usuario deseado en el panel LGA_NKS_Flow_Assignee_Panel
3. Se abrirá una ventana de estado mostrando el progreso
4. El script procesará automáticamente las rutas y creará/actualizará los permisos

**Uso directo:**
- `module.main(username)`: Llamada programática con usuario específico

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

## Integración con Panel de Assignees

### Ventana de Estado y Procesamiento en Hilos
Cuando se ejecuta desde el panel (Shift+Click), el script muestra automáticamente una ventana de estado:
- **Mensaje inicial**: "Habilitando rutas en la policy del usuario [NOMBRE]" (colores múltiples)
- **Rutas procesadas**: Muestra las rutas reales de buckets que se están habilitando (ej: `vfx-etdm/105/ETDM_5027_0200_Chroma_Camioneta`)
- **Éxito**: Mensaje verde confirmando asignación exitosa
- **Error**: Mensaje rojo con detalles del error (ej: límite de 5 versiones de policy)
- **Botón Close**: Permite cerrar la ventana manualmente después de completar la operación
- **Procesamiento**: Se ejecuta en hilo separado (`WasabiWorker`) para no bloquear la interfaz de Hiero

### Configuración de Usuarios
Los usuarios se cargan desde `Python/Startup/LGA_NKS_Flow_Users.json`:
```json
{
    "users": [
        {
            "name": "Lega Pugliese",
            "color": "#69135e",
            "wasabi_user": "lega"
        }
    ]
}
```

**Clases implementadas en este script:**
- `WasabiStatusWindow` - Ventana de estado con formato HTML y botón Close
- `WasabiWorker` - Procesamiento en hilo separado (QRunnable)
- `WasabiWorkerSignals` - Señales para comunicación entre hilos
- `get_user_info_from_config()` - Obtiene nombre y color del usuario desde JSON
- `main(username)` - Función principal que maneja toda la interfaz y procesamiento

### `wasabi_policy_utils.py`
**Módulo de utilidades** con funciones auxiliares para la gestión de políticas IAM.

**Funciones principales:**
- `validate_and_repair_policy()`: Valida y repara policies corruptas o inválidas
- `create_minimal_policy()`: Crea una policy mínima válida con permisos básicos
- `get_existing_policy_document()`: Obtiene el documento de policy existente
- `manage_policy_versions()`: Gestiona las versiones de policies (límite de 5)
- `read_user_policy_shots()`: Lee y extrae shots de una policy existente
- `remove_shot_from_policy()`: Elimina un shot específico de la policy

**Validación y Reparación:**
- Detecta statements inválidos o corruptos
- Elimina statements de `s3:*` sin recursos válidos
- Limpia prefixes vacíos en statements de `s3:ListBucket`
- Asegura que siempre existan permisos básicos (`s3:ListAllMyBuckets`)
- Convierte policies corruptas en policies mínimas válidas cuando es necesario

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
