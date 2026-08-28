"""
____________________________________________________________________

  LGA_NKS_Viewer_Mask v1.32 | Lega

  Ajusta el overlay del viewer a un aspect ratio especifico, alterna los
  estilos de mascara entre None, Half y Full, y corre los burn-ins del
  track BurnIn para que la mascara no los tape.

  Segun el aspect ratio la barra cae en un eje distinto:
    - letterbox (aspect MAS ANCHO que la secuencia): barras arriba y abajo,
      y el texto Frame se sube en Y.
    - pillarbox (aspect MAS ANGOSTO): barras a los costados, y la caja de
      cada burn-in se achica en X por los dos lados. El texto justificado a
      la izquierda se corre a la derecha, el de la derecha se corre a la
      izquierda y el centrado se queda quieto, sin tener que saber cual es
      cual ni cuantos efectos hay.

  v1.32: Modo pillarbox para 3:2, que achica la caja de TODOS los burn-ins
         en vez de subir uno solo. La marca de estado ahora dice en que eje
         quedo corrido el burn-in, no solo si lo esta: con dos ejes en juego
         un solo bit deshacia el desplazamiento equivocado.
  v1.31: El ajuste del texto Frame ahora depende del aspect ratio.
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import nuke
import os


# Variable global para activar o desactivar los prints
DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


# ============================
# Configuracion de Variables
# ============================

# Definicion de estilos de mascara en orden de rotacion
MASK_STYLE_ORDER = [
    hiero.ui.Player.MaskOverlayStyle.eMaskOverlayNone,
    hiero.ui.Player.MaskOverlayStyle.eMaskOverlayHalf,
    hiero.ui.Player.MaskOverlayStyle.eMaskOverlayFull,
]

# Nombre del track a inspeccionar
TRACK_NAME = "BurnIn"

# Palabra clave para buscar el efecto en modo letterbox (sube uno solo)
EFFECT_NAME_SEARCH = "Frame"

# Propiedades del nodo del efecto
MAIN_TOGGLE_PROPERTY = "opacity"
BOX_PROPERTY = "box"

# La opacity del efecto se usa como MARCA de estado: dice si el burn-in esta
# en su lugar original y, si no lo esta, EN QUE EJE se lo movio. Son valores
# arbitrarios -la diferencia visual es despreciable-; lo que importa es poder
# distinguirlos al deshacer. Guardar el eje es lo que evita que un aspect
# ratio reste un desplazamiento que puso otro sobre el eje contrario.
MARK_BASE = 1.0        # el burn-in esta en su lugar
MARK_LETTERBOX = 0.9   # subido en Y
MARK_PILLARBOX = 0.8   # achicado en X por los dos lados

# Letterbox: cuanto se sube el texto Frame al entrar en Full.
BOX_INDEX_TO_MODIFY = 3        # el 't' de la tupla box = (x, y, r, t)
BOX_ADJUSTMENT_INITIAL = 350

# Pillarbox: px extra hacia adentro ademas del ancho de la barra.
PILLARBOX_MARGIN = 0

# Aspect ratio -> modo de mascara. El modo NO se deduce del numero a
# proposito: asi se puede forzar el comportamiento de un boton sin depender
# del format de la secuencia que este abierta.
MASK_MODE_BY_ASPECT = {
    "3:2": "pillarbox",
    "2.35:1": "letterbox",
    "2:1": "letterbox",
}
MASK_MODE_DEFAULT = "letterbox"

MARK_BY_MODE = {"letterbox": MARK_LETTERBOX, "pillarbox": MARK_PILLARBOX}
MODE_BY_MARK = {MARK_LETTERBOX: "letterbox", MARK_PILLARBOX: "pillarbox"}


# ============================
# Geometria de la mascara
# ============================

def aspect_to_float(aspect_ratio):
    """
    Convierte "3:2" o "2.35:1" al numero. Devuelve None si no se entiende.
    """
    try:
        if ":" in aspect_ratio:
            izquierda, derecha = aspect_ratio.split(":", 1)
            return float(izquierda) / float(derecha)
        return float(aspect_ratio)
    except Exception as e:
        debug_print(f"No se pudo interpretar el aspect ratio {aspect_ratio}: {e}")
        return None


def pillarbox_bar_width(seq, aspect_ratio):
    """
    Ancho en px de la barra lateral que deja la mascara sobre la secuencia.

    Devuelve 0 si el aspect es igual o mas ancho que la secuencia -ahi la
    mascara es letterbox y no hay barras a los costados- o si no se pudo
    medir el format.
    """
    valor = aspect_to_float(aspect_ratio)
    if not valor:
        return 0

    try:
        fmt = seq.format()
        ancho = float(fmt.width())
        alto = float(fmt.height())
    except Exception as e:
        debug_print(f"No se pudo leer el format de la secuencia: {e}")
        return 0

    if alto <= 0 or valor >= (ancho / alto):
        return 0

    return int(round((ancho - alto * valor) / 2.0)) + PILLARBOX_MARGIN


def aspecto_canonico(mode):
    """
    Un aspect ratio que representa a este modo, para poder deshacer un
    desplazamiento sin saber que boton lo dejo puesto.

    Asume que hay un solo aspect pillarbox configurado, que es el caso: si
    algun dia hay dos con barras de distinto ancho, el ancho a deshacer deja
    de ser deducible de la marca y hay que guardarlo en el efecto.
    """
    for aspecto, modo in MASK_MODE_BY_ASPECT.items():
        if modo == mode:
            return aspecto
    return None


def deltas_de_modo(seq, mode):
    """
    Desplazamiento del box para un modo, como {indice: delta}.
    Devuelve None si ese modo no mueve nada en esta secuencia.
    """
    if mode == "letterbox":
        return {BOX_INDEX_TO_MODIFY: BOX_ADJUSTMENT_INITIAL}

    if mode == "pillarbox":
        barra = pillarbox_bar_width(seq, aspecto_canonico("pillarbox"))
        if barra <= 0:
            debug_print("La mascara pillarbox no deja barras laterales en esta secuencia.")
            return None
        # x hacia la derecha y r hacia la izquierda: la caja se achica y cada
        # texto se corre hacia adentro segun su propia justificacion.
        return {0: barra, 2: -barra}

    debug_print(f"Modo de mascara no reconocido: {mode}")
    return None


# ============================
# Acceso al efecto
# ============================

def nodo_del_efecto(effect_item):
    """
    Devuelve el nodo del efecto si sirve para lo que hacemos, o None.
    """
    if not isinstance(effect_item, hiero.core.EffectTrackItem):
        return None

    try:
        node = effect_item.node()
    except Exception as e:
        debug_print(f"No se pudo obtener el nodo del efecto: {e}")
        return None

    if not node:
        return None

    try:
        knobs = node.knobs()
    except Exception as e:
        debug_print(f"No se pudieron leer los knobs del efecto: {e}")
        return None

    if MAIN_TOGGLE_PROPERTY not in knobs or BOX_PROPERTY not in knobs:
        debug_print("El efecto no tiene opacity y box: se saltea.")
        return None

    return node


def mover_box(node, deltas):
    """
    Aplica {indice: delta} sobre el box del nodo. True si escribio.
    """
    try:
        actual = node[BOX_PROPERTY].value()
    except Exception as e:
        debug_print(f"No se pudo leer el box: {e}")
        return False

    if not isinstance(actual, (tuple, list)) or len(actual) < 4:
        debug_print(f"El box no tiene el formato esperado: {actual}")
        return False

    nuevo = list(actual)
    for indice, delta in deltas.items():
        nuevo[indice] += delta

    try:
        node[BOX_PROPERTY].setValue(tuple(nuevo))
    except Exception as e:
        debug_print(f"No se pudo escribir el box: {e}")
        return False

    debug_print(f"  box {tuple(actual)} -> {tuple(nuevo)}")
    return True


def toggle_burnin_effect(effect_item, new_mask_style, mode, seq, aplicar=True):
    """
    Deja el burn-in corrido o en su lugar segun el estilo de mascara nuevo.

    Con aplicar=False el efecto nunca se corre, pero SI se le deshace lo que
    tenga puesto de antes. Deshacer tiene que barrer todos los efectos del
    track aunque el modo actual mueva uno solo: si no, los que ese modo no
    mira se quedan corridos con la mascara apagada.

    Deshacer lee la MARCA -no el modo que se pide ahora-, asi que siempre
    revierte el desplazamiento que de verdad se aplico, aunque lo haya
    dejado puesto otro aspect ratio sobre el otro eje.
    """
    node = nodo_del_efecto(effect_item)
    if not node:
        return False

    try:
        marca = node[MAIN_TOGGLE_PROPERTY].value()
    except Exception as e:
        debug_print(f"No se pudo leer la opacity: {e}")
        return False

    quiere_correr = (new_mask_style == hiero.ui.Player.MaskOverlayStyle.eMaskOverlayFull)
    quiere_correr = quiere_correr and aplicar
    marca_destino = MARK_BY_MODE.get(mode) if quiere_correr else MARK_BASE

    if marca == marca_destino:
        debug_print(f"  ya esta en el estado pedido (marca {marca}).")
        return False

    escribio = False

    # 1) Deshacer el desplazamiento viejo, sea del eje que sea.
    if marca != MARK_BASE:
        modo_viejo = MODE_BY_MARK.get(marca)
        deltas_viejos = deltas_de_modo(seq, modo_viejo) if modo_viejo else None
        if deltas_viejos:
            debug_print(f"  deshaciendo desplazamiento previo ({modo_viejo})")
            if mover_box(node, {i: -d for i, d in deltas_viejos.items()}):
                escribio = True
        else:
            debug_print(f"  marca {marca} desconocida: no se deshace nada.")

    # 2) Aplicar el desplazamiento nuevo si corresponde.
    if quiere_correr:
        deltas_nuevos = deltas_de_modo(seq, mode)
        if not deltas_nuevos:
            marca_destino = MARK_BASE
        else:
            debug_print(f"  aplicando desplazamiento ({mode})")
            if mover_box(node, deltas_nuevos):
                escribio = True
            else:
                marca_destino = MARK_BASE

    # 3) Dejar la marca coherente con lo que quedo en el box.
    try:
        if node[MAIN_TOGGLE_PROPERTY].value() != marca_destino:
            node[MAIN_TOGGLE_PROPERTY].setValue(marca_destino)
            debug_print(f"  marca {marca} -> {marca_destino}")
            escribio = True
    except Exception as e:
        debug_print(f"No se pudo escribir la opacity: {e}")

    return escribio


# ============================
# Funciones Principales
# ============================

def rotate_overlay_style(viewer):
    """
    Rota el estilo de mascara del viewer al siguiente en el orden definido.
    """
    current_style = viewer.maskOverlayStyle()
    try:
        current_index = MASK_STYLE_ORDER.index(current_style)
        next_index = (current_index + 1) % len(MASK_STYLE_ORDER)
        new_style = MASK_STYLE_ORDER[next_index]
    except ValueError:
        # Si el estilo actual no esta en la lista, comenzar desde el principio
        new_style = MASK_STYLE_ORDER[0]

    return new_style


def efectos_del_track(seq, track_name):
    """
    Lista los EffectTrackItem del track pedido, en orden.
    """
    destino = None
    for track in seq.videoTracks():
        if track.name() == track_name:
            destino = track
            break

    if not destino:
        debug_print(f"No se encontro el track {track_name}.")
        return []

    try:
        filas = destino.subTrackItems()
    except Exception as e:
        debug_print(f"No se pudieron leer los subTrackItems: {e}")
        return []

    efectos = []
    for fila in filas:
        for item in fila:
            if isinstance(item, hiero.core.EffectTrackItem):
                efectos.append(item)

    return efectos


def main(aspect_ratio="3:2"):
    """
    Aplica el aspect ratio al viewer, rota el estilo de mascara y corre los
    burn-ins para que la mascara no los tape.

    Args:
        aspect_ratio (str): El aspect ratio a aplicar al viewer (ej: "3:2")
    """
    viewer = hiero.ui.currentViewer()
    if viewer is None:
        debug_print("No se pudo obtener el viewer actual.")
        return

    try:
        new_style = rotate_overlay_style(viewer)
        viewer.setMaskOverlayStyle(new_style)
        viewer.setMaskOverlayFromRemote(aspect_ratio)
        debug_print(f"Estilo de mascara nuevo: {new_style} | aspecto: {aspect_ratio}")
    except AttributeError as e:
        debug_print(f"Error al manipular el viewer: {e}")
        return

    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No hay secuencia activa: no se mueven los burn-ins.")
        return

    mode = MASK_MODE_BY_ASPECT.get(aspect_ratio, MASK_MODE_DEFAULT)
    efectos = efectos_del_track(seq, TRACK_NAME)
    if not efectos:
        debug_print(f"El track {TRACK_NAME} no tiene efectos.")
        return

    if mode == "pillarbox":
        # Las barras van a los costados y pueden tapar cualquiera de los
        # burn-ins, no solo el Frame: se achica la caja de todos.
        objetivo = list(efectos)
    else:
        # Letterbox: la barra de abajo tapa el Frame, que es el unico que se
        # sube. Se conserva el comportamiento historico.
        objetivo = []
        for efecto in efectos:
            try:
                nombre = efecto.name()
            except Exception:
                continue
            if EFFECT_NAME_SEARCH in nombre:
                objetivo = [efecto]
                break
        if not objetivo:
            debug_print("No se encontro ningun efecto con Frame en el nombre.")

    # Se recorren TODOS los efectos del track, no solo los que este modo
    # corre: a los demas hay que deshacerles lo que les haya dejado puesto
    # otro modo, o se quedan corridos con la mascara apagada.
    debug_print(f"Modo {mode}: se corren {len(objetivo)} de {len(efectos)} efectos del track.")
    for efecto in efectos:
        try:
            debug_print(f"Efecto: {efecto.name()}")
        except Exception:
            debug_print("Efecto: <sin nombre>")
        toggle_burnin_effect(efecto, new_style, mode, seq, efecto in objetivo)


# Ejecutar el script principal
if __name__ == "__main__":
    main("3:2")
