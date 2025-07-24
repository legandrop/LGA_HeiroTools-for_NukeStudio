# _________________________________________________
#
#   LGA_BuscarClipsRec709_Hiero v1.0
#   Busca clips que tienen colorspace "rec709"
#   en el Read node de cada mediaSource del bin.
# _________________________________________________

import hiero.core


def extraer_colorspace_desde_read(clip):
    """Intenta obtener el valor del knob 'colorspace' del nodo Read."""
    try:
        read_node = clip.readNode()
        if read_node and "colorspace" in read_node.knobs():
            return read_node["colorspace"].value()
    except Exception as e:
        pass
    return None


def buscar_clips_rec709_en_bin(bin_obj, encontrados):
    """Recorre recursivamente un bin y busca clips con colorspace 'rec709'."""
    for item in bin_obj.items():
        if isinstance(item, hiero.core.Bin):
            buscar_clips_rec709_en_bin(item, encontrados)
        elif isinstance(item, hiero.core.BinItem):
            clip = item.activeItem()
            if isinstance(clip, hiero.core.Clip):
                colorspace = extraer_colorspace_desde_read(clip)
                if colorspace and colorspace.lower() == "rec709":
                    try:
                        path = clip.mediaSource().firstpath()
                    except Exception:
                        path = "(sin path disponible)"
                    encontrados.append((clip.name(), path, colorspace))


def listar_clips_con_colorspace_rec709():
    proyectos = hiero.core.projects()
    if not proyectos:
        print("❌ No hay proyectos abiertos.")
        return

    encontrados = []

    for proyecto in proyectos:
        print(f"\n📁 Explorando proyecto: {proyecto.name()}")
        buscar_clips_rec709_en_bin(proyecto.clipsBin(), encontrados)

    if encontrados:
        print("\n🎯 Clips con colorspace 'rec709' encontrados:")
        for nombre, ruta, cs in encontrados:
            print(f" • {nombre} → {cs}\n   📍 {ruta}")
    else:
        print("✅ No se encontraron clips con colorspace 'rec709'.")


# Ejecutar
listar_clips_con_colorspace_rec709()
