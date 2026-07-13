"""
____________________________________________________________________

  LGA_NKS_SnapShot v0.62 | Lega

  Crea un snapshot de la imagen actual del viewer y lo copia al portapapeles

  v0.62: Shift+Click abre el snapshot en ShareX ImageEditor LGA sin crear archivos.
  v0.61: Se tiene en cuenta el pixel aspect ratio (PAR) del formato. El crop ahora se
         hace contra el DISPLAY aspect (storage * PAR) en lugar del storage aspect,
         porque viewer.image() ya entrega la imagen con el PAR aplicado. Antes, en
         timelines con PAR != 1, se recortaban los lados de la imagen.
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import os
import subprocess
import sys
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore

DEBUG = False
SaveToFile = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def crop_to_aspect_ratio(qimage, target_aspect):
    width = qimage.width()
    height = qimage.height()

    current_aspect = width / height

    if current_aspect > target_aspect:
        new_width = int(height * target_aspect)
        offset_x = int((width - new_width) / 2)
        rect = QtCore.QRect(offset_x, 0, new_width, height)
        cropped = qimage.copy(rect)
        return cropped
    else:
        new_height = int(width / target_aspect)
        offset_y = int((height - new_height) / 2)
        rect = QtCore.QRect(0, offset_y, width, new_height)
        cropped = qimage.copy(rect)
        return cropped


def open_in_image_editor(qimage):
    """Abre la captura en ShareX ImageEditor LGA sin generar un archivo temporal."""
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    app.clipboard().setImage(qimage)

    editor_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "LGA_NKS_Flow_Panel_py",
            "ShareX_ImageEditor_LGA",
            "ShareX_ImageEditor_LGA.exe",
        )
    )
    if not os.path.isfile(editor_path):
        raise FileNotFoundError(f"No se encontro ShareX ImageEditor LGA: {editor_path}")

    if sys.platform != "win32":
        raise RuntimeError("ShareX ImageEditor LGA solo esta disponible en Windows.")

    subprocess.Popen([editor_path, "--clipboard"])


def main(open_in_editor=False):
    output_path = r"T:\Borrame\snapshot.jpg"

    viewer = hiero.ui.currentViewer()
    if not viewer:
        raise Exception("No active viewer")

    qimage = viewer.image()
    if qimage is None or qimage.isNull():
        raise Exception("viewer.image() devolvió None o imagen nula")

    # Obtener la secuencia activa y su relacion de aspecto
    sequence = hiero.ui.activeSequence()
    if sequence is None:
        debug_print("No hay ninguna secuencia activa, usando 16:9 por defecto.")
        target_aspect = 16 / 9
    else:
        format = sequence.format()
        width = format.width()
        height = format.height()
        pixel_aspect = format.pixelAspect()
        # El viewer.image() ya entrega la imagen con el PAR aplicado (proporciones de
        # display), por lo que el crop debe hacerse contra el DISPLAY aspect ratio
        # (storage * PAR). Si se croppeara contra el storage aspect, se recortarian
        # los lados de la imagen (canvas muy chico en X) en timelines con PAR != 1.
        target_aspect = (width / height) * pixel_aspect
        debug_print(
            f"Relación de aspecto de la secuencia: {width} x {height} "
            f"(storage {width / height:.2f}, PAR {pixel_aspect:.2f}, "
            f"display {target_aspect:.2f})"
        )

    # Aplicar crop
    qimage_cropped = crop_to_aspect_ratio(qimage, target_aspect)

    debug_print(
        "Snapshot size (cropped):", qimage_cropped.width(), "×", qimage_cropped.height()
    )

    if SaveToFile:
        debug_print("Ruta de salida:", output_path)

        output_dir = os.path.dirname(output_path)
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        ok = qimage_cropped.save(output_path, "JPEG")
        debug_print("qimage.save result:", ok)

        if ok and os.path.exists(output_path):
            debug_print("✅ Archivo creado:", output_path)
        else:
            debug_print("❌ No se pudo crear el archivo.")

    if open_in_editor:
        open_in_image_editor(qimage_cropped)
        debug_print("Imagen abierta en ShareX ImageEditor LGA.")
        return

    # Copiar al portapapeles
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    clipboard = app.clipboard()
    clipboard.setImage(qimage_cropped)

    debug_print("✅ Imagen (cropeada) copiada al portapapeles.")


# --- Main Execution ---
if __name__ == "__main__":
    # Necesario para ejecucion standalone fuera de Nuke
    main()
