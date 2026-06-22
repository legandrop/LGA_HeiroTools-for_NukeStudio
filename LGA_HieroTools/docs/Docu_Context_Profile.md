# LGA_HieroTools - Studio/Client Context

## Objetivo

Permitir que las tools de Hiero trabajen en modo `studio` o `client` sin cambiar código,
solo editando un INI.

## Archivo de control

Ubicación:

- `~/.nuke/Python/Startup/LGA_HieroTools_context.ini`

Formato:

```ini
[Context]
mode=studio
```

Valores válidos:

- `mode=studio`
- `mode=client`

## Qué cambia por contexto

- Lectura de `config.secure` y `.key` desde:
  - `%APPDATA%/LGA/PipeSync` (studio)
  - `%APPDATA%/LGA/PipeSyncClient` (client)
- Resolución de `pipesync.db` y `pipesync_playlists.db` mediante helper compartido
  (`LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`) sin hardcodes fijos por script.
- Fallback de escaneo base en panel de proyectos:
  - `T:\` en studio
  - `N:\` en client (si no hay `AltTPath`)
- Scope de tasks en herramientas de edición:
  - `studio`: `comp`, `roto`, `cleanup`
  - `client`: solo `comp` (aplica a Create v000 y su flujo post-import desde Import Shot)

## Módulos clave

- `LGA_NKS_Shared/LGA_NKS_ContextProfile.py`
- `LGA_NKS_Shared/SecureConfig_Reader.py`
- `LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`
- `LGA_NKS_Shared/LGA_NKS_PipeSyncPreflight.py`

## Documentación complementaria

- `LGA_HieroTools/docs/Doc_HieroTools_Studio_Client_Context.md`
  (lista de archivos adaptados, pendientes y reglas de operación Pull/Push).
