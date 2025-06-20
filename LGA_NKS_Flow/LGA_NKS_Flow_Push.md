# LGA_NKS_Flow_Push

Este script Python, `LGA_NKS_Flow_Push.py`, está diseñado para automatizar la gestión de estados de tareas y versiones dentro de ShotGrid (anteriormente conocido como Flow) para proyectos relacionados con Nuke y Hiero. Su propósito principal es mantener la información de los proyectos actualizada y sincronizada entre ShotGrid y una base de datos SQLite local.

## Funcionalidades Principales:

*   **Actualización de Estados en ShotGrid:** Permite cambiar el estado de las tareas de Nuke/Hiero en ShotGrid, reflejando el progreso del trabajo.
*   **Sincronización con Base de Datos Local:** Mantiene una base de datos SQLite local (`pipesync.db`) sincronizada con los cambios realizados en ShotGrid, asegurando que la información esté disponible y accesible localmente.
*   **Gestión de Versiones:** Identifica y trabaja con las versiones de los `comps` (composiciones) de Nuke/Hiero, permitiendo actualizar sus estados.
*   **Notas para Versiones:** En ciertos estados específicos, el script abre una pequeña ventana de diálogo (`Input Dialog`) para que el usuario pueda introducir una nota o comentario. Esta nota se envía a ShotGrid y se asocia a la versión correspondiente, proporcionando un registro claro de los cambios o las razones detrás de una actualización de estado.
*   **Integración con ReviewPic:** El diálogo de notas ahora incluye automáticamente thumbnails de las imágenes de review capturadas previamente con el script `LGA_NKS_ReviewPic.py`, facilitando la referencia visual durante el proceso de revisión.

## Estados que Solicitan una Nota:

La ventana para introducir una nota se activa cuando el estado de la tarea se cambia a uno de los siguientes:

*   **"Corrections"** (que se traduce a `corr` en ShotGrid)
*   **"Corrs_Lega"** (que se traduce a `revleg` en ShotGrid)
*   **"Rev_Dir"** (que se traduce a `rev_di` en ShotGrid)
*   **"Rev_Lega"** (que se traduce a `revleg` en ShotGrid)
*   **"Rev_Hold"** (que se traduce a `revhld` en ShotGrid)

Este mecanismo asegura que, para estados que a menudo requieren aclaraciones o retroalimentación, se pueda adjuntar fácilmente un mensaje relevante.

## Integración con ReviewPic:

Cuando se abre el diálogo para introducir notas, el script automáticamente:

1. **Busca Imágenes de Review:** Examina la carpeta `ReviewPic_Cache` (ubicada en el mismo directorio que el script) buscando imágenes correspondientes al shot y versión actual usando la función `find_review_images()`.

2. **Muestra Thumbnails:** Si encuentra imágenes, las muestra como thumbnails de 150px de ancho debajo del área de texto de notas, en un área scrolleable implementada en la clase `InputDialog`.

3. **Información de Frame:** Cada thumbnail muestra el número de frame correspondiente alineado a la izquierda debajo de la imagen, extraído mediante `extract_frame_number_from_filename()`.

4. **Ajuste Automático de Ventana:** El ancho de la ventana se ajusta automáticamente para acomodar los thumbnails, con un mínimo del tamaño actual y un máximo de 1500px usando `adjust_window_size()`.

5. **Referencia Visual:** Los thumbnails incluyen tooltips que muestran el nombre del archivo al pasar el mouse, proporcionando una referencia visual rápida de las imágenes capturadas durante el proceso de review.

6. **Adjuntar a ShotGrid:** Las imágenes se adjuntan automáticamente a la nota en ShotGrid mediante `attach_images_to_note()` usando upload directo a Note con la convención de nombres `annot_version_<version_id>.<frame_number>.jpg` para que aparezcan con números de frame en la interfaz de ShotGrid.

7. **Opción de Limpieza:** Un checkbox "Delete all saved review images from disk" (marcado por defecto) permite al usuario elegir si borrar automáticamente toda la carpeta `ReviewPic_Cache` después de un envío exitoso únicamente.

8. **Organización Automática:** Las imágenes se organizan automáticamente por carpetas que siguen el patrón `{proyecto}_{secuencia}_{shot}_{task}_v{version}`, manteniéndose sincronizadas con el flujo de trabajo de revisión.

### Funciones Clave:
- **`find_review_images(base_name)`**: Localiza imágenes en `Python/Startup/LGA_NKS_Flow/ReviewPic_Cache/`
- **`attach_images_to_note(note_id, version_id, image_paths)`**: Sube imágenes a ShotGrid con números de frame
- **`extract_frame_number_from_path(image_path)`**: Extrae números de frame de nombres de archivo
- **`delete_review_pic_cache()`**: Borra el caché solo si la operación fue exitosa

Esta integración permite a los usuarios revisar visualmente las imágenes capturadas previamente mientras escriben sus notas de revisión, adjuntarlas automáticamente a ShotGrid con información de frame, y opcionalmente limpiar el caché local después del envío exitoso.
