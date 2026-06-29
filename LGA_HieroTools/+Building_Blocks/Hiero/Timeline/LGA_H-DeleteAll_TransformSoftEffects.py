#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
____________________________________________________________________

  LGA_H-DeleteAll_TransformSoftEffects | Lega

  Recorre TODOS los video tracks de la secuencia activa y BORRA todos
  los soft effects de tipo Transform (node.Class() == "Transform").

  Un soft effect es un hiero.core.EffectTrackItem y vive en
  track.subTrackItems(). Se elimina con track.removeSubTrackItem(item).
  Todo el borrado queda como un solo undo (Ctrl+Z para revertir).

  Nota: la API de Hiero NO permite seleccionar soft effects por codigo
  (setSelection solo acepta TrackItem), por eso se borran directo en
  vez de seleccionarlos primero.
____________________________________________________________________

"""

import hiero.core
import hiero.ui

# Clases de nodo consideradas "Transform". Ajustar si hiciera falta.
TRANSFORM_CLASSES = ("Transform",)


def collect_transform_soft_effects(seq):
    """Devuelve (track, effect) para cada Transform soft effect del timeline."""
    found = []
    for track in seq.videoTracks():
        for group in track.subTrackItems():
            for effect in group:
                if not isinstance(effect, hiero.core.EffectTrackItem):
                    continue
                node = effect.node()
                if node and node.Class() in TRANSFORM_CLASSES:
                    found.append((track, effect))
    return found


def delete_all_transform_soft_effects():
    seq = hiero.ui.activeSequence()
    if not seq:
        print("No hay una secuencia activa.")
        return

    targets = collect_transform_soft_effects(seq)
    if not targets:
        print("No se encontraron soft effects Transform en el timeline.")
        return

    print("Se encontraron %d soft effect(s) Transform para borrar:" % len(targets))
    for track, effect in targets:
        print("  [%s] %s (frame %s)" % (track.name(), effect.name(), effect.timelineIn()))

    project = seq.project()
    deleted = 0
    errors = 0
    # IMPORTANTE: el Transform esta linkeado al clip. removeSubTrackItem por
    # defecto borra los items linkeados (borraria el CLIP). Hay que pasar
    # eDontRemoveLinkedItems para eliminar SOLO el soft effect.
    dont_remove_linked = hiero.core.TrackBase.RemoveItemOptions.eDontRemoveLinkedItems

    with project.beginUndo("Delete All Transform Soft Effects"):
        for track, effect in targets:
            name = effect.name()
            try:
                track.removeSubTrackItem(effect, dont_remove_linked)
                deleted += 1
            except Exception as e:
                errors += 1
                print("  ERROR borrando %s: %s" % (name, e))

    print("\nListo. Borrados: %d  |  Errores: %d" % (deleted, errors))


if __name__ == "__main__":
    delete_all_transform_soft_effects()
