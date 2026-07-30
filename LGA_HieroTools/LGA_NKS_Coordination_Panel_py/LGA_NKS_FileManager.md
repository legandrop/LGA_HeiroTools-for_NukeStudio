> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# 🚀 Guía Rápida CLI - FileManager

## 🎯 ¿Qué hace FileManager?

FileManager es una aplicación para sincronizar archivos entre carpetas locales y Wasabi S3. Funciona completamente portable sin instalación.

## 📋 Comandos CLI Disponibles

> Contexto explicito obligatorio: los launchers de Hiero usan siempre
> `--context studio` o `--context client` (resuelto por
> `LGA_NKS_ContextProfile` y centralizado en
> `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_FileManagerLauncher.py`).

### 1. **Abrir FileManager en una ruta específica**
```bash
FileManagerS3.exe --context studio --path "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

- Abre la interfaz gráfica apuntando directamente a esa carpeta
- Escanea automáticamente la contraparte en Wasabi S3
- Muestra archivos locales vs remotos lado a lado

### 2. **Descargar desde Wasabi S3**
```bash
FileManagerS3.exe --context studio --download "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

- Abre la interfaz gráfica
- Muestra diálogo para resolver conflictos (Sobrescribir/Saltar/Cancelar)
- Descarga archivos desde Wasabi hacia la carpeta local
- Muestra progreso en tiempo real

### 3. **Subir a Wasabi S3**
```bash
FileManagerS3.exe --context studio --upload "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

- Abre la interfaz gráfica
- Muestra diálogo para resolver conflictos remotos
- Sube archivos desde carpeta local hacia Wasabi S3
- Muestra progreso en tiempo real

### 4. **Descargar un archivo individual desde Wasabi S3**
```bash
FileManagerS3.exe --context studio --download-file "T:\VFX-MOR\102\MOR_2015_010\_input\MOR_2015_010_EditRef_v01.mov"
```

- Descarga **un único archivo** (no una carpeta) desde Wasabi
- Crea solo la carpeta padre del archivo, no una carpeta con el nombre del archivo
- Resuelve el tamaño real del objeto en S3 antes de encolar la descarga
- Se descarga con `overwrite` activado
- `--download` y `--download-file` aceptan **múltiples rutas** y pueden combinarse en una sola invocación:
  ```bash
  FileManagerS3.exe --context studio --download "T:\VFX-MOR\102\SHOT\_input\seq_v01" --download-file "T:\VFX-MOR\102\SHOT\_input\ref.mov"
  ```

### 5. **Notificar a Hiero al terminar la descarga**
```bash
FileManagerS3.exe --context studio --download-file "T:\VFX-MOR\102\SHOT\_input\ref.mov" --notify-completion "C:\Users\...\Startup\LGA_HieroTools\logs\download_clip_done"
```

- `--notify-completion "<carpeta>"` hace que FileManager escriba un marcador `.json` en `<carpeta>` cuando cada tarea de descarga termina
- El valor es la **carpeta de salida** de los marcadores (Hiero le pasa su propia ruta, así no hay rutas hardcodeadas entre repos)
- Solo afecta a las descargas de esa invocación; lo usa el botón **Download Clip** para disparar la reconexión automática

## 🔧 Cómo usar desde compilar.bat

```bash
# Compilar y ejecutar con CLI
.\compilar.bat --path "T:\VFX-TOC\From_Wanka\20250909\Probando"
.\compilar.bat --download "T:\VFX-TOC\From_Wanka\20250909\Probando"
.\compilar.bat --upload "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

## 🍎 macOS: uso recomendado (app abierta o cerrada)

En macOS, `open -a ... --args` puede ignorar argumentos si la app ya está abierta.
Para garantizar que el CLI funcione siempre, usar el wrapper:

```bash
./fm_cli_mac.sh --path "/Volumes/T Viaja/T/VFX-BRDA/010-350/BRDA_040_010"
./fm_cli_mac.sh --download "/Volumes/T Viaja/T/VFX-BRDA/010-350/BRDA_040_010"
./fm_cli_mac.sh --upload "/Volumes/T Viaja/T/VFX-BRDA/010-350/BRDA_040_010"
```

Alternativa directa sin wrapper:

```bash
open -na /Users/leg4/Desktop/Codin/LGA_FileManager/build/FileManagerS3.app --args --path "/Volumes/T Viaja/T/VFX-BRDA/010-350/BRDA_040_010"
```

Notas:
- `fm_cli_mac.sh` es solo capa de exec: cuando lo lanza `LGA_NKS_FileManagerLauncher`, recibe la ruta ya resuelta segun el flag `Desarrollo` via `--app-path <ruta>`. En uso manual (sin `--app-path`) usa por defecto `build/FileManagerS3.app` (dev) o `/Applications/FileManagerS3.app` (prod).
- Para deploy, podés definir `FILEMANAGER_APP_PATH` con la ruta del `.app`.

## 📝 Reglas importantes

### ✅ Rutas válidas
- Deben empezar con `VFX-` (ej: `VFX-TOC`, `VFX-PHLDA`)
- Pueden tener barras `/` o `\`
- Usar comillas `"` si hay espacios

### ✅ Ejemplos válidos
```bash
--path "T:\VFX-TOC\From_Wanka\20250909\Probando"
--path "T:/VFX-PHLDA/022-055/PHLDA_030_010_Stab_Auto"
--download "T:\VFX-TOC\From_Wanka\20250909\TOC_067_010_HdMkup_Fabric_comp_v13"
```

### ❌ Ejemplos inválidos
```bash
--path "C:\Users\MiUsuario\Desktop"  # No es VFX-
--path "T:\MiProyecto\Archivos"      # No es VFX-
```

## 🎮 Comportamiento

- **Primera ejecución**: Abre interfaz gráfica y ejecuta la operación
- **App ya abierta**: Reutiliza la instancia existente (no abre nueva ventana)
- **Sin argumentos**: Abre interfaz normal (todos los tabs disponibles)

## 📊 Estados de archivos

- 🟢 **Verde**: Archivo existe local y remotamente (igual)
- 🔴 **Rojo**: Solo existe remotamente (se puede descargar)
- 🔵 **Azul**: Solo existe localmente (se puede subir)
- 🟡 **Amarillo**: Existe en ambos pero diferente (conflicto)

## 🚨 Solución de problemas

### "Bucket no encontrado"
- Verificar que la ruta empiece con `VFX-*`
- Revisar configuración de credenciales Wasabi

### "Carpeta no existe"
- Para `--download`: La carpeta se crea automáticamente
- Para `--upload`: Verificar que la ruta local exista

### "Conflicto de archivos"
- El diálogo muestra opciones: Sobrescribir/Saltar/Cancelar
- Elegir según necesites mantener o reemplazar archivos

---

## 🤖 Integración con Panel FlowProd

### Botones FileManager en Hiero/Nuke Studio

Los siguientes botones están disponibles en el panel **Flow Production** de Hiero:

#### 🎯 **Open in FileManager**
- **Función**: Abre la carpeta del shot seleccionado en FileManager
- **Comando**: `FileManagerS3.exe --context studio --path "ruta_del_shot"`
- **Uso**: Explorar y gestionar archivos del shot local vs Wasabi S3
- **Color**: Marrón (#8e6c17)

#### ⬇️ **Download Shot**
- **Función**: Descarga el shot completo desde Wasabi S3
- **Comando**: `FileManagerS3.exe --context studio --download "ruta_del_shot"`
- **Uso**: Sincronizar archivos remotos hacia local
- **Color**: Marrón (#8e6c17)

#### ⬆️ **Upload Shot**
- **Función**: Sube el shot completo a Wasabi S3
- **Comando**: `FileManagerS3.exe --context studio --upload "ruta_del_shot"`
- **Uso**: Sincronizar archivos locales hacia remoto
- **Color**: Marrón (#8e6c17)

#### 🎬 **Download Clip**
- **Función**: Descarga **solo el/los clip(s) seleccionado(s)** desde Wasabi S3, no el shot completo
- **Doble acción** (invertida en v3.80):
  - **Click**: descarga la **última versión** disponible en Wasabi y dispara la actualización de versión en el timeline.
  - **Shift+Click**: descarga la versión que el clip tiene puesta ahora.
- **Diferencia con Download Shot**: `Download Shot` descarga la carpeta entera del shot (unidad/proyecto/grupo/shot). `Download Clip` descarga únicamente el media del clip seleccionado.
- **Selección de clip**: usa el **Método 1 (selección pura)** — opera sobre los clips realmente seleccionados en el timeline, **ignorando el playhead**. Soporta seleccionar y descargar **uno o varios clips a la vez**, de cualquier track.
- **Lógica de ruta a descargar** (según `mediaSource().singleFile()`):
  - **Archivo de video único** (`.mov`, `.mp4` → `singleFile() == True`): se descarga ese archivo con `--download-file`.
  - **Secuencia de imágenes** (`..._%04d.exr` → `singleFile() == False`): se descarga la **carpeta** que contiene la secuencia con `--download`.
- **Comando**: arma **una sola llamada** combinando todos los clips seleccionados:
  `FileManagerS3.exe --context studio --download "<carpeta_seq1>" "<carpeta_seq2>" --download-file "<archivo1>" "<archivo2>" --notify-completion "<carpeta_marcadores>"`
- **Comando en Shift+Click**: usa los nuevos flags de latest:
  `FileManagerS3.exe --context studio --download-latest "<carpeta_seq_v05>" --download-latest-file "<archivo_v05.mov>" --notify-completion "<carpeta_marcadores>"`
- **Overwrite**: los archivos individuales se descargan con `overwrite=true` (un clip online se puede re-descargar).
- **Tabs**: a diferencia de los botones de shot, Download Clip **no abre ningún tab** en FileManager — solo dispara la descarga y FileManager cambia a la pestaña *Activity*.
- **Reconexión automática**: el comando incluye `--notify-completion "<Startup>/logs/download_clip_done"`. FileManager escribe un marcador `.json` al terminar cada descarga; el watcher `LGA_NKS_DownloadClip_Watcher.py` lo detecta y reconecta el clip offline en Hiero automáticamente (ver sección **Reconexión automática** más abajo).
- **Logging**: el script imprime via `debug_print`, por cada clip: nombre (`clip.name()`), ruta (`mediaSource().fileinfos()[0].filename()`), tipo (archivo/secuencia) y estado online/offline (`mediaSource().isMediaPresent()`).
- **Color**: Gradiente magenta/violeta (`gradient_magenta_violet`)

### 📂 Estructura de Rutas

Los botones operan sobre la **ruta del shot**, no del archivo individual:
```
Unidad:/VFX-PROJECTO/GRUPO/SHOT_NAME
Ejemplo: T:/VFX-LC/101/LC_1010_010_Beauty_Senora
```

**Nota**: La ruta se extrae automáticamente del clip seleccionado usando lógica inteligente (playhead primero, selección como fallback).

### 🔧 Implementación Técnica

Los scripts ejecutan comandos CLI reales de FileManager:
- **OpenPath**: `FileManagerS3.exe --context studio --path "ruta_del_shot"`
- **Download**: `FileManagerS3.exe --context studio --download "ruta_del_shot"`
- **Upload**: `FileManagerS3.exe --context studio --upload "ruta_del_shot"`
- **DownloadClip**: `FileManagerS3.exe --context studio --download "<carpeta_secuencia>" ... --download-file "<archivo>" ... --notify-completion "<carpeta_marcadores>"` (una sola llamada combinada para todos los clips seleccionados, con notificación de finalización)

**Cálculo de ruta del shot**: Los scripts detectan la carpeta del shot con lógica inteligente:

**Algoritmo**:
1. Normaliza la ruta para manejar separadores mixtos (`/` y `\`)
2. Busca primero un patrón de shot (ej: `BRDA_050_010`) y corta la ruta hasta esa carpeta
3. Si no encuentra patrón, usa una estructura de ruta dependiendo del OS:
   - macOS: `/Volumes/<volumen>/<drive>/<proyecto>/<grupo>/<shot>`
   - Windows: `T:/<proyecto>/<grupo>/<shot>`
4. Si la ruta es corta, usa fallback subiendo carpetas desde el archivo

**Ejemplo**:
- Ruta completa: `T:/VFX-LC/101/LC_1021_050_Beauty_Senora/Comp/4_publish/LC_1021_050_Beauty_Senora_comp_v014/LC_1021_050_Beauty_Senora_comp_v014_%04d.exr`
- Detecta `LC_1021_050_Beauty_Senora` y corta en: `T:/VFX-LC/101/LC_1021_050_Beauty_Senora`

**Rutas del ejecutable** (las resuelve `LGA_NKS_Shared/LGA_NKS_FileManagerLauncher.py`):
- **Producción**: `C:\Portable\LGA\FileManagerS3\FileManagerS3.exe` (la carpeta se renombró en FileManager S3 v0.906; el nombre viejo `LGA\FileManager` quedó reservado para la app local)
- **Desarrollo**: `C:\Portable\LGA_FileManager\build\FileManagerS3.exe` (cuando `Desarrollo = True`)

**macOS**:
- Wrapper recomendado: `LGA_NKS_Coordination_Panel_py/fm_cli_mac.sh` (usa `open -na`)

**Lógica de selección automática**:
- Si `Desarrollo = True` y el archivo existe en la carpeta build → usa desarrollo
- Si `Desarrollo = True` pero el archivo NO existe → usa producción como fallback
- Si `Desarrollo = False` → usa producción

Los scripts incluyen una variable `Desarrollo = True` para alternar entre rutas con verificación automática.

**Download Clip sigue la misma lógica**: las cuatro tools llaman a `build_filemanager_command()` del launcher compartido, que aplica ese patrón en un solo lugar (antes cada script tenía su propio `get_filemanager_exe()`). Por eso funciona tanto para quien tiene la versión build (la usa si existe) como para el resto de los usuarios (cae automáticamente a la versión instalada `C:\Portable\LGA\FileManagerS3\FileManagerS3.exe`). El watcher y el mecanismo de marcadores son independientes del ejecutable usado (la ruta de marcadores la pasa Hiero por `--notify-completion`).

> **⚠️ Despliegue**: los flags `--download-file` y `--notify-completion` viven en el código fuente de FileManager (`src/main.cpp`). Una versión **build** recién compilada los tiene; la versión **instalada** que usan los demás usuarios solo los tendrá cuando se **redespliegue** FileManager desde el código actualizado. Hasta entonces, una versión instalada vieja ignoraría esos flags (las secuencias vía `--download` se descargarían igual, pero los archivos sueltos y la reconexión automática no funcionarían).

Los comandos se ejecutan de forma asíncrona (subprocess.Popen) para no bloquear la interfaz de Hiero/Nuke Studio.

---

## 🔄 Reconexión automática (Download Clip)

Cuando se usa **Download Clip**, al terminar la descarga el clip se reconecta solo en Hiero, sin intervención del usuario. El mecanismo es **archivo marcador** (FileManager escribe, Hiero vigila):

### Flujo

1. **Download Clip** arma el comando agregando `--notify-completion "<Startup>/logs/download_clip_done"`.
2. **FileManager** descarga normalmente. Al recibir la señal `celeryTaskCompleted` de una tarea lanzada con `--notify-completion`, escribe un marcador `.json` (de forma atómica: `.tmp` + rename) en esa carpeta:
   ```json
   { "task_id": "...", "success": true, "items": [ { "path": "T:/.../ref.mov", "kind": "file" } ] }
   ```
   `kind` es `"file"` (archivo único) o `"folder"` (carpeta de la secuencia).
   En modo latest puede incluir además:
   ```json
   { "requested_path": "T:/..._v05.mov", "latest": true }
   ```
   para que Hiero matchee el clip por ruta original y haga `setActiveVersion()` al nuevo media.
3. **El watcher** `LGA_NKS_Coordination_Panel_py/LGA_NKS_DownloadClip_Watcher.py` (lo arranca el Coordination Panel al iniciar Hiero) revisa esa carpeta cada ~5 s con un `QTimer`. Por cada marcador:
   - Si `success` es `false` → no reconecta, descarta el marcador.
   - Si `success` es `true` → busca el/los clip(s) cuyo media coincide (`file` = ruta exacta; `folder` = `dirname` del media de la secuencia), ejecuta `reconnectMedia()` con fallback `refresh()`, hace un **toggle del estado `enabled`** del track item (restaurando el original) para forzar el refresco del viewer, y borra el marcador.

   > **Por qué el toggle de `enabled`**: tras `reconnectMedia()` el clip figura online pero el viewer mantiene cacheado el frame negro/offline. Cambiar el estado `enabled` del track item y volverlo a su valor obliga a Hiero a re-renderizarlo (es el mismo efecto que el disable/enable manual). Flow Pull no sufre esto porque al final llama a `enable_or_disable_clips()`, que hace `setEnabled()` sobre cada clip.

### Garantías de robustez

- El watcher corre en el **hilo principal** de Hiero (la reconexión toca la API de Hiero). El `QTimer` no bloquea: el callback es trabajo de milisegundos.
- Es **stateless** entre ticks: si la descarga se cancela, FileManager se cierra o crashea, **no se escribe marcador** → el watcher sigue idle y el clip queda offline (correcto).
- Cada marcador se **borra siempre** tras procesarlo (haya match o no).
- Marcadores sin clip que matchee (proyecto no cargado aún) se reintentan hasta un **TTL de 30 min** y luego se descartan → sin huérfanos eternos.
- Escritura atómica del marcador (`.tmp` + rename) → el watcher nunca lee un `.json` a medio escribir.

---

## 🧪 Arquitectura tecnica: Shift+Click en Download Clip (ultima version)

### Hallazgos de investigacion (estado actual)

- **Panel con doble accion ya resuelta en otros botones**:
  `LGA_NKS_Coordination_Panel.py` ya implementa `CustomButton` + `setShiftClickHandler()` para `Reveal in Flow` y `.Psync`, con tooltip explicito `Click` / `Shift+Click`.
- **Download Clip actual en Startup**:
  `LGA_NKS_FileManager_DownloadClip.py` soporta modo normal y modo latest:
  - normal: `--download` / `--download-file`
  - latest: `--download-latest` / `--download-latest-file`
  ambos con `--notify-completion`.
- **Watcher actual en Startup**:
  `LGA_NKS_DownloadClip_Watcher.py` reconecta por matching de ruta y, cuando el marker indica `latest=true`, aplica flujo de cambio de version en timeline (VersionScanner + `setActiveVersion()` + reconexion/repaint).
- **CLI de FileManager actual**:
  `src/main.cpp` soporta `--download`, `--download-file`, `--download-latest`, `--download-latest-file`, `--upload`, `--notify-completion` (incluyendo multi-ruta + IPC cuando la app ya esta abierta).
- **Infra de listado S3 ya existente y madura**:
  `S3PythonManager` + `py_scr/s3_persistent_server.py` + `py_scr/s3_list.py` ya resuelven listados no recursivos/recursivos; `S3Celery_ConflictChecker` ya filtra versiones para otros flujos.
- **Credenciales y seguridad**:
  FileManager centraliza credenciales Wasabi via `SecureConfig` (C++) y `SecureConfig_Reader.py` (Python), evitando duplicar logica sensible en Hiero.

### Decision tecnica recomendada

- **Centralizar la deteccion de ultima version en FileManager (CLI nuevo)** y mantener Hiero como cliente liviano (seleccion + UI + disparo).
- Motivo: evita duplicar parseo de versiones, acceso a credenciales y errores de S3 en dos repos distintos.

### Implementacion aplicada

1. **UI del panel (Startup)**
   - `Download Clip` usa `CustomButton` con doble accion.
   - Tooltip explicita `Click` vs `Shift+Click`.

2. **Script Download Clip (Startup)**
   - `LGA_NKS_FileManager_DownloadClip.py` incorpora parametro `download_latest`.
   - Envia flags latest de FileManager cuando corresponde.

3. **CLI nuevo en FileManager**
   - `main.cpp` parsea y enruta `--download-latest` y `--download-latest-file`.
   - Resuelve siblings por version y encola descarga en el mismo pipeline (S3Celery + Activity + notify marker).

4. **Regla de version solicitada**
   - Se toma el patron `_v##` o `_v###` del nombre.
   - Si existen multiples `_v...`, se usa **el ultimo**.
   - Para video: se lista carpeta padre del archivo.
   - Para secuencias: se lista carpeta contenedora de las carpetas de version.

5. **Reconexion con cambio de version en Hiero (alineado a Flow Pull)**
   - El watcher soporta marker latest con `requested_path`.
   - Cuando aplica, matchea el clip original y ejecuta subida de version en timeline (flujo equivalente a Flow Pull).

6. **Verificacion**
   - Casos: clip offline/online, video unico, secuencia, multiples clips seleccionados, markers sin match, path sin version, multiples `_v` en nombre.
   - Confirmar que la UI no bloquea y que Activity/markers siguen funcionando igual que hoy.

### Riesgos principales y mitigacion

- **Riesgo**: marker con path distinto al media actual no matchea en watcher.
  **Mitigacion**: ampliar payload del marker y agregar estrategia de match por identidad/base de clip + subida de version.
- **Riesgo**: ambiguedad de version por nombres no estandar.
  **Mitigacion**: regex explicita para "ultimo `_v\d+`" + logs de diagnostico por clip.
- **Riesgo**: divergencia entre repos (Startup vs FileManager).
  **Mitigacion**: documentar contrato CLI y marker en ambos repos.

---

## 📚 Referencias Técnicas

- **`LGA_NKS_Coordination_Panel.py`** (raíz de Startup)
  - Clase `FlowProdPanel`: define los botones del panel en `self.fixed_buttons`.
  - `download_shot_from_filemanager()`: lanza `LGA_NKS_FileManager_Download.py`.
  - `upload_shot_to_filemanager()`: lanza `LGA_NKS_FileManager_Upload.py`.
  - `open_shot_in_filemanager()`: lanza `LGA_NKS_FileManager_OpenPath.py`.
  - `download_clip_from_filemanager()`: lanza `LGA_NKS_FileManager_DownloadClip.py`.

- **`LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManager_OpenPath.py`**
  - `main()`, `get_shot_path()`, `build_filemanager_cmd()`: abre la carpeta del shot.

- **`LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManager_Download.py`**
  - `main()`, `get_shot_path()`, `build_filemanager_cmd()`: descarga el shot completo.

- **`LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManager_Upload.py`**
  - `main()`, `get_shot_path()`, `build_filemanager_cmd()`: sube el shot completo.

- **`LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManager_DownloadClip.py`**
  - `main()`: itera los clips seleccionados, los clasifica en secuencias/archivos y dispara la descarga.
  - `_get_selected_clips()`: obtiene los clips seleccionados (Método 1, sin playhead).
  - `_inspect_clip()`: extrae nombre, ruta, tipo (`singleFile()`) y estado online/offline.
  - `_path_has_vfx_root()`: valida que la ruta tenga raíz `VFX-` (requisito del CLI).
  - `get_filemanager_exe()`, `build_filemanager_cmd()`: resuelven el ejecutable y arman la llamada combinada de modo normal (`--download` / `--download-file`) o latest (`--download-latest` / `--download-latest-file`) con `--notify-completion`.
  - `get_notify_dir()`: devuelve la carpeta de marcadores (`logs/download_clip_done`).
  - `setup_debug_logging()`, `debug_print()`: sistema de logging a archivo.

- **`LGA_NKS_Coordination_Panel_py/LGA_NKS_DownloadClip_Watcher.py`** (lo arranca el Coordination Panel al iniciar Hiero)
  - `DownloadClipWatcher`: `QObject` con un `QTimer` que vigila la carpeta de marcadores.
  - `start_watcher()`: crea la instancia del watcher (se llama al cargarse el módulo).
  - `_scan_markers()`, `_process_marker()`: leen y procesan los marcadores `.json`.
  - `_find_and_reconnect()`: matchea la ruta del marcador con los clips de las secuencias.
  - `_reconnect_clip()`: ejecuta `reconnectMedia()` con fallback `refresh()` y un toggle de `setEnabled()` para refrescar el viewer.
  - `get_marker_dir()`: carpeta vigilada (debe coincidir con `get_notify_dir()` del script anterior).

- **`LGA_NKS_Coordination_Panel.py`**
  - Al final del módulo carga e inicia `LGA_NKS_DownloadClip_Watcher.py` (mantiene la referencia en `download_clip_watcher_module`).

- **`LGA_NKS_Shared/LGA_NKS_GetClip.py`**
  - `get_selected_clips()`: devuelve los clips seleccionados en el timeline (excluye efectos), usado por DownloadClip.
  - `get_clip_to_process()`: método híbrido playhead+selección, usado por Download/Upload/OpenPath.

- **`C:\Portable\LGA_FileManager\src\main.cpp`** (repo de FileManager)
  - `startCliDownloadFile()`: descarga un archivo individual (resuelve tamaño en S3, encola 1 objeto).
  - `startCliDownload()`: descarga una carpeta completa (shots / secuencias).
  - `startCliDownloadLatestFile()`, `startCliDownloadLatestFolder()`: resuelven sibling de versión más alta y delegan en el pipeline de descarga existente.
  - `registerCliNotifyTask()`, `writeCliCompletionMarker()`: registran la tarea y escriben el marcador `.json` al completarse (señal `celeryTaskCompleted`).
  - Parseo CLI de `--download`, `--download-file`, `--download-latest`, `--download-latest-file` (multi-ruta) y `--notify-completion`; transporte por IPC (`CliCommandPayload`).

---
