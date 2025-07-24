# _________________________________________________
#
#   LGA_FixRec709Clips_Hiero v1.2
#   Detecta clips con colorspace "rec709" o "gamma2.2"
#   y cambia su color transform a "Output - Rec.709"
# _________________________________________________

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


def buscar_y_cambiar_clips_rec709(bin_obj, corregidos):
    """Recorre recursivamente un bin, detecta clips con colorspace 'rec709' y los corrige."""
    for item in bin_obj.items():
        if isinstance(item, hiero.core.Bin):
            buscar_y_cambiar_clips_rec709(item, corregidos)
        elif isinstance(item, hiero.core.BinItem):
            clip = item.activeItem()
            if isinstance(clip, hiero.core.Clip):
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
        buscar_y_cambiar_clips_rec709(proyecto.clipsBin(), corregidos)

    if corregidos:
        print("\n🔧 Clips corregidos con nuevo colorspace:")
        for nombre, ruta, cs in corregidos:
            print(f" • {nombre} → {cs} ➡ {COLORSPACE_CORRECTO}\n   📍 {ruta}")
    else:
        print("✅ No se encontraron clips con colorspace 'rec709' o 'gamma2.2'.")


# Ejecutar
corregir_clips_con_colorspace_rec709()
