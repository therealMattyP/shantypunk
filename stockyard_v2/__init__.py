bl_info = {
    "name": "Shantypunk Stockyard v2.1",
    "author": "Matt / Shantypunk",
    "version": (0, 2, 1),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > Shantypunk",
    "description": "Generate deterministic multistory timber platforms with circulation hosts",
    "category": "Add Mesh",
}

from .stockyard_v2 import CLASSES


def register():
    import bpy

    for cls in CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Scene.stockyard_v2 = bpy.props.PointerProperty(
        type=next(cls for cls in CLASSES if cls.__name__ == "StockyardV2Properties")
    )


def unregister():
    import bpy

    if hasattr(bpy.types.Scene, "stockyard_v2"):
        del bpy.types.Scene.stockyard_v2

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
