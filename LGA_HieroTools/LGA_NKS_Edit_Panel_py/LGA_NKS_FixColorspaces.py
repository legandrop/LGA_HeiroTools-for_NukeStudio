"""
____________________________________________________________________

  LGA_NKS_FixColorspaces v1.10 | Lega

  Detecta clips con colorspace "rec709" o "gamma2.2"
  y cambia su color transform a "Output - Rec.709"
  (ahora busca en todos los clips del proyecto)
____________________________________________________________________

"""

import hiero.core

COLORSPACE_INVALIDO = ("rec709", "gamma2.2")
COLORSPACE_CORRECTO = "Output - Rec.709"


def extraer_colorspace_desde_read(clip):
    """Intenta obtener el valor del knob 'colorspace' del nodo Read."""
    try:
        read_node = clip.readNode()
        if read_node and "colorspace" in read_node.knobs():
            return read_node["colorspace"].value()
    except Exception:
        pass
    return None


def buscar_y_cambiar_clips_rec709_en_todos(proyecto, corregidos):
    """Recorre todos los clips del proyecto y corrige los que tengan colorspace 'rec709' o 'gamma2.2'."""
    for clip in proyecto.clips():
        colorspace = extraer_colorspace_desde_read(clip)
        if colorspace and colorspace.lower() in COLORSPACE_INVALIDO:
            try:
                clip.setSourceMediaColourTransform(COLORSPACE_CORRECTO)
                path = clip.mediaSource().firstpath()
                corregidos.append((clip.name(), path, colorspace))
            except Exception as e:
                print(f"⚠️ Error al cambiar el colorspace de {clip.name()}: {e}")


def corregir_clips_con_colorspace_rec709():
    proyectos = hiero.core.projects()
    if not proyectos:
        print("❌ No hay proyectos abiertos.")
        return

    corregidos = []

    for proyecto in proyectos:
        print(f"\n📁 Explorando proyecto: {proyecto.name()}")
        buscar_y_cambiar_clips_rec709_en_todos(proyecto, corregidos)

    if corregidos:
        print("\n🔧 Clips corregidos con nuevo colorspace:")
        for nombre, ruta, cs in corregidos:
            print(f" • {nombre} → {cs} ➡ {COLORSPACE_CORRECTO}\n   📍 {ruta}")
    else:
        print("✅ No se encontraron clips con colorspace 'rec709' o 'gamma2.2'.")


# Ejecutar
corregir_clips_con_colorspace_rec709()
