> **Regla de documentacion**: este archivo describe el comportamiento previsto del sistema de cola global de transcode. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: cada seccion funcional esta marcada como pendiente hasta que exista implementacion validada.

# Cola global de Transcode Plates

Plan de implementacion: [`LGA_import_shots_transcode_queue_PLAN.md`](LGA_import_shots_transcode_queue_PLAN.md).

> **Regla de mantenimiento**: si durante la implementacion aparecen decisiones nuevas,
> cambios de alcance o comportamientos no previstos, este documento debe actualizarse
> para describir el sistema real.

Sistema previsto para coordinar los transcodes EXR iniciados desde multiples ventanas de
`Import Shot`, evitando que varias conversiones pesadas corran en paralelo dentro de la
misma sesion de Hiero/Nuke Studio.

El objetivo es conservar la cola local por ventana/shot, pero agregar una autoridad global
que decida que secuencia se procesa en cada momento.

> Estado general: **Etapas 1, 2, 3, 4 y 4.5 implementadas y testeadas en Hiero/Nuke Studio**. **Etapa 5 implementada, pendiente de test en Hiero**.

---

## Problema (pendiente de implementacion y test)

Actualmente cada ventana de `Import Shot` puede ejecutar su propia cola de plates:

```text
SHOT_A: aPlate -> bPlate -> cPlate
SHOT_B: aPlate -> bPlate
SHOT_C: aPlate
```

Dentro de una ventana, las secuencias se procesan una por una. El problema aparece cuando
hay varias ventanas abiertas: cada ventana puede lanzar su propio `TranscodeWorker`, y cada
worker invoca `LGA_EXR_Convert.py`, que usa multiples procesos/threads para convertir
frames EXR.

Como `LGA_EXR_Convert.py` esta pensado para usar una porcion importante del CPU, correr
varios transcodes en paralelo reduce eficiencia, aumenta contencion de disco/CPU y puede
hacer que la UI se sienta menos estable.

---

## Decision principal (pendiente de implementacion y test)

Se implementara un **manager global en memoria**, compartido por todas las ventanas de
`Import Shot` abiertas dentro del mismo proceso de Hiero/Nuke Studio.

No se implementara lock externo por archivo, socket ni servicio separado. Si el usuario
abre dos sesiones distintas de Nuke Studio, cada sesion tendra su propia cola global y
podria convertir en paralelo. Ese escenario se considera aceptable.

---

## Unidad de cola (pendiente de implementacion y test)

La unidad real de la cola global sera una **secuencia/plate individual**, no una ventana
completa.

Ejemplo:

```text
1. SHOT_A / aPlate
2. SHOT_A / bPlate
3. SHOT_A / cPlate
4. SHOT_B / aPlate
5. SHOT_B / bPlate
6. SHOT_C / aPlate
```

Esto permite:

- Mostrar una posicion global clara: `Queued #1`, `Queued #2`, etc.
- Cancelar pendientes de una ventana al cerrarla sin afectar trabajos de otros shots.
- Mantener el orden natural si un shot encola varios plates antes que los demas.
- Seguir procesando aunque un plate falle.

Visualmente se puede agrupar por shot o ventana, pero internamente la cola debe estar
basada en jobs individuales.

---

## Manager global (pendiente de implementacion y test)

Se propone crear un modulo nuevo:

```text
LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue.py
```

Con un singleton:

```python
TranscodeQueueManager(QtCore.QObject)
```

Responsabilidades:

- Registrar ventanas activas de `Import Shot`.
- Recibir jobs de transcode desde cualquier ventana.
- Mantener una lista FIFO de jobs pendientes.
- Mantener un unico job activo.
- Lanzar `TranscodeWorker` solo cuando no haya otro transcode corriendo.
- Emitir senales para que todas las ventanas actualicen estado local y global.
- Remover jobs pendientes cuando una ventana se cierra.
- Marcar errores y continuar con el siguiente job.

El manager sera la unica autoridad que sabe:

- Que shot/plate esta procesando ahora.
- Que jobs estan pendientes.
- Que posicion ocupa cada job en la cola.
- Que ventanas siguen vivas.

Durante desarrollo, `LGA_import_shots.py` solo recarga este modulo si no hay ventanas
`Import Shot` visibles. Si hay una ventana abierta, reutiliza el modulo ya cargado para
no perder el manager ni duplicar colas.

Cada ventana conectada llama `note_window_opened(window_id, shot_name)` y cada cierre
llama `note_window_closed(...)`. El cierre puede llegar por varias senales Qt
(`closeEvent`, `finished`, `destroyed`), por lo que el manager lo trata como evento
idempotente por `window_id`.

---

## Modelo de job (pendiente de implementacion y test)

Cada job deberia guardar una copia autosuficiente de todo lo necesario para correr, sin
depender de que el usuario no cambie opciones despues de presionar `Start Transcode`.

Campos propuestos:

```python
{
    "job_id": "...",
    "window_id": "...",
    "shot_name": "PROJA_1012C_010",
    "row_i": 3,
    "item": {...},
    "target_w": 2048,
    "target_h": 1152,
    "global_opts": {...},
    "flags": {
        "test_mode": False,
        "move_originals": True,
        "delete_originals": False,
    },
    "shared_dir": "...",
    "created_at": 123456.0,
    "status": "queued",
}
```

Las opciones quedan **congeladas al encolar**. Si el usuario cambia DWAA on/off,
resolucion, channels, PAR o delete originals despues de encolar, esos cambios no deben
alterar jobs ya pendientes.

---

## Flujo de ejecucion (pendiente de implementacion y test)

1. El usuario entra a `Transcode Plates` en una ventana.
2. Selecciona uno o mas EXR.
3. Presiona `Start Transcode`.
4. La ventana construye jobs individuales con las opciones actuales.
5. La ventana registra esos jobs en `TranscodeQueueManager`.
6. El manager actualiza posiciones globales y notifica a todas las ventanas.
7. Si no hay job activo, el manager arranca el primer job.
8. Al terminar un job, el manager marca resultado y arranca el siguiente.
9. Cuando no quedan jobs, el estado global vuelve a idle.

La ventana ya no deberia llamar directamente a `_start_next_sequence()` para decidir la
cola total. Esa decision pasa al manager global.

---

## Estados por fila (pendiente de implementacion y test)

La columna `Estado` de cada plate deberia poder mostrar:

| Estado | Texto sugerido | Uso |
|--------|----------------|-----|
| idle | `Pendiente` | Plate aun no encolado |
| queued | `Queued #N` | Job pendiente en la cola global |
| running | barra de progreso | Job actualmente convirtiendo |
| done | `DONE (Xs)` | Conversion terminada OK con segundos reales |
| error | `Error` | Conversion fallida |
| cancelled | `Cancelado` | Job pendiente removido por cierre/cancelacion |
| unsupported | `No soportado` | MOV u otro formato no convertible |

Cuando termina un job, todos los jobs pendientes deben recalcular su numero de fila.

Ejemplo:

```text
SHOT_A / aPlate -> procesando
SHOT_A / bPlate -> Queued #1
SHOT_B / aPlate -> Queued #2
SHOT_C / aPlate -> Queued #3
```

Si termina `SHOT_A / aPlate`:

```text
SHOT_A / bPlate -> procesando
SHOT_B / aPlate -> Queued #1
SHOT_C / aPlate -> Queued #2
```

---

## Estado global visible (pendiente de implementacion y test)

Todas las paginas importantes de todas las ventanas muestran en la fila inferior de botones,
alineados a la izquierda, el boton `Open Queue`, el checkbox persistente
`Shot Rename and Transcode tabs` y el texto de estado global.
`Open Queue` solo se muestra cuando ese checkbox esta activado.
Los botones de accion principales quedan a la derecha.

Ubicacion implementada:

- Pagina media: `[Open Queue] [Shot Rename and Transcode tabs] [estado] ... [Rename] [Transcode Plates] [Import]`
- Pagina rename: `[Open Queue] [Shot Rename and Transcode tabs] [estado] ... [← Go Back] [Rename]`
- Pagina convert: `[Open Queue] [Shot Rename and Transcode tabs] [estado] ... [← Go Back] [Start Transcode]`
- Pagina import: `[Open Queue] [Shot Rename and Transcode tabs] [estado] ... [← Go Back] [Import Now] [Import and Create V000]`

Textos implementados:

```text
(vacío cuando idle)
Convirtiendo plates del shot SHOT_A. Plates restantes: 3
Convirtiendo plates del shot SHOT_A
```

El nombre del shot se muestra con `SHOTNAME_COLOR` (`#B56AB5`) y funciona como boton plano:
sin fondo ni borde, visualmente se lee como texto coloreado, pero al clickearlo trae al
frente la ventana de `Import Shot` del shot que esta convirtiendo en ese momento.
"Plates restantes" es el conteo global de jobs pendientes en la cola; cuando no hay
pendientes solo aparece el nombre del shot. El texto se vacia al terminar todos los jobs.

El estado global debe actualizarse por senales del manager, no por polling local de cada
ventana.

---

## Boton Open Queue (implementado, pendiente de test en Hiero)

Junto al texto de estado global se agregara un boton pequeno estilo selector rapido:

```text
Open Queue
```

Debe usar el mismo lenguaje visual que botones como `Select All`, `Clear`, `Plates`,
`References` y `Publish`.

Accion:

- Abre una ventana flotante no bloqueante con la cola global.
- Si la ventana ya esta abierta, la trae al frente.
- La ventana debe actualizarse en vivo cuando cambian jobs, estados o posiciones.

---

## Modulo UI de Open Queue (implementado, pendiente de test en Hiero)

La ventana de cola debe vivir en un modulo propio para mantener separadas las
responsabilidades:

```text
LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue_ui.py
```

Responsabilidades del modulo UI:

- Crear y mostrar la ventana no modal `TranscodeQueueWindow`.
- Recibir el manager global existente; no crear ni reemplazar el manager.
- Leer el snapshot actual del manager y conectarse a sus senales.
- Renderizar la cola, agrupada por `shot_name`.
- Reutilizar la logica de foco de ventanas existente para traer al frente una ventana de
  `Import Shot` por `window_id` o `shot_name`.
- Mantener el checkbox `Mantener arriba`.
- No ejecutar transcodes, no modificar archivos y no decidir el orden de la cola.

Contrato propuesto desde `LGA_import_shots.py`:

```python
show_queue_window(manager, parent=None, focus_window_callback=None)
```

Esto significa: el boton `Open Queue` no conoce los detalles de la UI; solo llama esa
funcion, pasandole el manager y una funcion para enfocar ventanas de Import Shot. La clase
interna recomendada para la ventana es `TranscodeQueueWindow`.

### Recarga de desarrollo del modulo UI

Durante desarrollo, `LGA_import_shots.py` debe poder recargar
`LGA_import_shots_transcode_queue_ui.py` para probar cambios sin reiniciar Hiero, pero solo
cuando sea seguro:

- Si no hay ventanas `Import Shot` visibles y no hay ventana `Open Queue` visible, puede
  borrar el modulo UI de `sys.modules` e importarlo de cero.
- Si hay alguna ventana `Import Shot` visible o una ventana `Open Queue` visible, debe
  reutilizar el modulo UI ya cargado.

La razon es similar a la del manager, aunque con menos riesgo de datos: recargar la UI con
ventanas vivas puede dejar widgets creados por clases viejas, senales duplicadas o una
ventana flotante desconectada del estado actual. El manager global sigue teniendo su propia
regla mas estricta: nunca recargarse mientras haya ventanas `Import Shot` abiertas, porque
ahi vive la cola real.

---

## Ventana de cola global (implementada, pendiente de test en Hiero)

Detalle visual y tecnico: [`LGA_import_shots_transcode_queue_ui.md`](LGA_import_shots_transcode_queue_ui.md).

La ventana `Import Shots - Transcode Queue` muestra una tabla unica, en orden global, con todos los jobs
activos/pendientes y un historial visual de jobs completados mientras la ventana este
abierta.
Los jobs completados conservan su posicion visual original: no se mueven al final al
terminar.

La UI debe respetar la estetica de `Import Shot`: fondo `#2B2B2B`, tablas oscuras,
bordes sobrios, tipografia y botones pequenos consistentes con los controles existentes.
No debe sentirse como una ventana nativa generica separada del resto de la herramienta.

La columna `Shot` usa texto/boton plano clickeable. Al hacer click sobre el nombre de shot:

- Si la ventana de `Import Shot` para ese shot sigue abierta, debe traerse al frente.
- La implementacion debe copiar/reutilizar el comportamiento ya implementado en el estado
  global visible: boton plano con `SHOTNAME_COLOR` que busca la ventana por `window_id`
  o `shot_name`, llama `show()`, `showNormal()` si estaba minimizada, `raise_()` y
  `activateWindow()`.
- Si la ventana ya fue cerrada, la primera version puede dejar el doble click sin accion
  y registrar el evento en log.
- Abrir/reconstruir una ventana cerrada desde la cola queda como mejora futura, porque
  requiere conservar o reconstruir el contexto completo del shot.

Columnas sugeridas:

| Columna | Contenido |
|---------|-----------|
| Shot | Nombre del shot como boton plano; alterna `SHOTNAME_COLOR` / `SHOTNAME_COLOR_ALT` cuando cambia el shot |
| Plate | Nombre de secuencia, con el mismo criterio visual que la columna Nombre de la tabla Convert |
| Duracion | `484f - 20.2s`, con el mismo color de frames/segundos usado en Convert |
| Estado | Barra de progreso para activo, `Queued #N` para pendiente, `DONE (Xs)`, `Error`, `Cancelado` |

Primera version recomendada:

- Solo lectura.
- Sin reordenar jobs.
- Sin cancelar jobs desde esta ventana.
- Click en shot solo trae al frente ventanas existentes.
- Boton `Show All Import Windows`.
- Boton `Clear Completed`, que limpia solo el historial visual de completados.
- Dropdown `CPU` con presets `High (6/6)`, `Medium (4/4)`, `Low (2/2)`, `Minimal (1/1)`.
- Checkbox `Keep this window on top`, persistente entre sesiones y alineado a la derecha de la fila inferior.

El dropdown `CPU` es global para la cola. Controla `workers` y `exrmetrics_threads`
del manifest que se envia a `LGA_EXR_Convert.py`:

| Preset | workers | exrmetrics_threads | Uso |
|--------|---------|--------------------|-----|
| High | 6 | 6 | Maxima velocidad, mayor consumo de CPU |
| Medium | 4 | 4 | Balance general |
| Low | 2 | 2 | Menor impacto mientras se trabaja en Hiero |
| Minimal | 1 | 1 | Conversion lenta, menor consumo |

El cambio no afecta el plate que ya esta convirtiendo. El manager aplica el preset
vigente justo antes de lanzar el siguiente `TranscodeWorker`, sobreescribiendo
`workers` y `exrmetrics_threads` en los `global_opts` del job. Por eso tambien
afecta jobs que ya estaban pendientes en la cola.

El checkbox `Keep this window on top` debe hacer que la ventana quede sobre el resto usando
`QtCore.Qt.WindowStaysOnTopHint`, pero la ventana debe seguir siendo **no modal**:

```python
queue_dialog.setModal(False)
```

Esto permite que la cola permanezca visible sin bloquear el uso de Hiero/Nuke Studio ni
de las ventanas de `Import Shot`.

Al cambiar el flag de always-on-top puede ser necesario preservar geometria, aplicar los
window flags, y hacer `hide()` / `show()` para que Qt actualice el comportamiento.

Cancelacion y reordenamiento pueden agregarse despues si hacen falta.

---

## Cierre de ventanas (pendiente de implementacion y test)

Cuando una ventana de `Import Shot` se cierra:

- Debe desregistrarse del manager global.
- Sus jobs pendientes deben removerse de la cola y marcarse como `cancelled`.
- Las posiciones de los demas jobs deben recalcularse.
- Las demas ventanas deben actualizar su UI.

Si la ventana cerrada tiene un job actualmente corriendo:

- Version inicial recomendada: dejar terminar el job activo.
- No iniciar mas jobs de esa ventana cuando termine.
- Registrar en log que la ventana se cerro mientras su job estaba activo.

No se recomienda matar el subprocess en la primera implementacion, porque un corte a mitad
de transcode debe resolver restauracion de originales, outputs parciales y estado de la UI.

---

## Errores y continuidad (pendiente de implementacion y test)

Si un job falla:

- La fila correspondiente debe quedar en `Error`.
- El log de la ventana que origino el job debe recibir el mensaje de error si la ventana
  sigue abierta.
- La cola global debe continuar con el siguiente job.
- El error no debe bloquear jobs de otros shots.

Si la ventana de origen ya no existe, el manager debe conservar el resultado para la ventana
`Open Queue` y escribir debug log, pero no intentar actualizar widgets destruidos.

---

## Integracion con el worker actual (pendiente de implementacion y test)

El sistema actual ya tiene piezas reutilizables:

- `TranscodeWorker`
- `TranscodeWorkerSignals`
- `build_manifest_for_sequence`
- `check_existing_outputs`
- `delete_existing_outputs`
- `show_overwrite_warning`

La integracion recomendada es mantener `TranscodeWorker` como ejecutor de una secuencia y
mover la decision de cola desde `ImportShotDialog._start_next_sequence()` hacia el manager
global.

En una primera implementacion, el manager puede lanzar un `TranscodeWorker` con una sola
secuencia por job:

```python
TranscodeWorker(
    [(row_i, item, target_w, target_h)],
    global_opts,
    test_mode=...,
    move_originals=...,
    delete_originals=...,
    shared_dir=...,
)
```

Esto minimiza cambios en el motor existente.

---

## Senales sugeridas (pendiente de implementacion y test)

Senales del manager:

```python
queue_changed = Signal(object)       # snapshot completo de la cola
job_started = Signal(object)         # job snapshot
job_progress = Signal(str, int, int) # job_id, done_frames, total_frames
job_done = Signal(object)            # job result snapshot
job_error = Signal(object)           # job result/error snapshot
global_status_changed = Signal(str)  # texto resumido para footer
```

Las ventanas deben escuchar estas senales y actualizar solo sus propias filas cuando el
`window_id` o `job_id` corresponda.

---

## Persistencia (pendiente de implementacion y test)

No habra persistencia de cola entre sesiones.

La cola vive solo en memoria:

- Si se cierra Nuke Studio, la cola desaparece.
- Si se reinicia la herramienta, no se reanudan jobs pendientes.
- Los archivos ya convertidos quedan en disco como resultado normal del transcode.

---

## Logs (pendiente de implementacion y test)

El manager escribe en un log propio:

```text
C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\logs\debugPy_ImportShotsTranscodeQueue.log
```

Este log se reinicia cuando el modulo de queue se recarga. Si hay ventanas `Import Shot`
abiertas, `LGA_import_shots.py` reutiliza el modulo existente y el log no se reinicia.

Eventos minimos:

- Alta de ventana.
- Baja de ventana.
- Jobs encolados.
- Job iniciado.
- Job terminado OK.
- Job terminado con error.
- Jobs pendientes removidos por cierre de ventana.
- Cola vacia.

---

## Riesgos conocidos (pendiente de implementacion y test)

- Si se destruye una ventana mientras hay senales Qt pendientes, hay que evitar actualizar
  widgets inexistentes.
- Si el job activo pertenece a una ventana cerrada, la UI no puede mostrar progreso local,
  pero el manager debe poder terminarlo y seguir.
- Los dialogos de overwrite actuales son UI bloqueante por secuencia. Hay que decidir si
  se muestran antes de encolar o justo antes de ejecutar. Para primera version conviene
  resolver conflictos antes de encolar desde la ventana de origen.
- En re-transcode, si existe `_input/Originals/<plate>/`, esos EXR son la fuente original:
  el overwrite debe restaurarlos a `item_path` antes de relanzar el worker, no borrarlos.
  Este flujo ya tiene preflight, restore verificado, validacion de rutas y postflight de
  output implementados; queda pendiente validarlo en Hiero con casos reales.
- Si se permite cancelar jobs activos mas adelante, habra que agregar soporte explicito
  para terminar subprocess y restaurar originales con seguridad.
- `QThreadPool.globalInstance()` puede ejecutar otros jobs de la aplicacion; el manager
  debe controlar su propio estado para no depender del limite global del thread pool.

---

## Referencias tecnicas

| Archivo | Funciones / clases clave |
|---------|--------------------------|
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots.py` | `ImportShotDialog`, `_run_transcode()`, `_start_next_sequence()`, `_on_sequence_started()`, `_poll_transcode_progress()`, `_on_sequence_done()`, `_on_worker_batch_done()`, `_finalize_transcode()`, `_on_transcode_error()` |
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots_transcode.py` | `TranscodeWorkerSignals`, `TranscodeWorker`, `build_manifest_for_sequence()`, `check_existing_outputs()`, `delete_existing_outputs()`, `show_overwrite_warning()` |
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_EXR_Convert.py` | `run_tasks()`, `convert_one()`, `build_exrmetrics_command()`, `build_oiiotool_command()`, `main()` |
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_EXR_Convert.MD` | Manifest JSON, parametros de conversion, comportamiento del motor EXR |
