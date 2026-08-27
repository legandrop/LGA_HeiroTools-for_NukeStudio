"""
____________________________________________________________________

  LGA_NKS_Timeline_Refresh_Wrap v1.43 | Lega

  Wrapper que ejecuta una secuencia de scripts para refrescar el timeline manteniendo el nivel de zoom original:

  1. Elimina tracks con tag icon 'icons:NukeVFX.png' del timeline activo
  2. Extiende los efectos de BurnIn hasta el último clip visible con imagen
  3. Captura el estado actual del timeline (zoom y scroll)
  4. Limpia el cache de reproducción (deshabilitado por el momento)
  5. Refresca el timeline
  6. Ajusta el tamaño de la ventana
  7. Scrollea al track superior
  8. Restaura el estado original (dos intentos) usando los valores exactos del slider y scrollbar

  v1.43: Se deja de barrer QApplication.allWidgets() a pelo. Esa lista trae wrappers
         de widgets que Qt ya destruyo del lado C++, y leerles el metaObject() lee
         el heap. Ahora se itera con iter_live_widgets() y se revalida con
         is_widget_alive() antes de cada deleteLater().
  v1.42: Sistema A de logging — solo archivo, sin consola. Wirea set_debug_handler en
         PreCleanup y ScrollToTopTrack para que usen el mismo logger.
  v1.41: Agregado pre-cleanup del timeline antes del refresh.
         Elimina tracks con tag icon 'icons:NukeVFX.png' y extiende BurnIn hasta el último clip visible.
  v1.40: Implementado cierre simultáneo de viewers + timelines para mantener equilibrio delicado de Hiero
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import os
import importlib.util
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import (
    QtWidgets,
    QtCore,
    is_widget_alive,
    iter_live_widgets,
)
import time

DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True

script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        record.relative_time = f"{record.created - script_start_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="TimelineRefreshWrap"):
    global debug_log_listener

    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", f"debugPy_{script_name}.log"
    )
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass

    logger = logging.getLogger(f"{script_name.lower()}_logger")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(RelativeTimeFormatter("[%(relative_time)s] %(message)s"))

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(log_queue, file_handler, respect_handler_level=True)
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="TimelineRefreshWrap")


def debug_print(*message, level="info"):
    global script_start_time
    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        if level == "debug":
            debug_logger.debug(msg)
        elif level == "warning":
            debug_logger.warning(msg)
        elif level == "error":
            debug_logger.error(msg)
        else:
            debug_logger.info(msg)

    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()
        print(f"[{time.time() - script_start_time:.3f}s] {msg}")

def get_timeline_state(timeline_editor=None):
    """
    Obtiene el estado actual del timeline.
    Si timeline_editor es None, usa activeSequence() como fallback.
    """
    try:
        if timeline_editor is None:
            t = hiero.ui.getTimelineEditor(hiero.ui.activeSequence())
        else:
            t = timeline_editor
        if not t:
            return None
            
        # Buscar el QSplitter primero
        splitter = None
        for child in t.window().children():
            if isinstance(child, QtWidgets.QSplitter):
                splitter = child
                break
                
        if not splitter:
            debug_print("No se pudo encontrar el QSplitter")
            return None
            
        # Buscar el TimelineView dentro del primer widget del QSplitter
        timeline_view = None
        for child in splitter.children():
            if isinstance(child, QtWidgets.QWidget):
                for subchild in child.children():
                    if isinstance(subchild, QtWidgets.QAbstractScrollArea):
                        timeline_view = subchild
                        break
                if timeline_view:
                    break
                    
        if not timeline_view:
            debug_print("No se pudo encontrar el TimelineView")
            return None
            
        # Buscar viewport y h_container por nombre
        viewport = None
        h_container = None
        for child in timeline_view.children():
            if hasattr(child, 'objectName'):
                if child.objectName() == "qt_scrollarea_viewport":
                    viewport = child
                elif child.objectName() == "qt_scrollarea_hcontainer":
                    h_container = child
        
        if not all([viewport, h_container]):
            debug_print("No se pudieron encontrar todos los widgets necesarios")
            return None
            
        # Obtener scrollbar y slider
        h_scrollbar = h_container.children()[0]  # QScrollBar
        h_slider = h_container.children()[2]     # QSlider
        
        viewport_width = viewport.width()
        scrollbar_range = h_scrollbar.maximum() - h_scrollbar.minimum() + h_scrollbar.pageStep()
        zoom_factor = viewport_width / scrollbar_range
        
        state = {
            'scroll_value': h_scrollbar.value(),
            'scroll_min': h_scrollbar.minimum(),
            'scroll_max': h_scrollbar.maximum(),
            'page_step': h_scrollbar.pageStep(),
            'viewport_width': viewport_width,
            'zoom_factor': zoom_factor,
            'slider_value': h_slider.value() if hasattr(h_slider, 'value') else None
        }
        
        return state
            
    except Exception as e:
        debug_print(f"Error al obtener el estado del timeline: {e}")
        if DEBUG:
            import traceback
            debug_print(traceback.format_exc())
        
    return None

def restore_timeline_state(state, timeline_editor=None):
    """
    Restaura el estado del timeline usando acceso directo al scrollbar y slider.
    Si timeline_editor es None, usa activeSequence() como fallback.
    """
    try:
        if timeline_editor is None:
            t = hiero.ui.getTimelineEditor(hiero.ui.activeSequence())
        else:
            t = timeline_editor
        if not t:
            return False
            
        # Buscar el QSplitter primero
        splitter = None
        for child in t.window().children():
            if isinstance(child, QtWidgets.QSplitter):
                splitter = child
                break
                
        if not splitter:
            debug_print("No se pudo encontrar el QSplitter")
            return False
            
        # Buscar el TimelineView dentro del primer widget del QSplitter
        timeline_view = None
        for child in splitter.children():
            if isinstance(child, QtWidgets.QWidget):
                for subchild in child.children():
                    if isinstance(subchild, QtWidgets.QAbstractScrollArea):
                        timeline_view = subchild
                        break
                if timeline_view:
                    break
                    
        if not timeline_view:
            debug_print("No se pudo encontrar el TimelineView")
            return False
            
        # Buscar viewport y h_container por nombre
        viewport = None
        h_container = None
        for child in timeline_view.children():
            if hasattr(child, 'objectName'):
                if child.objectName() == "qt_scrollarea_viewport":
                    viewport = child
                elif child.objectName() == "qt_scrollarea_hcontainer":
                    h_container = child
        
        if not all([viewport, h_container]):
            debug_print("No se pudieron encontrar todos los widgets necesarios")
            return False
            
        # Obtener scrollbar y slider
        h_scrollbar = h_container.children()[0]  # QScrollBar
        h_slider = h_container.children()[2]     # QSlider
        
        debug_print("\nRestaurando estado del timeline...")
        debug_print(f"Usando scrollbar y slider para restaurar zoom_factor: {state['zoom_factor']}")
        
        # 1. Primero restaurar el valor del slider
        if state['slider_value'] is not None:
            debug_print(f"Restaurando valor del slider: {state['slider_value']}")
            h_slider.setValue(state['slider_value'])
            QtCore.QCoreApplication.processEvents()
            
            # Verificar estado intermedio
            intermediate_state = get_timeline_state()
            debug_print("\nEstado después de restaurar slider:")
            debug_print(intermediate_state)
        
        # 2. Luego restaurar valores del scrollbar
        debug_print("\nRestaurando valores del scrollbar...")
        h_scrollbar.setPageStep(state['page_step'])
        h_scrollbar.setMaximum(state['scroll_max'])
        h_scrollbar.setMinimum(state['scroll_min'])
        h_scrollbar.setValue(state['scroll_value'])
        
        QtCore.QCoreApplication.processEvents()
        
        # Verificar el estado final
        final_state = get_timeline_state()
        debug_print("\nEstado FINAL después de restaurar:")
        debug_print(final_state)
        
        return True
            
    except Exception as e:
        debug_print(f"Error al restaurar el estado: {e}")
        return False

def find_and_close_old_viewers_and_timelines_safe(old_viewer_object_name=None, old_timeline_object_name=None):
    """
    Cierra viewers Y timelines viejos de forma SEGURA usando deleteLater() (no close()).
    Mantiene el EQUILIBRIO DELICADO de Hiero cerrando ambos simultáneamente.

    Estrategia basada en investigación: usar metaObject().className() y comparación de objectName.
    Documentación: "cerrar viewers + timelines JUNTOS funciona sin crash"

    Args:
        old_viewer_object_name: objectName del viewer que era activo ANTES del refresh.
        old_timeline_object_name: objectName del timeline que era activo ANTES del refresh.
                                Si se proporcionan, solo cierra los widgets específicos.
                                Si son None, cierra todos los que NO sean los actuales.
    """
    try:
        # Obtener viewers/timelines actualmente activos
        current_viewer = hiero.ui.currentViewer()
        current_viewer_obj_name = ""
        if current_viewer:
            try:
                current_window = current_viewer.window()
                if current_window and hasattr(current_window, 'objectName'):
                    current_viewer_obj_name = current_window.objectName()
            except Exception as e:
                debug_print(f"Error obteniendo current viewer objectName: {e}")

        # Obtener timeline activo
        active_seq = hiero.ui.activeSequence()
        current_timeline_obj_name = ""
        if active_seq:
            try:
                current_timeline = hiero.ui.getTimelineEditor(active_seq)
                if current_timeline:
                    current_window = current_timeline.window()
                    if current_window and hasattr(current_window, 'objectName'):
                        current_timeline_obj_name = current_window.objectName()
            except Exception as e:
                debug_print(f"Error obteniendo current timeline objectName: {e}")

        debug_print(f"\n🔍 Buscando viewers y timelines viejos para cerrar simultáneamente")
        debug_print(f"   Current viewer: {current_viewer_obj_name}")
        debug_print(f"   Current timeline: {current_timeline_obj_name}")

        # Buscar TODOS los widgets usando metaObject().className()
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets
        app = QtWidgets.QApplication.instance()
        if not app:
            debug_print("No se pudo obtener la instancia de QApplication")
            return False

        # iter_live_widgets saltea los wrappers de widgets que Qt ya destruyo
        # del lado C++, y evita la llamada a allWidgets() que rompia el heap.
        all_widgets = list(iter_live_widgets())
        old_viewers_found = 0
        old_timelines_found = 0
        old_viewers_closed = 0
        old_timelines_closed = 0

        # PRIMERA PASADA: Identificar qué cerrar (sin cerrar aún)
        widgets_to_close = []

        for widget in all_widgets:
            try:
                class_name = widget.metaObject().className() if hasattr(widget, 'metaObject') else ""
                obj_name = widget.objectName() if hasattr(widget, 'objectName') else ""

                # Filtrar widgets válidos
                if not obj_name or not obj_name.strip():
                    continue

                should_close = False
                widget_type = ""

                # Identificar VIEWERS
                if "Foundry::Storm::UI::Viewer" in class_name:
                    widget_type = "viewer"
                    if 'contactsheet' in obj_name.lower():
                        continue  # Saltar Contact Sheet

                    if old_viewer_object_name:
                        # Cerrar viewer específico identificado antes del refresh
                        should_close = (obj_name == old_viewer_object_name)
                    else:
                        # Cerrar todos viewers que NO sean currentViewer
                        should_close = (obj_name != current_viewer_obj_name)

                # Identificar TIMELINES
                elif "TimelineEditor" in class_name:
                    widget_type = "timeline"

                    if old_timeline_object_name:
                        # Cerrar timeline específico identificado antes del refresh
                        should_close = (obj_name == old_timeline_object_name)
                    else:
                        # Cerrar todos timelines que NO sean el currentTimeline
                        should_close = (obj_name != current_timeline_obj_name)

                if should_close:
                    widgets_to_close.append({
                        'widget': widget,
                        'object_name': obj_name,
                        'type': widget_type,
                        'window_title': widget.windowTitle() if hasattr(widget, 'windowTitle') else ""
                    })

                    if widget_type == "viewer":
                        old_viewers_found += 1
                    elif widget_type == "timeline":
                        old_timelines_found += 1

            except Exception as e:
                # Ignorar errores en widgets individuales
                continue

        # SEGUNDA PASADA: Cerrar simultáneamente (mantener equilibrio)
        debug_print(f"\n⚖️ CERRANDO SIMULTÁNEAMENTE para mantener equilibrio:")
        debug_print(f"   Viewers a cerrar: {old_viewers_found}")
        debug_print(f"   Timelines a cerrar: {old_timelines_found}")

        for item in widgets_to_close:
            try:
                widget = item['widget']
                # Entre las dos pasadas Qt pudo destruir el widget marcado.
                if not is_widget_alive(widget):
                    continue
                obj_name = item['object_name']
                widget_type = item['type']
                display_name = item['window_title'] or obj_name

                debug_print(f"  🗑️ Cerrando {widget_type}: {display_name} (obj: {obj_name})")

                # Usar deleteLater() - Mantiene el equilibrio del sistema
                widget.deleteLater()

                if widget_type == "viewer":
                    old_viewers_closed += 1
                elif widget_type == "timeline":
                    old_timelines_closed += 1

            except Exception as e:
                debug_print(f"  ❌ Error cerrando {item['type']} {item['object_name']}: {e}")

        # Procesar eventos para que los deleteLater() se ejecuten
        QtCore.QCoreApplication.processEvents()

        debug_print(f"\n📊 RESUMEN DEL CIERRE SIMULTÁNEO:")
        debug_print(f"   ✅ Viewers cerrados: {old_viewers_closed}/{old_viewers_found}")
        debug_print(f"   ✅ Timelines cerrados: {old_timelines_closed}/{old_timelines_found}")
        debug_print(f"   ⚖️ Equilibrio mantenido: {old_viewers_closed + old_timelines_closed} widgets cerrados juntos")

        success = (old_viewers_closed + old_timelines_closed) > 0
        if success:
            debug_print(f"   ✅ Cierre simultáneo exitoso - Equilibrio de Hiero mantenido")
        else:
            debug_print(f"   ⚠️ No se encontraron widgets para cerrar")

        return success

    except Exception as e:
        debug_print(f"❌ Error en find_and_close_old_viewers_and_timelines_safe: {e}")
        import traceback
        debug_print(traceback.format_exc())
        return False

def import_script(script_name):
    """
    Importa un script desde la carpeta privada del panel y, si no existe,
    hace fallback a los shareds globales.
    """
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), script_name + '.py'),
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "LGA_NKS_Shared",
            script_name + '.py',
        ),
    ]
    for script_path in candidate_paths:
        if os.path.exists(script_path):
            spec = importlib.util.spec_from_file_location(script_name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

    debug_print(f"Script no encontrado: {candidate_paths[0]}")
    return None

def main():
    """
    Función principal que coordina la ejecución de todos los scripts
    """
    try:
        start_total = time.time()

        # 1. Limpieza previa del timeline actual
        start_time = time.time()
        precleanup_module = import_script('LGA_NKS_Timeline_PreCleanup')
        if precleanup_module:
            if hasattr(precleanup_module, 'set_debug_handler'):
                precleanup_module.set_debug_handler(debug_print)
            try:
                precleanup_result = precleanup_module.main()
                debug_print(f"Resultado pre-cleanup: {precleanup_result}")
            except Exception as e:
                debug_print(f"Error ejecutando pre-cleanup: {e}")
        else:
            debug_print("No se pudo importar LGA_NKS_Timeline_PreCleanup.")
        debug_print(f"Tiempo ejecutando pre-cleanup: {time.time() - start_time:.3f} segundos")
        
        # 2. Capturar estado inicial
        start_time = time.time()
        original_state = get_timeline_state()
        if original_state is None:
            debug_print("No se pudo capturar el estado inicial del timeline.")
            return
        debug_print("\nEstado INICIAL:")
        debug_print(original_state)
        debug_print(f"Tiempo capturando estado inicial: {time.time() - start_time:.3f} segundos")

        # 3. Ejecutar Clear Cache Playback
        """
        start_time = time.time()
        cache_module = import_script('LGA_NKS_ClearCachePlayback')
        if cache_module:
            cache_module.main()
            QtCore.QThread.msleep(10)
            QtCore.QCoreApplication.processEvents()
        debug_print(f"Tiempo ejecutando clear cache: {time.time() - start_time:.3f} segundos")
        """

        # 4. CAPTURAR VIEWER Y TIMELINE ACTIVOS ANTES del refresh (serán los "viejos")
        old_viewer_object_name = None
        old_timeline_object_name = None

        active_viewer_before = hiero.ui.currentViewer()
        if active_viewer_before:
            try:
                old_viewer_window = active_viewer_before.window()
                if old_viewer_window and hasattr(old_viewer_window, 'objectName'):
                    old_viewer_object_name = old_viewer_window.objectName()
                    debug_print(f"📍 Viewer activo ANTES del refresh: {old_viewer_object_name}")
            except Exception as e:
                debug_print(f"⚠️ No se pudo capturar objectName del viewer activo: {e}")

        # Capturar también el timeline activo antes del refresh
        active_seq_before = hiero.ui.activeSequence()
        if active_seq_before:
            try:
                old_timeline = hiero.ui.getTimelineEditor(active_seq_before)
                if old_timeline:
                    old_timeline_window = old_timeline.window()
                    if old_timeline_window and hasattr(old_timeline_window, 'objectName'):
                        old_timeline_object_name = old_timeline_window.objectName()
                        debug_print(f"📍 Timeline activo ANTES del refresh: {old_timeline_object_name}")
            except Exception as e:
                debug_print(f"⚠️ No se pudo capturar objectName del timeline activo: {e}")

        # 5. Ejecutar refresh y obtener timeline/viewer nuevo
        start_time = time.time()
        refresh_module = import_script('LGA_NKS_Timeline_Refresh')
        new_timeline = None
        new_viewer = None
        if refresh_module:
            result = refresh_module.main()
            if result and len(result) >= 2:
                new_timeline, new_viewer = result[:2]  # Solo necesitamos timeline y viewer nuevos
                debug_print(f"Timeline nuevo recibido: {hex(id(new_timeline)) if new_timeline else None}")
                debug_print(f"Viewer nuevo recibido: {hex(id(new_viewer)) if new_viewer else None}")
                if len(result) >= 4:
                    debug_print(f"Viewer viejo objectName: {result[2]}")
                    debug_print(f"Timeline viejo objectName: {result[3]}")
            QtCore.QThread.msleep(10)
            QtCore.QCoreApplication.processEvents()
        debug_print(f"Tiempo ejecutando refresh timeline: {time.time() - start_time:.3f} segundos")

        # Si no obtuvimos el timeline nuevo, usar activeSequence() como fallback
        if not new_timeline:
            debug_print("⚠️ No se obtuvo timeline nuevo, usando activeSequence() como fallback")
            active_seq = hiero.ui.activeSequence()
            if active_seq:
                new_timeline = hiero.ui.getTimelineEditor(active_seq)

        start_time = time.time()
        reduce_module = import_script('LGA_NKS_Reduce_SeqWin')
        if reduce_module:
            reduce_module.main(new_timeline)  # Pasar el timeline nuevo
            QtCore.QThread.msleep(10)
            QtCore.QCoreApplication.processEvents()
        debug_print(f"Tiempo ejecutando reduce window: {time.time() - start_time:.3f} segundos")

        start_time = time.time()
        scroll_module = import_script('LGA_NKS_ScrollTo_TopTrack')
        if scroll_module:
            if hasattr(scroll_module, 'set_debug_handler'):
                scroll_module.set_debug_handler(debug_print)
            scroll_module.main(new_timeline)  # Pasar el timeline nuevo
            QtCore.QThread.msleep(10)
            QtCore.QCoreApplication.processEvents()
        debug_print(f"Tiempo ejecutando scroll to top: {time.time() - start_time:.3f} segundos")

        # 4. Primer intento de restauración usando el timeline nuevo
        start_time = time.time()
        debug_print("\nPrimer intento de restauración...")
        success = restore_timeline_state(original_state, new_timeline)
        debug_print(f"Tiempo primera restauración: {time.time() - start_time:.3f} segundos")
        
        # 5. Segundo intento de restauración usando el timeline nuevo
        start_time = time.time()
        debug_print("\nSegundo intento de restauración...")
        success = restore_timeline_state(original_state, new_timeline)
        debug_print(f"Tiempo segunda restauración: {time.time() - start_time:.3f} segundos")

        # 6. Procesar eventos finales
        QtCore.QCoreApplication.processEvents()
        time.sleep(0.2)

        # 7. ANALIZAR viewers/timelines para cierre (SIN CERRAR AÚN)
        debug_print(f"\n--- ANÁLISIS DE VIEWERS/TIMELINES PARA CIERRE ---")
        debug_print(f"   (Solo análisis - NO se cierra nada aún)")

        try:
            # Recopilar viewers actuales
            from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets
            app = QtWidgets.QApplication.instance()
            if not app:
                debug_print("❌ No QApplication")
                return

            # Buscar viewers con metaObject().className()
            viewers = []
            # iter_live_widgets saltea los wrappers de widgets ya destruidos.
            for widget in iter_live_widgets():
                try:
                    class_name = widget.metaObject().className() if hasattr(widget, 'metaObject') else ""
                    if "Foundry::Storm::UI::Viewer" in class_name:
                        obj_name = widget.objectName() if hasattr(widget, 'objectName') else ""
                        window_title = widget.windowTitle() if hasattr(widget, 'windowTitle') else ""

                        # Intentar obtener sequence name
                        seq_name = "Sin secuencia"
                        try:
                            if hasattr(widget, 'player') and widget.player():
                                player = widget.player()
                                if hasattr(player, 'sequence') and player.sequence():
                                    seq = player.sequence()
                                    seq_name = seq.name() if hasattr(seq, 'name') else "Sin nombre"
                        except:
                            seq_name = "Error obteniendo secuencia"

                        # Solo incluir viewers con objectName válido
                        if obj_name and obj_name.strip():
                            viewers.append({
                                'widget': widget,
                                'object_name': obj_name,
                                'window_title': window_title,
                                'sequence_name': seq_name,
                                'id': hex(id(widget))
                            })
                except Exception:
                    continue

            # Eliminar duplicados por objectName
            unique_viewers = []
            seen_names = set()
            for viewer in viewers:
                obj_name = viewer['object_name']
                if obj_name not in seen_names:
                    unique_viewers.append(viewer)
                    seen_names.add(obj_name)

            viewers = unique_viewers

            # Comparar con currentViewer()
            current_viewer = hiero.ui.currentViewer()
            current_obj_name = ""
            if current_viewer:
                try:
                    current_window = current_viewer.window()
                    if current_window and hasattr(current_window, 'objectName'):
                        current_obj_name = current_window.objectName()
                except Exception as e:
                    debug_print(f"Error obteniendo current objectName: {e}")

            # Recopilar timelines
            timelines = []
            # iter_live_widgets saltea los wrappers de widgets ya destruidos.
            for widget in iter_live_widgets():
                try:
                    class_name = widget.metaObject().className() if hasattr(widget, 'metaObject') else ""
                    if "TimelineEditor" in class_name:
                        obj_name = widget.objectName() if hasattr(widget, 'objectName') else ""
                        window_title = widget.windowTitle() if hasattr(widget, 'windowTitle') else ""

                        # Solo incluir timelines con objectName válido
                        if obj_name and obj_name.strip():
                            seq_name = "Sin secuencia"
                            try:
                                seq = widget.sequence() if hasattr(widget, 'sequence') else None
                                if seq:
                                    seq_name = seq.name()
                            except:
                                seq_name = "Error obteniendo secuencia"

                            timelines.append({
                                'widget': widget,
                                'object_name': obj_name,
                                'window_title': window_title,
                                'sequence_name': seq_name,
                                'id': hex(id(widget))
                            })
                except Exception:
                    continue

            # Eliminar duplicados por objectName
            unique_timelines = []
            seen_names = set()
            for timeline in timelines:
                obj_name = timeline['object_name']
                if obj_name not in seen_names:
                    unique_timelines.append(timeline)
                    seen_names.add(obj_name)

            timelines = unique_timelines

            # Comparar con getTimelineEditor()
            active_seq = hiero.ui.activeSequence()
            current_timeline = hiero.ui.getTimelineEditor(active_seq) if active_seq else None
            current_timeline_obj_name = ""
            if current_timeline:
                try:
                    current_window = current_timeline.window()
                    if current_window and hasattr(current_window, 'objectName'):
                        current_timeline_obj_name = current_window.objectName()
                except Exception as e:
                    debug_print(f"Error obteniendo timeline objectName: {e}")

            # MOSTRAR ANÁLISIS DETALLADO
            debug_print(f"\n🔍 VIEWERS ENCONTRADOS ({len(viewers)}):")
            for i, viewer in enumerate(viewers, 1):
                obj_name = viewer.get('object_name', 'N/A')
                window_title = viewer.get('window_title', '')
                seq_name = viewer.get('sequence_name', 'N/A')

                display_name = window_title or seq_name or obj_name
                is_current = (obj_name == current_obj_name and obj_name != "")
                status = "🎯 ACTIVO" if is_current else "📍 VIEJO"

                debug_print(f"   {i}. {status}: {display_name} (obj: {obj_name}, seq: {seq_name})")

            debug_print(f"\n🔍 TIMELINES ENCONTRADOS ({len(timelines)}):")
            for i, timeline in enumerate(timelines, 1):
                obj_name = timeline.get('object_name', 'N/A')
                window_title = timeline.get('window_title', '')
                seq_name = timeline.get('sequence_name', 'N/A')

                display_name = window_title or seq_name or obj_name
                is_current = (obj_name == current_timeline_obj_name and obj_name != "")
                status = "🎯 ACTIVO" if is_current else "📍 VIEJO"

                debug_print(f"   {i}. {status}: {display_name} (obj: {obj_name}, seq: {seq_name})")

            # RESUMEN EJECUTIVO
            debug_print(f"\n" + "="*80)
            debug_print("📋 RESUMEN EJECUTIVO - QUÉ CERRAR")
            debug_print("="*80)

            if current_viewer:
                current_window_title = ""
                try:
                    current_window = current_viewer.window()
                    if current_window and hasattr(current_window, 'windowTitle'):
                        current_window_title = current_window.windowTitle() or ""
                except:
                    pass
                active_display = current_window_title or "Sin título"
                debug_print(f"🎯 VIEWER ACTIVO: {active_display} (obj: {current_obj_name})")
            else:
                debug_print("❌ VIEWER ACTIVO: NO IDENTIFICADO")

            if active_seq:
                timeline_active_display = active_seq.name() if hasattr(active_seq, 'name') else "Sin nombre"
                debug_print(f"🎯 TIMELINE ACTIVO: {timeline_active_display} (obj: {current_timeline_obj_name})")
            else:
                debug_print("❌ TIMELINE ACTIVO: NO IDENTIFICADO")

            # Viewers a cerrar
            old_viewers = [v for v in viewers if v.get('object_name', '') != current_obj_name or not v.get('object_name', '').strip()]
            if old_viewers:
                debug_print("📍 VIEWERS A CERRAR:")
                for v in old_viewers:
                    obj_name = v.get('object_name', '')
                    window_title = v.get('window_title', '')
                    seq_name = v.get('sequence_name', 'N/A')

                    # Filtrar Contact Sheet
                    if 'contactsheet' in obj_name.lower():
                        debug_print(f"   ⚠️ SALTAR Contact Sheet: {obj_name}")
                        continue

                    display_name = window_title or seq_name or obj_name
                    debug_print(f"   📍 {display_name} (obj: {obj_name}, seq: {seq_name})")
            else:
                debug_print("✅ NO HAY VIEWERS PARA CERRAR")

            # Timelines a cerrar
            old_timelines = [t for t in timelines if t.get('object_name', '') != current_timeline_obj_name or not t.get('object_name', '').strip()]
            if old_timelines:
                debug_print("📍 TIMELINES A CERRAR:")
                for t in old_timelines:
                    obj_name = t.get('object_name', '')
                    window_title = t.get('window_title', '')
                    seq_name = t.get('sequence_name', 'N/A')

                    display_name = window_title or seq_name or obj_name
                    debug_print(f"   📍 {display_name} (obj: {obj_name}, seq: {seq_name})")
            else:
                debug_print("✅ NO HAY TIMELINES PARA CERRAR")

            debug_print(f"\n📊 TOTAL: {len(old_viewers)} viewers y {len(old_timelines)} timelines para cerrar")
            debug_print(f"   ✅ Análisis completado")

            # 8. CERRAR VIEWERS Y TIMELINES VIEJOS SIMULTÁNEAMENTE (EQUILIBRIO)
            debug_print(f"\n--- ⚖️ CERRANDO VIEWERS + TIMELINES SIMULTÁNEAMENTE ---")
            debug_print(f"   Para mantener el EQUILIBRIO DELICADO de Hiero")

            if old_viewer_object_name or old_timeline_object_name:
                debug_print(f"🎯 Cerrando widgets específicos identificados antes del refresh:")
                debug_print(f"   Viewer: {old_viewer_object_name or 'No identificado'}")
                debug_print(f"   Timeline: {old_timeline_object_name or 'No identificado'}")

                close_result = find_and_close_old_viewers_and_timelines_safe(
                    old_viewer_object_name=old_viewer_object_name,
                    old_timeline_object_name=old_timeline_object_name
                )

                if close_result:
                    debug_print(f"✅ Widgets viejos cerrados exitosamente - Equilibrio mantenido")
                else:
                    debug_print(f"⚠️ No se pudieron cerrar los widgets viejos")
            else:
                debug_print(f"⚠️ No se identificaron widgets viejos específicos, omitiendo cierre automático")

        except Exception as e:
            debug_print(f"❌ Error en análisis: {e}")
            import traceback
            debug_print(traceback.format_exc())

        debug_print(f"\nTiempo total de operación: {time.time() - start_total:.3f} segundos")

    except Exception as e:
        debug_print(f"Error en Timeline Refresh Wrap: {e}")
        import traceback
        debug_print(traceback.format_exc())

if __name__ == "__main__":
    main()
