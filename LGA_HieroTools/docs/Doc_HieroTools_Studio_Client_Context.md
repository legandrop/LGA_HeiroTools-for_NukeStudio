# LGA_HieroTools - Contexto Studio/Client (integración con PipeSync)

## Referencia principal

Este documento complementa a:

- `C:/Portable/LGA_PipeSync_2/Docs/Doc_Studio_Client_Context.md`

PipeSync define la arquitectura de contexto. Este MD documenta cómo se aplica en
HieroTools, qué scripts quedaron adaptados y cuáles requieren revisión adicional.

## Estado actual

- Control de contexto por INI: `LGA_HieroTools_context.ini` (`mode=studio|client`).
- Resolución de `config.secure/.key` por contexto activo.
- Resolución de cache/DB por contexto activo (con fallback portable histórico).
- Preflight bloqueante en Pull/Push con mensajes UI cuando faltan prerequisitos.
- Projects Panel con switch Studio/Client visible solo para `lega@wanka.tv`
  (leyendo PipeSync normal).
- Para los demás usuarios, el Projects Panel no crea ni conecta los botones del
  switch; el panel inicia normalmente y usa el contexto configurado.

## Reglas operativas

- Si falta `config.secure` o `pipesync.db`, Pull y Push muestran error claro.
- Push además valida `Flow.Url`, `Flow.Login`, `Flow.Password`.
- En client no se debe caer en DB studio como fallback funcional.
- El switch Studio/Client actualiza INI, fuerza recarga del Projects Panel y
  avisa por el bus a los paneles suscriptos.
- Scope de tasks por contexto:
  - `studio`: tasks `comp`, `roto`, `cleanup`.
  - `client`: solo task `comp` (no se consideran `roto`/`cleanup`).

## Paneles dinamicos por contexto

El switch existe para **un solo usuario**. El resto tiene contexto FIJO, definido
por el zip que instalo (ver Packaging), y nunca lo cambia en caliente. Por eso
toda la maquinaria dinamica esta detras de un gate:

- `LGA_NKS_Shared/LGA_NKS_ContextSwitch.py` resuelve `has_context_switch()`
  comparando el `Flow.Login` del perfil PipeSync **normal** contra
  `SWITCH_USER_LOGIN`. El resultado no cambia durante la sesion, asi que se
  memoiza: resolverlo implica leer y desencriptar `config.secure`, y antes lo
  hacian por separado el Projects Panel (dos veces), el UIManager y el ViewerTL.
- Si el gate da **False**, `subscribe()` y `notify()` no hacen nada: no se
  instancia el QObject del bus, no se conecta ninguna senal y no queda ningun
  callback vivo. El panel lee `get_context_mode()` una vez en `__init__` — una
  lectura de INI que ya ocurria — arma su UI y ahi termina.
- Si da **True**, recien ahi se crea el bus. `ProjectsPanel.set_context_mode()`
  emite **despues** de escribir el INI, porque los suscriptos releen el contexto
  y tienen que ver el valor nuevo.

Paneles suscriptos: Flow Panel (`on_context_changed` -> `build_buttons`) y
Assignee Panel (`on_context_changed` -> `build_buttons`).

### Estados de Flow por contexto

Los dos sitios de Flow no tienen la misma lista de `sg_status_list`, asi que los
botones del Flow Panel y los dropdowns de Create Shot se filtran por contexto.
Detalle completo en [Docu_Flow_Estados_Colores.md](Docu_Flow_Estados_Colores.md).

### Assignee Panel en client

En client el panel queda **deshabilitado**, con el motivo a la vista. No es una
decision de UI: es que ahi no hay assignees que mostrar.

- El envelope `HumanUser.sg_pipesync_user_json` es un custom field que solo
  existe en el sitio de studio. En client todos los usuarios llegan con
  `assignable = 0`.
- La `pipesync_stats.db` de client tampoco tiene las columnas `panel_order` y
  `skip_wasabi_policy`, asi que la query de `load_flow_users()` levantaba
  `OperationalError` y devolvia lista vacia.
- Las policies de Wasabi por shot no aplican: en client el acceso se resuelve con
  Vendor Groups y permission rules de Flow.

Antes de este cambio el panel se dibujaba igual, con los dos botones fijos y
ningun usuario — indistinguible de "PipeSync todavia no sincronizo", que es un
problema distinto y con arreglo.

## Impacto en herramientas de Edit

- `Create v000`:
  - En `client` la UI muestra únicamente el botón `comp`.
  - El chequeo de solape/versions en timeline para elegibilidad de shot se hace
    solo sobre el track de `comp`.
  - Un shot se considera completo en `client` cuando `comp` ya tiene clip
    superpuesto en el rango del shot.
- `Import Shot`:
  - El import mantiene su comportamiento general.
  - En `client`, el flujo post-import `Create v000` hereda el scope de tasks
    del contexto (solo `comp`).

## Archivos adaptados (confirmados)

### Núcleo de contexto

- `LGA_HieroTools_context.ini`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextProfile.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextSwitch.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py`
- `LGA_HieroTools/LGA_NKS_Shared/SecureConfig_Reader.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_BucketResolver.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_PipeSyncPreflight.py`
- `LGA_HieroTools/docs/Docu_Context_Profile.md`

### Flow Pull / Push

- `LGA_HieroTools/LGA_NKS_Flow_Panel.py`
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py`

### Playlist / permisos

- `LGA_HieroTools/LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Pull.py`
- `LGA_HieroTools/LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Push.py`
- `LGA_HieroTools/LGA_NKS_Playlist_Panel_py/LGA_NKS_FlowPlaylist_Shot_info.py`
- `LGA_HieroTools/LGA_NKS_Playlist_Panel_py/LGA_NKS_Playlist_Panel_Permissions.py`

### Projects

- `LGA_HieroTools/LGA_NKS_Projects_Panel.py`
- `LGA_HieroTools/LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py`
- `LGA_HieroTools/LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py`

### Edit / CreateV000

- `LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py`
- `LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_import_shots.py` (flujo post-import hacia CreateV000)

## Archivos revisados que siguen parciales o con deuda

- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_OpenPath.py`
  - usa rutas hardcodeadas de instalación (no completamente context-aware).
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py`
  - requiere confirmar matriz Studio/Client en entorno deploy.
- `LGA_HieroTools/+Building_Blocks/PipeSync_Usuario_Actual.md`
  - documentación desactualizada respecto a estructura actual shared/contexto.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull_README.md`
  - referencias históricas y ejemplos con paths legacy.

## Packaging (release generator)

- El `_LGA_ReleaseGen-HieroTools.bat` genera dos zips y cada uno viaja con un
  `LGA_HieroTools_context.ini` fijado por el packaging, independiente del
  INI activo de Lega al momento de releasar:
  - Zip público `*_gh.zip`: `mode = client` (fuente:
    `Python/Startup/LGA_HieroTools_context_gh.ini`).
  - Zip interno `*.zip`: `mode = studio` (fuente:
    `Python/Startup/LGA_HieroTools_context_studio.ini`).
- Los INI fuente son fijos, versionados y verificados por preflight
  (existencia + valor de `mode`) antes de empaquetar.
- El INI se agrega al zip con 7z desde un directorio temporal renombrado a
  `Startup/LGA_HieroTools_context.ini`, así el installer lo deposita en el
  path esperado.
- El `i_win_engine.ps1` copia el `LGA_HieroTools_context.ini` a
  `%USERPROFILE%/.nuke/python/startup/` siempre pisando el previo. No se
  respeta el INI del usuario final: la política es que el modo lo define el
  zip que se instala (client para gh, studio para interno).
- Consecuencia: la editora del cliente siempre arranca en modo client sin
  intervención manual, y los demás reviewers de estudio siempre arrancan en
  studio (sin ver el switch, porque su `Flow.Login` de PipeSync normal no
  es `lega@wanka.tv`).

## Decisiones de diseño implementadas

- Switch en Projects Panel:
  - persistencia en `LGA_HieroTools_context.ini`;
  - override de sesión vía `LGA_HIEROTOOLS_CONTEXT_INI` y `PIPESYNC_CONTEXT`;
  - recarga de panel/proyectos sin reinicio obligatorio.
- Visibilidad del switch:
  - solo si `Flow.Login` de `%APPDATA%/LGA/PipeSync/config.secure` es
    `lega@wanka.tv`.
- Preflight:
  - validación común para Pull/Push con mensajes de error accionables.

## Gaps detectados (seguimiento)

- Unificar paths de runtime/ejecutable de PipeSync en módulos de Coordination.
- Revisar documentación auxiliar para eliminar ejemplos studio-only.
- Validar en QA que todos los paneles abiertos en sesión refrescan contexto sin
  reinicio en escenarios edge.
