"""
Script de exploración para investigar los métodos disponibles en el viewer de Hiero
"""

import hiero.core
import hiero.ui


def explore_viewer():
    """
    Explora todos los métodos y atributos disponibles en el viewer actual
    """
    print("=== EXPLORACIÓN DEL VIEWER DE HIERO ===")

    viewer = hiero.ui.currentViewer()
    if not viewer:
        print("❌ No hay viewer activo")
        return

    print(f"Tipo del viewer: {type(viewer)}")
    print(f"Clase del viewer: {viewer.__class__}")

    # Explorar todos los métodos y atributos del viewer
    print("\n=== MÉTODOS Y ATRIBUTOS DEL VIEWER ===")
    all_attributes = dir(viewer)

    # Filtrar métodos que podrían estar relacionados con refresh/update
    refresh_methods = []
    update_methods = []
    repaint_methods = []

    for attr in sorted(all_attributes):
        if not attr.startswith("_"):  # Ignorar métodos privados
            print(f"- {attr}")

            # Buscar métodos relacionados con refresh
            if "refresh" in attr.lower():
                refresh_methods.append(attr)
            elif "update" in attr.lower():
                update_methods.append(attr)
            elif "repaint" in attr.lower() or "paint" in attr.lower():
                repaint_methods.append(attr)

    print(f"\n=== MÉTODOS RELACIONADOS CON REFRESH ===")
    for method in refresh_methods:
        print(f"- {method}")

    print(f"\n=== MÉTODOS RELACIONADOS CON UPDATE ===")
    for method in update_methods:
        print(f"- {method}")

    print(f"\n=== MÉTODOS RELACIONADOS CON REPAINT ===")
    for method in repaint_methods:
        print(f"- {method}")

    # Explorar el player si existe
    print("\n=== EXPLORACIÓN DEL PLAYER ===")
    try:
        player = viewer.player()
        if player:
            print(f"Tipo del player: {type(player)}")
            print(f"Clase del player: {player.__class__}")

            print("\n=== MÉTODOS Y ATRIBUTOS DEL PLAYER ===")
            player_attributes = dir(player)

            player_refresh_methods = []
            player_update_methods = []

            for attr in sorted(player_attributes):
                if not attr.startswith("_"):
                    print(f"- {attr}")

                    if "refresh" in attr.lower():
                        player_refresh_methods.append(attr)
                    elif "update" in attr.lower():
                        player_update_methods.append(attr)

            print(f"\n=== PLAYER - MÉTODOS RELACIONADOS CON REFRESH ===")
            for method in player_refresh_methods:
                print(f"- {method}")

            print(f"\n=== PLAYER - MÉTODOS RELACIONADOS CON UPDATE ===")
            for method in player_update_methods:
                print(f"- {method}")
        else:
            print("❌ No se pudo obtener el player del viewer")
    except Exception as e:
        print(f"❌ Error explorando el player: {e}")

    # Explorar métodos globales de hiero.ui
    print("\n=== MÉTODOS GLOBALES DE HIERO.UI RELACIONADOS CON VIEWER ===")
    hiero_ui_attributes = dir(hiero.ui)

    for attr in sorted(hiero_ui_attributes):
        if (
            "viewer" in attr.lower()
            or "refresh" in attr.lower()
            or "update" in attr.lower()
            or "flush" in attr.lower()
        ):
            print(f"- hiero.ui.{attr}")


if __name__ == "__main__":
    explore_viewer()
