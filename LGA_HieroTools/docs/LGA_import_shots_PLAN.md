# LGA_import_shots — Plan de Desarrollo

**Script:** `LGA_NKS_Edit_Panel_py/LGA_import_shots.py`  
**Botón:** Edit Panel → "Import shot" (verde `#2a4d3a`)  
**Estado:** Planeamiento — v0.5

---

## ⚠️ Regla de modularidad — OBLIGATORIA

A medida que el script crece, los helpers se extraen a archivos separados.
**Nunca agregar cientos de líneas nuevas al archivo principal.**

Convención de nombres: `LGA_import_shots_<tipo>.py`

| Archivo | Contenido |
|---------|-----------|
| `LGA_import_shots.py` | Entry point, clase `ImportShotDialog`, lógica de orquestación |
| `LGA_import_shots_scan.py` | Helpers de escaneo de carpetas (`_scan_input_folder`, `_scan_publish_folders`, `_read_exr_metadata`, etc.) |
| `LGA_import_shots_timeline.py` | Helpers de timeline (`_push_clips_right`, `_stretch_burnin`, `_find_insert_frame`, `_shot_exists_in_timeline`, etc.) |
| `LGA_import_shots_bin.py` | Helpers de bin (`_find_or_create_bin`, `_import_clip_to_bin`, `_bin_path_for_shot`, etc.) |
| `LGA_import_shots_ui.py` | Constantes de estilo, helpers de widgets (`_stepper_widget`, `_separator`, `_section_label`, estilos CSS, etc.) |

Todos los módulos auxiliares viven en la misma carpeta: `LGA_NKS_Edit_Panel_py/`.

---

## ⚠️ Referencias críticas de implementación

### LGA_NKS_CreateV000 — referencia principal

`LGA_NKS_CreateV000.py` es la referencia más importante para esta herramienta en múltiples aspectos:

- **Estética de UI:** fondo oscuro `#2B2B2B`, texto `#a7a7a7`/`#CCCCCC`, botones custom, ancho mínimo 720px,
  `QTextEdit` readonly con HTML coloreado para previews de path.
- **Sistema de colores de path:** lavanda para shot root, colores por nivel para subcarpetas.
  Ver constantes `PATH_SHOT_COLOR`, `PATH_SEP_COLOR`, `PATH_LEVEL_COLORS`.
- **Importación a bin:** `hiero.core.Clip(first_frame_path)` detecta la secuencia completa automáticamente.
  Bin destino: `project.clipsBin()/F <Secuencia>/<ShotName>` (estructura de OrganizeProject).
- **Colocación en timeline:** `track_item.setTimes(timeline_in, timeline_out, 0, frame_count - 1)`.
  Los source frames empiezan en 0 (independiente de que los EXR físicos empiecen en 1001).
  `setVersionLinkedToBin(True)` debe llamarse al final, después de ajustar tiempos.
- **Detección de shot root:** buscar segmento `_input` en el path para cortar el shot root.
- **Naming utils:** `clean_base_name()`, `extract_shot_code()` desde `LGA_NKS_Flow_NamingUtils`.
- **Settings persistentes:** patrón `.ini` en `%APPDATA%/LGA/HieroTools/`.

**Archivos de referencia:**
```
LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py          ← script principal (2262 líneas)
LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.md           ← documentación técnica completa
+Building_Blocks/LGA_NKS_CreateV000_Plan.md           ← plan de desarrollo con exploración validada
```

### +Building_Blocks — scripts de exploración validados

La carpeta `+Building_Blocks/` contiene scripts de test y exploración de la API de Hiero.
Antes de implementar cualquier operación de timeline o bin, revisar si ya existe un script
de exploración validado ahí.

Subcarpetas relevantes:
```
+Building_Blocks/Hiero/Bin/          ← operaciones de bin
+Building_Blocks/Hiero/Timeline/     ← operaciones de timeline (push clips, insert, etc.)
+Building_Blocks/Hiero/GUI/          ← widgets Qt en contexto Hiero
+Building_Blocks/LGA_NKS_CreateV000_Plan.md   ← resultados validados de exploración
+Building_Blocks/funciones_disponibles_timeline.md
+Building_Blocks/funciones_disponibles_timeline_2.md
```

---

## Concepto general

Herramienta para importar un shot completo al timeline de Nuke Studio de forma semi-automática.
El usuario clickea el botón; la herramienta detecta automáticamente dónde debe ir el shot
en el timeline, analiza la carpeta, previsualiza el resultado, opcionalmente procesa la media,
y finalmente ejecuta la importación.

El flujo es **lineal y secuencial** — no se puede saltar fases.  
La UI es **una sola ventana** que cambia de contenido según la fase,
con un stepper de progreso arriba: `[1. Analizar] → [2. Prep Media] → [3. Importar]`

---

## Estructura de carpetas del shot (confirmada)

```
T:/VFX-PROYECTO/101/PROJA_1012C_010/          ← shot root (elegido por el usuario)
│
├── _input/                                  ← nivel raíz del shot, siempre
│   ├── PROJA_1012C_010_aPlate_v01/            ← subcarpeta por secuencia EXR
│   │   ├── PROJA_1012C_010_aPlate_v01_1001.exr
│   │   └── ...
│   ├── PROJA_1012C_010_bPlate_v01/
│   ├── PROJA_1012C_010_cPlate_v01/
│   ├── PROJA_1012C_010_dPlate_v01/
│   ├── PROJA_1012C_010_EditRefComp_v01.mov    ← editref: va al track EditRef
│   └── PROJA_1012C_010_SeqRef_v01.mov         ← seqref: solo va al bin, NO al timeline
│
├── Comp/                                    ← task folders (capitalizados en disco)
│   ├── 1_projects/
│   ├── 2_prerenders/
│   ├── 3_review/
│   └── 4_publish/
│       └── PROJA_1012C_010_comp_v00/
│           └── PROJA_1012C_010_comp_v00_1001.exr
│
└── Roto/
    └── 4_publish/
        └── PROJA_1012C_010_roto_v002/
            └── ...
```

**Notas:**
- Los EXR físicos empiezan en frame `1001`. Al colocarlos en el timeline, el source empieza en `0`
  y Hiero mapea internamente. Se usa `setTimes(tl_in, tl_out, 0, frame_count - 1)`.
- Los task folders en disco están capitalizados (`Comp`, `Roto`) pero los tracks usan
  lowercase con guiones bajos (`_comp_`, `_roto_`).
- Versiones en publish: `v00` = v000 (placeholder), `v001`, `v002`... Comparación numérica.

---

## Fase 1 — Selección de carpeta

**Trigger:** usuario clickea "Import shot" desde el Edit Panel.

**Acciones:**
1. Capturar el sequence activo.
2. Abrir file browser nativo para elegir la carpeta raíz del shot.
3. Extraer `shot_name` del nombre de la carpeta (igual que usa Set Shot Name).
4. **Verificar si el shot ya existe en el timeline.** Si se detecta, mostrar diálogo de error
   con el mensaje: *"El shot [nombre] ya existe en el timeline."* Solo opción: `Cancelar`.
   El script termina ahí.
5. Escanear el timeline para determinar la posición de inserción (ver lógica abajo).
6. Ejecutar el análisis de la carpeta → abrir ventana en Fase 2.

**Datos capturados:**
- `shot_root_path` — carpeta elegida
- `shot_name` — nombre del shot (extraído de la carpeta)
- `insert_frame` — frame de inicio calculado por posición alfabética en el timeline
- `frames_to_push` — cuántos frames empujar a la derecha
- `active_sequence`

### Lógica de posicionamiento automático en el timeline

Los shots en el timeline siempre están **ordenados alfabéticamente de izquierda a derecha**.
La herramienta determina la posición correcta así:

1. Escanear los tracks `aPlate` y `EditRef` (los más confiables como referencia de posición).
2. Listar todos los shots existentes con sus rangos de frames en el timeline.
3. Ordenar alfabéticamente e insertar el nuevo shot en la posición que le corresponde.
4. El `insert_frame` = frame de inicio del shot que en la lista alfabética viene
   inmediatamente después del nuevo shot (el nuevo shot se inserta antes de ese).
5. Si el nuevo shot va al final: `insert_frame` = último frame ocupado + 1.

**Track BurnIn:** tiene clips muy largos que cubren todo el timeline. No se pushea.
Al insertar el nuevo shot, el clip de BurnIn se **estira** para cubrir el nuevo largo total.

---

## Fase 2 — Análisis y tabla de media

La ventana muestra **una tabla con toda la media encontrada** en la carpeta del shot.

### Fuentes analizadas

| Carpeta | Contenido buscado | Track destino |
|---------|------------------|---------------|
| `{shot}/_input/*/` | Subcarpetas con EXR sequences | `aPlate`, `bPlate`, etc. |
| `{shot}/_input/` | `.mov`/`.mxf` con keyword `editref` | `EditRef` |
| `{shot}/_input/` | `.mov`/`.mxf` con keyword `seqref` | *(solo bin, no timeline)* |
| `{shot}/_input/` | Otros archivos sueltos (jpg, etc.) | *(listados, sin track)* |
| `{shot}/{Task}/4_publish/` | EXR seq de versión más alta | `_{task}_` |

### Columnas de la tabla

| # | Nombre | Tipo | Resolución | FPS | Compresión | Frames | Track | ✓ |
|---|--------|------|------------|-----|------------|--------|-------|---|
| 1 | PROJA_1012C_010_aPlate_v01 | EXR seq | 4096×3072 | 24 | ZIP | 1001–1120 | aPlate | ☑ |
| 2 | PROJA_1012C_010_aPlate_v02 | EXR seq | 4096×3072 | 24 | ZIP | 1001–1120 | aPlate | ☐ |
| 3 | PROJA_1012C_010_aPlate_v03 ★ | EXR seq | 4096×3072 | 24 | ZIP | 1001–1120 | aPlate | ☑ |
| 4 | PROJA_1012C_010_bPlate_v01 | EXR seq | 4096×3072 | 24 | ZIP | 1001–1120 | bPlate | ☑ |
| 5 | PROJA_1012C_010_EditRefComp_v01 | MOV | 1920×1080 | 24 | H.264 | — | EditRef | ☐ |
| 6 | PROJA_1012C_010_SeqRef_v01 | MOV | 1920×1080 | 24 | H.264 | — | *(solo bin)* | ☐ |
| 7 | PROJA_1012C_010_comp_v00 | EXR seq | 2048×1152 | 24 | DWAA | 1001–1120 | _comp_ | ☐ |
| 8 | PROJA_1012C_010_roto_v002 | EXR seq | 2048×1152 | 24 | DWAA | 1001–1120 | _roto_ | ☐ |

**Reglas de checkbox y versiones múltiples:**
- Si hay múltiples versiones de un mismo plate (ej: `aPlate_v01`, `aPlate_v02`, `aPlate_v03`),
  se muestran como **filas separadas**, agrupadas y ordenadas por versión.
- La versión más alta se marca con ★ y viene con checkbox marcado por defecto.
- Las versiones anteriores vienen desmarcadas. El usuario puede marcar las que quiere procesar.
- **A la hora de importar al bin/timeline, siempre se usa la versión más alta** (Hiero
  maneja el versionado automáticamente desde el bin). Las versiones previas que el usuario
  haya marcado solo se procesan en Prep Media (rename/convert), pero no van al timeline.
- MOV/MXF, archivos sueltos y clips de publish → desmarcados por defecto.
- El SeqRef muestra ⚠ y texto: *"Se importará al bin. No se coloca en el timeline."*

La tabla es scrollable. El **track destino es editable** (dropdown inline) por si la detección falla.

### Botones inferiores de Fase 2

```
[ Prep Media ]                    [ → Continuar ]
```

- **Prep Media:** activo solo si hay al menos un item marcado. Cambia el contenido a la sub-vista.
- **→ Continuar:** siempre disponible. Prep Media es opcional.

---

## Sub-vista: Prep Media

*La ventana cambia de contenido. Solo aplica a los items marcados con checkbox.*

Dos secciones lado a lado:

### Izquierda — Rename

Interfaz estilo PowerRename:
- Campo **"Buscar"** + campo **"Reemplazar con"**
- Preview en tiempo real: columna "Original" → "Resultado" para cada item marcado
- **Presets guardables:** lista de pares find/replace con nombre, botones guardar/eliminar
- Persistidos en settings `.ini` (patrón de CreateV000)

### Derecha — Convert

- Checkbox: **"Convertir a DWAA"**
- Selector de **resolución destino** con presets guardables (ej: `2K — 2048×1152`, `4K — 4096×2304`, `Original`, `Custom...`)
- Checkbox: **"Mover originales a /Originals"** (marcado por defecto)
- Checkbox: **"Borrar /Originals al terminar"** (desmarcado por defecto)

> La lógica de conversión se integrará con la herramienta `.py` externa que Lega está
> desarrollando. Irá en `LGA_NKS_Edit_Panel_py/`. Se llama como script externo.

### Botón y ejecución

```
[ Ejecutar ]
```

- Cada fila muestra un **spinner** mientras se procesa.
- Al terminar cada item: ✓ verde o ✗ rojo con mensaje inline.
- **Panel de log** (3 líneas visibles, solo lectura) en la parte inferior:
  - Botón **▲** expande el log hasta cubrir toda la ventana.
  - Botón **▼** colapsa de nuevo.
- Al terminar: botón **"← Volver"** activo → regresa a Fase 2 con tabla actualizada.

---

## Fase 3 — Preview de placement e importación final

*La ventana cambia de contenido. Stepper muestra paso 3 activo.*

### Tabla de placement

| Track | Clip | Duración | Origen |
|-------|------|----------|--------|
| aPlate | PROJA_1012C_010_aPlate_v01 | 120 frames | _input |
| bPlate | PROJA_1012C_010_bPlate_v01 | 120 frames | _input |
| EditRef | PROJA_1012C_010_EditRefComp_v01 | 120 frames | _input |
| *(bin only)* | PROJA_1012C_010_SeqRef_v01 ⚠ | — | _input |
| _comp_ | PROJA_1012C_010_comp_v00 | 120 frames | Comp/4_publish |
| _roto_ | PROJA_1012C_010_roto_v002 | 120 frames | Roto/4_publish |
| _cleanup_ | *(carpeta no existe)* | — | — |

- **Duración del hueco:** la del plate más largo en `_input`.
- Las filas de plates de `_input` son **reordenables** (drag vertical, solo cambia el track asignado).
- Las filas de publish son informativas, no reordenables.
- Si task folder existe pero `4_publish/` está vacía → fila con checkbox **"Crear v000"**.
- Si task folder no existe en disco → no aparece.
- SeqRef siempre muestra ⚠ con nota: *"Solo se importará al bin."*

### Botones de Fase 3

```
[ ← Volver ]                    [ ✓ Importar ]
```

### Al confirmar "Importar"

1. Push de todos los clips de todos los tracks (excepto BurnIn) desde `insert_frame` hacia la derecha.
2. Stretch del clip BurnIn al nuevo largo total del timeline.
3. Importar toda la media al bin del shot: `project.clipsBin()/F <Secuencia>/<ShotName>`.
   - Si el bin del shot ya existe, reutilizarlo.
   - Si el SeqRef ya está en el bin, no volver a importarlo.
   - Si el SeqRef no existe en el bin, importarlo y mostrar mensaje informativo (no error).
4. Colocar cada clip en su track en `insert_frame`.
   - Source frames: `setTimes(insert_frame, insert_frame + frame_count - 1, 0, frame_count - 1)`.
   - `setVersionLinkedToBin(True)` al final, después de ajustar tiempos.
5. Ejecutar `LGA_NKS_SetShotName.py` sobre los clips recién colocados en el timeline.
6. Si hay tasks con "Crear v000" marcadas: ejecutar `LGA_NKS_CreateV000.py` para cada una.

---

## Lógica de detección de tracks para plates

El tipo de plate se extrae del **nombre de la subcarpeta** en `_input/` (case-insensitive):

| Keyword en el nombre | Track asignado |
|---------------------|----------------|
| `seqref` | *(solo bin, no timeline)* |
| `editrefclean` | `EditRefClean` |
| `editref` | `EditRef` |
| `fgplate` | `fgPlate` |
| `bgplate` | `bgPlate` |
| `aplate` | `aPlate` |
| `bplate` | `bPlate` |
| `cplate` | `cPlate` |
| `dplate` | `dPlate` |

> `seqref` y `editref` se evalúan antes que `plate` para evitar falsos positivos.

**Fallback:** si ninguna keyword coincide, EXR sequences se asignan `aPlate`, `bPlate`...
en orden alfabético. Excepción: cualquier nombre que contenga `fg` va primero.

**MOV/MXF sin coincidencia:** → `EditRef`.

---

## Lógica de detección de versiones en publish

Para cada task folder que exista en el shot root (`Comp/`, `Roto/`, `Cleanup/`...):
1. Buscar subcarpetas en `{Task}/4_publish/` con patrón `_v\d+` al final.
2. Tomar la de número más alto (comparación numérica, no lexicográfica).
3. Si hay versiones → incluir en tabla y en preview de Fase 3.
4. Si `4_publish/` existe pero vacía → ofrecer "Crear v000" en Fase 3.
5. Si el task folder no existe → no mostrar fila.

**Mapeo task folder → track:**

| Carpeta en disco | Track EXR |
|-----------------|-----------|
| `Comp/` | `_comp_` |
| `Roto/` | `_roto_` |
| `Cleanup/` | `_cleanup_` |
| `DMP/` | `_dmp_` |

---

## Diseño de la ventana

Basado en la estética de `LGA_NKS_CreateV000.py`:

- **Título:** `"Import Shot — PROJA_1012C_010"`
- **Tamaño inicial:** ~750 × 600 px, redimensionable. Ancho mínimo 720px.
- **Fondo:** `#2B2B2B`, texto `#a7a7a7` / `#CCCCCC`
- **Stepper superior:** `[1. Analizar] → [2. Prep Media] → [3. Importar]`
  Paso activo resaltado; pasos completados con ✓.
- **Sin tabs** — flujo estrictamente lineal. El stepper comunica el progreso.
- Botón "← Volver" siempre disponible excepto durante ejecución.

---

## Preguntas abiertas


---

## Resuelto / Confirmado

| # | Pregunta | Respuesta |
|---|----------|-----------|
| P1 | ¿Dónde está `_input`? | Raíz del shot, siempre |
| P2 | ¿Subcarpetas por secuencia? | Sí. También puede haber sueltos (jpg, mov) |
| P3 | ¿Nombre del shot de carpeta raíz? | Sí, igual que Set Shot Name |
| P4 | ¿Push de todos los tracks? | Sí, todos en paralelo |
| P5 | ¿Qué track no se pushea? | BurnIn — se estira al nuevo largo |
| P6 | ¿Herramienta de conversión? | Script .py externo, misma carpeta |
| P7 | ¿Un plate solo es válido? | Sí, Prep Media es opcional |
| P8 | ¿Múltiples shots? | Single shot en v1. Multi-shot a futuro |
| P9 | ¿Cómo se posiciona el shot? | Escaneando el timeline, orden alfabético |
| P10 | ¿Qué hace el playhead? | Nada — la posición la determina el orden alfabético |
| P11 | ¿EditRef y SeqRef? | EditRef → track EditRef. SeqRef → solo bin + ⚠ aviso |
| P12 | ¿Frame offset? | Source empieza en 0. `setTimes(tl_in, tl_out, 0, frame_count-1)` |
| P13 | ¿Bin destino? | `project.clipsBin()/F <Secuencia>/<ShotName>` (igual que OrganizeProject) |
| P14 | ¿BurnIn inexistente? | Se omite el stretch silenciosamente, sin error |
| P15 | ¿Shot ya existe en timeline? | Error inmediato al abrir. Solo opción: Cancelar |
| P16 | ¿Versiones múltiples en _input? | Se muestran todas como filas independientes. ★ marca la más alta (checked). Solo la más alta va al timeline |
| P17 | ¿Cómo detectar si shot ya existe? | Doble criterio: nombre del TrackItem Y path de la media (shot root en la ruta). Ambos. PROJA_1012_010 ≠ PROJA_1012C_010 — son shots distintos, no hay falsos positivos |
| P18 | ¿Versiones múltiples agrupadas visualmente? | No. Filas separadas, cada una es un archivo independiente |
