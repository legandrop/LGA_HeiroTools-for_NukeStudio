# LGA_BurnIn — soft effect de burn-in con metadata del clip visible

> Estado (28 ago 2026): EN DESARROLLO. El mecanismo completo esta probado en
> vivo; la version reconstruida sobre la anatomia del gizmo nativo esta
> pendiente de validacion visual final. Faltan: ventana de settings,
> auditoria de cierre y entrada de changelog.

## Que es

Un unico soft effect para el timeline de Hiero/Nuke Studio que reemplaza la
pila de soft effects Text con metadata. Es un **gizmo** (`LGA_BurnIn.gizmo`,
solo nodos Text2 adentro) registrado en el menu Effects. Muestra datos del
**clip visible** (respeta tracks prendidos/apagados, igual que las
expresiones de metadata de un Text comun) y pinta en **rojo** lo que no
coincide con el objetivo del proyecto.

## Campos (cada uno con su checkbox)

| Campo | Contenido | Rojo condicional |
|---|---|---|
| clip name | `hiero/clip` | no |
| resolution | `input/width` x `input/height` | si: difiere del objetivo del proyecto. **Solo compara plates** (extensiones en `compare_res_exts`, default `exr`); refs/QuickTimes nunca se comparan |
| frame | `Frame: <input/frame>` | no |
| timecode | `TC: <input/timecode>` | no |
| colorspace | `sourceMediaColourTransform()` del clip (por API + cache; no esta en la metadata del stream) | no |
| fps | `input/frame_rate` | si: difiere del objetivo del proyecto |

Objetivos de comparacion: `res_target` y `fps_target`, valor `"timeline"`
(formato/fps de la secuencia) o explicito (`"3840x2160"`, `24`).

## Archivos

```
LGA_HieroTools/
  LGA_NKS_BurnIn.py              registro en el menu Effects + eventos de proyecto
  LGA_NKS_BurnIn_py/
    LGA_BurnIn.gizmo             el efecto (solo Text2, anatomia calcada del BurnIn nativo)
    LGA_NKS_BurnIn_Logic.py      lo que llaman las expresiones: textos, comparaciones, cache
    LGA_NKS_BurnIn_Config.py     capa pura de config (testeable sin Nuke)
    LGA_NKS_BurnIn_ProjectTag.py lectura/escritura del override que viaja en el .hrox
    logs/DebugPy_LGA_NKS_BurnIn.log  log de cada sesion (convencion del pack)
```

Se carga via `MODULES` en `LGA_HieroTools_Startup.py`. El paquete se agrega
a `sys.path` (las expresiones importan `LGA_NKS_BurnIn_Logic` por nombre) y
a los plugin paths de Nuke (para que exista la clase `LGA_BurnIn`).

## Config en dos capas

1. **Usuario** — `%APPDATA%\LGA\HieroTools\BurnIn.json`:
   ```json
   {
     "default": { "res_target": "timeline", "fps_target": "timeline" },
     "projects": { "PROJA": { "res_target": "3840x2160" } }
   }
   ```
   Las keys de `projects` son PREFIJOS del nombre de proyecto de Hiero
   (`PROJA` matchea `PROJA_SUP_v012`); gana el prefijo mas largo.
   **Este archivo mapea nombres reales de proyectos: NO se versiona.**
2. **Proyecto** — tag `LGA_BurnIn_Settings` en el `tagsBin()` del proyecto,
   key `tag.lga_burnin_config` con el mismo JSON adentro. Viaja dentro del
   `.hrox` (los settings acompanan al proyecto al mandarselo a alguien) y el
   Clean Project no lo toca. Pisa a la capa de usuario.

Cache por proyecto en la logica; se invalida al cargar/guardar/cerrar
proyecto y cuando cambia el mtime del JSON.

## Panel del efecto

- **LGA BurnIn** (tab 1): color, opacity, font, **font digits** (elegir una
  monoespaciada, ej. Courier New, para que el fondo de frame/TC no cambie de
  ancho con los digitos), text scale, checkboxes por campo, y seccion
  Background (toggle por campo + color/opacidad/padding globales).
- **Layout** (tab 2): caja de cada campo en fracciones del formato (0-1),
  para que las posiciones se adapten solas al cambiar de resolucion de
  proyecto. Cada campo ancla a su esquina (clip arriba-izq, res arriba-der,
  frame/TC/colorspace abajo-izq a centro, fps abajo-der).

## Limitaciones conocidas

- **Esquinas redondeadas del fondo: no.** El fondo nativo de Text2 es
  rectangular y ningun nodo "dibujante" adicional esta permitido dentro de
  un soft effect (romperia el realtime). Posible via BlinkScript, no
  explorado.
- El fondo abraza al texto: el ancho fijo se logra con la fuente mono en
  `font digits`, no hay caja de fondo de tamano fijo.
- El colorspace se cachea por clip: un cambio de colorspace hecho a mano se
  refleja al guardar/reabrir el proyecto (eventos que invalidan el cache).
- Comparacion de resolucion solo para plates (EXR por default).

## Pendientes

- Validacion visual de la version con anatomia nativa (blobs de estado).
- Fijar defaults de Layout con los valores elegidos por Lega.
- Ventana de settings con el estilo del pack (editar config de usuario y
  estampar el override al tag del proyecto).
- Layouts verticales (campos rotados 90 a los costados): mecanismo probado
  via blob `animation_layers` + `fromScript`, no integrado.
- Auditoria de cierre + changelog + versionado de headers.

## Deuda de diagnostico

El detalle de todos los problemas encontrados (expresiones sin `[frame]`,
serializacion de expresiones python, blobs de estado de Text2, tag keys con
prefijo `tag.`, etc.) esta en `Docu_SoftEffects_Aprendizajes.md`.
