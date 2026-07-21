# LGA_HieroTools - Project Bucket Resolver

## Objetivo

Unificar el mapeo entre proyecto lógico y bucket físico Wasabi cuando un mismo
proyecto (`ERSO`) necesita buckets distintos por contexto:

- Studio -> `vfx-erso`
- Client -> `vfx-ers0`

Sin cambiar:

- nombre de proyecto en Flow;
- shot codes;
- carpeta local canónica `VFX-{PROJECT}`.

## Fuente de configuración

El resolver usa el `config.secure` del contexto activo mediante helpers ya
existentes:

- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextProfile.py`
  - `get_context_mode()`
  - `get_secure_config_path()`
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/SecureConfig_Reader.py`
  - `read_secure_config_with_status()`
  - lectura con shared lock para evitar lecturas parciales de `config.secure`.

Schema esperado (opcional):

```json
{
  "Wasabi": {
    "ProjectBucketOverrides": {
      "ERSO": "vfx-ers0"
    }
  }
}
```

## Helper central

Archivo:

- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_BucketResolver.py`

Funciones clave:

- `resolve_bucket_for_project(project_name, snapshot=None)`
- `resolve_bucket_from_local_path(local_path, snapshot=None)`
- `resolve_project_for_bucket(bucket_name, snapshot=None)`
- `resolve_project_folder_from_bucket_and_prefix(bucket_name, prefix, snapshot=None)`
- `normalize_and_validate_overrides(raw_overrides)`
- `load_snapshot(config_dict=None)`
- `build_snapshot_from_raw_value(raw_overrides_value, overrides_field_present, known_projects=None)`

Reglas aplicadas:

- proyecto normalizado a uppercase, `VFX-` opcional;
- clave vacía después de normalizar conservada como warning global;
- bucket normalizado a lowercase + validación DNS/S3;
- fallback legacy solo si no hay entrada explícita para el proyecto;
- entrada explícita inválida => fail-closed (proyecto bloqueado);
- schema no-object en `ProjectBucketOverrides` => fail-closed global;
- colisiones por bucket efectivo (override + fallback de conocidos) también
  bloquean reverse mapping ambiguo;
- ante error transitorio leyendo `config.secure`, el runtime conserva el último
  snapshot válido en vez de volver silenciosamente al fallback.

## Integración runtime en Assignee Panel

Archivo migrado:

- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py`
  - `parse_path_for_policy(...)` ahora usa
    `resolve_bucket_from_local_path(...)`.

Resultado:

- las policies IAM se generan contra el bucket físico correcto del contexto;
- el parse sigue usando `folder/subfolder` de la ruta local para la parte de
  prefix en policy;
- no hay hardcode de `ERSO` ni de `vfx-ers0`.

## Ejemplos

- `N:/VFX-ERSO/060/ERSO_060_010` (Client + override) ->
  `bucket=vfx-ers0`, `prefix=060/ERSO_060_010`
- `T:/VFX-ERSO/060/ERSO_060_010` (Studio sin override) ->
  `bucket=vfx-erso`
- `T:/VFX-MORLASP/1048/MOR_1048_040` (legacy) ->
  `bucket=vfx-morlasp`
