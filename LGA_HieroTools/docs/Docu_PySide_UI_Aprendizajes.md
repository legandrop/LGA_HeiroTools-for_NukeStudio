> **Regla de documentacion**: este archivo recopila aprendizajes y soluciones a
> problemas recurrentes de UI con PySide/PyQt en Hiero/Nuke Studio. No es un
> historial ni changelog; cada seccion describe un problema concreto, las
> opciones probadas y la solucion ganadora.

# Aprendizajes UI — PySide / PyQt en Hiero/Nuke

Bitacora de problemas de styling y rendering de widgets que se repitieron en
multiples herramientas del proyecto. La idea es no volver a perder tiempo
reinventando la rueda cuando aparezca el mismo sintoma.

---

## Dropdowns (`QComboBox`)

### Problema 1 — La flecha `▼` se ve como un cuadradito

Cuando se aplica un stylesheet custom a `QComboBox`, la flecha del drop-down
aparece como un pequeño cuadrado solido en vez del triangulo `▼` esperado.
Sintoma comun cuando se usa el truco de los borders CSS para "dibujar" el
triangulo.

#### Opciones probadas

| # | Estrategia | Resultado |
|---|-----------|-----------|
| 1 | CSS triangle (`border-left/right transparent + border-top solido`, `width:0; height:0`) | ❌ Aparece un cuadrado en vez del triangulo |
| 2 | SVG inline via `image: url("data:image/svg+xml;...")` | ❌ No renderea el SVG en este Qt build |
| 3 | Sin custom drop-down (solo styling de `QComboBox`) | ❌ Mantiene el cuadrado heredado del style |
| 4 | `image: none` con drop-down area visible | ❌ Mismo cuadrado |
| 5 | Subclase con `paintEvent` dibujando el triangulo via `QPainter` | ✅ Flecha perfecta |
| 6 | Sin stylesheet (default puro de Qt) | ❌ Estetica inconsistente con el resto de la UI |
| 7 | `setStyle(QStyleFactory.create("Fusion"))` | ⚠ Flecha mas fea pero el popup no muestra checkboxes |

#### Solucion ganadora

**Subclase con `paintEvent`** (opcion 5). Se oculta la flecha nativa via
stylesheet y se pinta el triangulo manualmente:

```python
class _ArrowComboBox(QtWidgets.QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        cx = rect.right() - 10
        cy = rect.center().y() + 1
        path = QtGui.QPainterPath()
        path.moveTo(cx - 4, cy - 2)
        path.lineTo(cx + 4, cy - 2)
        path.lineTo(cx, cy + 3)
        path.closeSubpath()
        p.fillPath(path, QtGui.QColor("#999999"))
        p.end()
```

Stylesheet acompañante para ocultar la flecha nativa:

```css
QComboBox::drop-down { border: 0px; width: 18px; }
QComboBox::down-arrow { image: none; width: 0px; height: 0px; }
```

---

### Problema 2 — El popup desplegado muestra checkboxes a la izquierda de cada item

Al desplegar el `QComboBox`, los items aparecen con un check indicator (caja
vacia) a la izquierda. Es el delegate nativo del style de Windows.

#### Opciones probadas

| # | Estrategia | Resultado |
|---|-----------|-----------|
| A | `combo.setView(QtWidgets.QListView())` | ✅ Popup limpio |
| B | `combo.setItemDelegate(QtWidgets.QStyledItemDelegate(combo))` | ✅ Popup limpio (visualmente igual a A) |
| Fallback | `combo.setStyle(QStyleFactory.create("Fusion"))` | ✅ Popup limpio (pero cambia look del combo entero) |

#### Solucion ganadora

**`setView(QListView)`** (opcion A). `QListView` no incluye check indicators
y es la solucion mas limpia. Se llama una vez despues de crear el combo:

```python
combo = _ArrowComboBox()
combo.setView(QtWidgets.QListView())
```

---

### Problema 3 — El item en hover del popup tiene texto negro sobre fondo gris

Al hacer hover sobre un item del popup desplegado, el texto pasa a negro
(heredado del sistema) sobre un fondo de seleccion del OS. La combinacion
es ilegible sobre fondos oscuros.

#### Solucion

Agregar `selection-color` y usar `selection-background-color` explicito en
el stylesheet del `QAbstractItemView`:

```css
QComboBox QAbstractItemView {
    background-color: #2B2B2B;
    color: #a7a7a7;
    selection-background-color: #272727;
    selection-color: #a7a7a7;
    outline: 0;
}
```

---

### Receta canonica — `_ArrowComboBox` completo

Combo styled con flecha custom, popup sin checkboxes y hover legible:

```python
combo = _ArrowComboBox()
combo.setView(QtWidgets.QListView())
combo.setStyleSheet(
    "QComboBox { background-color:#272727; border:1px solid #444; "
    "color:#a7a7a7; padding:3px 6px; }"
    "QComboBox::drop-down { border:0px; width:18px; }"
    "QComboBox::down-arrow { image:none; width:0px; height:0px; }"
    "QComboBox QAbstractItemView { background-color:#2B2B2B; color:#a7a7a7; "
    "selection-background-color:#272727; selection-color:#a7a7a7; outline:0; }"
)
```

Para version sin border (columna Track en tabla):

```python
combo = _ArrowComboBox()
combo.setView(QtWidgets.QListView())
combo.setStyleSheet(
    "QComboBox { background-color:#272727; border:0px; "
    "color:#a7a7a7; padding:1px 4px; }"
    "QComboBox::drop-down { border:0px; width:14px; }"
    "QComboBox::down-arrow { image:none; width:0px; height:0px; }"
    "QComboBox QAbstractItemView { background-color:#2B2B2B; "
    "border:1px solid #444444; color:#a7a7a7; "
    "selection-background-color:#272727; selection-color:#a7a7a7; outline:none; }"
)
```

---

## SpinBox (`QSpinBox` / `QDoubleSpinBox`)

### Problema — Los botones arriba/abajo desaparecen con stylesheet custom

Cuando se aplica un stylesheet custom a `QSpinBox`, los botones up/down pueden
desaparecer o quedar invisibles si no se definen los sub-controles
`::up-button`, `::down-button`, `::up-arrow` y `::down-arrow`.

A diferencia de `QComboBox`, **el CSS triangle (border trick) SÍ funciona** en
`QSpinBox` para renderear las flechas según la documentación oficial — pero en
la práctica su efectividad depende del build y plataforma de Qt.

#### Opciones probadas — Ronda 1 (CSS, todas fallaron en este build)

| # | Estrategia | Resultado |
|---|-----------|-----------|
| 1 | CSS triangle, 18px buttons, `subcontrol-origin:border` | ❌ flechas no visibles |
| 2 | CSS triangle, 22px buttons, más anchas | ❌ flechas no visibles |
| 3 | CSS triangle, `subcontrol-origin:padding` | ❌ flechas no visibles |
| 4 | Arrows nativos del SO (solo custom background, sin `::up-arrow`) | ❌ flechas no visibles |
| 5 | `NoButtons` vía CSS (`width:0px`) | — sin flechas por diseño |

**Conclusión ronda 1:** el CSS triangle (border trick) que SÍ funciona para `QComboBox`
**NO funciona** para `QSpinBox` en este build de Qt. Ninguna variante CSS produce flechas visibles.

#### Opciones probadas — Ronda 2 (enfoques no-CSS)

| # | Estrategia | Resultado |
|---|-----------|-----------|
| 1 | `setButtonSymbols(PlusMinus)` — `+` y `−` nativos Qt | — |
| 2 | Default puro (sin `setStyleSheet`) — arrows del SO | — |
| 3 | `setStyle(QStyleFactory.create("Fusion"))` en el widget | — |
| 4 | `setStyle(QStyleFactory.create("Windows"))` en el widget | — |
| 5 | Wrapper: `NoButtons` + QPushButton ▲▼ externos (verticales) | ✅ OK (workaround viable) |
| 6 | Wrapper: `NoButtons` + QPushButton [−] valor [+] horizontales | ✅ OK (workaround viable) |
| 7 | Subclase + `paintEvent` dibuja ▲▼ via `QPainter` (análogo a `_ArrowComboBox`) | ✅ **GANADORA** |

#### Solución ganadora — `_ArrowSpinBox`

**Opción 7**: subclase de `QSpinBox` que llama a `super().paintEvent()` y dibuja
encima los triángulos ▲▼ con `QPainter`. Los botones nativos del SO siguen siendo
funcionales (zona de click intacta); solo se reemplaza visualmente la imagen de la flecha.

Mismo patrón que `_ArrowComboBox` (solución ganadora para combos).

```python
class _ArrowSpinBox(QtWidgets.QSpinBox):
    _STYLE = (
        "QSpinBox { background:#272727; border:1px solid #444; color:#a7a7a7;"
        " padding:2px 20px 2px 4px;"
        " selection-background-color:#d8d8d8; selection-color:#333333; }"
        "QSpinBox::up-button, QSpinBox::down-button"
        " { background:transparent; border:none; width:18px; }"
        "QSpinBox::up-arrow, QSpinBox::down-arrow"
        " { image:none; width:0; height:0; }"
    )

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect()
        cx = r.right() - 9
        cy_up = r.height() // 4
        path_up = QtGui.QPainterPath()
        path_up.moveTo(cx - 4, cy_up + 2)
        path_up.lineTo(cx + 4, cy_up + 2)
        path_up.lineTo(cx,     cy_up - 2)
        path_up.closeSubpath()
        p.fillPath(path_up, QtGui.QColor("#999999"))
        cy_dn = r.height() * 3 // 4
        path_dn = QtGui.QPainterPath()
        path_dn.moveTo(cx - 4, cy_dn - 2)
        path_dn.lineTo(cx + 4, cy_dn - 2)
        path_dn.lineTo(cx,     cy_dn + 2)
        path_dn.closeSubpath()
        p.fillPath(path_dn, QtGui.QColor("#999999"))
        p.end()
```

Notas de uso:
- `padding: 2px 20px 2px 4px` reserva el espacio derecho para la zona de los botones
- `width: 18px` en `::up-button` / `::down-button` define el área de click de los nativos
- `selection-background-color: #d8d8d8; selection-color: #333333` — evita el amarillo default
- Ancho recomendado para 4-5 dígitos: `setFixedWidth(72)`

---

## Scripts ejecutados desde panel

### Problema — El script principal se actualiza pero sus helpers quedan cacheados

Cuando un boton del panel ejecuta un script externo con `importlib.util.spec_from_file_location`
y `spec.loader.exec_module(module)`, el script principal se evalua de cero en cada click.
Pero los helpers importados por ese script siguen pasando por el cache normal de Python
en `sys.modules`.

Sintoma: se modifica un helper, se aprieta de nuevo el boton del panel, y el cambio no aparece
hasta reiniciar Hiero/Nuke Studio.

#### Solucion para desarrollo

Forzar que el helper se borre de `sys.modules` antes de importarlo. Esto hace que cada
ejecucion del script principal vuelva a leer el helper desde disco:

```python
import importlib
import sys

_TRANSCODE_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_transcode"
if _TRANSCODE_HELPER in sys.modules:
    del sys.modules[_TRANSCODE_HELPER]
_transcode_mod = importlib.import_module(_TRANSCODE_HELPER)
TranscodeWorker = _transcode_mod.TranscodeWorker
```

#### Cuando usarlo

- Durante desarrollo iterativo de helpers llamados por herramientas de panel.
- Cuando el script principal ya se ejecuta fresco, pero sus imports internos no.
- En produccion se puede volver al import normal si no se necesita hot reload.

Ejemplo aplicado: `LGA_import_shots.py` fuerza recarga de
`LGA_import_shots_transcode.py` para que `TranscodeWorker` tome cambios sin reiniciar.

---

## Undo en Hiero con múltiples proyectos abiertos

### Problema — `project.beginUndo()` no agrupa las operaciones cuando hay 2+ proyectos abiertos

Al ejecutar una operación con `project.beginUndo("nombre")`, si el `project` se obtiene via
`hiero.core.projects()[0]`, el undo group se abre en el **primero de la lista** — que puede
no ser el proyecto que contiene la secuencia que se está editando.

Síntoma: la operación funciona correctamente, pero al deshacer hay que presionar Ctrl+Z
muchas veces (una por cada operación individual). Con un solo proyecto abierto todo anda bien;
el problema aparece al tener un segundo proyecto abierto simultáneamente.

#### Por qué falla

`hiero.core.projects()` devuelve todos los proyectos abiertos. El índice `[0]` no garantiza
que sea el proyecto activo ni el que contiene la secuencia en uso. El `beginUndo` se abre en
ese proyecto ajeno, y las operaciones de timeline quedan como entradas independientes en el
undo stack del proyecto correcto.

#### Solución

Obtener el proyecto **desde la secuencia** con `seq.project()`:

```python
# MAL — falla con múltiples proyectos abiertos
project = hiero.core.projects()[0]

# BIEN — siempre usa el proyecto que contiene la secuencia activa
project = self.seq.project()
```

Esto garantiza que el `beginUndo` se abre en el proyecto correcto sin importar cuántos
proyectos estén abiertos ni en qué orden.

#### Notas

- El mismo error puede ocurrir en cualquier operación que use `projects()[0]` para obtener
  el contexto de undo: creación de tracks, coloreo de bins, cualquier operación agrupada.
- En herramientas que no tienen acceso a una secuencia, usar `hiero.ui.activeSequence().project()`
  como alternativa.

---

## Drag & drop de archivos en un dialogo

### Problema — el drop nunca llega al dialogo, o el cartel de drop sale invisible

Al agregar `setAcceptDrops(True)` a un `QDialog` que ya tiene un campo de texto,
arrastrarle un archivo encima no dispara `dropEvent`: el archivo se pega como
ruta dentro del texto. Y si el cartel "soltar aca" se arma como un `QWidget`
hijo con stylesheet, aparece transparente, sin fondo ni borde punteado.

#### Por que falla

1. `QPlainTextEdit` y `QLineEdit` aceptan drops por su cuenta. Como estan
   arriba del dialogo en el hit test, se quedan con el evento y lo interpretan
   como texto. Qt solo propaga el drag al ancestro cuando el widget de abajo
   **no** acepta drops.
2. Un `QWidget` pelado no dibuja el `background-color` ni el `border` que le
   pide la hoja de estilo. Los widgets que si lo hacen (`QFrame`, `QLabel`,
   `QPushButton`) tienen su propio dibujado; el `QWidget` base necesita que se
   le prenda el atributo a mano.

#### Solucion

```python
# 1) El dialogo acepta drops y al campo de texto se los apagamos
self.setAcceptDrops(True)
self.text_edit.setAcceptDrops(False)

# 2) El overlay necesita WA_StyledBackground para pintar fondo y borde
overlay = QtWidgets.QWidget(self)
overlay.setObjectName("DropOverlay")
overlay.setAttribute(Qt.WA_StyledBackground, True)
overlay.setStyleSheet(
    "QWidget#DropOverlay { background-color: rgba(28, 24, 40, 235);"
    " border: 2px dashed #774DCB; border-radius: 8px; }"
)
overlay.hide()
```

#### Notas

- El overlay es hijo del dialogo, asi que hay que reposicionarlo en
  `resizeEvent` con `setGeometry(self.rect())` y llamarle `raise_()` antes de
  `show()`, o queda tapado por los widgets que se agregaron despues.
- Validar las rutas en `dragEnterEvent` **y** en `dragMoveEvent`: si solo se
  acepta en el enter, Qt cancela el drop igual.
- `QDragLeaveEvent` no tiene `mimeData()`: en `dragLeaveEvent` solo se puede
  ocultar el cartel.
- Las rutas salen de `event.mimeData().urls()`, filtrando por
  `url.isLocalFile()` — un drag desde un navegador trae URLs remotas.

Ejemplo aplicado: `InputDialog` en
[LGA_NKS_Flow_Push.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py), el
dialogo de notas del Push, que acepta png/jpg arrastrados y los adjunta a la
nota de Flow.

---

## Referencias

- [LGA_import_shots.py](../LGA_NKS_Edit_Panel_py/LGA_import_shots.py) — clase
  `_ArrowComboBox`, constantes `_COMBO_BASE`, `_COMBO_STYLE_VARIANT_A`.
- [LGA_NKS_Panel_Style_Guide.md](LGA_NKS_Panel_Style_Guide.md) — guia general
  de estilos de paneles (colores, fuentes, bordes).
- [GUI_Windows_Reference.md](GUI_Windows_Reference.md) — referencias de
  ventanas y widgets utilizados en el proyecto.
- [LGA_NKS_Flow_Push.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py) — clase
  `InputDialog`, metodos `_create_drop_overlay`, `_media_paths_from_mime`,
  `dropEvent`, `add_dropped_images`.
