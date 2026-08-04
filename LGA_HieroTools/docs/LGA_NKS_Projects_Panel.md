> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Panel de Proyectos LGA - Documentacion

## Concepto rapido
- Panel `com.lega.ProjectsPanel` para Hiero/Nuke Studio que escanea `T:\` (`VFX-*/*_SUP`), detecta la ultima version `.hrox` de cada proyecto, y permite abrir proyectos y sus secuencias.
- Barra superior: `Refresh` reescanea en background; estado visible; `Reimport` ejecuta el smart reload para redockear y aplicar cambios.
- Click en proyecto lo abre; click en secuencia la abre en timeline (cross-project) preservando ajustes de viewer y dejando apagado el Frame Number del ViewerTL.
- Boton `Update`: aparece al lado de proyectos abiertos cuando existe version mas nueva en disco y permite actualizar automaticamente.

## Archivos clave
- `LGA_NKS_Projects_Panel.py` - Panel definitivo. Clase `ProjectsPanel`. Se auto-registra en `hiero.ui.windowManager()` (`AUTO_CREATE_PANEL`).
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectItem.py` - Clase `ProjectItem` para widgets de proyecto y secuencias. Gestiona el boton `Update`.
- `LGA_NKS_Projects_Panel_py/LGA_NKS_Workers.py` - Clases `WorkerSignals`, `ScanWorker` para operaciones en background.
- `LGA_NKS_Projects_Panel_py/LGA_NKS_UIManager.py` - Clase `UIManager` para configuracion y gestion de interfaz.
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ScanManager.py` - Clase `ScanManager` para gestion de operaciones de escaneo.
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectHandler.py` - Clase `ProjectHandler` para manejo de proyectos y apertura. `on_update_project_click()` actualiza proyectos.
- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py` - `scan_projects_on_disk()`, `obtener_clave_proyecto()`, `_clave_agrupacion_proyecto()`, `_agrupar_hrox_por_proyecto()`, `_elegir_version_mas_alta()`, `is_path_under_root()`, `get_open_projects_info(base_path)`, `is_project_open()`, `get_project_sequences()`, `get_projects_with_newer_versions()`.
- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py` - `switch_to_sequence_hybrid()` (V3 hibrida: preserva gain/gamma/saturation/playhead, optimiza UI, hace pre-cleanup del timeline nuevo, apaga `Frame_Only`, funciona cross-project y registra diagnostico post-event-loop de viewers/timelines). **Cierra el viewer+timeline viejos ANTES de abrir la secuencia nueva** (`CLOSE_BEFORE_OPEN`): al reves, la destruccion compite con el IO de la media recien abierta y el switch tarda entre 4 y 15 segundos en vez de menos de uno. Por eso el playhead se captura y restaura a mano, con `_get_current_playhead()` / `_restore_playhead()`. Detalle en `LGA_Projects_Panel_SwitchSequence_README.md`. `disable_frame_number_on_active_sequence()` desactiva el Frame Number del ViewerTL sin crearlo ni reposicionarlo.
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectsPanel_Logging.py` - Helper compartido de logging para todo el flujo del panel.
- `LGA_NKS_Shared/LGA_NKS_Timeline_PreCleanup.py` - `main()`, `remove_nukevfx_tracks()`, `extend_burnin_to_last_visible()`. Limpieza compartida de timeline para ViewerTL y Projects Panel.
- `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py` - `main()`, `obtener_limites_scrollbar()`, `scroll_to_position()`. Scroll vertical al top track, integrado al log del panel cuando se usa desde Projects Panel.
- `LGA_NKS_Projects_Panel_py/LGA_NKS_Projects_Panel_Smart_Reload.py` - `main()` recarga y redockea el panel.
- `LGA_NKS_Projects_Panel.ini` - Configuracion. Solo queda `[General] AutoRefreshInterval` para los re-escaneos periodicos; la seccion `[Colors]` se elimino.
- `LGA_NKS_Shared/LGA_NKS_Project_Colors_Config.py` - `load_project_colors()`, `find_project_color()`, `get_project_colors_db_path()`. Lee los colores de proyecto de la `pipesync_stats.db` del contexto activo.
- `LGA_NKS_Shared/LGA_QtAdapter_HieroTools.py` - Adapter Qt obligatorio.

## Flujo y funcionalidades
- Escaneo automatico al abrir y en cada Refresh (`QRunnable` + `QThreadPool`, no bloquea UI).
- Nuke 16: se usa `QTimer.singleShot(500ms)` para esperar que Qt este completamente inicializado antes de ejecutar threads.
- Proyectos: se listan alfabeticamente con version mas alta. Click abre con `hiero.core.openProject()`.
- Una carpeta `*_SUP` puede tener mas de un proyecto (por ejemplo `PROJB_SUP_v040.hrox` y `PROJB_Breakdown_v004.hrox`): los `.hrox` se agrupan por nombre base ignorando version y sufijos (`_Mac`), y cada grupo entra a la lista como un proyecto propio con su version mas alta.
- Colores: cada item lleva `project_key`, el proyecto de trabajo tomado de la carpeta `VFX-<proyecto>` de la ruta, asi que todos los `.hrox` de una misma carpeta VFX comparten color aunque tengan nombres base distintos.
- El color de cada proyecto sale de PipeSync, no de este repo. La fuente de verdad es Flow (`Project.sg_pipesync_project_settings_json`, campo `project_color`) y PipeSync lo cachea en la tabla `project_settings_cache` de `pipesync_stats.db`; los nombres salen de la tabla `projects`. Se lee la DB del contexto activo (`cache/` en studio, `cacheClient/` en client), read-only.
- Si PipeSync no sincronizo ese contexto, o el proyecto no figura en la DB, el item usa el color por defecto `#cccccc`. No hay fallback local: los colores se editan en PipeSync > Project Settings para que sean iguales en todas las maquinas.
- El color de Flow se elige como color IDENTITARIO del proyecto, no como color de texto, asi que los oscuros no se leen contra el panel. Antes de pintarlos, `ensure_min_luminance()` (en `LGA_NKS_Projects_Panel.py`) les aplica un piso de luminancia de `MIN_TEXT_LUMINANCE = 150` (Rec. 709, escala 0-255). El aclarado va en dos etapas para no lavar el color: primero sube el brillo al maximo manteniendo tono y saturacion, y solo si no alcanza mezcla hacia blanco lo justo y necesario. Los grises van directo al gris del piso, porque escalarles el brillo los mandaria a blanco puro. Esto es solo presentacion: no toca ni Flow ni la DB, y la lista read-only del panel de settings sigue mostrando el hex original.
- Update automatico: proyectos abiertos muestran boton `Update` cuando existe version mas nueva en disco. La version mas alta se busca SOLO entre archivos del mismo proyecto: `encontrar_version_mas_alta()` filtra por `obtener_clave_proyecto_archivo()`, la misma clave con la que agrupa el escaneo. No usar globs por prefijo aca — `PROJB*` tambien matchea `PROJB_BREAKDOWN_*` y termina ofreciendo la version de otro proyecto.
- Proyectos abiertos: solo se listan los que cuelgan del root del contexto activo (`T:\` en studio, `N:\` en client). Un proyecto abierto desde el otro contexto queda fuera de la lista, del chequeo de versiones nuevas y del match de "ya esta abierto". El filtro lo hace `is_path_under_root()` comparando por componentes, no por prefijo de texto.
- Secuencias: solo de proyectos abiertos. Click llama `switch_to_sequence_hybrid()` y usa `hiero.ui.openInTimeline()` con el objeto `Sequence`.
- En el cambio de secuencia se ejecuta un pre-cleanup sobre el timeline nuevo antes de los ajustes finales de UI: elimina tracks NukeVFX y extiende BurnIn hasta el ultimo clip visible.
- Al final de cada cambio de secuencia, `disable_frame_number_on_active_sequence()` busca `Frame_Only` en el track `BurnIn` de la secuencia activa y lo deshabilita si estaba activo. No llama al toggle de posicionamiento, por lo que no crea el efecto ni lo enciende por accidente.
- Contadores: etiqueta inferior muestra totales de proyectos encontrados y abiertos.
- Reimport: ejecuta el smart reload externo para probar cambios sin reiniciar Hiero.

## Logging y debug
- El panel usa `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectsPanel_Logging.py`.
- Flags por defecto:
  - `DEBUG = True`
  - `DEBUG_CONSOLE = False`
  - `DEBUG_LOG = True`
- Archivo principal: `logs/DebugPy_ProjectsPanel.log`
- Cada `switch_to_sequence_hybrid()` reinicia el `.log` una sola vez al comienzo del cambio de timeline, dejando una traza independiente por secuencia.
- `LGA_NKS_Shared/LGA_NKS_Timeline_PreCleanup.py` y `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py` escriben en ese mismo `.log` cuando son invocados desde Projects Panel.
- El cambio de secuencia registra snapshots `[Widgets]`, targets `[Targets]`, widgets agendados con `deleteLater()` (`[DeleteLater]`), tiempos de `processEvents` / `DeferredDelete` (`[QtEvents]`) y una espera final `[CleanupWait]` para detectar si Hiero sigue cerrando/rearmando timelines despues de que las llamadas Python retornan.
- El log actual incluye:
  - pasos principales del `switch_to_sequence_hybrid()`
  - tiempos de ejecucion por etapa
  - tiempo post-event-loop real (`[Summary] Post-event cleanup wait`)
  - resultados del pre-cleanup de timeline
  - resultados del scroll vertical al top track
  - resultado de `Frame Number off`
  - mensajes del smart reload del panel

## Referencias tecnicas
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel.py`: `ProjectsPanel`, import y wiring de `switch_to_sequence_hybrid()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_NKS_ProjectItem.py`: `ProjectItem.show_sequences()`, `ProjectItem.on_sequence_click()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_Projects_Panel_SwitchSequence.py`: `switch_to_sequence_hybrid()`, `disable_frame_number_on_active_sequence()`, `import_script()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_ViewerTL_Panel_py\LGA_NKS_FrameNumber.py`: `find_frame_only_effect()`, `print_box_values()`.

## UI del panel
- Titulo centrado `Projects`.
- Toolbar derecha: `Refresh`, `Settings`, estado, `Reimport` (opcional).
- Lista con scroll: proyectos cerrados/abiertos y boton `Update` cuando corresponde.
- Etiqueta inferior con resumen de conteos.
- Vista de `Settings`:
  - Dropdown `Auto-refresh interval`: `never`, `5min`, `10min`, `15min`, `30min`, `1h`, `2h`
  - Lista READ-ONLY `Project colors`: nombre, swatch y hex de cada proyecto segun PipeSync. No se edita aca; si la DB no tiene datos se muestra el motivo en vez de una lista vacia. Se repuebla cada vez que se abre la vista.
  - Botones `Cancel` y `Save`. `Save` solo guarda el intervalo.

## Compatibilidad Qt (Nuke 15/16)
Usar siempre el adapter:

```python
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
```

No importar PySide2/PySide6 directamente. Helpers disponibles: `horizontal_advance`, `primary_screen_geometry`, `set_layout_margin`.

### Consideraciones especificas de Nuke 16
- Threading requiere delay de inicializacion: `QTimer.singleShot(500ms)` antes de usar `QThreadPool`
- `QFontMetrics.width()` -> usar `horizontal_advance()` del adapter
- `QShortcut` se movio de `QtWidgets` a `QtGui` en PySide6
