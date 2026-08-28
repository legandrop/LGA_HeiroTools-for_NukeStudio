"""
____________________________________________________________________

  LGA_NKS_OpenInNukeX v1.33 | Lega

  Abre el script asociado al clip seleccionado en NukeX
  Verifica si hay una version mas reciente y pregunta si desea abrirla


  v1.33 - Los dialogos y carteles llevan la fuente del pack
          (apply_ui_font); sin eso salian con la fuente del host
  v1.32 - Dialogos y carteles migrados al modulo de estilo del pack
          (LGA_UI_Style_HieroTools + LGA_NKS_MessageBox)
  v1.31 - Si la version pedida no existe, permite seleccionar otra version disponible
  v1.30 - Obtiene la ruta de NukeX desde la configuracion de LGA_OpenInNukeX
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import subprocess
import socket
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color, Metric, apply_ui_font
from LGA_NKS_Shared.LGA_NKS_MessageBox import styled_message_box

DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def show_message(title, message, duration=None):
    # Cartel estandar con el estilo del pack (LGA_NKS_MessageBox)
    msgBox = styled_message_box(None, title, message)
    # Interpretar el mensaje como HTML si incluye etiquetas, de lo contrario como texto normal
    if "<" in message and ">" in message:
        msgBox.setTextFormat(QtCore.Qt.TextFormat.RichText)  # Interpretar como HTML
    else:
        msgBox.setTextFormat(
            QtCore.Qt.TextFormat.PlainText
        )  # Interpretar como texto normal
    msgBox.setText(message)
    msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
    apply_ui_font(msgBox)  # de nuevo: el boton Ok recien existe ahora
    if duration:
        QtCore.QTimer.singleShot(duration, msgBox.close)
    msgBox.exec_()


def show_timed_message(title, message, duration):
    msgBox = TimedMessageBox(title, message, duration)
    msgBox.exec_()


class CustomVersionDialog(QtWidgets.QDialog):
    def __init__(self, current_version, latest_version, parent=None):
        super().__init__(parent)
        self.result_value = (
            None  # None = cerrado con X/ESC, True = actual, False = ultima
        )

        self.setWindowTitle("Verificacion de Version")
        self.setModal(True)
        # Estilo del pack: hoja de formulario y tokens en vez de hexes sueltos
        self.setStyleSheet(Style.FORM)

        # Layout principal
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(
            Metric.DIALOG_MARGIN,
            Metric.DIALOG_MARGIN,
            Metric.DIALOG_MARGIN,
            Metric.DIALOG_MARGIN,
        )
        layout.setSpacing(Metric.SPACING)

        # Mensaje HTML
        message_label = QtWidgets.QLabel()
        message_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        message_label.setText(
            f"<div style='text-align: center;'>"
            f"<span style='color: {Color.WARNING_TEXT};'><b>¡Atencion!</b></span><br><br>"
            f"La version que intentas abrir no es la mas reciente:<br><br>"
            f"Version actual: <span style='color: {Color.WARNING_TEXT};'>{current_version}</span><br>"
            f"Ultima version: <span style='color: {Color.OK_TEXT};'>{latest_version}</span><br><br>"
            f"¿Deseas abrir la ultima version en su lugar?</div>"
        )
        layout.addWidget(message_label)

        # Botones: la accion recomendada (ultima version) va ultima, a la
        # derecha y en violeta; la otra queda como secundaria
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.yes_button = QtWidgets.QPushButton("Abrir version actual")
        self.no_button = QtWidgets.QPushButton("Abrir ultima version")
        self.yes_button.setStyleSheet(Style.BTN_SECONDARY)
        self.no_button.setStyleSheet(Style.BTN_PRIMARY)

        self.no_button.clicked.connect(self.accept_current)
        self.yes_button.clicked.connect(self.accept_latest)

        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)
        layout.addLayout(button_layout)

        # Hacer que el boton "Abrir ultima version" sea el por defecto
        self.no_button.setDefault(True)

        # Fuente del pack al final del armado: recorre los hijos ya creados.
        apply_ui_font(self)

    def accept_current(self):
        debug_print("Usuario eligio 'Abrir version actual'")
        self.result_value = True
        self.accept()

    def accept_latest(self):
        debug_print("Usuario eligio 'Abrir ultima version'")
        self.result_value = False
        self.accept()

    def closeEvent(self, event):
        debug_print("Usuario cerro el dialogo con X o ESC, abortando")
        self.result_value = None
        event.accept()

    def get_result(self):
        return self.result_value


def show_version_dialog(current_version, latest_version, current_path, latest_path):
    debug_print("Ejecutando show_version_dialog con dialogo personalizado")
    dialog = CustomVersionDialog(current_version, latest_version)
    dialog.exec_()
    result = dialog.get_result()
    debug_print(f"Resultado del dialogo personalizado: {result}")
    return result


class VersionSelectionDialog(QtWidgets.QDialog):
    def __init__(self, requested_label, versions, parent=None):
        super().__init__(parent)
        self.selected_path = None  # None = cancelado, str = ruta elegida

        self.setWindowTitle("Version no encontrada")
        self.setModal(True)
        # Estilo del pack: hoja de formulario y tokens en vez de hexes sueltos
        self.setStyleSheet(Style.FORM)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(
            Metric.DIALOG_MARGIN,
            Metric.DIALOG_MARGIN,
            Metric.DIALOG_MARGIN,
            Metric.DIALOG_MARGIN,
        )
        layout.setSpacing(Metric.SPACING)

        # Mensaje HTML
        message_label = QtWidgets.QLabel()
        message_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        message_label.setText(
            f"<div style='text-align: center;'>"
            f"<span style='color: {Color.WARNING_TEXT};'><b>Version no encontrada</b></span><br><br>"
            f"La version <span style='color: {Color.WARNING_TEXT};'>{requested_label}</span> que intentas abrir no existe.<br><br>"
            f"Selecciona una version disponible:</div>"
        )
        layout.addWidget(message_label)

        # Combo con las versiones disponibles (ordenadas de mayor a menor)
        self.combo = QtWidgets.QComboBox()
        self.combo.setStyleSheet(Style.COMBO)
        for version, path in versions:
            label = get_version_label(os.path.basename(path)) or f"v{version}"
            self.combo.addItem(label, path)
        layout.addWidget(self.combo)

        # Botones: Cancelar secundario y Abrir (accion) ultimo, a la derecha
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        self.open_button = QtWidgets.QPushButton("Abrir")
        self.cancel_button = QtWidgets.QPushButton("Cancelar")
        self.open_button.setStyleSheet(Style.BTN_PRIMARY)
        self.cancel_button.setStyleSheet(Style.BTN_SECONDARY)
        self.open_button.clicked.connect(self.accept_selection)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.open_button)
        layout.addLayout(button_layout)

        self.open_button.setDefault(True)

        # Fuente del pack al final del armado: recorre los hijos ya creados.
        apply_ui_font(self)

    def accept_selection(self):
        self.selected_path = self.combo.currentData()
        debug_print(f"Usuario eligio version: {self.selected_path}")
        self.accept()

    def get_selected_path(self):
        return self.selected_path


def show_version_selection_dialog(requested_label, versions):
    debug_print("Ejecutando show_version_selection_dialog")
    dialog = VersionSelectionDialog(requested_label, versions)
    dialog.exec_()
    return dialog.get_selected_path()


def get_version_from_filename(filename):
    debug_print(f"Analizando version del archivo: {filename}")
    # Busca patrones como _v0, _v00, _v000, etc. antes de la extension (1 a 3 digitos)
    match = re.search(r"_v(\d{1,3})\.nk$", filename)
    if match:
        version = int(match.group(1))
        debug_print(f"Version encontrada: {version}")
        return version
    debug_print("No se encontro version en el nombre del archivo")
    return 0


def get_version_label(filename):
    """Devuelve la etiqueta de version tal cual aparece en el nombre (ej: 'v000', 'v01')."""
    match = re.search(r"_v(\d{1,3})\.nk$", filename)
    if match:
        return "v" + match.group(1)
    return None


def find_all_versions(script_path):
    """Devuelve una lista de (version, ruta) de todas las versiones existentes, ordenada de mayor a menor."""
    debug_print(f"Buscando versiones en: {script_path}")
    directory = os.path.dirname(script_path)
    base_name = os.path.splitext(os.path.basename(script_path))[0]
    debug_print(f"Nombre base del archivo: {base_name}")

    # Eliminar la version actual del nombre base si existe (1 a 3 digitos)
    base_name = re.sub(r"_v\d{1,3}$", "", base_name)
    debug_print(f"Nombre base sin version: {base_name}")

    versions = []
    if not os.path.isdir(directory):
        debug_print(f"El directorio no existe: {directory}")
        return versions

    # Buscar todos los archivos que coincidan con el patrón (1 a 3 digitos)
    pattern = re.compile(f"{re.escape(base_name)}_v\\d{{1,3}}\\.nk$")

    debug_print(f"Buscando archivos en directorio: {directory}")
    for file in os.listdir(directory):
        debug_print(f"Archivo encontrado: {file}")
        if pattern.match(file):
            version = get_version_from_filename(file)
            full_path = os.path.join(directory, file)
            versions.append((version, full_path))
            debug_print(f"Version valida encontrada: {version} en {full_path}")

    # Ordenar por version de mayor a menor
    versions.sort(key=lambda x: x[0], reverse=True)
    return versions


def find_latest_version(script_path):
    versions = find_all_versions(script_path)
    if not versions:
        debug_print("No se encontraron versiones validas")
        return None, None
    latest = versions[0]
    debug_print(f"Version mas alta encontrada: {latest[0]} en {latest[1]}")
    return latest


class TimedMessageBox(QtWidgets.QMessageBox):
    def __init__(self, title, message, duration):
        super().__init__()
        self.setWindowTitle(title)
        self.setText(message)
        self.setStandardButtons(QtWidgets.QMessageBox.Ok)
        # Estilo del pack: mismo tratamiento que styled_message_box,
        # conservando el timer del boton OK
        self.setIcon(QtWidgets.QMessageBox.NoIcon)
        self.setStyleSheet(Style.FORM)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.updateButton)
        self.timeLeft = duration // 1000  # Convert milliseconds to seconds
        self.timer.start(1000)  # Update every second

        self.updateButton()  # Initialize the button text
        # Fuente del pack con el boton OK ya creado por setStandardButtons.
        apply_ui_font(self)

    def updateButton(self):
        if self.timeLeft > 0:
            self.button(QtWidgets.QMessageBox.Ok).setText(f"OK ({self.timeLeft})")
            self.timeLeft -= 1
        else:
            self.timer.stop()
            self.accept()  # Close the message box automatically


def get_project_path(file_path):
    debug_print(f"Obteniendo project path de: {file_path}")
    # Dividir el path en partes usando '/' como separador
    path_parts = file_path.split("/")
    debug_print(f"Partes del path: {path_parts}")
    # Construir la nueva ruta agregando '/Comp/1_projects'
    project_path = "/".join(path_parts[:4]) + "/Comp/1_projects"
    debug_print(f"Project path construido: {project_path}")
    return project_path


def get_script_name(file_path):
    debug_print(f"Obteniendo script name de: {file_path}")
    # Extraer el nombre del archivo del path completo
    script_name = os.path.basename(file_path)
    debug_print(f"Nombre base del archivo: {script_name}")
    # Eliminar la extension y cualquier secuencia de frame como %04d
    script_name = re.sub(r"_%\d+?d\.exr$", "", script_name)
    debug_print(f"Nombre sin secuencia de frame: {script_name}")
    script_name = script_name + ".nk"
    debug_print(f"Nombre final del script: {script_name}")
    return script_name


def get_nukex_path_from_config():
    """
    Obtiene la ruta de NukeX desde la configuracion de LGA_OpenInNukeX
    Busca en: %AppData%\LGA\OpenInNukeX\nukeXpath.txt
    """
    debug_print("Obteniendo ruta de NukeX desde configuracion de OpenInNukeX")
    try:
        # Obtener el directorio AppData del usuario
        appdata_path = os.environ.get("APPDATA")
        if not appdata_path:
            debug_print("No se pudo obtener la ruta de APPDATA")
            return None

        # Construir la ruta al archivo de configuracion
        config_path = os.path.join(appdata_path, "LGA", "OpenInNukeX", "nukeXpath.txt")
        debug_print(f"Buscando configuracion en: {config_path}")

        # Verificar si el archivo existe
        if not os.path.exists(config_path):
            debug_print(f"Archivo de configuracion no encontrado: {config_path}")
            return None

        # Leer la ruta de NukeX del archivo
        with open(config_path, "r", encoding="utf-8") as file:
            nuke_path = file.readline().strip()
            debug_print(f"Ruta de NukeX leida: {nuke_path}")

            # Verificar que la ruta no este vacia y que el archivo exista
            if nuke_path and os.path.exists(nuke_path):
                debug_print("Ruta de NukeX valida encontrada")
                return nuke_path
            else:
                debug_print("Ruta de NukeX no valida o archivo no existe")
                return None

    except Exception as e:
        debug_print(f"Error al leer configuracion de NukeX: {e}")
        return None


def open_nuke_script(nk_filepath):
    host = "localhost"
    port = 54325

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((host, port))
            # Enviar un comando 'ping'
            s.sendall("ping".encode())
            # Esperar una respuesta para confirmar que NukeX esta operativo
            response = s.recv(1024).decode()
            if "pong" in response:
                debug_print("NukeX esta activo y respondiendo.")
                # Cerrar el socket anterior y abrir uno nuevo para enviar el comando de ejecucion
                s.close()
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as new_socket:
                    new_socket.connect((host, port))
                    normalized_path = os.path.normpath(nk_filepath).replace("\\", "/")
                    full_command = f"run_script||{normalized_path}"
                    new_socket.sendall(full_command.encode())
                    show_timed_message(
                        "OpenInNukeX",
                        (
                            f"<div style='text-align: center;'>"
                            f"<span>Abriendo</span><br>"
                            f"<span style='font-style: italic; color: {Color.TEXT_DIM}; font-size: 0.9em;'>{os.path.basename(nk_filepath)}</span><br><br>"
                            f"<span style='color:{Color.TEXT_STRONG};'>Por favor, cambia a la ventana de NukeX...</span>"
                            f"</div>"
                        ),
                        5000,
                    )
                    return

            else:
                raise Exception("NukeX no esta respondiendo como se esperaba.")
    except (socket.timeout, ConnectionRefusedError) as e:
        # Si no se puede establecer la conexion, obtener la ruta de NukeX desde la configuracion
        nuke_path = get_nukex_path_from_config()

        if nuke_path:
            debug_print(f"Usando ruta de NukeX desde configuracion: {nuke_path}")
            debug_print(f"Ejecutando comando: {nuke_path} --nukex {nk_filepath}")
            subprocess.Popen(
                [nuke_path, "--nukex", nk_filepath],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            show_timed_message(
                "OpenInNukeX",
                (
                    f"<span style='color:{Color.TEXT_STRONG};'><b>Fallo la conexion con NukeX</b></span><br><br>"
                    f"Abriendo una nueva instancia de NukeX<br>"
                    f"<span style='font-style: italic; color: {Color.TEXT_DIM}; font-size: 0.9em;'>{nuke_path}</span>"
                ),
                5000,
            )
        else:
            debug_print(
                "No se encontro configuracion de NukeX y no hay conexion activa"
            )
            show_message(
                "Error",
                "No se pudo conectar con NukeX y no se encontro la configuracion de la ruta de NukeX.<br><br>"
                "Por favor, configura la ruta de NukeX usando LGA_OpenInNukeX o verifica que NukeX este ejecutandose.",
            )
    except ConnectionResetError:
        show_message("Error", "La conexion fue cerrada por el servidor.")
    except Exception as e:
        debug_print(f"Error inesperado: {e}")
        show_message("Error", "Ocurrio un error inesperado al abrir NukeX.")


def main():
    try:
        debug_print("Iniciando main()")
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay una secuencia activa.")
            show_message("Error", "No hay una secuencia activa.")
            return

        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection()
        debug_print(f"Clips seleccionados: {len(selected_clips)}")

        if len(selected_clips) == 0:
            debug_print("*** No hay clips seleccionados en la pista ***")
            show_message("Error", "No hay clips seleccionados.")
            return

        for shot in selected_clips:
            if isinstance(shot, hiero.core.EffectTrackItem):
                debug_print("Ignorando clip de tipo EffectTrackItem")
                continue
            try:
                debug_print("Procesando clip...")
                file_path = (
                    shot.source().mediaSource().fileinfos()[0].filename()
                    if shot.source().mediaSource().fileinfos()
                    else None
                )
                if not file_path:
                    debug_print("No se encontro el path del archivo del clip.")
                    continue
                debug_print(f"Path del archivo encontrado: {file_path}")

                project_path = get_project_path(file_path)
                script_name = get_script_name(file_path)
                script_full_path = os.path.join(project_path, script_name)
                debug_print(f"Ruta completa del script: {script_full_path}")

                if os.path.exists(script_full_path):
                    debug_print("El script existe, verificando versiones...")
                    # Verificar si hay una version mas reciente
                    latest_version, latest_path = find_latest_version(script_full_path)
                    current_version = get_version_from_filename(script_name)
                    debug_print(
                        f"Version actual: {current_version}, Version mas reciente: {latest_version}"
                    )

                    if latest_version and latest_version > current_version:
                        debug_print("Se encontro una version mas reciente")
                        current_label = (
                            get_version_label(script_name) or f"v{current_version}"
                        )
                        latest_label = (
                            get_version_label(os.path.basename(latest_path))
                            or f"v{latest_version}"
                        )
                        user_choice = show_version_dialog(
                            current_label,
                            latest_label,
                            script_full_path,
                            latest_path,
                        )

                        # Si el usuario cerro el dialogo sin elegir, abortar
                        if user_choice is None:
                            debug_print(
                                "Usuario cerro el dialogo sin elegir, abortando operacion"
                            )
                            return
                        elif user_choice:
                            debug_print("Usuario eligio abrir la version mas reciente")
                            script_full_path = latest_path

                    debug_print(f"Abriendo script: {script_full_path}")
                    open_nuke_script(script_full_path)
                else:
                    debug_print(f"El script no existe en: {script_full_path}")
                    # La version pedida no existe: buscar otras versiones disponibles
                    available_versions = find_all_versions(script_full_path)
                    if available_versions:
                        debug_print(
                            f"Versiones disponibles encontradas: {len(available_versions)}"
                        )
                        requested_label = (
                            get_version_label(script_name) or "desconocida"
                        )
                        selected_path = show_version_selection_dialog(
                            requested_label, available_versions
                        )
                        if selected_path:
                            debug_print(f"Abriendo version elegida: {selected_path}")
                            open_nuke_script(selected_path)
                        else:
                            debug_print("Usuario cancelo la seleccion de version")
                    else:
                        debug_print("No hay ninguna version disponible")
                        formatted_message = (
                            "<div style='text-align: left;'><b>Archivo no encontrado</b><br><br>"
                            + script_full_path
                            + "</div>"
                        )
                        show_message("Error", formatted_message)
                return
            except AttributeError as e:
                debug_print(f"El clip no tiene una fuente valida: {e}")
            except Exception as e:
                debug_print(f"Error procesando el clip: {e}")

        show_message("Error", "No se encontro un clip valido.")
    except Exception as e:
        debug_print(f"Error durante la operacion: {e}")


if __name__ == "__main__":
    main()
