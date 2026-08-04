> **Regla de documentacion**: este archivo es un checklist vivo de implementacion. No describe intenciones generales; describe entregables concretos y su estado.
> **Regla de documentacion**: cada item completado debe reflejar codigo real existente y probado. Si algo cambia, este checklist debe actualizarse.

# LGA NKS Playlist Panel Checklist

## Etapa 1 - Esqueleto y permisos

- [x] Crear el documento de checklist de implementacion.
- [x] Crear la subcarpeta `LGA_NKS_Playlist_Panel_py`.
- [x] Crear el archivo principal `LGA_NKS_Playlist_Panel.py`.
- [x] Mantener la convencion de encabezado con nombre, version y notas de version.
- [x] Implementar una utilidad de deteccion de `Master` basada en:
  - `config.secure` via `SecureConfig_Reader.py`
  - roles declarados en `SpecialUsers.cpp`
- [x] Probar con un `.py` temporario que el usuario actual se detecta correctamente como `Master`.
- [x] Borrar el `.py` temporario luego de la prueba.
- [x] Hacer que el panel no se cargue si el usuario actual no es `Master`.
- [x] Crear la UI base del panel con los botones en el orden acordado.
- [x] Respetar colores y look general alineados al `Flow Panel`.
- [x] Dejar botones con comportamiento placeholder por ahora.
- [x] Dejar `Rev Dir` mostrando mensaje `todavia no implementado`.

## Etapa 2 - Vendor check por accion

- [x] Implementar la funcion corta de validacion de timeline vendor dentro del panel.
- [x] Hacer que todas las acciones pasen primero por ese chequeo.
- [x] Mostrar mensaje con contexto si el timeline actual no es vendor.
- [x] Quitar `Shift+T` del `Playlist Panel` para evitar conflicto con el `Flow Panel`.

## Etapa 2b - Reutilizacion temporal del Flow Panel

- [x] Copiar a `LGA_NKS_Playlist_Panel_py` los scripts base necesarios del `Flow Panel`:
  - `LGA_NKS_Flow_Pull.py`
  - `LGA_NKS_Flow_Shot_info.py`
  - `LGA_NKS_ReviewPic.py`
  - `LGA_NKS_Flow_Push.py`
  - `LGA_NKS_Flow_Push_connector.py`
- [x] Conectar `Playlist Pull` para que, por ahora, ejecute el mismo flujo que `Flow Pull`.
- [x] Conectar `Shot Info` para que, por ahora, ejecute el mismo flujo que `Flow Shot Info`.
- [x] Conectar `Review Pic` para que, por ahora, ejecute el mismo flujo que `Review Pic`.
- [x] Conectar `Corrections` para que, por ahora, ejecute el mismo flujo que el push del `Flow Panel`.
- [x] Conectar `Rev Dir` para que, por ahora, ejecute el mismo flujo que el push del `Flow Panel`.
- [x] Conectar `Approved` para que, por ahora, ejecute el mismo flujo que el push del `Flow Panel`.
- [x] Mantener `Send Note` y `Show Playlist` en placeholder hasta su implementacion especifica.
- [x] Mantener esta etapa explicitamente documentada como transitoria, hasta reemplazar la logica Flow por la logica Playlist real.

## Etapa 3 - Playlist Pull

- [ ] Implementar seleccion de clips/timeline igual que `Flow Pull`.
- [ ] Resolver estado base desde `pipesync.db`.
- [ ] Calcular `ultima_actividad_playlist`.
- [ ] Definir y persistir el modelo de estado local en `pipesync_playlists.db`.
- [ ] Aplicar la regla final de colores:
  - `Corrections`
  - `Rev Lega`
  - `Approved`

## Etapa 4 - Shot Info

- [x] Reutilizar la UI base del `Shot Info` del `Flow Panel`.
- [x] Migrar `FlowPlaylist_Shot_info.py` al sistema de logging avanzado con `.log` propio por defecto.
- [x] Migrar tambien `LGA_NKS_Flow_Shot_info.py` al sistema de logging avanzado para mantener paridad con la base reutilizada.
- [x] Agregar logs de diagnostico en ambos `Shot Info` para dejar visibles:
  - `clip_name`
  - `file_path`
  - `base_name`
  - `project_name`/contexto de proyecto
  - `shot_code`
- [x] Hacer que `LGA_NKS_Flow_Shot_info.py` redirija automaticamente al `Shot Info` de playlist cuando se ejecuta sobre timeline vendor.
- [x] Priorizar primero el chequeo de `Playlist Panel` registrado y solo usar chequeo de `Master` como fallback para esa redireccion.
- [x] Hacer que `FlowPlaylist_Shot_info.py` resuelva shots vendor usando el proyecto real del timeline y no solo el proyecto parseado del filename.
- [x] Normalizar el nombre del proyecto abierto en Hiero al `project_name` real de PipeSync.
- [x] (v0.02) Priorizar el `project_name` extraido del segmento `VFX-NOMBRE` de la ruta del clip (`extract_project_name_from_path`) sobre el timeline normalizado y el parseado del filename, en Pull/Push/Push_connector/Shot_info del panel. Ver `Docu_ProjectName_Extraction.md`.
- [x] Validar el caso vendor `PROJA_2004_030`:
  - proyecto abierto `PROJALT_SUP_v004`
  - proyecto buscado en DB `PROJALT`
- [x] Documentar el mapeo real entre captura/UI y `pipesync_playlists.db` en un MD tecnico separado.
- [x] Mostrar `Descripcion Tarea` desde `pipesync.db`.
- [x] Mostrar `Descripcion Version` desde `pipesync_playlists.db`.
- [x] Mostrar notas, replies y attachments desde `pipesync_playlists.db`.
- [x] Resolver attachments de notas y replies por separado (`note_id` y `reply_id`).
- [x] Mostrar multiples apariciones de la misma version si pertenece a playlists distintas.
- [ ] Ajustar formato de fecha/hora para que coincida exactamente con el `Playlist Tab` de PipeSync.

## Etapa 5 - Review Pic y Send Note

- [ ] Crear cache propia de imagenes para el `Playlist Panel`.
- [ ] Reutilizar la logica funcional de `Review Pic`.
- [ ] Implementar la ventana previa de seleccion entre `New Note` y `Reply to #N`.
- [ ] Numerar notas y replies para seleccion visual.
- [ ] Reutilizar el dialogo de notas del `Flow Panel`.
- [ ] Reutilizar el checkbox para borrar imagenes cacheadas tras envio exitoso.

## Etapa 6 - Escrituras reales en Flow

- [ ] Hacer probes temporales para crear nota nueva.
- [ ] Hacer probes temporales para responder una nota.
- [ ] Hacer probes temporales para adjuntar imagenes.
- [ ] Validar conservacion de frame number.
- [ ] Leer lo escrito para verificarlo.
- [ ] Borrar lo escrito de prueba.
- [ ] Recién despues implementar codigo productivo.

## Etapa 7 - Corrections y Approve

- [ ] Implementar `Corrections` escribiendo en DB y en Flow.
- [ ] Hacer que `Corrections` saque de aprobado si corresponde.
- [ ] Guardar timestamp local del cambio de estado en playlist.
- [ ] Implementar `Approve` escribiendo en DB y en Flow.
- [ ] Reflejar el estado en task comp y en playlist.

## Etapa 8 - Show Playlist

- [ ] Investigar la URL correcta de apertura de playlist en browser.
- [ ] Implementar apertura directa si hay una sola playlist.
- [ ] Implementar selector si hay varias playlists.

## Etapa 9 - Refresh y pulido

- [ ] Analizar y copiar el flujo de refresh post escritura del `Flow Panel`.
- [ ] Revisar formato amigable de fechas/horas usando como referencia `Playlist Tab` de PipeSync.
- [ ] Verificar que el checklist y el plan sigan alineados.
