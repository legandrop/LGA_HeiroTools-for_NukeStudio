> **Regla de documentacion**: este archivo recopila aprendizajes sobre soft
> effects custom (gizmos en el timeline) de Hiero/Nuke Studio. No es un
> historial ni changelog; cada seccion describe un problema concreto, las
> opciones probadas y la solucion ganadora. Nacio del desarrollo de
> LGA_BurnIn (ago 2026), la primera herramienta del pack que registra un
> soft effect propio.

# Aprendizajes — Soft Effects custom (gizmos) en Hiero/Nuke Studio

Un "soft effect" del timeline es un nodo de Nuke con render GPU. Un soft
effect custom es un **gizmo** (Group serializado como `.gizmo`) registrado
en el menu Effects. Todo lo de aca abajo se midio en Nuke Studio 17.0v4
sobre Windows; las citas de doc oficial estan verificadas.

---

## Registro de un soft effect custom

Mecanismo oficial (ejemplo en
`<install>\pythonextensions\site-packages\hiero\examples\custom_soft_effect.py`,
y el menu real se arma igual en `hiero\ui\nuke_bridge\add_effect.py`):

```python
from hiero.ui import registerAction
action = QAction(QIcon("icons:Text.png"), "Mi Efecto", None)
action.setObjectName("foundry.timeline.effect.addMiEfecto")  # prefijo obligatorio
action.setData("MiGizmo")   # nombre de CLASE del nodo = nombre del archivo .gizmo
registerAction(action)
```

- El `.gizmo` tiene que estar en un plugin path (`nuke.pluginAddPath(carpeta)`).
- Correr esto en el startup (en este repo: un modulo en `MODULES` de
  `LGA_HieroTools_Startup.py`). Funciona igual que en el ejemplo real de la
  comunidad `mbires/hiero_custom_notes` (MIT, GitHub).

## Regla dura: que puede haber adentro del gizmo

Doc oficial (soft_effects.html): *"Soft effects have equivalent Nuke nodes
with the same name. **Only these nodes can be used in gizmos to create
custom soft effects**"* y *"Valid custom soft effects must have a GPUEngine
implementation"*. En la practica: Text2, Transform, Grade, etc. — la lista
del menu Effects. Un Read, Merge, Constant o Rectangle adentro del gizmo
**rompe el render en tiempo real** del timeline (aunque el export renderiza).
Consecuencia concreta: no hay esquinas redondeadas para fondos — el fondo
nativo de Text2 es rectangular y no se puede meter un nodo que dibuje otra
cosa. (Camino posible no explorado: BlinkScript, que si es soft effect.)

## El gran clasico: campos que no aparecen o aparecen todos apilados

Sintomas que tuvimos en LGA_BurnIn, en orden, con su causa real:

| # | Sintoma | Hipotesis probadas | Causa real |
|---|---------|--------------------|-----------|
| 1 | Solo un campo visible; los demas ni aparecen | ¿metadata? ¿modulo? | Las expresiones TCL del `message` SIN dependencia de `[frame]` se evaluan UNA sola vez al cargar (antes de conectar el input) y quedan vacias para siempre. **Siempre pasar `\[frame\]` en la expresion**, como hace el BurnIn nativo en sus 6 campos. |
| 2 | Colores condicionales muertos (knobs con expresion python en 0) | serializacion propia inventada | La serializacion de una expresion python en un knob numerico NO se escribe a mano: se setea en vivo con `setExpression()` y se captura con `knob.toScript()`. Formato real: `{"\[python \{...\}]"}` (comillas, `\[` y `\{` escapados). |
| 3 | Campos anclados top/right invisibles; bottom-left visibles | ¿justify roto en GPU? (falso) | Ver #4: era el mismo problema de posicionamiento. Con el gizmo bien armado, `xjustify right` / `yjustify top` desde archivo funcionan perfecto. |
| 4 | TODOS los campos apilados abajo a la izquierda, knobs y boxes correctos al dumpearlos por Python | ¿tooltip en knob 84? (no era) ¿aritmetica sin comillas en expresiones de box? (no alcanzo) | Los Text2 escritos a mano SIN los blobs de estado internos del nativo (`transforms`, `animation_layers`, `cursor_initialised`, `group_animations`, `center`, `old_message`) no inicializan su sistema de layout y el GPU los dibuja en el origen. **Copiar los bloques Text2 del `BurnIn.gizmo` nativo VERBATIM** y cambiar solo message/box/color/disable/font. |

### La tecnica que destrabo todo: el control byte a byte

Cuando "mi gizmo no funciona y no se por que", el experimento de control
definitivo es: **copiar el `BurnIn.gizmo` nativo tal cual con otro nombre**
(`LGA_TestBI.gizmo`), registrarlo por la via custom propia, y probarlo.

- Si la copia funciona (fue nuestro caso): el registro custom esta bien y el
  problema es el contenido del archivo propio → converger por diff contra el
  nativo, cambiando una cosa por vez.
- Si la copia fallara: el problema seria del mecanismo de registro o del
  entorno, no del archivo.

El `BurnIn.gizmo` nativo (`C:\Program Files\Nuke<ver>\plugins\BurnIn.gizmo`)
es LA referencia de sintaxis: 6 Text2 con knobs de usuario en el Group,
expresiones a `parent.*`, y todos los anclajes funcionando.

## setValue vs expresiones

Un `knob.setValue()` sobre un knob **con expresion** no pisa la expresion:
el valor mostrado puede cambiar en el dump pero la expresion sigue mandando.
Para mover un campo cuyo box esta expresado contra knobs del padre, se
setean **los knobs del padre**, no el box del Text2.

## Expresiones del timeline y Python propio

- Las expresiones `[python ...]` de un soft effect pueden importar modulos
  del startup (`__import__('MiModulo')`) — probado. Eso permite logica viva
  (comparaciones, config por proyecto) fuera del gizmo.
- Esas funciones corren POR FRAME: cachear todo lo costoso, no tirar nunca
  excepciones (devolver valores neutros y loguear una sola vez).

## Metadata disponible en el stream del timeline

Keys reales medidas con `[metadata keys input/*]` en un Text2 del timeline:
`input/width`, `input/height`, `input/frame`, `input/frame_rate`,
`input/timecode`, `input/filename`, `input/bitsperchannel`, `input/ctime`,
`input/mtime`, `input/filesize`, `input/filereader`. Ademas evaluan
`hiero/clip`, `hiero/project`, `hiero/sequence/frame_rate`.

- **El colorspace NO viaja en el stream**: hay que resolverlo por API
  (`clip.sourceMediaColourTransform()`), ubicando el clip por nombre, con cache.
- Ojo: el nombre de una key en el timeline puede diferir del que se ve en
  Nuke (caso real de foro: `exr/nuke/input/stime`). Ante una expresion que
  "no evalua", inspeccionar con `[metadata values]`.

## Persistencia por proyecto (viaja en el .hrox)

- `hiero.core.Tag` agregado a `project.tagsBin()` con
  `tag.metadata().setValue(...)` se serializa dentro del `.hrox` y sobrevive
  guardar/reabrir (probado). **Las keys DEBEN empezar con `tag.`** (RuntimeError
  si no).
- El Clean Project del Edit Panel borra BinItems sin uso pero NO toca tags:
  un "clip fantasma" para transportar settings moriria; un tag no.

## Fondo de texto que "respira"

El fondo nativo de Text2 (`enable_background` etc., el mismo del BurnIn de
Foundry) abraza al texto. Con fuente proporcional, un `1` y un `8` miden
distinto y el fondo cambia de ancho con cada frame. Solucion: **fuente
monoespaciada para campos de digitos** (frame, timecode). No hay fondo de
ancho fijo nativo.

## Rotacion de Text2 (layouts verticales)

El knob `rotate` de Text2 es un proxy de UI sobre el layer seleccionado: el
transform real vive en el blob `animation_layers`
(`{1 11 centerX centerY tx ty sw sh skx sky rotate 0}`). Setear `rotate` por
codigo no rinde; **copiar el blob con `fromScript()`** desde un nodo rotado a
mano si funciona (probado). El center va horneado en pixeles: recalcular por
formato.

## BlinkScript en el timeline (lo aprendido construyendo LGA_BurnIn)

| # | Problema | Causa real / solucion |
|---|---|---|
| 1 | `recompile.execute()` por script no compila NADA en el timeline (el nodo queda con el kernel default Swirlomatic; sin popup) | La unica via que compila por script es `kernelSourceFile` + `reloadKernelSourceFile.execute()` (el boton Load). En GUI, abrir el panel del nodo tambien dispara el compile. |
| 2 | Un BlinkScript del timeline que fallo un compile puede quedar CLAVADO (ni Load lo revive) | No pelearlo: crear un efecto fresco. |
| 3 | Los knobs de los parametros del kernel no existen al cargar el gizmo | Se generan AL COMPILAR, prefijados con el nombre del kernel (`LGARoundedPanels_clip_x`). Por eso no se pueden escribir expresiones para ellos en el archivo del gizmo: se atan por codigo post-compile (onCreate -> setup -> setExpression). Buscarlos por sufijo, no por nombre exacto. |
| 4 | Kernel con FUNCION MIEMBRO no compilaba en el timeline; el mismo codigo inline si | Escribir los kernels del timeline sin funciones auxiliares: todo inline en `process()`, una declaracion por linea (estilo de los ejemplos oficiales). |
| 5 | ¿Un BlinkScript adentro de un gizmo custom corre en el timeline? | SI — medido (gizmo de prueba con kernel embebido + onCreate). La frase de la doc "can't publish kernels to Groups or Gizmos" refiere al boton Publish, no a esto. |
| 6 | ¿Renderiza en el export? | Los soft effects van al export por default ("Include Effects"); confirmado por doc para soft effects en general. El gpuOP viewport-only era la era pre-14.1. |
| 7 | Params del soft effect BlinkScript | Solo `int`, `float`, `bool` (doc). Todo escalar; los toggles llegan como 0.0/1.0 por expresion. |

Dos trampas mas, medidas en NKS 16 con el efecto andando:

- **`hiero/project` llega VACIO en el stream del gizmo en el timeline**,
  aunque el preset del BurnIn nativo lo liste. Para saber el proyecto desde
  la logica: fallback a `hiero.ui.activeSequence().project()` y, si no, al
  unico proyecto abierto.
- **Las expresiones `[python ...]` de knobs de color NO se re-evaluan al
  cambiar datos externos** (config, tag): el timeline cachea hasta que el
  NODO se ensucia. Tras cambiar config por fuera, tocar un knob del efecto
  (nudge: setValue(v-0.001) y setValue(v)) fuerza el refresco.

Serializacion de un kernel embebido en `.gizmo` (patron de los NST_*):
`kernelSource` en UNA linea con `\n`, `\{`, `\}`, `\"`; `KernelDescription`
es un blob que genera Nuke al compilar (no se escribe a mano — por eso el
camino onCreate+Load en vez de embeberlo).

## Datos de version

- El soft effect Burn-In nativo acepta texto arbitrario y TCL en sus campos
  recien desde **17.0v3** (release note ID 224896); en 15.x/16.x solo presets.
- El mecanismo de registro (`registerAction` + `foundry.timeline.effect.*`)
  es identico al menos desde Nuke 13 hasta 17.x.

## Rotacion del texto por campo: RESUELTA (medido y validado, 29-08)

Se quiso rotar cada campo (texto + fondo) por separado —para burn-ins
verticales a los costados—. Estado: **funcionando** (validado en NKS a 90 y
270 con capturas). Los caminos directos NO rotan; el que SI, abajo. Pruebas
en NKS 16, con capturas del viewer:

1. El transform tab del Text2 (`translate`, `rotate`) NO renderiza: mover
   `translate` 400px no movio el texto; `rotate` 90 no lo roto. El Text2 se
   posiciona solo por su `box` + `xjustify`/`yjustify`.
2. El blob `animation_layers` (que en un comp guarda el transform real del
   texto) con la ranura de rotacion en 90 tampoco roto nada en el timeline.
3. Un nodo **Transform** SI renderiza dentro del gizmo: uno antes del Output
   roto TODA la imagen (footage + burn-in). Pero un Transform sobre la salida
   AISLADA de un Text2 (Text2 dibujado sobre negro) NO rota el texto, ni
   siquiera con un pixel-op (Grade) forzando el raster antes del Transform.
4. Un Transform sobre el composite final SI rota (probado), pero rota todo
   junto (global), no por campo.

**LO QUE SI FUNCIONA (mecanismo encontrado):** rotar el GRUPO "root transform"
del propio Text2. En la UI: tab **Groups** -> seleccionar "root transform" ->
rotar. Eso escribe la rotacion en el blob `animation_layers` y RENDERIZA.
Serializado, el layer es:

    {1 11 <cx> <cy> <tx> <ty> <sx> <sy> <skewX> <skewY> <ROT> <?>}

o sea la **rotacion esta en la posicion [10]** (indice 0), y hay que tener el
grupo **SELECCIONADO** (`group_animations ... selected: 0`). Capturado de un
Text2 rotado a mano (rotate 59 -> `... 0 0 59 0` en [10]).

Trampas medidas al intentar cablearlo:
- La rotacion tiene que ir como **LITERAL**. Una expresion `{parent.bi_x_rot}`
  en el blob NO se evalua (rompe el layer y el texto no renderiza).
- **Setear el blob por API (`fromScript`/`setValue`) NO dispara el re-render**
  del soft effect (queda el frame cacheado). La edicion interactiva de la UI y
  un cambio de frame SI. Para el panel: escribir el literal y refrescar por
  cambio de frame, o encontrar el trigger que usa la UI.
- El **centro** de la rotacion (posiciones [2][3] del layer) hay que ajustarlo
  por campo para que rote SOBRE SI MISMO; con el default queda descentrado.

CABLEADO (v1.03 del Blink): `apply_rotation()` lee `bi_<f>_rot` y escribe el
literal en [10] con el grupo seleccionado; el pivote es el CENTRO del panel
(`panel_geo('cx')` + la formula del alto), el mismo que se bindea a ax/ay del
kernel — texto y fondo giran juntos y el conjunto rota sobre si mismo. Se llama
desde el onCreate (setup), el knobChanged (bi_<f>_rot / x / y / size / scale /
text_pad / weight) y el panel. Dos trampas mas, medidas al cablear:

- `gizmo.width()/height()` por API devuelven el formato DEFAULT (640x480), no
  el del stream: el formato real sale de `hiero.ui.activeSequence().format()`
  (`_timeline_format()`).
- Un efecto creado/mutado por API puede no aparecer en el viewer hasta forzar
  un refresh de verdad: ni el nudge de opacity ni un toggle de enable alcanzan
  siempre; el `LGA_NKS_Timeline_Refresh` del pack (cerrar/reabrir el viewer) lo
  garantiza. En interaccion normal de UI el problema no aparece.


## Crear y BORRAR soft effects por codigo (medido con Apply AMF)

### Crear: `subTrackIndex` no es opcional

`VideoTrack.createEffect(effectType=..., trackItem=..., subTrackIndex=...)`.
Pasando `trackItem` el efecto queda LINKEADO al clip y hereda su timing.

La doc dice: *"subTrackIndex - if specified, will be placed on the appropriate
sub-track, otherwise will be placed on a NEW sub-track"*. O sea que **sin
pasarlo, CADA llamada abre un subtrack nuevo**.

Sintoma cuando falta: el primer clip con efectos ocupa los subtracks 0 y 1, y
el segundo clip -que tiene s0 y s1 libres, porque los del primero estan en otro
rango de tiempo- se va igual a s1 y s2. Queda un s0 vacio debajo de sus
efectos, que en pantalla se ve como una franja muerta VERTICAL entre el clip y
su propia cadena, y crece con cada clip. No es un problema de frames: los
rangos coinciden al frame.

### Borrar: la opcion que evita borrar el CLIP

Un soft effect vive en `track.subTrackItems()` y se elimina con
`track.removeSubTrackItem(item, opciones)`.

**`removeSubTrackItem` por defecto borra tambien los items LINKEADOS.** Como
los efectos creados con `createEffect(trackItem=...)` estan linkeados al clip,
llamarlo sin opciones **borra el clip del timeline**.

La opcion correcta es:

```python
opciones = hiero.core.TrackBase.RemoveItemOptions.eDontRemoveLinkedItems
track.removeSubTrackItem(effect, opciones)
```

Regla: si esa enum no se puede resolver, **cancelar el borrado**. No hay
fallback a `removeSubTrackItem(effect)` a secas — ese "fallback" es exactamente
el accidente que se quiere evitar.

### Que se puede borrar sin equivocarse

Coincidir la clase del nodo NO alcanza para decidir que un efecto es tuyo. Un
`OCIOCDLTransform` puede haberlo puesto el usuario a mano. Apply AMF usa tres
condiciones juntas:

1. La clase del nodo esta en la lista de las que crea la tool.
2. Esta linkeado al clip, o cubre exactamente su rango. Un solape PARCIAL
   queda afuera: puede ser un grade que abarca varios clips del track.
3. El knob `file` apunta a la carpeta de look del shot.

La 3 es la que distingue lo propio de lo ajeno. Se eligio la ruta en vez de un
tag propio porque los timelines que ya existen tienen efectos creados por
versiones anteriores, sin tag, y una marca nueva los dejaria fuera de alcance.

### Seleccion

La API **no permite seleccionar soft effects por codigo** (`setSelection` solo
acepta `TrackItem`). Por eso se opera directo sobre ellos en vez de
seleccionarlos primero.

### Habilitar / deshabilitar

`EffectTrackItem.setEnabled()` **no figura en la API documentada de Nuke 16**
-ni `SubTrackItem` ni `TrackItemBase` la listan- pero existe y es la via buena:
al llamarla, el knob `disable` del nodo se mueve solo.

## Refrescar el viewer tras un cambio de knobs por API (medido 01-09)

Un `setValue` por API deja al viewer del timeline mostrando el frame CACHEADO
del estado anterior; saltar el playhead o `nuke.clearRAMCache()` no alcanzan y
`LGA_NKS_Timeline_Refresh` abre un tab duplicado por llamada. Lo que si anda,
sin tabs: `hiero.ui.currentViewer().flushCache()` seguido de
`resumeCaching()` (flushCache PAUSA el cacheo, documentado) mas el nudge de
opacidad. `hiero.ui.updateViewer()` existe pero pide dos argumentos: no se usa.
`LGA_NKS_BurnIn` lo programa diferido (QTimer 0 ms) en cada knobChanged de un
`bi_*`, asi el panel refresca solo.

## Medir texto por API vs en render (medido 01-09)

Por API el Input del gizmo no tiene stream: los campos de metadata miden texto
vacio (ancho 0) y `parent.width()` da 640x480. Por eso `panel_geo('w')`
recuerda el ultimo ancho medido EN RENDER por campo y lo devuelve cuando la
llaman el panel o `apply_rotation`. Trampa medida: cambiar la medicion a
`QRawFont` (advances de diseno) da los mismos numeros por API que
`QFontMetricsF`, pero el render dibuja paneles ~1.3x mas anchos y corridos:
la medicion queda con `QFontMetricsF` sobre el TTF del repo.
