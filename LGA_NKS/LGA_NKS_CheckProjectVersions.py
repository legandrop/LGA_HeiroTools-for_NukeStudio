"""
_______________________________________________________________

  LGA_NKS_CheckProjectVersions v1.81 - 2025 - Lega
  Chequea versiones de todos los proyectos abiertos en Hiero
_______________________________________________________________

"""

import hiero.core
import hiero.ui
import re
import os
import glob
import datetime
from PySide2.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGridLayout,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QApplication,
    QHBoxLayout,
    QAbstractItemView,
)
from PySide2.QtCore import Qt, QTimer
from PySide2.QtGui import QFont, QColor

# Configuración del temporizador (en minutos)
INTERVALO_TEMPORIZADOR = 4

# Variable global para almacenar el temporizador activo
temporizador_global = None
temporizador_id = "LGA_CheckProjects_Timer"

# Variable global para controlar si el temporizador esta habilitado
is_timer_enabled = True

DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def extraer_version(ruta_disco):
    """Extrae el número de versión de la ruta del archivo en disco"""
    if not ruta_disco:
        return "No detectada"

    try:
        # Obtener el nombre del archivo (sin la ruta completa)
        nombre_archivo = os.path.basename(ruta_disco)

        # Quitar la extensión .hrox
        nombre_sin_extension = os.path.splitext(nombre_archivo)[0]

        # Buscar la parte que comienza con 'v' seguida de números al final del nombre
        resultado = re.search(r"(?:_|-)?(v\d+)$", nombre_sin_extension)
        if resultado:
            return resultado.group(1)  # Devuelve 'v###'

        # Si no encuentra 'v', buscar solo números al final después de un guion bajo o guion
        resultado = re.search(r"(?:_|-)?(\d+)$", nombre_sin_extension)
        if resultado:
            return "v" + resultado.group(1)  # Añade 'v' a los números encontrados

        return "No detectada"
    except Exception as e:
        debug_print(f"Error al extraer versión: {str(e)}")
        return "Error"


def comparar_versiones(version1, version2):
    """Compara dos versiones en formato 'v###' y devuelve la mayor"""
    try:
        # Extraer solo los números de las versiones
        match1 = re.search(r"v?(\d+)", version1)
        match2 = re.search(r"v?(\d+)", version2)

        if not match1 or not match2:
            return (
                version1  # Si no se pueden extraer números, devuelve la primera versión
            )

        num1 = int(match1.group(1))
        num2 = int(match2.group(1))

        if num1 > num2:
            return version1
        else:
            return version2
    except Exception as e:
        debug_print(f"Error al comparar versiones {version1} y {version2}: {str(e)}")
        return version1  # En caso de error, devuelve la primera versión


def encontrar_version_mas_alta(ruta_actual):
    """Encuentra la ruta del archivo con la versión más alta en la misma carpeta"""
    if not ruta_actual or not os.path.exists(ruta_actual):
        return "No disponible"

    try:
        # Obtener la carpeta que contiene el archivo actual
        directorio = os.path.dirname(ruta_actual)

        # Obtener el nombre base del proyecto (sin versión ni extensión)
        nombre_archivo = os.path.basename(ruta_actual)

        # Extraer la parte base del nombre (antes de la versión)
        base_match = re.match(r"(.+?)(?:_|-)?v?\d+\.hrox$", nombre_archivo)
        if not base_match:
            base_match = re.match(r"(.+?)\.hrox$", nombre_archivo)
            if not base_match:
                return "No detectada"

        base_nombre = base_match.group(1)

        # Buscar todos los archivos .hrox en el directorio con el mismo nombre base
        patron_busqueda = os.path.join(directorio, f"{base_nombre}*v*.hrox")
        archivos = glob.glob(patron_busqueda)

        # Si no encuentra con el patrón v*.hrox, intentar con cualquier número
        if not archivos:
            patron_busqueda = os.path.join(directorio, f"{base_nombre}*[0-9]*.hrox")
            archivos = glob.glob(patron_busqueda)

        if not archivos:
            return "No hay otras versiones"

        # Extraer versiones de todos los archivos encontrados
        version_mas_alta = None
        archivo_mas_alto = None

        for archivo in archivos:
            version = extraer_version(archivo)
            if version == "No detectada" or version == "Error":
                continue

            if version_mas_alta is None:
                version_mas_alta = version
                archivo_mas_alto = archivo
            else:
                version_previa = version_mas_alta
                version_mas_alta = comparar_versiones(version_mas_alta, version)

                if version_mas_alta != version_previa:
                    archivo_mas_alto = archivo

        if version_mas_alta and archivo_mas_alto:
            # Devolver la ruta completa del archivo con la versión más alta
            return archivo_mas_alto
        else:
            return "No detectada"

    except Exception as e:
        debug_print(f"Error al buscar versión más alta: {str(e)}")
        return "Error"


def obtener_timestamp():
    """Devuelve una cadena formateada con la fecha y hora actual"""
    ahora = datetime.datetime.now()
    return ahora.strftime("%d/%m/%Y %H:%M:%S")


class ProyectosAbertosDialog(QMainWindow):
    def __init__(self, parent=None, proyectos_con_version_alta=None):
        super(ProyectosAbertosDialog, self).__init__(parent)
        self.setWindowTitle("Proyectos Abiertos")
        self.setMinimumSize(900, 200)  # Reducir la altura a la mitad

        # Establecer un nombre de objeto único para esta ventana
        self.setObjectName("LGA_ProyectosAbertosDialog")

        # Variable para almacenar los datos de proyectos actuales
        self.proyectos_data = []

        # Configurar banderas de ventana para permitir minimizar, maximizar y cerrar
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        # Hacer que la ventana se destruya completamente cuando se cierra
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Conectar el evento de cierre para detener el temporizador
        self.destroyed.connect(self.on_destroyed)

        # Mostrar IDs de la ventana
        debug_print(f"ID de ventana nativo: {self.winId()}")
        debug_print(f"Nombre de objeto: {self.objectName()}")

        # Widget central y layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Añadir título
        titulo = QLabel("Versiones de Proyectos Abiertos")
        titulo.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        titulo.setFont(font)
        layout.addWidget(titulo)

        # Añadir información del temporizador
        self.label_timer = QLabel(f"Actualizando cada {INTERVALO_TEMPORIZADOR} minutos")
        self.label_timer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_timer)

        # Tabla para mostrar los datos
        self.tabla_proyectos = QTableWidget()
        self.tabla_proyectos.setColumnCount(3)
        self.tabla_proyectos.setHorizontalHeaderLabels(
            ["Nombre del Proyecto", "Ruta en Disco", "Versión Más Alta en Disco"]
        )
        self.tabla_proyectos.horizontalHeader().setStretchLastSection(True)
        self.tabla_proyectos.setColumnWidth(0, 200)  # Nombre del proyecto
        self.tabla_proyectos.setColumnWidth(1, 350)  # Ruta en disco

        # Configurar selección de filas
        self.tabla_proyectos.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_proyectos.setSelectionMode(QAbstractItemView.SingleSelection)

        layout.addWidget(self.tabla_proyectos)

        # Botones inferiores en layout horizontal
        botones_layout = QHBoxLayout()

        # Botón para abrir nueva versión y cerrar actual
        boton_abrir_y_cerrar = QPushButton("Cerrar versión actual y abrir la nueva")
        boton_abrir_y_cerrar.clicked.connect(self.abrir_nueva_version_y_cerrar_actual)
        botones_layout.addWidget(boton_abrir_y_cerrar)

        # Botón para abrir nueva versión
        boton_abrir_nueva = QPushButton("Abrir nueva versión")
        boton_abrir_nueva.clicked.connect(self.abrir_nueva_version)
        botones_layout.addWidget(boton_abrir_nueva)

        # Nuevo botón para deshabilitar el temporizador
        self.boton_deshabilitar = QPushButton("Deshabilitar chequeos automáticos")
        self.boton_deshabilitar.clicked.connect(self.deshabilitar_temporizador_ui)
        botones_layout.addWidget(self.boton_deshabilitar)

        layout.addLayout(botones_layout)

        # Actualizar el estado del boton de deshabilitar y el label del timer al inicializar la UI
        global is_timer_enabled
        if not is_timer_enabled:
            self.label_timer.setText("Temporizador Deshabilitado")
            self.boton_deshabilitar.setEnabled(False)

        # Cargar proyectos o usar los datos proporcionados
        if proyectos_con_version_alta:
            self.actualizar_proyectos_con_datos(proyectos_con_version_alta)
        else:
            self.actualizar_proyectos()

    def on_destroyed(self):
        """Se llama cuando la ventana se destruye"""
        global is_timer_enabled
        is_timer_enabled = False  # Asegura que el estado de 'deshabilitado' persista al cerrar la ventana
        # Detener el temporizador si la ventana se cierra
        detener_temporizador()
        debug_print(
            "Ventana de verificación de versiones cerrada. Temporizador deshabilitado."
        )

    def actualizar_proyectos(self):
        """Actualiza la información de los proyectos abiertos en la tabla"""
        debug_print("Actualizando información de proyectos...")
        # Limpiar tabla existente
        self.tabla_proyectos.clearContents()
        self.tabla_proyectos.setRowCount(0)

        # Actualizar etiqueta de temporizador
        self.label_timer.setText(
            f"Actualizando cada {INTERVALO_TEMPORIZADOR} minutos. Última: {obtener_timestamp()}"
        )

        # Llamar al método original de carga
        self.cargar_proyectos()

    def actualizar_proyectos_con_datos(self, proyectos_con_version_alta):
        """Actualiza la tabla con los datos proporcionados"""
        debug_print("Actualizando información de proyectos con datos preexistentes...")
        # Limpiar tabla existente
        self.tabla_proyectos.clearContents()
        self.tabla_proyectos.setRowCount(0)

        # Almacenar los datos de proyectos para uso posterior
        self.proyectos_data = proyectos_con_version_alta

        # Actualizar etiqueta de temporizador
        self.label_timer.setText(
            f"Actualizando cada {INTERVALO_TEMPORIZADOR} minutos. Última: {obtener_timestamp()}"
        )

        # Configurar el número de filas para los proyectos con versión más alta
        self.tabla_proyectos.setRowCount(len(proyectos_con_version_alta))

        # Cargar datos directamente en la tabla
        for i, proyecto_data in enumerate(proyectos_con_version_alta):
            # Crear elementos de tabla
            item_nombre = QTableWidgetItem(proyecto_data["nombre"])
            item_ruta = QTableWidgetItem(proyecto_data["ruta_actual"])
            item_ruta_alta = QTableWidgetItem(proyecto_data["ruta_alta"])

            # Asignar a la tabla
            self.tabla_proyectos.setItem(i, 0, item_nombre)
            self.tabla_proyectos.setItem(i, 1, item_ruta)
            self.tabla_proyectos.setItem(i, 2, item_ruta_alta)

            debug_print(f"Añadido a tabla: {proyecto_data['nombre']}")

        # Seleccionar la primera fila por defecto si hay datos
        if len(proyectos_con_version_alta) > 0:
            self.tabla_proyectos.selectRow(0)

    def cargar_proyectos(self):
        """Carga la información de los proyectos abiertos en la tabla"""
        proyectos = hiero.core.projects()

        if not proyectos:
            self.close()  # Cerrar la ventana si no hay proyectos abiertos
            return

        # Paso 1: Crear un diccionario de todos los proyectos abiertos agrupados por nombre base
        proyectos_abiertos_por_base = {}

        for proyecto in proyectos:
            ruta_disco = proyecto.path()
            nombre_base = obtener_nombre_base_proyecto(ruta_disco)

            if nombre_base:
                if nombre_base not in proyectos_abiertos_por_base:
                    proyectos_abiertos_por_base[nombre_base] = []

                version_num = -1
                version_str = extraer_version(ruta_disco)
                if version_str != "No detectada" and version_str != "Error":
                    match = re.search(r"v?(\d+)", version_str)
                    if match:
                        version_num = int(match.group(1))

                proyectos_abiertos_por_base[nombre_base].append(
                    {
                        "proyecto": proyecto,
                        "ruta": ruta_disco,
                        "version_num": version_num,
                        "version_str": version_str,
                    }
                )

        # Paso 2: Filtrar proyectos que tienen una versión más alta disponible que NO esté ya abierta
        proyectos_con_version_alta = []

        for proyecto in proyectos:
            # Obtener nombre de la interfaz
            nombre_interfaz = proyecto.name()

            # Obtener ruta del disco
            ruta_disco = proyecto.path()
            nombre_base = obtener_nombre_base_proyecto(ruta_disco)

            if not nombre_base:
                continue

            # Extraer versión de la ruta en disco (para comparación)
            version_actual = extraer_version(ruta_disco)

            # Encontrar la ruta de la versión más alta en disco
            ruta_version_alta = encontrar_version_mas_alta(ruta_disco)

            # Verificar si tiene una versión más alta que la actual
            version_actual_num = -1
            version_alta_num = -1

            try:
                if version_actual != "No detectada" and version_actual != "Error":
                    match_actual = re.search(r"v?(\d+)", version_actual)
                    if match_actual:
                        version_actual_num = int(match_actual.group(1))

                if (
                    ruta_version_alta != "No detectada"
                    and ruta_version_alta != "Error"
                    and ruta_version_alta != "No disponible"
                    and ruta_version_alta != "No hay otras versiones"
                ):
                    version_alta = extraer_version(ruta_version_alta)
                    if version_alta != "No detectada" and version_alta != "Error":
                        match_alta = re.search(r"v?(\d+)", version_alta)
                        if match_alta:
                            version_alta_num = int(match_alta.group(1))
            except Exception as e:
                debug_print(f"Error al comparar versiones: {str(e)}")

            # Verificar si la versión más alta ya está abierta
            version_alta_ya_abierta = False
            if nombre_base in proyectos_abiertos_por_base and version_alta_num > 0:
                for proyecto_abierto in proyectos_abiertos_por_base[nombre_base]:
                    if proyecto_abierto["version_num"] == version_alta_num:
                        version_alta_ya_abierta = True
                        debug_print(
                            f"La versión más alta v{version_alta_num} del proyecto {nombre_base} ya está abierta"
                        )
                        break

            # Solo incluir proyectos con versión más alta disponible QUE NO ESTÉ YA ABIERTA
            if (
                version_actual_num > 0
                and version_alta_num > 0
                and version_actual_num < version_alta_num
                and not version_alta_ya_abierta
            ):
                proyectos_con_version_alta.append(
                    {
                        "proyecto": proyecto,
                        "nombre": nombre_interfaz,
                        "ruta_actual": ruta_disco,
                        "ruta_alta": ruta_version_alta,
                    }
                )
                debug_print(
                    f"Proyecto {nombre_interfaz} - Versión actual: v{version_actual_num}, Versión más alta disponible (no abierta): v{version_alta_num}"
                )

        # Si no hay proyectos con versiones más altas que no estén ya abiertas, cerrar la ventana
        if not proyectos_con_version_alta:
            debug_print(
                "No hay proyectos con versiones más altas que no estén ya abiertas. Cerrando ventana."
            )
            self.close()  # Cerrar la ventana si no hay proyectos con versiones más altas
            return

        # Cargar datos de proyectos con versión más alta
        self.actualizar_proyectos_con_datos(proyectos_con_version_alta)

    def abrir_nueva_version(self):
        """Abre la versión más alta encontrada del proyecto seleccionado"""
        # Obtener la fila seleccionada
        fila_seleccionada = self.tabla_proyectos.currentRow()

        if fila_seleccionada < 0:
            print("Por favor, selecciona un proyecto de la tabla.")
            return

        if fila_seleccionada >= len(self.proyectos_data):
            print("Error: fila seleccionada fuera de rango.")
            return

        # Obtener los datos del proyecto seleccionado
        proyecto_data = self.proyectos_data[fila_seleccionada]
        ruta_nueva_version = proyecto_data["ruta_alta"]

        # Verificar que la ruta de la nueva versión existe
        if not os.path.exists(ruta_nueva_version):
            print(f"Error: No se puede encontrar el archivo {ruta_nueva_version}")
            return

        try:
            # Abrir el proyecto de la nueva versión en Hiero
            debug_print(f"Abriendo nueva versión: {ruta_nueva_version}")
            nuevo_proyecto = hiero.core.openProject(ruta_nueva_version)

            if nuevo_proyecto:
                print(
                    f"Proyecto abierto exitosamente: {os.path.basename(ruta_nueva_version)}"
                )
                debug_print(f"Nuevo proyecto cargado: {nuevo_proyecto.name()}")
            else:
                print(f"Error al abrir el proyecto: {ruta_nueva_version}")

        except Exception as e:
            print(f"Error al abrir la nueva versión: {str(e)}")
            debug_print(f"Excepción al abrir proyecto: {str(e)}")

    def abrir_nueva_version_y_cerrar_actual(self):
        """Cierra el proyecto actual y abre la versión más alta encontrada del proyecto seleccionado"""
        # Obtener la fila seleccionada
        fila_seleccionada = self.tabla_proyectos.currentRow()

        if fila_seleccionada < 0:
            print("Por favor, selecciona un proyecto de la tabla.")
            return

        if fila_seleccionada >= len(self.proyectos_data):
            print("Error: fila seleccionada fuera de rango.")
            return

        # Obtener los datos del proyecto seleccionado
        proyecto_data = self.proyectos_data[fila_seleccionada]
        proyecto_actual = proyecto_data["proyecto"]
        ruta_nueva_version = proyecto_data["ruta_alta"]

        # Verificar que la ruta de la nueva versión existe
        if not os.path.exists(ruta_nueva_version):
            print(f"Error: No se puede encontrar el archivo {ruta_nueva_version}")
            return

        try:
            # Paso 1: Cerrar el proyecto actual
            debug_print(f"Cerrando proyecto actual: {proyecto_actual.name()}")
            print(f"Cerrando proyecto: {proyecto_actual.name()}")

            # Cerrar el proyecto usando el método close()
            proyecto_actual.close()

            # Paso 2: Abrir el proyecto de la nueva versión
            debug_print(f"Abriendo nueva versión: {ruta_nueva_version}")
            print(f"Abriendo nueva versión: {os.path.basename(ruta_nueva_version)}")

            nuevo_proyecto = hiero.core.openProject(ruta_nueva_version)

            if nuevo_proyecto:
                print(
                    f"Proyecto actualizado exitosamente a: {os.path.basename(ruta_nueva_version)}"
                )
                debug_print(f"Nuevo proyecto cargado: {nuevo_proyecto.name()}")

                # Cerrar la ventana después de la operación exitosa
                self.close()
            else:
                print(f"Error al abrir el proyecto: {ruta_nueva_version}")
                # Si no se pudo abrir la nueva versión, intentar reabrir la original
                try:
                    print("Intentando reabrir el proyecto original...")
                    hiero.core.openProject(proyecto_data["ruta_actual"])
                except Exception as restore_e:
                    print(f"Error al restaurar proyecto original: {str(restore_e)}")

        except Exception as e:
            print(f"Error durante el proceso de cambio de versión: {str(e)}")
            debug_print(f"Excepción al cambiar versión: {str(e)}")
            # Intentar reabrir el proyecto original si algo salió mal
            try:
                print("Intentando reabrir el proyecto original debido al error...")
                hiero.core.openProject(proyecto_data["ruta_actual"])
            except Exception as restore_e:
                print(f"Error al restaurar proyecto original: {str(restore_e)}")

    def deshabilitar_temporizador_ui(self):
        """Deshabilita el temporizador y actualiza el label."""
        self._disable_timer_and_update_ui()

    def _disable_timer_and_update_ui(self):
        """Deshabilita el temporizador y actualiza el label."""
        global temporizador_global, is_timer_enabled
        if temporizador_global and temporizador_global.isActive():
            temporizador_global.stop()
        is_timer_enabled = False
        self.label_timer.setText("Temporizador Deshabilitado")
        self.boton_deshabilitar.setEnabled(
            False
        )  # Deshabilitar el boton una vez presionado
        print("Temporizador de verificación de versiones deshabilitado.")


def buscar_ventana_existente(nombre_objeto):
    """
    Busca si ya existe una ventana con el nombre de objeto especificado
    Devuelve la ventana si existe y está visible, None en caso contrario
    """
    for widget in QApplication.instance().allWidgets():
        if (
            widget.objectName() == nombre_objeto
            and isinstance(widget, QMainWindow)
            and widget.isVisible()
        ):
            return widget
    return None


def detener_temporizador():
    """Detiene el temporizador global si existe"""
    global temporizador_global
    if temporizador_global is not None and temporizador_global.isActive():
        debug_print(f"Deteniendo temporizador con ID: {temporizador_id}")
        temporizador_global.stop()
        temporizador_global = None


def iniciar_temporizador():
    """Inicia o reinicia el temporizador global"""
    global temporizador_global, is_timer_enabled, temporizador_id
    if not is_timer_enabled:
        debug_print("El temporizador esta deshabilitado globalmente. No se iniciara.")
        return

    # Detener temporizador existente si hay alguno
    detener_temporizador()

    # Crear un nuevo temporizador
    temporizador_global = QTimer()
    temporizador_global.setObjectName(temporizador_id)
    temporizador_global.timeout.connect(main)
    temporizador_global.start(
        INTERVALO_TEMPORIZADOR * 60 * 1000
    )  # Convertir minutos a milisegundos

    debug_print(
        f"Iniciado temporizador con ID: {temporizador_id}, intervalo: {INTERVALO_TEMPORIZADOR} minutos"
    )

    # Si la ventana ya existe, actualiza el label del timer
    ventana_existente = buscar_ventana_existente("LGA_ProyectosAbertosDialog")
    if ventana_existente:
        # Si el temporizador esta deshabilitado, actualiza el texto del label
        if not is_timer_enabled:
            ventana_existente.label_timer.setText("Temporizador Deshabilitado")
            ventana_existente.boton_deshabilitar.setEnabled(False)
        else:
            ventana_existente.label_timer.setText(
                f"Actualizando cada {INTERVALO_TEMPORIZADOR} minutos"
            )
            ventana_existente.boton_deshabilitar.setEnabled(True)

    else:
        # Si no existe, abre una nueva ventana y se encarga de la inicializacion
        dialogo = ProyectosAbertosDialog()
        dialogo.show()
        debug_print("Nueva ventana de proyectos abiertos mostrada.")


def actualizar_intervalo_temporizador(nuevo_intervalo):
    """Actualiza el intervalo del temporizador y lo reinicia"""
    global INTERVALO_TEMPORIZADOR

    # Actualizar la variable global
    INTERVALO_TEMPORIZADOR = nuevo_intervalo

    # Reiniciar el temporizador con el nuevo intervalo
    iniciar_temporizador()

    # Actualizar la etiqueta en la ventana si existe
    ventana_existente = buscar_ventana_existente("LGA_ProyectosAbertosDialog")
    if ventana_existente:
        ventana_existente.label_timer.setText(
            f"Actualizando cada {INTERVALO_TEMPORIZADOR} minutos"
        )


def obtener_nombre_base_proyecto(ruta):
    """Obtiene el nombre base del proyecto sin versión ni extensión"""
    if not ruta:
        return None

    nombre_archivo = os.path.basename(ruta)
    # Extraer la parte base del nombre (antes de la versión)
    base_match = re.match(r"(.+?)(?:_|-)?v?\d+\.hrox$", nombre_archivo)
    if not base_match:
        base_match = re.match(r"(.+?)\.hrox$", nombre_archivo)
        if not base_match:
            return None

    return base_match.group(1)


def main():
    """Función principal que muestra el diálogo con los proyectos abiertos SOLO si hay versiones más altas"""
    # Iniciar o reiniciar el temporizador
    iniciar_temporizador()

    # Verificar primero si hay proyectos abiertos
    proyectos = hiero.core.projects()
    if not proyectos or len(proyectos) == 0:
        debug_print("No hay proyectos abiertos. No se mostrará la ventana.")
        return

    # Paso 1: Crear un diccionario de todos los proyectos abiertos agrupados por nombre base
    proyectos_abiertos_por_base = {}

    for proyecto in proyectos:
        ruta_disco = proyecto.path()
        nombre_base = obtener_nombre_base_proyecto(ruta_disco)

        if nombre_base:
            if nombre_base not in proyectos_abiertos_por_base:
                proyectos_abiertos_por_base[nombre_base] = []

            version_num = -1
            version_str = extraer_version(ruta_disco)
            if version_str != "No detectada" and version_str != "Error":
                match = re.search(r"v?(\d+)", version_str)
                if match:
                    version_num = int(match.group(1))

            proyectos_abiertos_por_base[nombre_base].append(
                {
                    "proyecto": proyecto,
                    "ruta": ruta_disco,
                    "version_num": version_num,
                    "version_str": version_str,
                }
            )

    # Paso 2: Verificar si hay proyectos con versiones más altas disponibles
    # pero que NO estén ya abiertos
    proyectos_con_version_alta = []

    for proyecto in proyectos:
        nombre_interfaz = proyecto.name()
        ruta_disco = proyecto.path()
        nombre_base = obtener_nombre_base_proyecto(ruta_disco)

        if not nombre_base:
            continue

        version_actual = extraer_version(ruta_disco)
        ruta_version_alta = encontrar_version_mas_alta(ruta_disco)

        # Verificar si tiene una versión más alta que la actual
        version_actual_num = -1
        version_alta_num = -1

        try:
            if version_actual != "No detectada" and version_actual != "Error":
                match_actual = re.search(r"v?(\d+)", version_actual)
                if match_actual:
                    version_actual_num = int(match_actual.group(1))

            if (
                ruta_version_alta != "No detectada"
                and ruta_version_alta != "Error"
                and ruta_version_alta != "No disponible"
                and ruta_version_alta != "No hay otras versiones"
            ):
                version_alta = extraer_version(ruta_version_alta)
                if version_alta != "No detectada" and version_alta != "Error":
                    match_alta = re.search(r"v?(\d+)", version_alta)
                    if match_alta:
                        version_alta_num = int(match_alta.group(1))
        except Exception as e:
            debug_print(f"Error al comparar versiones: {str(e)}")

        # Verificar si la versión más alta ya está abierta
        version_alta_ya_abierta = False
        if nombre_base in proyectos_abiertos_por_base and version_alta_num > 0:
            for proyecto_abierto in proyectos_abiertos_por_base[nombre_base]:
                if proyecto_abierto["version_num"] == version_alta_num:
                    version_alta_ya_abierta = True
                    debug_print(
                        f"La versión más alta v{version_alta_num} del proyecto {nombre_base} ya está abierta"
                    )
                    break

        # Solo incluir proyectos con versión más alta disponible QUE NO ESTÉ YA ABIERTA
        if (
            version_actual_num > 0
            and version_alta_num > 0
            and version_actual_num < version_alta_num
            and not version_alta_ya_abierta
        ):
            proyectos_con_version_alta.append(
                {
                    "proyecto": proyecto,
                    "nombre": nombre_interfaz,
                    "ruta_actual": ruta_disco,
                    "ruta_alta": ruta_version_alta,
                }
            )
            debug_print(
                f"Proyecto {nombre_interfaz} - Versión actual: v{version_actual_num}, Versión más alta disponible (no abierta): v{version_alta_num}"
            )

    # Si no hay proyectos con versiones más altas que no estén ya abiertas, no abrir la ventana
    if not proyectos_con_version_alta:
        debug_print(
            "No hay proyectos con versiones más altas que no estén ya abiertas. No se mostrará la ventana."
        )
        return

    # Verificar si ya existe una ventana abierta con el mismo nombre de objeto
    ventana_existente = buscar_ventana_existente("LGA_ProyectosAbertosDialog")

    if ventana_existente:
        # Si ya existe, mostrar su ID y activarla
        debug_print(f"Ya existe una ventana con ID: {ventana_existente.winId()}")
        debug_print(
            f"Usando ventana existente con nombre de objeto: {ventana_existente.objectName()}"
        )

        # Actualizar los datos de la ventana existente
        ventana_existente.actualizar_proyectos_con_datos(proyectos_con_version_alta)

        # Activar la ventana existente (traerla al frente)
        ventana_existente.setWindowState(
            ventana_existente.windowState() & ~Qt.WindowMinimized | Qt.WindowActive
        )
        ventana_existente.activateWindow()
        ventana_existente.raise_()
    else:
        # Si no existe, crear una nueva ventana
        global ventana_proyectos
        ventana_proyectos = ProyectosAbertosDialog(
            hiero.ui.mainWindow(), proyectos_con_version_alta
        )
        ventana_proyectos.show()  # Usar show() en lugar de exec_() para modo no modal


if __name__ == "__main__":
    main()
