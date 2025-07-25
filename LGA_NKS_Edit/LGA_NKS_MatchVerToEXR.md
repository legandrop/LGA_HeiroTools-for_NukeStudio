# LGA_NKS_MatchVerToEXR

Herramienta para sincronizar versiones entre tracks EXR y REV en Hiero/Nuke Studio.

## Descripción

Busca la versión actual de todos los clips del track llamado "EXR" e intenta subir la versión de todos los clips del track llamado "REV" a la misma versión. Solo procesa clips que contengan "_comp_" en su nombre.

## Archivos principales

- **Script principal:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_NKS_Edit\LGA_NKS_MatchVerToEXR.py`
- **Panel de control:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_NKS_EditTools_Panel.py`

## Acceso

**Botón del panel:** "Match Rev Ver" en EditTools Panel
- **Click normal:** Procesa clips seleccionados o todos si no hay selección
- **Shift + Click:** Fuerza procesamiento de todos los clips independientemente de la selección

## Funcionamiento

### Requisitos
- Secuencia activa con tracks llamados "EXR" y "REV"
- Clips con "_comp_" en el nombre del archivo

### Proceso
1. Analiza versiones de clips EXR seleccionados (o todos)
2. Busca clips REV correspondientes por nombre base
3. Actualiza clips REV a la versión más alta disponible
4. Si la versión EXR no está disponible, agrega tag rojo "Version Mismatch"
5. Muestra ventana con resultados del proceso

### Estados de resultado
- **Updated:** Clip REV actualizado exitosamente
- **Already Matched:** Las versiones ya coincidían
- **Version Not Available:** La versión EXR no existe para el clip REV

## Funciones principales

### `match_exr_to_rev(force_all_clips=False)`
Función principal que inicializa la GUI y ejecuta el proceso.

### `HieroOperations.process_tracks()`
Lógica principal que:
- Detecta tracks EXR y REV
- Procesa clips según parámetro `force_all_clips`
- Actualiza versiones y agrega tags según resultado

### `VersionMatcherGUI`
Interfaz que muestra resultados en tabla con:
- Nombre del shot
- Versión EXR
- Versión REV anterior
- Estado del proceso

## Notas técnicas

- Utiliza expresiones regulares para extraer números de versión
- Maneja archivos EXR con secuencias (%04d) y archivos de video
- Implementa sistema de undo para reversión de cambios
- Compatible con selección múltiple y procesamiento masivo
