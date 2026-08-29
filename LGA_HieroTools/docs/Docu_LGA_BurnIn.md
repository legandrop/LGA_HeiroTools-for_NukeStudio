# LGA_BurnIn — soft effect de burn-in con metadata del clip visible

> Estado (29 ago 2026): **LGA_BurnIn** con el rediseno grande — 8 campos (con
> 2 custom text), tamano por campo, peso de Inter (Bold incluido, via
> `NUKE_FONT_PATH` al fonts del repo), Properties pelado a un boton y ventana
> propia rediseniada (tabla + detalle, drag-sliders, paint-toggle, seleccion
> multiple). Validado en NKS por dev-link + capturas del harness. Rotacion por
> campo: investigada, NO es posible (ver Limitaciones). La version anterior
> queda como **LGA_BurnIn_v0** (solo Text2) en el mismo menu.

## Que es

Un unico soft effect para el timeline de Hiero/Nuke Studio (NKS) que
reemplaza la pila de soft effects Text con metadata. Es un **gizmo**
registrado en el menu Effects que muestra datos del **clip visible**
(respeta tracks prendidos/apagados) sobre **paneles redondeados** dibujados
en GPU por un kernel BlinkScript propio, y pinta en **rojo** lo que no
coincide con el objetivo del proyecto.

## Campos (cada uno con checkbox propio y panel de fondo opcional)

| Campo | Contenido | Rojo condicional |
|---|---|---|
| clip name | `hiero/clip` | no |
| colorspace | `sourceMediaColourTransform()` del clip (por API + cache; no viaja en la metadata del stream) | no |
| resolution | `input/width` x `input/height` | si: difiere del objetivo. **Solo compara plates** (`compare_res_exts`, default `exr`) |
| frame | `Frame: <input/frame>` | no |
| timecode | `TC: <input/timecode>` | no |
| fps | `input/frame_rate` | si: difiere del objetivo |
| custom 1 | texto libre del usuario (`bi_custom1_text`) | no |
| custom 2 | texto libre del usuario (`bi_custom2_text`) | no |

Objetivos: `res_target` y `fps_target` — `"timeline"` (formato/fps de la
secuencia) o explicitos (`"3840x2160"`, `24`).

Cada campo tiene ademas **tamano propio** (`bi_<f>_size`, en %) que escala
su fuente sin tocar a los demas.

Layout: **los paneles ABRAZAN a su texto** — el ancho se mide con las
metricas del **TTF real de Inter que usa Nuke** (QFontMetrics cargando ese
mismo archivo; medir con el nombre de familia crudo daba distinto porque Qt
sustituye la fuente). Para frame/TC los digitos se normalizan a "0" (ancho
estable por frame); el resto se mide exacto. El ancho suma `text padding` y
el alto sale de una formula compartida con los box de los Text2 (centrado
vertical exacto); ambos dependen del tamano por campo.
Cada campo tiene un ANCLA (x, y en fracciones del formato; izquierda,
centro o derecha segun el campo). Default: dos filas balanceadas — arriba
`clip | colorspace | res`, abajo `frame | tc | fps`. Un campo sin texto no
dibuja panel.

## Arquitectura del gizmo

```
Input -> Dot -> BlinkScript (Blink_Panels) -> 8x Text2 -> Output
```

**Fuente**: es **Inter**, fija (la del pack); el usuario elige solo el PESO
(Regular/SemiBold/Bold via `bi_weight`, que setea el `bi_font` invisible por
`apply_font()`). Para no depender de que Inter este instalada en la maquina,
el startup (`LGA_HieroTools_Startup.py`) antepone el fonts dir del repo
(`LGA_NKS_Shared/fonts/`, con los tres pesos) a `NUKE_FONT_PATH`, que Nuke
lee al escanear las fuentes (una vez, al arrancar; no en runtime). Asi Nuke
descubre el Inter del repo —incluido Bold, que el Inter de Windows no trae—
sin instalar nada. Al cambiar el peso, el fondo se recalcula (mide con el
TTF del peso nuevo).

- **Blink_Panels**: kernel `LGA_RoundedPanels.blink` (SDF de rounded box,
  antialiasing 1px, los 6 paneles en UNA pasada, params solo float). Su
  `onCreate` llama a `LGA_NKS_BurnIn_Blink.setup()`, que compila el kernel
  via `kernelSourceFile` + Load (la unica via que compila por script en el
  timeline) y ata cada parametro a los knobs del gizmo padre por expresion
  (los knobs del kernel recien existen tras compilar, prefijados con el
  nombre del kernel).
- **Text2 x8** (6 de metadata + custom1/custom2): anatomia calcada del
  BurnIn nativo (blobs de estado incluidos — sin ellos el GPU los dibuja en
  el origen). Cada message llama a `LGA_NKS_BurnIn_Logic.bi_text()` con
  `[frame]`; res y fps llevan el color condicional via `bi_ok()` en los
  canales g/b. El texto se centra verticalmente dentro de su panel
  (`yjustify center`) con `text padding`.
- El gizmo se REGENERA con
  `+Building_Blocks/BurnIn/gen_LGA_BurnIn_gizmo.py` (tabla de layout +
  kernel + plantilla Text2). No editar el `.gizmo` a mano.

## Archivos

```
LGA_HieroTools/
  LGA_NKS_BurnIn.py                registro de LGA_BurnIn y LGA_BurnIn_v0 + eventos
  LGA_NKS_BurnIn_py/
    LGA_BurnIn.gizmo               el efecto (generado)
    LGA_BurnIn_v0.gizmo            version anterior (solo Text2)
    LGA_RoundedPanels.blink        kernel de los paneles (produccion)
    LGA_RoundedPanel.blink         kernel de UN panel (sonda historica)
    LGA_NKS_BurnIn_Blink.py        setup del BlinkScript (compilar + atar params)
    LGA_NKS_BurnIn_Logic.py        textos, comparaciones, cache de config
    LGA_NKS_BurnIn_Config.py       capa pura de config (testeable sin Nuke)
    LGA_NKS_BurnIn_ProjectTag.py   override que viaja en el .hrox (tag)
    LGA_NKS_BurnIn_Panel.py        ventana con el estilo del pack
    logs/DebugPy_LGA_NKS_BurnIn.log
  +Building_Blocks/BurnIn/gen_LGA_BurnIn_gizmo.py   generador (dev)
  +Building_Blocks/UI_Capture/fixtures/h3_burnin_panel.py  fixture del harness
```

## Panel propio (Open LGA Panel)

El properties del gizmo quedo **pelado a un solo boton** (Open LGA Panel);
todo se edita en la ventana `LGA_NKS_BurnIn_Panel` (estilo del pack,
`Style.FORM`, captura en `UI_Captures/BurnIn_Panel.png`), rediseniada a
**tabla + detalle**:

- **Tabla**, una fila por campo: nombre, ON, BG, y **X / Y / SIZE** con
  drag-sliders estilo Nuke (click-drag cambia, click escribe). Los checkbox
  ON/BG tienen **paint-toggle** (click+drag tilda/destilda varios). Las
  filas son de **seleccion multiple**.
- **Detalle** (opera sobre TODA la seleccion): ancla 3x3 que manda X/Y a una
  esquina/centro, y el texto de los campos custom (con un unico custom
  seleccionado). No hay rotacion (ver Limitaciones).
- **Style global**: text color, peso de Inter, opacidades, radio, padding.
- **Keep on top** (default ON) abajo a la izquierda.
- **Presets**: guardan campos+layout+estilo con nombre en el BurnIn.json
  de AppData; Load los aplica al efecto y nudgea.
- **Save Targets to Project**: tag `LGA_BurnIn_Settings` en el `tagsBin()`
  (key `tag.lga_burnin_config`) — viaja dentro del `.hrox`; Clean Project
  no toca tags. Hay que guardar el proyecto despues. Tras guardar, la
  ventana NUDGEA los efectos (el timeline no re-evalua las expresiones de
  color hasta que el nodo se ensucia — medido).
- **Save Targets as Defaults**: `%APPDATA%\LGA\HieroTools\BurnIn.json`
  (**no se versiona**: mapea nombres reales de proyectos; ejemplos siempre
  con `PROJA`).

Se abre desde el boton **Open LGA Panel** del propio efecto (knob PyScript;
si el boton no dispara en el panel del timeline, la ventana se puede abrir
desde el Script Editor con `__import__('LGA_NKS_BurnIn_Panel').show_panel()`).

## Config en dos capas

1. Usuario — `BurnIn.json` en AppData: `{"default": {...}, "projects":
   {"PROJA": {...}}}`; las keys de `projects` son PREFIJOS del nombre de
   proyecto (gana el mas largo).
2. Proyecto — el tag de arriba; pisa a la capa de usuario.

Cache por proyecto en la logica; se invalida en load/save/close de proyecto
y al cambiar el mtime del JSON.

## Limitaciones conocidas

- Un burn-in por vez en la ventana: edita el primer efecto LGA_BurnIn que
  encuentra en la secuencia activa (boton Refresh para re-buscar).
- El colorspace se cachea por clip; un cambio a mano se refleja al
  guardar/reabrir el proyecto.
- Comparacion de resolucion solo para plates (EXR por default).
- El costo GPU del kernel es una pasada full-frame por instancia; con "Use
  GPU if available" activo es despreciable frente a un Denoise.
- **La rotacion por campo todavia no esta cableada** (los knobs `bi_<f>_rot`
  existen pero inertes; sin control en el panel). El transform tab del Text2 no
  renderiza en soft effects, PERO rotar el GRUPO "root transform" del Text2 SI:
  seleccionarlo y escribir la rotacion como literal en la posicion [10] de
  `animation_layers`. Falta la pasada de wiring (write del literal + centro por
  campo + trigger de re-render). Detalle en `Docu_SoftEffects_Aprendizajes.md`.

## Pendientes

- Aplicar defaults de config a instancias nuevas (hoy los defaults viven en
  el gizmo generado).

## Deuda de diagnostico

Todo lo aprendido (y sufrido) esta en `Docu_SoftEffects_Aprendizajes.md`.
