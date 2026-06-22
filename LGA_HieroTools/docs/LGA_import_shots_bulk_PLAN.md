> **Regla de documentacion**: este archivo es el PLAN de desarrollo del Bulk Import.
> Registra decisiones de diseno, alcance y etapas. Cuando una etapa se implementa y
> testea, se actualiza la documentacion principal (`LGA_import_shots.md` y los .md de
> seccion) y aqui se marca la etapa como hecha.

# LGA_import_shots — Bulk Import (PLAN)

Importar **varios shots** al timeline en una sola operacion, en el orden alfabetico
correcto, como si se importaran uno por uno. El usuario selecciona varias carpetas de
shot, revisa un preview combinado de como quedara el timeline final (teniendo en cuenta
shots ya existentes que queden entre medio), y ejecuta todo en un unico paso de undo.

El flujo **mono-shot actual queda intacto**: si se selecciona una sola carpeta, se abre
la `ImportShotDialog` de siempre. El bulk es un camino nuevo y separado.

---

## Decisiones tomadas (Q&A con el usuario)

| Tema | Decision |
|------|----------|
| **Seleccion de carpetas** | Browser `QFileDialog` **no-nativo** (Qt) con `ExtendedSelection`: multi-seleccion de carpetas con Shift/Ctrl en el mismo browser. El nativo de Windows no permite multi-seleccion de carpetas. |
| **Control por shot** | Auto **editable por shot**: defaults automaticas iguales a mono-shot (ultimo plate + editref + tracks auto-detectados), pero el usuario puede ajustar tracks/checkboxes de cada shot antes de ejecutar. |
| **Que se importa por defecto** | Igual que mono-shot hoy: ultimo plate de `_input` checked + editrefs auto; publish NO checked por defecto. |
| **Duplicados (shot ya en timeline)** | **Saltar y avisar**: los shots que ya existen se omiten del bulk; el resto se importa. Resumen de cuales se saltaron. |
| **Layout de UI** | **Tabs por shot** + un tab final **"Preview"** con el timeline combinado. Un tab por cada shot con su tabla de media (tracks + checkboxes). |
| **Alcance del preview** | Timeline **completo pero acotado**: desde el primer shot nuevo hasta el ultimo (+ vecino inmediato a cada lado). No se arrastran shots lejanos. |

---

## Insight clave del codigo existente

`ImportShotDialog._do_import()` **recalcula** la posicion con `_find_insert_frame()`
justo antes de importar (lineas ~5325-5336). Por eso la **ejecucion encadenada sale
gratis**: si se importan los shots nuevos en orden alfabetico uno tras otro, cada
`_find_insert_frame()` se recalcula contra el timeline que ya incluye a los shots
anteriores del batch, y `push_clips_right()` hace el espacio acumulado.

Lo dificil NO es ejecutar, es el **preview combinado**: simular donde quedara cada shot
ANTES de tocar el timeline.

---

## Modulo nuevo: `LGA_import_shots_bulk.py`

Para no inflar mas `LGA_import_shots.py` (286KB) ni arriesgar el mono-shot.

### Modelo de datos por shot

```python
ShotEntry = {
    "shot_root":     str,
    "shot_name":     str,
    "input_items":   list[dict],   # de _scan_input_folder
    "publish_items": list[dict],   # de _scan_publish_folders
    "max_frames":    int,          # duracion master = max frame_count de plates latest
    # estado editable por el usuario (defaults auto al cargar):
    "row_state":     {...},        # track overrides + checkboxes por fila
}
```

### Funcion de simulacion: `simulate_bulk_layout(seq, new_shots)`

Calcula donde caera cada shot nuevo en el timeline final.

1. Tomar shots existentes con `_collect_timeline_shots(seq)` → lista de
   `{shot_name, timeline_in, timeline_out}` (cada uno con rango master real).
2. Para cada shot nuevo: `master_dur = max(frame_count de plates latest)`.
3. Ordenar **todos** (existentes + nuevos) alfabeticamente por `shot_name.lower()`.
4. Recorrer en orden: para cada shot nuevo, determinar su `insert_frame` segun el
   estado **simulado** del timeline (existentes + nuevos ya colocados), asignarle
   `tl_in/tl_out` y desplazar `+master_dur` a todos los shots cuyo `tl_in >= insert_frame`
   (espejo de `push_clips_right` a nivel de shot-master).
5. Retornar, por shot nuevo: `insert_frame`, `tl_in`, `tl_out`, `prev_shot_name`,
   `next_shot_name` (que pueden ser otro shot nuevo del batch o uno existente).

Esto alimenta el preview combinado. Para el detalle por-track (handles de editref,
multiples plates) se reusa la logica de `build_import_preview_data` por shot, posicionada
con el `insert_frame` simulado.

### Browser multi-select: `pick_shot_folders(initial_dir)`

`QFileDialog` no-nativo con `DontUseNativeDialog`, `FileMode.Directory`, y
`ExtendedSelection` forzado en el `QListView`/`QTreeView` internos. Retorna lista de
carpetas. Si retorna 1 sola → el caller usa el flujo mono-shot.

El browser tiene tamaño y colores configurables mediante constantes
`✅✅💾⚠️`. La selección usa gris claro en lugar del highlight amarillo. El
El sidebar usa un ancho fijo configurable, conserva los accesos estándar y suma carpetas `VFX-*`
detectadas en `T:/` y `N:/`, con labels como `T:/VFX-MOR`. Las columnas Type
y Date Modified se autoajustan por contenido y usan mínimos configurables.

---

## Routing en `main()`

```
main()
  └─ pick_shot_folders()
       ├─ 0 carpetas → return (cancelado)
       ├─ 1 carpeta  → flujo mono-shot actual (ImportShotDialog) — SIN CAMBIOS
       └─ 2+ carpetas → flujo bulk:
            ├─ por cada carpeta: _get_shot_name_from_folder + scan input/publish
            ├─ filtrar (saltar y avisar) los que ya existen en timeline
            ├─ ordenar alfabeticamente
            ├─ simulate_bulk_layout()
            └─ BulkImportDialog(...)
```

---

## UI: `BulkImportDialog`

- **Header tabs:** un tab por shot (`SHOT_A`, `SHOT_B`, ...) + tab final **PREVIEW**.
- **Tab de shot:** reusa la tabla de media (tracks + checkboxes + quick-select) con las
  defaults auto. Estado independiente por shot.
- **Tab Preview:** timeline combinado, una tira por track, acotado al rango de los shots
  nuevos + vecino inmediato. Los shots existentes que caigan en el rango se muestran como
  contexto. Refresca al cambiar a este tab.
- **Footer:** botones `Import All` / `Import All + V000` (a definir), resumen de shots
  saltados.

> La tabla de media hoy esta acoplada al estado `self.*` (single-shot) de
> `ImportShotDialog`. Para reusarla por-shot hay que extraerla a un widget/panel que
> tome estado por shot, o instanciar N estados. Ver Etapa 2.

---

## Ejecucion: `_do_bulk_import()`

```
with project.beginUndo("Bulk Import: N shots"):
    for shot in new_shots (orden alfabetico):
        insert_frame, push = _find_insert_frame(seq, shot.shot_name, shot.max_frames)  # recalc vivo
        push_clips_right(...)        # si push > 0
        for item por track (segun row_state del shot):
            import_item_to_bin(...)
            place_clip_in_timeline(...)
    stretch_burnin(seq)
# fuera del undo: set_viewer_to_shot al rango del primer..ultimo shot nuevo
```

Errores parciales se acumulan y se reportan al final (igual que mono-shot).

---

## Etapas

| Etapa | Contenido | Estado |
|-------|-----------|--------|
| **1** | Modulo `LGA_import_shots_bulk.py`: `pick_shot_folders()` + `simulate_bulk_layout()` con logging y routing en `main()`. | implementado |
| **2** | Tabla de media reusable mediante `_BulkShotPanel`. `BulkImportDialog` con tabs por shot. | implementado |
| **3** | Tab Preview combinado por track, acotado a nuevos + vecinos inmediatos. | implementado |
| **4** | `_do_bulk_import()` (ejecucion encadenada en un undo) + resumen de saltados + view post-import. | implementado |
| **5** | Documentacion principal actualizada. | implementado |

---

## Riesgos / a vigilar

- **Acoplamiento de la tabla de media** al estado single-shot de `ImportShotDialog`
  (Etapa 2 es la mas pesada).
- **Tracks que no existen** y que un shot del batch crea (ej. `+ Crear track dPlate`):
  decidir si la creacion de tracks aplica al batch entero antes de ejecutar.
- **Recalculo vivo vs simulado:** el preview usa la simulacion; la ejecucion usa
  `_find_insert_frame` vivo. Deben coincidir. Validar con casos de shots intercalados.
- **Handles de editref** por shot: se calculan igual que mono-shot dentro de cada shot.

---

## Referencias tecnicas

| Archivo | Funciones / clases clave |
|---------|--------------------------|
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_bulk.py` | `pick_shot_folders()`, `simulate_bulk_layout()`, `BulkImportDialog` (etapas 2-4) |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots.py` | `main()`, `_find_insert_frame()`, `_collect_timeline_shots()`, `_shot_exists_in_timeline()`, `_scan_input_folder()`, `_scan_publish_folders()`, `_get_shot_name_from_folder()`, `ImportShotDialog._do_import()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_timeline.py` | `push_clips_right()`, `place_clip_in_timeline()`, `stretch_burnin()`, `set_viewer_to_shot()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_bin.py` | `find_or_create_shot_bin()`, `import_item_to_bin()` |
| `LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py` | `build_import_preview_data()` (reuso por shot en el preview combinado) |
| `docs/LGA_import_shots_PLAN.md` | Plan original mono-shot |
