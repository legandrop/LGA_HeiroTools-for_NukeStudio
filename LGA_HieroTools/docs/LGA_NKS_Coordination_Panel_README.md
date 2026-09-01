> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_NKS_Coordination_Panel - Panel de Coordination (Flow)

## Descripción
El panel de Coordination proporciona herramientas esenciales para operaciones de producción con Flow Production Tracking (ShotGrid) desde Hiero/Nuke Studio.

## Funcionalidades Principales

### 1. Reveal in Flow
- **Shortcut**: `Ctrl+Shift+F` (abre el Shot completo)
- **Función Click normal**: Abre la task comp del clip seleccionado en Chrome
- **Función Shift+Click/Shortcut**: Abre el Shot completo en Chrome (sin la task específica)
- **Tooltip**: Se muestra el shortcut y funcionalidad de Shift+Click al hacer hover sobre el botón
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py`
- **Comportamiento**: Click normal busca el shot y task correspondiente al clip seleccionado y abre la URL de la task comp. Shift+Click o Ctrl+Shift+F abre directamente la URL del shot completo sin especificar la task.

### 2. Thumbnail
- **Función**: Crea un thumbnail del clip seleccionado y lo sube a Flow Production Tracking
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py`
- **Comportamiento**: Genera una imagen thumbnail del frame actual del clip y la asocia con el shot en Flow

### 3. Create Shot
- **Función**: Crea shots automáticamente en Flow Production Tracking basándose en los clips seleccionados
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
- **Comportamiento**: Analiza los clips seleccionados, extrae información del shotname y crea los shots correspondientes en Flow si no existen
- **Pre-chequeo v1.33**: Antes de mostrar la UI verifica si ya existen; si hay múltiples y alguno existe se cancela mostrando la lista, si es un único shot existente lanza Modify Shot automáticamente

### 4. Modify Shot
- **Función**: Modifica un shot ya existente en Flow (agregar o quitar tasks, actualizar descripciones) sin tocar estados actuales
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`
- **Restricción**: Solo admite un clip seleccionado a la vez
- **Comportamiento**: Lee la configuración real del shot en Flow, precarga la misma UI compacta y aplica únicamente las diferencias solicitadas

### 5. Check Shots Exist
- **Función**: Chequea si los shots del track comp existen en Flow
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py`

### 6. Shot Priority
- **Función**: Cambia la prioridad del shot (alta ↔ normal)
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py`

### 7. .Psync
- **Función**: Genera un archivo `<SHOT>.psync` en el escritorio para compartir y arrastrar dentro de PipeSync
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py`

### 8. FileManagerS3
- **Función**: Abre la carpeta del shot en FileManagerS3
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py`

### 9. Download Shot
- **Función**: Descarga el shot desde Wasabi S3
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py`

### 10. Upload Shot
- **Función**: Sube el shot a Wasabi S3
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py`

### 11. Download AMF
- **Función**: Descarga la carpeta `_input/Look_Files` del shot del clip seleccionado desde Wasabi S3 (los `.amf`/`.cdl`/`.clf` necesarios para ver bien los renders de comp)
- **Script utilizado**: `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_DownloadAmf.py`
- **Comportamiento**: No chequea si la carpeta existe localmente; siempre dispara la descarga vía FileManagerS3 CLI sobre `<shot>/_input/Look_Files`

## Compatibilidad de Nomenclatura

El panel es compatible con ambos sistemas de nomenclatura utilizados en la empresa:

### Formato con Descripción (5 bloques)
```
PROYECTO_SEQ_SHOT_DESC1_DESC2_TASK_vVERSION
Ejemplo: PROJA_000_140_Chroma_Auto_comp_v19
```

### Formato Simplificado (3 bloques)
```
PROYECTO_SEQ_SHOT_TASK_vVERSION
Ejemplo: PROJF_080_010_comp_v007
```

El sistema detecta automáticamente el formato utilizado sin necesidad de configuración previa.

## Estructura del Panel

### Botones Disponibles
1. **Thumbnail** - Crea y sube thumbnail del clip seleccionado
2. **Create Shot** - Crea shots automáticamente en Flow
3. **Modify Shot** - Modifica un shot existente en Flow
4. **Check Shots Exist** - Chequea si los shots del track comp existen en Flow
5. **Shot Priority** - Cambia la prioridad del shot (alta ↔ normal)
6. **.Psync** - Genera un archivo `.psync` portable para compartir
7. **FileManagerS3** - Abre carpeta del shot en FileManagerS3
8. **Download Shot** - Descarga el shot desde Wasabi S3
9. **Upload Shot** - Sube el shot a Wasabi S3
10. **Download AMF** - Descarga la carpeta `_input/Look_Files` del shot del clip seleccionado
11. **Reveal in Flow** - `Ctrl+Shift+F` - Abre la task comp en Chrome

## Requisitos

- Hiero/Nuke Studio con acceso a Flow Production Tracking
- Credenciales configuradas en `SecureConfig_Reader.py`
- Clips con nombres de archivo que sigan el formato de nomenclatura estándar

## Uso

1. Seleccionar uno o más clips en el timeline de Hiero
2. Hacer clic en el botón deseado del panel
3. El script correspondiente se ejecutará automáticamente

## Notas Técnicas

- El panel utiliza funciones compartidas de `LGA_NKS_Flow_NamingUtils.py` para el parsing de nombres
- La detección de formato es automática y transparente para el usuario
- Los scripts llamados manejan sus propias interfaces de usuario (ventanas de estado, errores, etc.)
- Las operaciones se ejecutan en hilos separados para no bloquear la interfaz de Hiero
- Compatible con caracteres Unicode (nombres con acentos, etc.)

## Scripts Relacionados

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py` - Funcionalidad de Reveal in Flow
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py` - Funcionalidad de Thumbnails
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py` - Funcionalidad de Create Shot
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py` - Funcionalidad de Modify Shot
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py` - Funcionalidad de Check Shots Exist
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py` - Funcionalidad de Shot Priority
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py` - Generación de archivos `.psync` portables
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_OpenPath.py` - Funcionalidad de PipeSync (Open)
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py` - Funcionalidad de FileManagerS3 (Open)
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py` - Funcionalidad de Download Shot
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py` - Funcionalidad de Upload Shot
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_DownloadAmf.py` - Funcionalidad de Download AMF (carpeta `_input/Look_Files`)
- `LGA_NKS_Flow/LGA_NKS_Flow_NamingUtils.py` - Utilidades compartidas de nomenclatura (usado por los scripts de producción)
