# LGA_BurnIn — soft effect de burn-in con metadata del clip visible

> Estado (29 ago 2026): **LGA_BurnIn** VALIDADO EN NKS REAL (efecto desde
> el menu Effects, paneles medidos en el viewer, rojo condicional, ventana
> desde el boton, presets) con capturas. La version anterior queda como
> **LGA_BurnIn_v0** (solo Text2), registrada aparte en el mismo menu.
> Pendiente: commit de esta ronda cuando Lega lo pida.

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

Objetivos: `res_target` y `fps_target` — `"timeline"` (formato/fps de la
secuencia) o explicitos (`"3840x2160"`, `24`).

Layout: **los paneles ABRAZAN a su texto** — el ancho se mide con
QFontMetrics del contenido real (con los digitos normalizados a "8" para
que frame/TC no cambien de ancho) mas `text padding`; el alto sale de una
formula compartida con los box de los Text2 (centrado vertical exacto).
Cada campo tiene un ANCLA (x, y en fracciones del formato; izquierda,
centro o derecha segun el campo). Default: dos filas balanceadas — arriba
`clip | colorspace | res`, abajo `frame | tc | fps`. Un campo sin texto no
dibuja panel.

## Arquitectura del gizmo

```
Input -> Dot -> BlinkScript (Blink_Panels) -> 6x Text2 -> Output
```

- **Blink_Panels**: kernel `LGA_RoundedPanels.blink` (SDF de rounded box,
  antialiasing 1px, los 6 paneles en UNA pasada, params solo float). Su
  `onCreate` llama a `LGA_NKS_BurnIn_Blink.setup()`, que compila el kernel
  via `kernelSourceFile` + Load (la unica via que compila por script en el
  timeline) y ata cada parametro a los knobs del gizmo padre por expresion
  (los knobs del kernel recien existen tras compilar, prefijados con el
  nombre del kernel).
- **Text2 x6**: anatomia calcada del BurnIn nativo (blobs de estado
  incluidos — sin ellos el GPU los dibuja en el origen). Cada message llama
  a `LGA_NKS_BurnIn_Logic.bi_text()` con `[frame]`; res y fps llevan el
  color condicional via `bi_ok()` en los canales g/b. El texto se centra
  verticalmente dentro de su panel (`yjustify center`) con `text padding`.
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

El properties panel de Nuke no se puede re-estilar, pero el render solo lee
knobs: la ventana `LGA_NKS_BurnIn_Panel` (estilo del pack, `Style.FORM`,
captura en `UI_Captures/BurnIn_Panel.png`) edita en vivo el efecto —
campos, fondos, colores, opacidades, radio, padding — y los objetivos del
proyecto, con dos guardados:

- **Layout (% of format)**: posicion X/Y de cada campo en porcentaje,
  editada en vivo sobre el efecto.
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

## Pendientes

- Validacion visual final en NKS (efecto nuevo + boton del panel).
- Layouts verticales (campos rotados 90): mecanismo probado via blob
  `animation_layers` + `fromScript`, no integrado.
- Aplicar defaults de config a instancias nuevas (hoy los defaults viven en
  el gizmo generado).

## Deuda de diagnostico

Todo lo aprendido (y sufrido) esta en `Docu_SoftEffects_Aprendizajes.md`.
