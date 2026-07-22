> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# ÃƒÂ°Ã…Â¸Ã…Â¡Ã¢â€šÂ¬ GuÃƒÆ’Ã‚Â­a RÃƒÆ’Ã‚Â¡pida CLI - FileManager

## ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Â¯ Ãƒâ€šÃ‚Â¿QuÃƒÆ’Ã‚Â© hace FileManager?

FileManager es una aplicaciÃƒÆ’Ã‚Â³n para sincronizar archivos entre carpetas locales y Wasabi S3. Funciona completamente portable sin instalaciÃƒÆ’Ã‚Â³n.

## ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬Â¹ Comandos CLI Disponibles

> Contexto explicito obligatorio: los launchers de Hiero usan siempre
> `--context studio` o `--context client` (resuelto por
> `LGA_NKS_ContextProfile` y centralizado en
> `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_FileManagerLauncher.py`).

### 1. **Abrir FileManager en una ruta especÃƒÆ’Ã‚Â­fica**
```bash
FileManagerS3.exe --context studio --path "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

- Abre la interfaz grÃƒÆ’Ã‚Â¡fica apuntando directamente a esa carpeta
- Escanea automÃƒÆ’Ã‚Â¡ticamente la contraparte en Wasabi S3
- Muestra archivos locales vs remotos lado a lado

### 2. **Descargar desde Wasabi S3**
```bash
FileManagerS3.exe --context studio --download "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

- Abre la interfaz grÃƒÆ’Ã‚Â¡fica
- Muestra diÃƒÆ’Ã‚Â¡logo para resolver conflictos (Sobrescribir/Saltar/Cancelar)
- Descarga archivos desde Wasabi hacia la carpeta local
- Muestra progreso en tiempo real

### 3. **Subir a Wasabi S3**
```bash
FileManagerS3.exe --context studio --upload "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

- Abre la interfaz grÃƒÆ’Ã‚Â¡fica
- Muestra diÃƒÆ’Ã‚Â¡logo para resolver conflictos remotos
- Sube archivos desde carpeta local hacia Wasabi S3
- Muestra progreso en tiempo real

### 4. **Descargar un archivo individual desde Wasabi S3**
```bash
FileManagerS3.exe --context studio --download-file "T:\VFX-MOR\102\MOR_2015_010\_input\MOR_2015_010_EditRef_v01.mov"
```

- Descarga **un ÃƒÆ’Ã‚Âºnico archivo** (no una carpeta) desde Wasabi
- Crea solo la carpeta padre del archivo, no una carpeta con el nombre del archivo
- Resuelve el tamaÃƒÆ’Ã‚Â±o real del objeto en S3 antes de encolar la descarga
- Se descarga con `overwrite` activado
- `--download` y `--download-file` aceptan **mÃƒÆ’Ã‚Âºltiples rutas** y pueden combinarse en una sola invocaciÃƒÆ’Ã‚Â³n:
  ```bash
  FileManagerS3.exe --context studio --download "T:\VFX-MOR\102\SHOT\_input\seq_v01" --download-file "T:\VFX-MOR\102\SHOT\_input\ref.mov"
  ```

### 5. **Notificar a Hiero al terminar la descarga**
```bash
FileManagerS3.exe --context studio --download-file "T:\VFX-MOR\102\SHOT\_input\ref.mov" --notify-completion "C:\Users\...\Startup\LGA_HieroTools\logs\download_clip_done"
```

- `--notify-completion "<carpeta>"` hace que FileManager escriba un marcador `.json` en `<carpeta>` cuando cada tarea de descarga termina
- El valor es la **carpeta de salida** de los marcadores (Hiero le pasa su propia ruta, asÃƒÆ’Ã‚Â­ no hay rutas hardcodeadas entre repos)
- Solo afecta a las descargas de esa invocaciÃƒÆ’Ã‚Â³n; lo usa el botÃƒÆ’Ã‚Â³n **Download Clip** para disparar la reconexiÃƒÆ’Ã‚Â³n automÃƒÆ’Ã‚Â¡tica

## ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â§ CÃƒÆ’Ã‚Â³mo usar desde compilar.bat

```bash
# Compilar y ejecutar con CLI
.\compilar.bat --path "T:\VFX-TOC\From_Wanka\20250909\Probando"
.\compilar.bat --download "T:\VFX-TOC\From_Wanka\20250909\Probando"
.\compilar.bat --upload "T:\VFX-TOC\From_Wanka\20250909\Probando"
```

## ÃƒÂ°Ã…Â¸Ã‚ÂÃ…Â½ macOS: uso recomendado (app abierta o cerrada)

En macOS, `open -a ... --args` puede ignorar argumentos si la app ya estÃƒÆ’Ã‚Â¡ abierta.
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
- `fm_cli_mac.sh` usa por defecto `build/FileManagerS3.app` (dev) o `/Applications/FileManagerS3.app` (prod).
- Para deploy, podÃƒÆ’Ã‚Â©s definir `FILEMANAGER_APP_PATH` con la ruta del `.app`.

## ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Reglas importantes

### ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Rutas vÃƒÆ’Ã‚Â¡lidas
- Deben empezar con `VFX-` (ej: `VFX-TOC`, `VFX-PHLDA`)
- Pueden tener barras `/` o `\`
- Usar comillas `"` si hay espacios

### ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Ejemplos vÃƒÆ’Ã‚Â¡lidos
```bash
--path "T:\VFX-TOC\From_Wanka\20250909\Probando"
--path "T:/VFX-PHLDA/022-055/PHLDA_030_010_Stab_Auto"
--download "T:\VFX-TOC\From_Wanka\20250909\TOC_067_010_HdMkup_Fabric_comp_v13"
```

### ÃƒÂ¢Ã‚ÂÃ…â€™ Ejemplos invÃƒÆ’Ã‚Â¡lidos
```bash
--path "C:\Users\MiUsuario\Desktop"  # No es VFX-
--path "T:\MiProyecto\Archivos"      # No es VFX-
```

## ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Â® Comportamiento

- **Primera ejecuciÃƒÆ’Ã‚Â³n**: Abre interfaz grÃƒÆ’Ã‚Â¡fica y ejecuta la operaciÃƒÆ’Ã‚Â³n
- **App ya abierta**: Reutiliza la instancia existente (no abre nueva ventana)
- **Sin argumentos**: Abre interfaz normal (todos los tabs disponibles)

## ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  Estados de archivos

- ÃƒÂ°Ã…Â¸Ã…Â¸Ã‚Â¢ **Verde**: Archivo existe local y remotamente (igual)
- ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â´ **Rojo**: Solo existe remotamente (se puede descargar)
- ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Âµ **Azul**: Solo existe localmente (se puede subir)
- ÃƒÂ°Ã…Â¸Ã…Â¸Ã‚Â¡ **Amarillo**: Existe en ambos pero diferente (conflicto)

## ÃƒÂ°Ã…Â¸Ã…Â¡Ã‚Â¨ SoluciÃƒÆ’Ã‚Â³n de problemas

### "Bucket no encontrado"
- Verificar que la ruta empiece con `VFX-*`
- Revisar configuraciÃƒÆ’Ã‚Â³n de credenciales Wasabi

### "Carpeta no existe"
- Para `--download`: La carpeta se crea automÃƒÆ’Ã‚Â¡ticamente
- Para `--upload`: Verificar que la ruta local exista

### "Conflicto de archivos"
- El diÃƒÆ’Ã‚Â¡logo muestra opciones: Sobrescribir/Saltar/Cancelar
- Elegir segÃƒÆ’Ã‚Âºn necesites mantener o reemplazar archivos

---

## ÃƒÂ°Ã…Â¸Ã‚Â¤Ã¢â‚¬â€œ IntegraciÃƒÆ’Ã‚Â³n con Panel FlowProd

### Botones FileManager en Hiero/Nuke Studio

Los siguientes botones estÃƒÆ’Ã‚Â¡n disponibles en el panel **Flow Production** de Hiero:

#### ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Â¯ **Open in FileManager**
- **FunciÃƒÆ’Ã‚Â³n**: Abre la carpeta del shot seleccionado en FileManager
- **Comando**: `FileManagerS3.exe --context studio --path "ruta_del_shot"`
- **Uso**: Explorar y gestionar archivos del shot local vs Wasabi S3
- **Color**: MarrÃƒÆ’Ã‚Â³n (#8e6c17)

#### ÃƒÂ¢Ã‚Â¬Ã¢â‚¬Â¡ÃƒÂ¯Ã‚Â¸Ã‚Â **Download Shot**
- **FunciÃƒÆ’Ã‚Â³n**: Descarga el shot completo desde Wasabi S3
- **Comando**: `FileManagerS3.exe --context studio --download "ruta_del_shot"`
- **Uso**: Sincronizar archivos remotos hacia local
- **Color**: MarrÃƒÆ’Ã‚Â³n (#8e6c17)

#### ÃƒÂ¢Ã‚Â¬Ã¢â‚¬Â ÃƒÂ¯Ã‚Â¸Ã‚Â **Upload Shot**
- **FunciÃƒÆ’Ã‚Â³n**: Sube el shot completo a Wasabi S3
- **Comando**: `FileManagerS3.exe --context studio --upload "ruta_del_shot"`
- **Uso**: Sincronizar archivos locales hacia remoto
- **Color**: MarrÃƒÆ’Ã‚Â³n (#8e6c17)

#### ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Â¬ **Download Clip**
- **FunciÃƒÆ’Ã‚Â³n**: Descarga **solo el/los clip(s) seleccionado(s)** desde Wasabi S3, no el shot completo
- **Doble acciÃƒÆ’Ã‚Â³n**:
  - **Click**: descarga la ruta actual del clip (comportamiento clÃƒÆ’Ã‚Â¡sico).
  - **Shift+Click**: descarga la **ÃƒÆ’Ã‚Âºltima versiÃƒÆ’Ã‚Â³n disponible** del clip en Wasabi y dispara actualizaciÃƒÆ’Ã‚Â³n de versiÃƒÆ’Ã‚Â³n en timeline.
- **Diferencia con Download Shot**: `Download Shot` descarga la carpeta entera del shot (unidad/proyecto/grupo/shot). `Download Clip` descarga ÃƒÆ’Ã‚Âºnicamente el media del clip seleccionado.
- **SelecciÃƒÆ’Ã‚Â³n de clip**: usa el **MÃƒÆ’Ã‚Â©todo 1 (selecciÃƒÆ’Ã‚Â³n pura)** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â opera sobre los clips realmente seleccionados en el timeline, **ignorando el playhead**. Soporta seleccionar y descargar **uno o varios clips a la vez**, de cualquier track.
- **LÃƒÆ’Ã‚Â³gica de ruta a descargar** (segÃƒÆ’Ã‚Âºn `mediaSource().singleFile()`):
  - **Archivo de video ÃƒÆ’Ã‚Âºnico** (`.mov`, `.mp4` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `singleFile() == True`): se descarga ese archivo con `--download-file`.
  - **Secuencia de imÃƒÆ’Ã‚Â¡genes** (`..._%04d.exr` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `singleFile() == False`): se descarga la **carpeta** que contiene la secuencia con `--download`.
- **Comando**: arma **una sola llamada** combinando todos los clips seleccionados:
  `FileManagerS3.exe --context studio --download "<carpeta_seq1>" "<carpeta_seq2>" --download-file "<archivo1>" "<archivo2>" --notify-completion "<carpeta_marcadores>"`
- **Comando en Shift+Click**: usa los nuevos flags de latest:
  `FileManagerS3.exe --context studio --download-latest "<carpeta_seq_v05>" --download-latest-file "<archivo_v05.mov>" --notify-completion "<carpeta_marcadores>"`
- **Overwrite**: los archivos individuales se descargan con `overwrite=true` (un clip online se puede re-descargar).
- **Tabs**: a diferencia de los botones de shot, Download Clip **no abre ningÃƒÆ’Ã‚Âºn tab** en FileManager ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â solo dispara la descarga y FileManager cambia a la pestaÃƒÆ’Ã‚Â±a *Activity*.
- **ReconexiÃƒÆ’Ã‚Â³n automÃƒÆ’Ã‚Â¡tica**: el comando incluye `--notify-completion "<Startup>/logs/download_clip_done"`. FileManager escribe un marcador `.json` al terminar cada descarga; el watcher `LGA_NKS_DownloadClip_Watcher.py` lo detecta y reconecta el clip offline en Hiero automÃƒÆ’Ã‚Â¡ticamente (ver secciÃƒÆ’Ã‚Â³n **ReconexiÃƒÆ’Ã‚Â³n automÃƒÆ’Ã‚Â¡tica** mÃƒÆ’Ã‚Â¡s abajo).
- **Logging**: el script imprime via `debug_print`, por cada clip: nombre (`clip.name()`), ruta (`mediaSource().fileinfos()[0].filename()`), tipo (archivo/secuencia) y estado online/offline (`mediaSource().isMediaPresent()`).
- **Color**: Gradiente magenta/violeta (`gradient_magenta_violet`)

### ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬Å¡ Estructura de Rutas

Los botones operan sobre la **ruta del shot**, no del archivo individual:
```
Unidad:/VFX-PROJECTO/GRUPO/SHOT_NAME
Ejemplo: T:/VFX-LC/101/LC_1010_010_Beauty_Senora
```

**Nota**: La ruta se extrae automÃƒÆ’Ã‚Â¡ticamente del clip seleccionado usando lÃƒÆ’Ã‚Â³gica inteligente (playhead primero, selecciÃƒÆ’Ã‚Â³n como fallback).

### ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â§ ImplementaciÃƒÆ’Ã‚Â³n TÃƒÆ’Ã‚Â©cnica

Los scripts ejecutan comandos CLI reales de FileManager:
- **OpenPath**: `FileManagerS3.exe --context studio --path "ruta_del_shot"`
- **Download**: `FileManagerS3.exe --context studio --download "ruta_del_shot"`
- **Upload**: `FileManagerS3.exe --context studio --upload "ruta_del_shot"`
- **DownloadClip**: `FileManagerS3.exe --context studio --download "<carpeta_secuencia>" ... --download-file "<archivo>" ... --notify-completion "<carpeta_marcadores>"` (una sola llamada combinada para todos los clips seleccionados, con notificaciÃƒÆ’Ã‚Â³n de finalizaciÃƒÆ’Ã‚Â³n)

**CÃƒÆ’Ã‚Â¡lculo de ruta del shot**: Los scripts detectan la carpeta del shot con lÃƒÆ’Ã‚Â³gica inteligente:

**Algoritmo**:
1. Normaliza la ruta para manejar separadores mixtos (`/` y `\`)
2. Busca primero un patrÃƒÆ’Ã‚Â³n de shot (ej: `BRDA_050_010`) y corta la ruta hasta esa carpeta
3. Si no encuentra patrÃƒÆ’Ã‚Â³n, usa una estructura de ruta dependiendo del OS:
   - macOS: `/Volumes/<volumen>/<drive>/<proyecto>/<grupo>/<shot>`
   - Windows: `T:/<proyecto>/<grupo>/<shot>`
4. Si la ruta es corta, usa fallback subiendo carpetas desde el archivo

**Ejemplo**:
- Ruta completa: `T:/VFX-LC/101/LC_1021_050_Beauty_Senora/Comp/4_publish/LC_1021_050_Beauty_Senora_comp_v014/LC_1021_050_Beauty_Senora_comp_v014_%04d.exr`
- Detecta `LC_1021_050_Beauty_Senora` y corta en: `T:/VFX-LC/101/LC_1021_050_Beauty_Senora`

**Rutas del ejecutable**:
- **ProducciÃƒÆ’Ã‚Â³n**: `C:\Portable\LGA\FileManager\FileManagerS3.exe`
- **Desarrollo**: `C:\Portable\LGA_FileManager\build\FileManagerS3.exe` (cuando `Desarrollo = True`)

**macOS**:
- Wrapper recomendado: `LGA_NKS_Coordination_Panel_py/fm_cli_mac.sh` (usa `open -na`)

**LÃƒÆ’Ã‚Â³gica de selecciÃƒÆ’Ã‚Â³n automÃƒÆ’Ã‚Â¡tica**:
- Si `Desarrollo = True` y el archivo existe en la carpeta build ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ usa desarrollo
- Si `Desarrollo = True` pero el archivo NO existe ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ usa producciÃƒÆ’Ã‚Â³n como fallback
- Si `Desarrollo = False` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ usa producciÃƒÆ’Ã‚Â³n

Los scripts incluyen una variable `Desarrollo = True` para alternar entre rutas con verificaciÃƒÆ’Ã‚Â³n automÃƒÆ’Ã‚Â¡tica.

**Download Clip sigue la misma lÃƒÆ’Ã‚Â³gica**: `get_filemanager_exe()` en `LGA_NKS_FileManager_DownloadClip.py` usa el mismo patrÃƒÆ’Ã‚Â³n. Por eso funciona tanto para quien tiene la versiÃƒÆ’Ã‚Â³n build (la usa si existe) como para el resto de los usuarios (cae automÃƒÆ’Ã‚Â¡ticamente a la versiÃƒÆ’Ã‚Â³n instalada `C:\Portable\LGA\FileManager\FileManagerS3.exe`). El watcher y el mecanismo de marcadores son independientes del ejecutable usado (la ruta de marcadores la pasa Hiero por `--notify-completion`).

> **ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â Despliegue**: los flags `--download-file` y `--notify-completion` viven en el cÃƒÆ’Ã‚Â³digo fuente de FileManager (`src/main.cpp`). Una versiÃƒÆ’Ã‚Â³n **build** reciÃƒÆ’Ã‚Â©n compilada los tiene; la versiÃƒÆ’Ã‚Â³n **instalada** que usan los demÃƒÆ’Ã‚Â¡s usuarios solo los tendrÃƒÆ’Ã‚Â¡ cuando se **redespliegue** FileManager desde el cÃƒÆ’Ã‚Â³digo actualizado. Hasta entonces, una versiÃƒÆ’Ã‚Â³n instalada vieja ignorarÃƒÆ’Ã‚Â­a esos flags (las secuencias vÃƒÆ’Ã‚Â­a `--download` se descargarÃƒÆ’Ã‚Â­an igual, pero los archivos sueltos y la reconexiÃƒÆ’Ã‚Â³n automÃƒÆ’Ã‚Â¡tica no funcionarÃƒÆ’Ã‚Â­an).

Los comandos se ejecutan de forma asÃƒÆ’Ã‚Â­ncrona (subprocess.Popen) para no bloquear la interfaz de Hiero/Nuke Studio.

---

## ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ¢â‚¬Å¾ ReconexiÃƒÆ’Ã‚Â³n automÃƒÆ’Ã‚Â¡tica (Download Clip)

Cuando se usa **Download Clip**, al terminar la descarga el clip se reconecta solo en Hiero, sin intervenciÃƒÆ’Ã‚Â³n del usuario. El mecanismo es **archivo marcador** (FileManager escribe, Hiero vigila):

### Flujo

1. **Download Clip** arma el comando agregando `--notify-completion "<Startup>/logs/download_clip_done"`.
2. **FileManager** descarga normalmente. Al recibir la seÃƒÆ’Ã‚Â±al `celeryTaskCompleted` de una tarea lanzada con `--notify-completion`, escribe un marcador `.json` (de forma atÃƒÆ’Ã‚Â³mica: `.tmp` + rename) en esa carpeta:
   ```json
   { "task_id": "...", "success": true, "items": [ { "path": "T:/.../ref.mov", "kind": "file" } ] }
   ```
   `kind` es `"file"` (archivo ÃƒÆ’Ã‚Âºnico) o `"folder"` (carpeta de la secuencia).
   En modo latest puede incluir ademÃƒÆ’Ã‚Â¡s:
   ```json
   { "requested_path": "T:/..._v05.mov", "latest": true }
   ```
   para que Hiero matchee el clip por ruta original y haga `setActiveVersion()` al nuevo media.
3. **El watcher** `LGA_NKS_Coordination_Panel_py/LGA_NKS_DownloadClip_Watcher.py` (lo arranca el Coordination Panel al iniciar Hiero) revisa esa carpeta cada ~5 s con un `QTimer`. Por cada marcador:
   - Si `success` es `false` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ no reconecta, descarta el marcador.
   - Si `success` es `true` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ busca el/los clip(s) cuyo media coincide (`file` = ruta exacta; `folder` = `dirname` del media de la secuencia), ejecuta `reconnectMedia()` con fallback `refresh()`, hace un **toggle del estado `enabled`** del track item (restaurando el original) para forzar el refresco del viewer, y borra el marcador.

   > **Por quÃƒÆ’Ã‚Â© el toggle de `enabled`**: tras `reconnectMedia()` el clip figura online pero el viewer mantiene cacheado el frame negro/offline. Cambiar el estado `enabled` del track item y volverlo a su valor obliga a Hiero a re-renderizarlo (es el mismo efecto que el disable/enable manual). Flow Pull no sufre esto porque al final llama a `enable_or_disable_clips()`, que hace `setEnabled()` sobre cada clip.

### GarantÃƒÆ’Ã‚Â­as de robustez

- El watcher corre en el **hilo principal** de Hiero (la reconexiÃƒÆ’Ã‚Â³n toca la API de Hiero). El `QTimer` no bloquea: el callback es trabajo de milisegundos.
- Es **stateless** entre ticks: si la descarga se cancela, FileManager se cierra o crashea, **no se escribe marcador** ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ el watcher sigue idle y el clip queda offline (correcto).
- Cada marcador se **borra siempre** tras procesarlo (haya match o no).
- Marcadores sin clip que matchee (proyecto no cargado aÃƒÆ’Ã‚Âºn) se reintentan hasta un **TTL de 30 min** y luego se descartan ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ sin huÃƒÆ’Ã‚Â©rfanos eternos.
- Escritura atÃƒÆ’Ã‚Â³mica del marcador (`.tmp` + rename) ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ el watcher nunca lee un `.json` a medio escribir.

---

## ÃƒÂ°Ã…Â¸Ã‚Â§Ã‚Âª Arquitectura tecnica: Shift+Click en Download Clip (ultima version)

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

## ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â¡ Referencias TÃƒÆ’Ã‚Â©cnicas

- **`LGA_NKS_Coordination_Panel.py`** (raÃƒÆ’Ã‚Â­z de Startup)
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
  - `_get_selected_clips()`: obtiene los clips seleccionados (MÃƒÆ’Ã‚Â©todo 1, sin playhead).
  - `_inspect_clip()`: extrae nombre, ruta, tipo (`singleFile()`) y estado online/offline.
  - `_path_has_vfx_root()`: valida que la ruta tenga raÃƒÆ’Ã‚Â­z `VFX-` (requisito del CLI).
  - `get_filemanager_exe()`, `build_filemanager_cmd()`: resuelven el ejecutable y arman la llamada combinada de modo normal (`--download` / `--download-file`) o latest (`--download-latest` / `--download-latest-file`) con `--notify-completion`.
  - `get_notify_dir()`: devuelve la carpeta de marcadores (`logs/download_clip_done`).
  - `setup_debug_logging()`, `debug_print()`: sistema de logging a archivo.

- **`LGA_NKS_Coordination_Panel_py/LGA_NKS_DownloadClip_Watcher.py`** (lo arranca el Coordination Panel al iniciar Hiero)
  - `DownloadClipWatcher`: `QObject` con un `QTimer` que vigila la carpeta de marcadores.
  - `start_watcher()`: crea la instancia del watcher (se llama al cargarse el mÃƒÆ’Ã‚Â³dulo).
  - `_scan_markers()`, `_process_marker()`: leen y procesan los marcadores `.json`.
  - `_find_and_reconnect()`: matchea la ruta del marcador con los clips de las secuencias.
  - `_reconnect_clip()`: ejecuta `reconnectMedia()` con fallback `refresh()` y un toggle de `setEnabled()` para refrescar el viewer.
  - `get_marker_dir()`: carpeta vigilada (debe coincidir con `get_notify_dir()` del script anterior).

- **`LGA_NKS_Coordination_Panel.py`**
  - Al final del mÃƒÆ’Ã‚Â³dulo carga e inicia `LGA_NKS_DownloadClip_Watcher.py` (mantiene la referencia en `download_clip_watcher_module`).

- **`LGA_NKS_Shared/LGA_NKS_GetClip.py`**
  - `get_selected_clips()`: devuelve los clips seleccionados en el timeline (excluye efectos), usado por DownloadClip.
  - `get_clip_to_process()`: mÃƒÆ’Ã‚Â©todo hÃƒÆ’Ã‚Â­brido playhead+selecciÃƒÆ’Ã‚Â³n, usado por Download/Upload/OpenPath.

- **`C:\Portable\LGA_FileManager\src\main.cpp`** (repo de FileManager)
  - `startCliDownloadFile()`: descarga un archivo individual (resuelve tamaÃƒÆ’Ã‚Â±o en S3, encola 1 objeto).
  - `startCliDownload()`: descarga una carpeta completa (shots / secuencias).
  - `startCliDownloadLatestFile()`, `startCliDownloadLatestFolder()`: resuelven sibling de versiÃƒÆ’Ã‚Â³n mÃƒÆ’Ã‚Â¡s alta y delegan en el pipeline de descarga existente.
  - `registerCliNotifyTask()`, `writeCliCompletionMarker()`: registran la tarea y escriben el marcador `.json` al completarse (seÃƒÆ’Ã‚Â±al `celeryTaskCompleted`).
  - Parseo CLI de `--download`, `--download-file`, `--download-latest`, `--download-latest-file` (multi-ruta) y `--notify-completion`; transporte por IPC (`CliCommandPayload`).

---
