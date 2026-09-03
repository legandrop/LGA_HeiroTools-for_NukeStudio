> **Regla de documentacion**: este archivo describe el estado actual del codigo
> y de la convencion del pipeline. No es un historial de cambios ni un changelog.
> Incluye al final una seccion de referencias tecnicas con rutas completas y las
> funciones clave de cada archivo.

# Look_Files: un .amf por plate, y como se elige cual

La carpeta `<shot>/_input/Look_Files` trae el color del shot: de ahi salen los
soft effects que pone Apply AMF en el timeline y los nodos de color que arma su
contraparte en Nuke. Este documento existe porque la eleccion del archivo NO es
obvia y ya causo un bug: durante varias versiones la tool se quedaba con el
primer archivo alfabetico de la carpeta y le ponia a un clip el grade de otra
toma.

## Que hay adentro

    <shot>/_input/Look_Files/
        PROJA_1033_0200_VND_aPlate_v001.amf
        PROJA_1033_0200_VND_aPlate_v001.cdl
        PROJA_1033_0200_VND_aPlate_v001.cc
        PROJA_1033_0200_VND_bPlate_v001.amf
        PROJA_1033_0200_VND_bPlate_v001.cdl
        PROJA_1033_0200_VND_bPlate_v002.amf
        PROJA_1033_0200_VND_bPlate_v002.cdl
        PROJA_1033_0200_VND_cbPlate_v001.amf
        ...
        algun_lmt_acesap0_linear.clf
        A107C003_25121789.mxf_1.3.1.jpg

Lo que hay que saber, medido sobre shots reales:

- **Un `.amf` por PLATE, no por shot.** Un shot puede traer aPlate, bPlate,
  cPlate y cbPlate, cada uno con el suyo. Un shot del proyecto en curso tiene
  diez.
- **Cada plate tiene su propio grade.** Medido: en un shot el aPlate declara un
  offset y el cbPlate otro distinto. Elegir mal no es un detalle de forma, es
  ponerle a un clip la correccion de otra toma.
- **El `.cdl` es HERMANO del `.amf`**: mismo nombre base, otra extension, uno a
  uno. En el shot de diez `.amf` hay exactamente diez `.cdl`.
- **El `.clf` es UNO y lo comparten todos.** El LMT es del proyecto, no del
  plate, y su nombre no sigue la convencion del shot.
- **Un plate puede tener varias versiones** (`bPlate_v001`, `bPlate_v002`). En
  todos los casos medidos las versiones de un mismo plate traen el MISMO grade,
  asi que ofrecer todas seria ruido: se toma la mas alta.
- **Hay ruido en la carpeta**: JPGs de referencia de camara, y copias con el
  nombre mal formado donde la extension quedo con guion bajo
  (`..._aPlate_v001_amf`). Nada de eso termina en `.amf`, asi que el filtro por
  extension los ignora solo. No agregar filtros de mas por ellos.

## Como se elige el archivo, y por que las dos tools difieren

**En Hiero se DEDUCE. No se pregunta nada.** La tool es un toggle de uso rapido
que opera sobre todos los clips bajo el playhead, y cada clip YA dice de que
plate es: su media se llama `<shot>_<plate>_v###`. Preguntar seria absurdo
teniendo el dato, y ademas habria que preguntar una vez por clip.

El orden es:

1. El `.amf` del plate del clip, en su version mas alta.
2. Si el shot no trae uno para ese plate, el del **aPlate**.
3. Si el clip **no es un plate** -un `_comp`, un precomp, un render de review-,
   tambien el del aPlate: el look que le corresponde es el del plate principal.
4. Si tampoco hay aPlate, el primero de la carpeta.

Los pasos 2 y 3 son el mismo codigo: se busca el plate pedido y, si no esta, se
busca `PLATE_POR_DEFECTO`. Un clip sin plate entra con `None` y cae directo al
default.

**En Nuke se PREGUNTA.** Ahi la tool arranca del `.nk` abierto, que representa
el SHOT y no un plate: no hay de donde deducirlo. Por eso muestra el cartel
`Select AMF` cuando hay mas de un archivo, agrupando por plate y quedandose con
la version mas alta de cada uno. Con uno solo no pregunta nada.

## Trampas medidas

- **El `.cdl` tiene que salir del `.amf` elegido, no de la carpeta.** Resolver
  bien el `.amf` y despues tomar "el primer `.cdl`" es el mismo bug con un paso
  mas. Se resuelve por hermano.
- **Si el `.amf` elegido no tiene hermano**, se acepta un `.cdl` suelto SOLO
  cuando hay uno en la carpeta: ahi el nombre esta fuera de convencion pero no
  hay ambiguedad. Con varios y ninguno hermano se avisa y NO se crea el nodo de
  grade. Aplicar el primero seria volver al bug.
- **Las mayusculas no coinciden, ni entre archivos ni contra la media.** Hay
  shots con la carpeta MEZCLADA: `..._APLATE_V001.amf` y `..._BPLATE_V002.amf`
  en mayusculas conviviendo con `..._cbPlate_v001.amf` en minusculas, y la media
  de ese mismo aPlate llamandose `..._aPlate_v001`. Por eso el plate se compara
  siempre en minuscula y el hermano se busca ignorando mayusculas. Verificado
  sobre un shot asi: un clip cuya media dice `aPlate` encuentra el `.amf` que
  dice `APLATE`, y su `.cdl` hermano.
- **Un prerender puede traer dos `_v###`**, como
  `<shot>_aPlate_v001_Denoised_v02`. El plate y su version salen del MISMO match
  del patron, asi que vale el que esta pegado al plate y no el ultimo del
  nombre.
- **El plate se lee del NOMBRE DEL ARCHIVO, no de la ruta.** La carpeta del shot
  puede nombrar un plate que no es el del clip.

## Costo: por que hay cache

El toggle arma el plan por CLIP, y todos los clips de un shot miran la misma
carpeta. Sin cache, veinte clips son cuarenta listados de carpeta y cuarenta
parseos de XML de los mismos archivos, y `Look_Files` vive en el disco del
estudio, no en local. Con el cache la carpeta se lista una vez por corrida y
cada plan se arma una vez por plate distinto.

Medido sobre veinte clips: **de 8,5 ms a 1,6 ms**, y deja de crecer con la
cantidad de clips.

El cache NO se persiste entre corridas: entre un toggle y el siguiente el
usuario pudo bajar un `.amf` que faltaba. Hoy eso ya lo garantiza el cargador
-el panel corre la tool con `execute_external_script`, que arma un modulo nuevo
por click y no lo registra en `sys.modules`-, pero `reset_caches()` se llama
igual, porque el dia que alguien importe el modulo de la forma normal el
cargador deja de salvarnos.

## Referencias tecnicas

**`LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_NKS_ApplyAMF.py`** (la de Hiero):

- `PLATE_VER_RE` — el patron que saca plate y version de un nombre. Es el mismo
  que usa `LGA_NKS_CreateNKScript`; se copia y no se importa porque los dos
  modulos son hermanos y ninguno depende del otro.
- `PLATE_POR_DEFECTO` — `"aplate"`, el respaldo de los pasos 2 y 3.
- `plate_and_version(nombre)` / `plate_from_path(path)` — de que plate es una
  media.
- `pick_amf_for_plate(look_dir, plate)` — la regla de eleccion completa.
- `sibling_look_file(amf_path, extension)` — el `.cdl` hermano.
- `_archivos_de(look_dir)` / `_PLAN_CACHE` / `reset_caches()` — el cache.
- `build_effect_plan(look_dir, plate)` — arma el plan; cachea por
  (carpeta, plate).

**`LGA_ToolPack-B/py/LGA_ApplyAMF.py`** (la de Nuke, en otro repo):

- `scan_amf_entries(look_dir)` — agrupa por plate y se queda con la version mas
  alta, para el cartel.
- `sibling_look_file(amf_path, extension)` — misma idea que en Hiero.
- `LGA_ApplyAMF_Dialogs.pick_plate(parent, entries)` — el cartel `Select AMF`.

**Documentos relacionados**: `Docu_SoftEffects_Aprendizajes.md` explica como se
crean y borran los soft effects, y por que el `working_space` de los nodos OCIO
no es "donde esta la entrada".
