> **Regla de documentacion**: este archivo describe el plan vigente del tema. No es un changelog ni una bitacora temporal.
> **Regla de documentacion**: este archivo debe mantenerse alineado con el estado real del codigo y con las decisiones arquitectonicas ya tomadas.

# LGA NKS Playlist Panel Plan

## Objetivo general

Crear un panel de Hiero/Nuke Studio para trabajar reviews de playlists vendor desde el timeline, con una experiencia parecida al `Flow Panel`, pero usando como fuente principal la base `pipesync_playlists.db`.

El panel debe permitir:

- pull visual desde la DB local de playlists;
- consulta de info del shot;
- creacion de imagenes de review;
- envio de notas a la playlist a la que pertenece la version actual;
- aprobacion y desaprobacion de la version desde el timeline.

## Relacion con Flow Panel y PipeSync

- `PipeSync` sigue siendo la fuente de sincronizacion local.
- `pipesync.db` se usara solo para resolver la info del shot en el boton `Shot Info`.
- `pipesync_playlists.db` sera la fuente para:
  - detectar playlists;
  - obtener mensajes/notas/replies/attachments;
  - resolver aprobacion de version;
  - identificar la playlist elegida por el usuario cuando una version pertenezca a varias playlists.
- El `Playlist Panel` sera equivalente funcional al `Flow Panel`, pero orientado al dominio playlist/vendor en lugar del dominio task/shot del flujo normal.

## Reglas ya definidas

### Regla 1: el panel solo existe para usuarios Master

- El script del panel debe chequear al inicio si el usuario actual tiene permiso `Master` en PipeSync.
- Si no tiene permiso `Master`, el panel no debe cargarse.
- El script termina en ese punto, sin registrar el panel ni exponer UI parcial.

### Regla 2: el panel solo se usara para vendor playlists

- Por ahora el `Playlist Panel` se usara solo para playlists vendor.
- Esto debe quedar explicitado en el codigo y en la documentacion.
- Mas adelante se podra evaluar si conviene abrirlo tambien a playlists no vendor.

### Regla 3: deteccion de timeline vendor

- La deteccion debe seguir el mismo criterio funcional ya adoptado en PipeSync.
- Se compara `shot_code` contra el `project_name` del timeline.
- Si no coinciden, se considera que estamos en un timeline vendor.
- Esta logica debe usarse para habilitar o validar el flujo del panel.

### Regla 4: separacion de bases

- `pipesync.db` solo se usa para `Shot Info`.
- `pipesync_playlists.db` se usa para todo el resto del panel.
- No mezclar logica runtime de playlist con joins improvisados a `pipesync.db`, salvo la excepcion explicita del boton `Shot Info`.

### Regla 5: si una version pertenece a varias playlists, el usuario elige

- Cuando una version este presente en mas de una playlist, el panel debe pedir al usuario que elija.
- La eleccion debe mostrarse con:
  - nombre de playlist;
  - fecha de creacion de la playlist.
- La eleccion vale solo para la accion actual.
- No debe persistirse como contexto global del clip.

## Confirmaciones sobre el Flow Panel actual

Queda confirmado que el `Flow Panel` ya maneja comentarios y attachments de forma no lineal en `Shot Info`.

En `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Flow_Panel_py\LGA_NKS_Flow_Shot_info.py`:

- se consultan notas desde `version_notes`;
- se cargan `local_attachment_paths`;
- se renderizan thumbnails por comentario;
- no se filtran las notas con `from_playlist`, por lo que tambien se muestran comentarios provenientes de playlists cuando existen en `pipesync.db`.

Esto sirve como referencia UX para el nuevo panel, pero no implica reutilizar exactamente la misma fuente de datos.

## Fuente de datos prevista

### Desde `pipesync.db`

Solo para `Shot Info`:

- datos generales del shot;
- informacion historica ya visible hoy en el `Flow Panel`.

### Desde `pipesync_playlists.db`

Para el resto del panel:

- playlists asociadas a la version;
- notas de playlist;
- replies;
- attachments;
- estado de aprobacion;
- metadata de version dentro de playlist.

## Botones previstos del panel

La lista de botones debe respetar, en orden y color, una logica lo mas parecida posible al `Flow Panel`.

Orden actual acordado:

1. `Playlist Pull`
2. `Shot Info`
3. `Review Pic`
4. `Corrections`
5. `Send Note`
6. `Rev Dir`
7. `Approve`
8. `Show Playlist`

Colores esperados:

- `Playlist Pull`: mismo look oscuro que `Flow Pull`
- `Shot Info`: mismo look oscuro que `Shot Info` del `Flow Panel`
- `Review Pic`: mismo look oscuro que `Review Pic` del `Flow Panel`
- `Corrections`: mismo azul que `Corrections` del `Flow Panel`
- `Send Note`: boton oscuro, alineado visualmente al panel
- `Rev Dir`: mismo verde que `Rev Dir` del `Flow Panel`
- `Approve`: mismo verde que `Approved` del `Flow Panel`
- `Show Playlist`: boton oscuro nuevo, alineado visualmente al panel

Atajo de teclado:

- `Shift+T` queda reservado al `Shot Info` del `Flow Panel`.
- El `Playlist Panel` no debe registrar ese shortcut para evitar conflicto.
- En timeline vendor, cuando se ejecuta `Shot Info` desde el `Flow Panel`, ese flujo debe redirigir internamente al `Shot Info` del `Playlist Panel`.
- La redireccion debe activarse si:
  - estamos en timeline vendor; y
  - el `Playlist Panel` ya esta registrado/cargado, o en su defecto el usuario actual es `Master`.
- Se prioriza primero el chequeo de panel registrado por ser mas liviano en recursos.

### 1. Playlist Pull

Funcion esperada:

- leer desde `pipesync_playlists.db` la informacion de la version actual;
- determinar si la version pertenece a una o varias playlists;
- si hay mas de una, pedir eleccion al usuario;
- reflejar en el timeline el estado correspondiente del contexto playlist elegido.

Decision tomada:

- cuando el pull detecta cambios sobre clips, esos clips se pintan siempre con el color `Rev Lega`.
- el `Playlist Pull` debe verse y sentirse lo mas parecido posible al `Flow Pull`.

Pendiente:

- definir todas las fuentes que participa del `pull` cuando exista informacion cruzada entre `pipesync.db` y `pipesync_playlists.db`;
- el comportamiento debe copiar al `Flow Pull`:
  - click normal: opera sobre todo el timeline;
  - `Shift+Click`: opera solo sobre el shot/clip seleccionado.

### 2. Shot Info

Funcion esperada:

- usar la misma fuente que el `Flow Panel` actual para mostrar informacion del shot;
- esta es la unica parte del panel que consultara `pipesync.db`.

Estado actual implementado:

- `FlowPlaylist_Shot_info.py` ya tiene logging avanzado con `.log` propio por defecto;
- el lookup del shot para contexto vendor ya no usa solo el `project_name` parseado del filename;
- desde v0.02, primero extrae el `project_name` del segmento `VFX-NOMBRE` de la ruta del clip;
- si no hay ruta valida, resuelve el proyecto del timeline activo y lo normaliza al `project_name` real de PipeSync;
- como ultimo recurso cae al `project_name` parseado del filename.
- el `Shot Info` ya fue migrado a modelo hibrido real:
  - `Descripcion Tarea` desde `pipesync.db`
  - `Descripcion Version`, notas, replies y attachments desde `pipesync_playlists.db`
  - multiples apariciones del mismo shot/version en playlists distintas

Ejemplo validado:

- proyecto abierto en Hiero: `PROJALT_SUP_v004`
- proyecto real en `pipesync.db`: `PROJALT`
- shot buscado: `PROJA_2004_030`

Regla actual de busqueda (desde v0.02):

- `project_name` desde el path (`VFX-NOMBRE`) es el **primario** (`extract_project_name_from_path`);
- `parsed_project_name` se sigue registrando en el log como referencia;
- `timeline_project_name` se obtiene desde la secuencia activa;
- `normalized_timeline_project_name` se deriva desde el nombre del proyecto abierto;
- `search_project_name` usa el valor del path; si no hay ruta valida, cae al normalizado del timeline y, en ultimo caso, al parseado del filename.
- ver `docs/Docu_ProjectName_Extraction.md`.

Logging requerido:

- el log de `Shot Info` de playlist debe mostrar explicitamente:
  - `parsed_project_name`
  - `timeline_project_name`
  - `normalized_timeline_project_name`
  - `search_project_name`
  - `shot_code`
- si falla el lookup, el warning debe dejar visibles esos mismos valores para diagnostico.

Documentacion tecnica complementaria:

- ver [LGA_NKS_Playlist_ShotInfo_Data_Mapping.md](C:/Users/leg4-pc/.nuke/Python/Startup/docs/LGA_NKS_Playlist_ShotInfo_Data_Mapping.md)
- ese documento deja asentado:
  - que data real existe hoy en `pipesync_playlists.db`
  - como se mapean notas/replies/attachments
  - por que los attachments de replies requieren lookup por `reply_id`
  - que no hace falta ampliar schema para la lectura del `Shot Info`

Redireccion desde `Flow Shot Info`:

- `LGA_NKS_Flow_Shot_info.py` debe detectar si el timeline actual es vendor.
- Si lo es, no debe mostrar el lookup normal del `Flow Panel`.
- En ese caso debe ejecutar `LGA_NKS_FlowPlaylist_Shot_info.py`.
- Esta decision debe quedar loggeada en el `.log` del `Flow Shot Info`.

Pendiente:

- definir si la ventana sera reutilizada tal cual o si habra una variante adaptada al panel playlist;
- revisar si conviene agregar avatares, mas metadata visual o un formato de fecha exactamente igual al `Playlist Tab`;
- validar visualmente en Hiero si hay que ajustar spacing/indentacion para replies y attachments.

### 3. Review Pic

Funcion esperada:

- crear snapshots del viewer con numero de frame;
- dejarlos listos para adjuntarse luego a una nota de playlist.

Decision tomada:

- el `Playlist Panel` tendra una cache de imagenes separada del `Flow Panel`;
- el funcionamiento sera el mismo que en `Flow Panel`.

### 4. Send Note

Funcion esperada:

- abrir un dialogo para escribir una nota;
- adjuntar las review pics guardadas;
- enviar la nota a la playlist elegida a la que pertenece la version actual.

Flujo acordado:

- antes de abrir el editor de nota, el boton debe analizar si ya existen notas para esa version dentro de la playlist elegida;
- si existen, debe abrirse primero una ventana visualmente equivalente a `Shot Info`;
- esa ventana debe permitir elegir entre:
  - responder a una nota existente;
  - crear una nota nueva al final del thread, sin ser reply.
- luego de esa eleccion, se abre la ventana de notas identica a la del `Flow Panel`.
- el sistema de imagenes debe ser igual al de `Flow Panel`, pero usando cache separada del `Playlist Panel`.
- la numeracion de elementos debe ayudar a elegir facilmente el target:
  - numerar cada nota;
  - numerar cada reply.
- no existe reply del reply:
  - todas las respuestas cuelgan de una nota principal;
  - una nota principal puede tener uno o varios replies.

Pendiente:

- validar contra Flow real el endpoint/campo exacto para crear una nota nueva en contexto playlist;
- validar contra Flow real el endpoint/campo exacto para responder a una nota existente;
- definir exactamente como se selecciona una nota previa cuando hay multiples notas y replies;
- definir si el usuario puede borrar individualmente imagenes antes del envio, igual que en `Flow Push`.

### 5. Corrections

Funcion esperada:

- cambiar el color del clip al mismo azul que `Corrections` en el `Flow Panel`;
- escribir estado en DB local;
- escribir estado en Flow;
- si el plano estaba aprobado, al ejecutar `Corrections` debe salir del estado aprobado.

Decision tomada:

- no existira un boton `Unapprove` separado;
- `Corrections` asume tambien el comportamiento operativo de sacar al plano de aprobado cuando corresponda.
- la intencion funcional es que este panel escriba en DB y en Flow, tal como el `Flow Panel`.

Decision pendiente importante:

- definir si `Corrections` debe escribirse:
  - solo en `pipesync_playlists.db`;
  - en `pipesync_playlists.db` y tambien en `pipesync.db`;
  - y como se prioriza cada fuente luego en los pulls.

Nuevas decisiones:

- `Corrections` debe escribir en ambas DBs;
- ademas, igual que en `Flow Panel`, debe cambiar el estado del shot/task comp en Flow;
- en `pipesync_playlists.db` conviene guardar tambien un timestamp del cambio de estado.

Nota muy importante:

- aun queda por definir la regla final para saber cual es el estado actual del shot/version al hacer `Playlist Pull`, especialmente en casos donde:
  - el proyecto de Hiero es viejo;
  - el timeline no fue guardado luego del ultimo pull;
  - los colores/versiones visibles del timeline quedaron desactualizados.
- este punto queda marcado como una decision critica pendiente.

### 6. Rev Dir

Funcion esperada:

- por ahora no hace nada.

Decision tomada:

- el boton existe desde el arranque para mantener la estructura del panel alineada al `Flow Panel`;
- la logica compleja se agregara mas adelante.
- visualmente debe ocupar su lugar real en el panel desde el principio.

### 7. Approve

Funcion esperada:

- aprobar la version;
- cambiar el color del clip a verde.

Decision tomada:

- `Approve` no requiere confirmacion previa.

Pendiente:

- validar contra Flow real cual es la operacion remota exacta de aprobacion;
- definir si la aprobacion se hace sobre la version global o sobre el contexto de version dentro de playlist.

### 8. Show Playlist

Funcion esperada:

- si la version pertenece a mas de una playlist, pedir al usuario cual abrir;
- abrir la playlist elegida en el browser.

Decision tomada:

- si hay una sola playlist asociada, se abre directamente;
- si hay mas de una, se pregunta cual.

Pendiente:

- validar la URL exacta a construir/abrir;
- definir si la seleccion de playlist usa exactamente el mismo selector que `Send Note` y `Playlist Pull`.
- antes de implementarlo hay que hacer pruebas especificas para descubrir la URL correcta de apertura en browser, porque no es simple.

### Boton descartado: Unapprove

- `Unapprove` no existira como boton separado.
- Su efecto operativo queda absorbido por `Corrections` cuando el plano este aprobado.

## Diferencias importantes respecto del Flow Panel

### 1. Dominio playlist en vez de task

El `Flow Panel` trabaja principalmente contra task/version del flujo normal.

El `Playlist Panel` debe trabajar contra:

- `version_sg_id`;
- una playlist elegida;
- el contexto de review de esa version dentro de esa playlist.

Eso obliga a resolver el contexto antes de permitir acciones de escritura.

### 2. Una version puede estar en varias playlists

Esto no suele ser un problema equivalente en el `Flow Panel`.

En el `Playlist Panel` si una misma version aparece en varias playlists:

- el usuario debe elegir explicitamente;
- todas las acciones posteriores deben quedar atadas a esa eleccion;
- hay que definir si la eleccion vale solo para esa accion o para toda la sesion del panel mientras el clip siga activo.

### 3. Vendor-only

El panel arranca con un scope mas acotado:

- solo para usuarios `Master`;
- solo para playlists vendor;
- solo en timelines detectados como vendor.

### 4. Aprobacion con significado funcional propio

En este panel la aprobacion no es solo "poner color verde".

Debe existir una correspondencia entre:

- estado real en Flow;
- estado reflejado en `pipesync_playlists.db`;
- color del clip en Hiero.

### 5. Validacion previa de timeline vendor por accion

- Antes de ejecutar cualquier accion, se correra un script Python que valide si el timeline actual es vendor.
- Si no lo es:
  - se muestra un mensaje;
  - la accion no se ejecuta.
- Esta validacion es independiente del chequeo de permiso `Master` al cargar el panel.
- La implementacion puede vivir como una funcion corta dentro del mismo Python del panel, no hace falta que sea un script externo.

### 6. Probes obligatorios antes de implementar escrituras reales

- Antes de implementar de forma productiva cualquier escritura sobre Flow para playlists, se deben hacer pruebas reales con `.py` temporales.
- El flujo obligatorio de validacion sera:
  - escribir;
  - leer para comprobar;
  - borrar lo escrito de prueba.
- Esto aplica a:
  - crear notas nuevas;
  - responder notas;
  - adjuntar imagenes;
  - subir imagenes con numero de frame;
  - aprobar;
  - sacar de aprobado si corresponde.
- Estos probes temporales deben hacerse antes de tocar el codigo definitivo del panel.
- La validacion tiene que comprobar tanto escritura como lectura posterior y limpieza final del dato de prueba.

## Riesgos ya detectados

### Riesgo 1: escribir en la playlist equivocada

Si una version pertenece a varias playlists y no se fija bien el contexto, una nota o una aprobacion pueden terminar en la playlist incorrecta.

### Riesgo 2: asumir una API de aprobacion que no este validada

La DB ya guarda `client_approved_at` y `client_approved_by`, pero aun no esta validado el mecanismo exacto para escribir ese estado desde el panel.

### Riesgo 3: mezclar demasiado con la logica del Flow Panel

Aunque la UX sea parecida, el dominio es distinto. Reutilizar componentes visuales es razonable; reutilizar sin revisar la logica de push puede generar errores conceptuales.

### Riesgo 4: depender de datos que no esten en `pipesync_playlists.db`

Si el panel necesita informacion adicional para operar, lo correcto sera extender:

- `create_database_playlists.py`;
- `get_Flow_playlists.py`;
- la documentacion de schema.

No resolverlo con dependencias ocultas a otras fuentes en runtime.

## Puntos pendientes de definir

### Contexto y seleccion

- que pasa si no hay playlists asociadas a la version.

### Pull visual

- si el pull debe leer aprobacion, correcciones, descripcion de version, o una combinacion de esos estados.
- como se resuelven conflictos si `pipesync.db` y `pipesync_playlists.db` contienen informacion util pero no identica.
- como influye el hecho de que `Corrections` podria terminar escribiendose tambien en `pipesync.db`.
- este bloque forma parte del mismo problema mayor:
  - como reconstruir el estado actual real del shot/version al hacer pull, incluso si el timeline local de Hiero esta viejo o no fue guardado luego de cambios previos.
- posible direccion a evaluar mas adelante:
  - usar siempre el estado de la task comp del shot como guia principal;
  - combinar eso con estado playlist;
  - o definir una prioridad fija entre ambas fuentes.

### Notas

- si se permiten multiples imagenes como hoy.
- si al enviar nota se limpian automaticamente las imagenes cacheadas.
- si la respuesta puede apuntar solo a una nota principal o tambien a un reply existente.
- como se numeran visualmente las notas y replies para la seleccion.
- aunque se numeren replies, sigue siendo importante validar si Flow permite una semantica real de respuesta a reply o si operativamente toda respuesta cae bajo la nota principal.

### Aprobacion

- si `Approve` puede convivir con una nota opcional.
- como se representa en DB el hecho de que `Corrections` saco al plano de aprobado.
- como se refleja en `pipesync.db` y `pipesync_playlists.db` para evitar estados cruzados inconsistentes.

### UX y validaciones

- el mensaje cuando el timeline actual no es vendor debe incluir contexto.
- que mensaje se muestra si el usuario es `Master` pero la version no pertenece a ninguna playlist vendor.
- si el panel debe ocultar o deshabilitar botones segun contexto.

Decision tomada:

- si no hay playlist asociada para la version actual, se mostrara un mensaje con contexto que incluya:
  - shot;
  - version;
  - proyecto/timeline detectado.

### Persistencia y refresh

- aunque por ahora no se implementara, queda pendiente definir como refrescar `pipesync_playlists.db` o la UI luego de escribir notas/aprobaciones para no quedar con estado stale.

### Shot Info del Playlist Panel

- la ventana tendra estetica y UI identicas a la existente en `Flow Panel`;
- el bloque superior debe mostrar:
  - `Descripcion Tarea: ...` leida desde `pipesync.db`;
  - `Descripcion Version: ...` leida desde `pipesync_playlists.db`.
- debajo de eso:
  - notas;
  - replies;
  - attachments;
  - todo leido desde `pipesync_playlists.db`.
- visualmente debe ser identica a la ventana del `Flow Panel`, salvo por esa adaptacion del bloque de descripcion.
- la razon de esta mezcla es que en playlists no existe la descripcion de tarea del shot como en el flujo normal, pero si existe una descripcion propia de version dentro de playlist.

Ejemplo funcional esperado:

En `Flow Panel`, el caso actual puede verse asi:

```text
PROJA_2029A_050 | Guadalupe Barbara

Description: Agregar efecto lluvia.

v004 | Guadalupe Barbara
ajuste direccion lluvia

Juan Olivares: super! paso a lega

Sebas Romano: Paso a Juano para validar planteo.

Guadalupe Barbara: ajuste direccion lluvia

v003 | Guadalupe Barbara
voy subiendo progreso de lluvia direccionada hacia el centro donde esta moria, como en la refe, con algunos gotas a las que les den mas la luz y tengan destellos

Sebas Romano: Ajustemos, en principio, direccion de lluvia para que matchee con plate.
```

En `Playlist Panel`, la logica esperada sera mas rica:

```text
PROJA_2029A_050

Descripcion Tarea: Agregar efecto lluvia.

v004 | Subida por TAL | ayer 4:31pm | playlist "nombre de playlist"
Descripcion de Version: ajuste direccion lluvia

Comentario Juan Olivares: super! paso a lega
    Sebas Romano: Paso a Juano para validar planteo.

v004 | Subida por TAL | ayer 3:31pm | playlist "nombre de playlist"
Descripcion de Version: ajuste direccion lluvia

Comentario Guadalupe Barbara: ajuste direccion lluvia

v003 | Subida por TAL | miercoles 4:40am | playlist "TAL"
...
```

Reglas implicitas de este ejemplo:

- en vendor playlists no deberia mostrarse assignee del shot como en el ejemplo del `Flow Panel`;
- una misma `version number` puede aparecer varias veces si pertenece a playlists distintas o a playlists de distinta fecha;
- el orden visual se define por contexto de playlist/fecha, no solo por numero de version;
- replies deben verse indentados;
- visualmente la ventana sigue siendo la misma del `Flow Panel`, pero con esta estructura de datos.

Decision tomada:

- en `Shot Info` se deben mostrar todas las apariciones relevantes de la version, incluso si el mismo numero de version aparece en playlists distintas;
- por lo tanto, la vista no queda limitada solo a la playlist elegida para la accion actual;
- el orden debe permitir ver primero la aparicion mas reciente y luego las mas viejas, aunque compartan numero de version.

### Seleccion de notas/replies para Send Note

- la ventana previa a `Send Note` debe mostrar todo:
  - descripcion;
  - notas;
  - replies;
  - attachments.
- se numeraran las notas y replies para que el usuario pueda elegir facilmente el target.
- abajo habra una opcion para:
  - `New Note`;
  - `Reply to #N`.
- `#N` debe apuntar solo a una nota principal.
- aunque visualmente los replies tambien esten numerados, no existe reply de reply y no se debe modelar como tal.

## Decisiones ya tomadas que deben respetarse

### Escritura en DB y en Flow

- la intencion del panel es escribir en DB y en Flow, igual que el `Flow Panel`;
- esto aplica al menos a:
  - `Corrections`;
  - `Approve`;
  - futuras escrituras de `Rev Dir`;
  - `Send Note`.
- en algunos casos todavia resta validar exactamente que se escribe en cada DB y con que prioridad se relee luego.

### Vendor check por accion

- cada accion debe empezar validando si el timeline actual es vendor;
- si no pasa el check:
  - se muestra un mensaje con contexto;
  - no se ejecuta nada mas.
- esta validacion puede implementarse como una funcion corta dentro del mismo Python del panel;
- no hace falta un script externo.

### Notas y replies en playlists

- en playlists puede existir una descripcion inicial de la version;
- despues puede haber notas;
- cada nota puede tener uno o varios replies;
- no existe reply de reply;
- esa estructura debe respetarse tanto en lectura como al plantear la UX de `Send Note`.

### Flujo de imagenes identico al Flow Panel

- `Review Pic` y `Send Note` deben copiar el mismo flujo funcional del `Flow Panel`;
- el dialogo de envio de nota debe incluir el mismo checkbox para borrar las imagenes cacheadas tras un envio exitoso;
- la implementacion deberia copiar esa logica del `Flow Panel` y adaptarla al cache propio del `Playlist Panel`.

### Approve

- por ahora `Approve` no abre nota opcional;
- debe cambiar tanto el estado de la task comp en `pipesync.db` / Flow, como el estado correspondiente en playlist.

### Rev Dir

- por ahora debe mostrar mensaje `todavia no implementado`;
- a futuro, en lineas generales, deberia servir para crear una nueva playlist subiendo este MOV y enviarla a direccion.

### Fechas y horas

- en selectores y vistas debe mostrarse fecha y hora completa;
- el formato tiene que ser amigable para el usuario;
- queda pendiente revisar como lo hace el `Playlist Tab` de PipeSync para reutilizar exactamente esa misma logica visual.

### Refresh post escritura

- el comportamiento posterior a escribir debe intentar ser identico al `Flow Panel`;
- queda pendiente analizar y copiar ese flujo.

## Preguntas y dudas pendientes

Esta seccion debe mantenerse siempre actualizada. Cuando una duda se resuelve, debe borrarse de aqui.

1. Regla final de prioridad para reconstruir el estado real en `Playlist Pull`.
   Hay que definir como se determina el estado actual del shot/version cuando pueden existir datos en:
   - `pipesync.db`
   - `pipesync_playlists.db`
   - Flow
   y el timeline de Hiero puede estar desactualizado o no guardado.

2. Fuente principal para guiarnos en el pull.
   Queda por definir si conviene:
   - usar siempre el estado de la task comp como guia principal;
   - usar siempre el estado playlist;
   - o combinar ambas fuentes con una prioridad fija.

3. Modelo de estado local en `pipesync_playlists.db`.
   Hay que definir si conviene:
   - un solo campo tipo `local_review_state`;
   - varios campos separados;
   - y como guardar el timestamp asociado al cambio.

4. Exactamente que compara `Playlist Pull` para considerar que hay cambios.
   Falta definir si compara:
   - aprobacion;
   - correcciones;
   - descripcion de version;
   - notas nuevas;
   - una combinacion de varias cosas.

5. Mensaje de error/contexto cuando no hay playlist asociada.
   Falta decidir el contenido exacto del mensaje.

6. `Shot Info`: alcance del contexto playlist.
   Falta definir si la vista muestra:
   - todas las playlists asociadas a la version;
   - o solo la playlist elegida para la accion actual.

7. Escrituras reales de notas/replies/attachments en Flow.
   Aunque ya esta definido que se haran probes temporales, todavia falta validar:
   - crear nota nueva;
   - responder nota;
   - adjuntar imagenes;
   - conservar numero de frame;
   - leer lo escrito;
   - borrar lo escrito de prueba.
   Esta tarea queda explicitamente asignada a la etapa de investigacion previa a la implementacion, y la resolvere yo con `.py` temporales de prueba antes de tocar codigo productivo.

8. URL final de `Show Playlist`.
   Falta descubrir la URL correcta y estable para abrir una playlist en browser.

## Criterio temporal acordado para vendor playlists

Para este dominio puntual de vendor playlists, se considera valido usar `tasks.updated_at` de `pipesync.db` como referencia temporal suficiente para el estado de la task comp.

Motivo:

- en estos proyectos las tasks no se usan como flujo operativo diario;
- no se tocan para trabajo artistico normal;
- se crean y mantienen principalmente para:
  - descripcion del shot/tarea;
  - estado;
- por lo tanto, para este caso, `tasks.updated_at` se considera una aproximacion suficiente al "ultimo cambio relevante de estado".

Consecuencia para el futuro `Playlist Pull`:

- se podra comparar `tasks.updated_at` contra actividad de playlist mas reciente;
- si hubo actividad de playlist posterior al `updated_at` de la task comp, eso podra forzar el clip a `Rev Lega`;
- si no la hubo, el clip podra respetar el estado base derivado de la task comp (`Corrections` o `Approved`).

Nota:

- esta decision vale para este flujo vendor y con las reglas actuales de uso;
- si en el futuro las tasks vendor empiezan a usarse para mas operaciones, este supuesto debera revisarse.

## Definicion acordada de `ultima_actividad_playlist`

Para una version dada en contexto playlist vendor, `ultima_actividad_playlist` se define como el timestamp maximo relevante de review asociado a esa version.

Debe calcularse como el maximo entre:

1. `playlists.created_at_flow`
   - siempre cuenta;
   - si una version aparece en una playlist nueva, eso ya se considera actividad de review.

2. `playlist_notes.created_at_flow`
   - una nota nueva cuenta como actividad.

3. `playlist_note_replies.created_at_flow`
   - un reply nuevo tambien cuenta como actividad.

4. `playlist_versions.client_approved_at`
   - una aprobacion en playlist cuenta como actividad.

5. timestamp local del ultimo cambio de estado hecho desde el panel
   - por ejemplo un campo tipo `local_review_state_changed_at`;
   - cambios como `Corrections` y `Approve` deben actualizarlo.

No deben contar como `ultima_actividad_playlist`:

- refresh tecnicos;
- descarga de media;
- descarga de thumbs;
- apertura de playlist en browser;
- cambios internos de sync sin significado de review.

Consecuencia funcional:

- si `ultima_actividad_playlist > tasks.updated_at`, el clip debe forzarse a `Rev Lega`;
- si no, el clip respeta el estado base derivado de la task comp.

## Regla acordada de colores del Playlist Pull

El `Playlist Pull` debe terminar pintando el clip con uno de estos tres colores:

- `Corrections`
- `Rev Lega`
- `Approved`

### Estado base

Primero se toma el estado base desde `pipesync.db`, igual que el `Flow Pull` actual, usando la task comp del shot.

Mapeo base esperado:

- `corr` -> `Corrections`
- estados approved-ish (`apr`, `check`, y equivalentes) -> `Approved`

### Override por actividad playlist

Luego se compara:

- `tasks.updated_at`
- `ultima_actividad_playlist`

Si `ultima_actividad_playlist > tasks.updated_at`:

- el color final del clip pasa a `Rev Lega`.

Si no:

- el clip conserva el color derivado del estado base.

## Enfoque de implementacion por etapas

Este panel no debe implementarse de una sola vez. Se trabajara por etapas pequenas, verificables y comparables contra este documento.

### Primer paso propuesto

El primer paso recomendado es:

- crear el `.py` base del `Playlist Panel`;
- crear la UI del panel;
- crear todos los botones en el orden final;
- dejar los botones sin logica real por ahora;
- antes de exponer/cargar el panel, validar que el usuario actual de esta computadora puede detectarse correctamente como `Master`.

Motivo:

- permite validar el esqueleto del panel y su lugar en Hiero;
- obliga a resolver primero el chequeo de permisos, que es una condicion fundacional;
- evita mezclar desde el arranque UI, DB, Flow y escritura remota.

### Validacion previa obligatoria del primer paso

Antes de dar por terminada esta primera etapa, debe quedar probado que:

- el codigo puede detectar correctamente si el usuario actual es `Master`;
- en esta maquina actual el resultado debe ser positivo, porque el usuario actual si es `Master`;
- si el usuario no fuera `Master`, el panel no deberia cargarse.

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Flow_Panel.py`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Flow_Panel_py\LGA_NKS_Flow_Shot_info.py`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Flow_Panel_py\LGA_NKS_Flow_Push.py`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\Docu_Logging_System.md`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\Docu_Logica_Nombres_Tracks.md`
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\Docu_Metodos_Seleccion_Clip.md`
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_DB_Playlist.md`
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_Tab_Playlist.md`
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_Tab_Playlist_Plan.md`
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_User_Permisos.md`
- `C:\Portable\LGA_PipeSync_2\Docs\Doc_Flow_Sync.md`
