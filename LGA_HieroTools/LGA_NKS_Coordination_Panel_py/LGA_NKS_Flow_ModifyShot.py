"""
____________________________________________________________________

  LGA_NKS_Flow_ModifyShot v1.40 | Lega

  Script para modificar shots existentes en ShotGrid sin afectar estados.
  - Carga información actual del shot (descripción, tasks) desde Flow.
  - Reutiliza la UI compacta del script de creación para garantizar consistencia.
  - Permite agregar o eliminar tasks y actualizar la descripción de forma segura.
  - El número de versión siempre coincide con Create Shot para compatibilidad.
  - Desde v1.33, Create Shot dispara este flujo automáticamente cuando detecta un shot único que ya existe.

  v1.40: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.
  v1.39: Campos EDITABLES y prefilled con datos reales de Flow (estado del shot y
         de cada task con dropdowns coloreados, prioridad, reviewers). El
         ModifyShotWorker aplica los cambios de estado de shot, prioridad, y estado
         + reviewers de tasks existentes. Ver docs/Docu_Flow_Estados_Colores.md.
  v1.38: Si el shot no tiene thumbnail en Flow, el dialogo ofrece "Take Snapshot"
         para capturar uno; al confirmar "Modify Shot" el ModifyShotWorker lo sube
         a Flow (sg.upload_thumbnail) y borra el temporal.
  v1.37: Muestra el thumbnail actual del shot (descargado de Flow) en el
         placeholder del dialogo. La descarga ocurre en el LoadShotInfoWorker
         (hilo) y se pasa al dialogo via existing_thumb_path.
  v1.36: La secuencia se obtiene del segmento de carpeta que sigue a VFX-NOMBRE
         en el path del clip (get_active_sequence_name(file_path)), con fallback
         al nombre del timeline de Hiero. Ver docs/Docu_ProjectName_Extraction.md.
  v1.35: El diálogo de configuración heredado de Create Shot ahora corre
         no modal y continúa por callback, evitando bloquear el foco de Hiero.
  v1.34: Creación automática de carpetas para nuevas tasks agregadas
         Integración con módulo LGA_NKS_Flow_CreateShot_Folders
____________________________________________________________________
"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning
QApplication = QtWidgets.QApplication
QMessageBox = QtWidgets.QMessageBox
QDialog = QtWidgets.QDialog
QObject = QtCore.QObject
QRunnable = QtCore.QRunnable
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
Slot = QtCore.Slot

# Agregar el directorio actual al sys.path para importar módulos locales
import sys
import os
import tempfile
import urllib.request
from pathlib import Path
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from LGA_NKS_Flow_CreateShot import (
    FlowStatusWindow,
    HieroOperations,
    ShotConfigDialog,
    ShotGridManager,
    WorkerSignals,
    debug_print,
    get_active_sequence_name,
    get_flow_credentials_secure,
    print_debug_messages,
    reviewers_config_from_task,
)

# Importar módulo de creación de carpetas
from LGA_NKS_Flow_CreateShot_Folders import create_folders_for_shot_tasks


def _download_thumbnail(image_url):
    """Descarga la URL del thumbnail actual del shot a un JPG temporal.
    Returns: ruta temporal o None si no hay URL o falla la descarga."""
    if not image_url:
        return None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="LGA_ModifyThumb_", suffix=".jpg")
        os.close(fd)
        with urllib.request.urlopen(image_url, timeout=15) as resp:
            data = resp.read()
        with open(temp_path, "wb") as f:
            f.write(data)
        if os.path.getsize(temp_path) > 0:
            return temp_path
        return None
    except Exception as e:
        debug_print(f"No se pudo descargar el thumbnail actual del shot: {e}")
        return None


class ShotDataSignals(QObject):
    loaded = Signal(object, object, int)  # shot, tasks, project_id
    error = Signal(str)
    debug_output = Signal()


class LoadShotInfoWorker(QRunnable):
    def __init__(self, project_name, shot_code):
        super(LoadShotInfoWorker, self).__init__()
        self.project_name = project_name
        self.shot_code = shot_code
        self.signals = ShotDataSignals()

    @Slot()
    def run(self):
        try:
            debug_print(
                f"Iniciando carga de informacion del shot: {self.project_name} / {self.shot_code}"
            )
            sg_url, sg_login, sg_password = get_flow_credentials_secure()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.debug_output.emit()
                self.signals.error.emit("No se pudo inicializar la conexión a ShotGrid.")
                return

            project_id = sg_manager.get_project_id(self.project_name)
            if not project_id:
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    f"No se encontró el proyecto '{self.project_name}' en Flow."
                )
                return

            shot, tasks, _ = sg_manager.find_shot_and_tasks(
                self.project_name,
                self.shot_code,
                shot_config=None,
                thumbnail_path=None,
                create_if_missing=False,
            )

            if not shot:
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    f"El shot '{self.shot_code}' no existe en Flow (usa Create Shot)."
                )
                return

            # Descargar el thumbnail actual del shot (si tiene) para mostrarlo en el
            # dialogo. Se hace aca porque ya estamos en un hilo separado.
            shot["_local_thumb_path"] = _download_thumbnail(shot.get("image"))

            debug_print(
                f"Informacion cargada correctamente para shot '{self.shot_code}'"
            )
            self.signals.loaded.emit(shot, tasks or [], project_id)
            self.signals.debug_output.emit()
        except Exception as e:
            debug_print(f"Error cargando informacion del shot: {e}")
            self.signals.debug_output.emit()
            self.signals.error.emit(str(e))


class ModifyShotWorker(QRunnable):
    def __init__(
        self,
        shot_config,
        clip_info,
        shot_data,
        existing_tasks,
        project_id,
        original_description,
        thumbnail_path=None,
    ):
        super(ModifyShotWorker, self).__init__()
        self.shot_config = shot_config
        self.clip_info = clip_info
        self.shot_data = shot_data
        self.existing_tasks = existing_tasks or []
        self.project_id = project_id
        self.original_description = original_description or ""
        self.thumbnail_path = thumbnail_path
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print(
                f"Iniciando modificacion del shot: {self.clip_info.get('shot_code')}"
            )
            self.signals.shot_info_ready.emit(
                self.clip_info["shot_code"], self.clip_info["project_name"]
            )
            self.signals.step_update.emit("Preparando modificación del shot...")

            sg_url, sg_login, sg_password = get_flow_credentials_secure()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.debug_output.emit()
                self.signals.error.emit("No se pudo inicializar la conexión a ShotGrid.")
                return

            shot_id = self.shot_data["id"]
            existing_task_map = {task["content"]: task for task in self.existing_tasks}
            tasks_config = self.shot_config.get("tasks", {})

            tasks_to_create = []
            tasks_to_delete = []

            for task_name, task_cfg in tasks_config.items():
                enabled_now = task_cfg.get("enabled", False)
                existed = task_name in existing_task_map

                if existed and not enabled_now:
                    tasks_to_delete.append(existing_task_map[task_name])
                elif not existed and enabled_now:
                    tasks_to_create.append((task_name, task_cfg))

            created_count = 0
            deleted_count = 0

            for task in tasks_to_delete:
                task_name = task["content"]
                self.signals.step_update.emit(f"Eliminando task '{task_name}'...")
                if sg_manager.delete_task(task["id"]):
                    deleted_count += 1
                else:
                    self.signals.step_update.emit(
                        f"ERROR eliminando task '{task_name}'."
                    )

            for task_name, task_cfg in tasks_to_create:
                self.signals.step_update.emit(f"Creando task '{task_name}'...")
                success = sg_manager.create_task_for_shot(
                    project_id=self.project_id,
                    shot_id=shot_id,
                    task_name=task_name,
                    task_config=task_cfg,
                    shot_description=self.shot_config["description"],
                )
                if success:
                    created_count += 1
                else:
                    self.signals.step_update.emit(
                        f"ERROR creando task '{task_name}'. Revisa los logs."
                    )

            # ==================================================================================
            # CREAR CARPETAS PARA LAS NUEVAS TASKS
            # ==================================================================================
            if tasks_to_create and self.clip_info.get("file_path"):
                debug_print(f"Creando carpetas - tasks_to_create: {len(tasks_to_create)}, file_path: {self.clip_info.get('file_path')}")

                # Calcular shot_base_path
                hiero_ops = HieroOperations(None)
                shot_base_path = hiero_ops.calculate_shot_base_path(self.clip_info["file_path"])
                debug_print(f"shot_base_path calculado: {shot_base_path}")

                if shot_base_path:
                    # Obtener lista de nuevas tasks creadas exitosamente
                    new_task_names = [task_name for task_name, _ in tasks_to_create]
                    debug_print(f"new_task_names: {new_task_names}")

                    if new_task_names:
                        self.signals.step_update.emit(f"Creando carpetas para {len(new_task_names)} task(s) nueva(s)...")
                        try:
                            folder_result, folder_logs = create_folders_for_shot_tasks(
                                shot_base_path, new_task_names
                            )
                            
                            # Loguear todos los mensajes del proceso de carpetas
                            for log_msg in folder_logs:
                                debug_print(log_msg)

                            # Validar que folder_result sea un diccionario antes de acceder
                            if isinstance(folder_result, dict) and 'created' in folder_result and 'existing' in folder_result:
                                created_folders = len(folder_result['created'])
                                existing_folders = len(folder_result['existing'])
                                self.signals.step_update.emit(
                                    f"Carpetas procesadas: {created_folders} creadas, {existing_folders} ya existían"
                                )
                            else:
                                debug_print(f"ERROR: folder_result no tiene el formato esperado: {type(folder_result)}")
                                debug_print(f"folder_result contenido: {folder_result}")
                                self.signals.step_update.emit("ERROR: Resultado de creación de carpetas inválido")
                        except Exception as e:
                            debug_print(f"ERROR creando carpetas: {e}")
                            self.signals.step_update.emit(f"ERROR creando carpetas: {e}")
                else:
                    debug_print("No se pudo calcular shot_base_path")
                    self.signals.step_update.emit("No se pudo calcular la ruta base para crear carpetas")

            updated_tasks = sg_manager.find_tasks_for_shot(shot_id)
            new_description = self.shot_config["description"] or ""
            description_changed = (
                new_description.strip() != self.original_description.strip()
            )

            if description_changed:
                self.signals.step_update.emit(
                    "Actualizando descripcion del shot y sus tasks..."
                )
                sg_manager.update_shot_description(shot_id, new_description)
                for task in updated_tasks:
                    sg_manager.update_task_description(task["id"], new_description)

            # ----- Estado y prioridad del SHOT -----
            shot_status_changed = False
            new_shot_status = self.shot_config.get("shot_status")
            if new_shot_status and new_shot_status != self.shot_data.get("sg_status_list"):
                self.signals.step_update.emit("Actualizando estado del shot...")
                if sg_manager.update_shot_status(shot_id, new_shot_status):
                    shot_status_changed = True

            priority_changed = False
            new_priority = "high" if self.shot_config.get("high_priority") else "normal"
            old_priority = (self.shot_data.get("sg_prioridad") or "normal").lower()
            if new_priority != old_priority:
                self.signals.step_update.emit("Actualizando prioridad del shot...")
                if sg_manager.update_shot_priority(shot_id, new_priority):
                    priority_changed = True

            # ----- Estado y reviewers de TASKS existentes habilitadas -----
            tasks_updated = 0
            for task_name, task_cfg in tasks_config.items():
                if not task_cfg.get("enabled", False):
                    continue
                existing = existing_task_map.get(task_name)
                if not existing:
                    continue  # task nueva: ya se creo con su estado/reviewers
                changed_here = False
                new_status = task_cfg.get("task_status")
                if new_status and new_status != existing.get("sg_status_list"):
                    self.signals.step_update.emit(
                        f"Actualizando estado de task '{task_name}'..."
                    )
                    if sg_manager.update_task_status(existing["id"], new_status):
                        changed_here = True
                # Reviewers: comparar UI vs Flow y actualizar solo si cambiaron
                desired_rev = task_cfg.get("reviewers", {})
                current_rev = reviewers_config_from_task(existing)
                if desired_rev != current_rev:
                    self.signals.step_update.emit(
                        f"Actualizando reviewers de task '{task_name}'..."
                    )
                    if sg_manager.update_task_reviewers(existing["id"], desired_rev):
                        changed_here = True
                if changed_here:
                    tasks_updated += 1

            # Subir el thumbnail capturado en el dialogo (si el usuario tomo uno)
            thumb_uploaded = False
            if self.thumbnail_path:
                self.signals.step_update.emit("Subiendo thumbnail a Flow...")
                if sg_manager.upload_thumbnail("Shot", shot_id, self.thumbnail_path):
                    thumb_uploaded = True
                else:
                    self.signals.step_update.emit("ERROR subiendo el thumbnail.")

            self.signals.debug_output.emit()

            if any(
                [
                    created_count,
                    deleted_count,
                    description_changed,
                    shot_status_changed,
                    priority_changed,
                    tasks_updated,
                    thumb_uploaded,
                ]
            ):
                summary_parts = []
                if created_count:
                    summary_parts.append(f"{created_count} task(s) nueva(s)")
                if deleted_count:
                    summary_parts.append(f"{deleted_count} task(s) eliminada(s)")
                if description_changed:
                    summary_parts.append("descripcion actualizada")
                if shot_status_changed:
                    summary_parts.append("estado del shot")
                if priority_changed:
                    summary_parts.append("prioridad")
                if tasks_updated:
                    summary_parts.append(f"{tasks_updated} task(s) actualizada(s)")
                if thumb_uploaded:
                    summary_parts.append("thumbnail actualizado")
                summary = ", ".join(summary_parts)
                self.signals.finished.emit(
                    True, f"Shot modificado correctamente ({summary})."
                )
            else:
                self.signals.finished.emit(
                    True, "No se detectaron cambios para aplicar en el shot."
                )
        except Exception as e:
            debug_print(f"Error en ModifyShotWorker: {e}")
            self.signals.debug_output.emit()
            self.signals.error.emit(f"Error modificando shot: {str(e)}")
        finally:
            # Borrar el thumbnail temporal capturado (ya fue subido o ya no se usa)
            if self.thumbnail_path and os.path.exists(self.thumbnail_path):
                try:
                    os.remove(self.thumbnail_path)
                except Exception as e:
                    debug_print(f"No se pudo borrar el thumbnail temporal: {e}")


_loader_window = None
_status_window = None
_config_dialog = None


def _show_error(message):
    show_warning(None, "Modify Shot", message)


def _launch_config_dialog(
    clip_info, sequence_name, shot_data, tasks, project_id, loader_window
):
    global _loader_window, _config_dialog

    if loader_window:
        loader_window.hide()
    if _loader_window is loader_window:
        _loader_window = None

    debug_print("Mostrando dialogo de configuracion en modo Modify Shot")
    dialog = ShotConfigDialog(
        clips_info=[clip_info],
        sequence_name=sequence_name,
        dialog_mode="modify",
        action_button_label="Modify Shot",
        allow_thumbnail_creation=False,
        existing_thumb_path=shot_data.get("_local_thumb_path"),
    )

    existing_tasks_map = {task["content"]: task for task in tasks}
    # Modify Shot: campos EDITABLES (estado, prioridad, reviewers) y prefilled con
    # los valores reales de Flow.
    dialog.prefill_from_existing_shot(
        shot_data, existing_tasks_map, lock_existing_task_fields=False
    )

    _config_dialog = dialog
    dialog.finished.connect(
        lambda result, config_dialog=dialog: _handle_config_dialog_finished(
            result,
            config_dialog,
            clip_info,
            shot_data,
            tasks,
            project_id,
        )
    )
    dialog.show()


def _handle_config_dialog_finished(
    result, dialog, clip_info, shot_data, tasks, project_id
):
    global _config_dialog, _status_window

    if result != QDialog.Accepted:
        debug_print("Dialogo Modify Shot cancelado por el usuario", level="warning")
        dialog.cleanup_thumbnail()
        if _config_dialog is dialog:
            _config_dialog = None
        dialog.deleteLater()
        return

    shot_config = dialog.get_config()
    # Snapshot capturado en el dialogo (Take Snapshot), si hubo. Lo leemos ANTES de
    # cleanup y lo desligamos del dialogo para que cleanup_thumbnail no lo borre:
    # lo sube y lo borra el worker.
    new_thumbnail_path = dialog.thumbnail_path
    dialog.thumbnail_path = None
    dialog.cleanup_thumbnail()
    if _config_dialog is dialog:
        _config_dialog = None
    dialog.deleteLater()
    if not shot_config:
        debug_print("No se obtuvo configuracion para Modify Shot", level="warning")
        if new_thumbnail_path and os.path.exists(new_thumbnail_path):
            try:
                os.remove(new_thumbnail_path)
            except Exception:
                pass
        return

    _status_window = FlowStatusWindow("modificar shot")
    _status_window.show()
    _status_window.show_processing_message()

    worker = ModifyShotWorker(
        shot_config=shot_config,
        clip_info=clip_info,
        shot_data=shot_data,
        existing_tasks=tasks,
        project_id=project_id,
        original_description=shot_data.get("description", "") or "",
        thumbnail_path=new_thumbnail_path,
    )

    worker.signals.shot_info_ready.connect(
        lambda shot_name, project_name, window=_status_window: window.update_shot_info(
            shot_name, project_name
        )
    )
    worker.signals.step_update.connect(
        lambda message, window=_status_window: window.show_step_message(message)
    )
    worker.signals.finished.connect(
        lambda success, message, window=_status_window: (
            window.show_success(message) if window else None
        )
    )
    worker.signals.error.connect(
        lambda error_msg, window=_status_window: (
            window.show_error(error_msg) if window else None
        )
    )
    worker.signals.debug_output.connect(lambda: print_debug_messages())

    QThreadPool.globalInstance().start(worker)


def modify_shot_from_selected_clip():
    debug_print("=== Iniciando LGA_NKS_Flow_ModifyShot ===")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    hiero_ops_temp = HieroOperations(None)
    clips_info = hiero_ops_temp.get_selected_clips_info()

    if not clips_info:
        debug_print("No se encontraron clips seleccionados para modificar", level="warning")
        _show_error("No se encontraron clips seleccionados en Hiero.")
        return

    if len(clips_info) != 1:
        debug_print("Modify Shot requiere un solo clip", level="warning")
        _show_error("Modify Shot solo admite un clip seleccionado a la vez.")
        return

    clip_info = clips_info[0]

    if not clip_info.get("project_name") or not clip_info.get("shot_code"):
        debug_print("No se pudo extraer proyecto/shot del clip", level="warning")
        _show_error("No se pudo extraer el proyecto o shot del clip seleccionado.")
        return

    # Secuencia: primario desde la ruta del clip (segmento despues de VFX-NOMBRE),
    # fallback al nombre del timeline de Hiero. Ver docs/Docu_ProjectName_Extraction.md.
    sequence_name = get_active_sequence_name(clip_info.get("file_path"))
    if not sequence_name:
        debug_print("No se pudo obtener nombre de secuencia activa", level="warning")
        _show_error(
            "No se pudo obtener el nombre de la secuencia activa en Hiero."
        )
        return

    global _loader_window
    _loader_window = FlowStatusWindow("modificar shot")
    _loader_window.show()
    _loader_window.show_step_message("Cargando informacion del shot desde Flow...")

    loader = LoadShotInfoWorker(
        clip_info["project_name"],
        clip_info["shot_code"],
    )

    loader.signals.loaded.connect(
        lambda shot, tasks, project_id: _launch_config_dialog(
            clip_info, sequence_name, shot, tasks, project_id, _loader_window
        )
    )
    loader.signals.error.connect(
        lambda message: (
            _loader_window.show_error(message) if _loader_window else None
        )
    )
    loader.signals.debug_output.connect(lambda: print_debug_messages())

    QThreadPool.globalInstance().start(loader)


def main():
    modify_shot_from_selected_clip()


if __name__ == "__main__":
    main()
