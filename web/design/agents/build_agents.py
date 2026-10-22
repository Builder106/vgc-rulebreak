"""Build the three study agents as original toy-robot coaches in Blender.

Run inside Blender (the Blender MCP executes it with exec). It builds the
scene "vgc-agents" without touching any other scene, and each agent wears a
honeycomb rack of hex cells, one per maximum Protect PP:

- SourceAgent: Scarlet/Violet rules, 16 lit cells, stocky amber body.
- AdaptedAgent: the source body refitted with native parts; 16 sockets, 8 lit, 8 capped.
- NativeAgent: Champions rules, 8 lit cells, slender lavender body.

Units are meters with the origin at each agent's feet.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

SCENE = "vgc-agents"
PREFIX = "agent-"
CELL_RADIUS = 0.034
CELL_LAYOUT = CELL_RADIUS * 1.12
SQRT3 = math.sqrt(3)


def linear(hex_color: str) -> tuple[float, float, float, float]:
    """Convert an sRGB hex color to linear RGBA for Principled BSDF."""
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    out = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return (*out, 1.0)


def material(name: str, color: str, roughness: float = 0.45, emission: float = 0.0, metallic: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.get(PREFIX + name) or bpy.data.materials.new(PREFIX + name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = linear(color)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Coat Weight"].default_value = 0.25
    bsdf.inputs["Coat Roughness"].default_value = 0.2
    if emission:
        bsdf.inputs["Emission Color"].default_value = linear(color)
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def reset_scene() -> tuple[bpy.types.Scene, bpy.types.Collection]:
    old = bpy.data.scenes.get(SCENE)
    if old:
        for obj in list(old.collection.all_objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(old)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.worlds):
        for item in list(block):
            if item.name.startswith(PREFIX) and item.users == 0:
                block.remove(item)
    scene = bpy.data.scenes.new(SCENE)
    return scene, scene.collection


def finish(name: str, bm: bmesh.types.BMesh, mat: bpy.types.Material, parent: bpy.types.Object, loc, smooth: bool = True) -> bpy.types.Object:
    me = bpy.data.meshes.new(PREFIX + name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    me.materials.append(mat)
    obj = bpy.data.objects.new(PREFIX + name, me)
    parent.users_collection[0].objects.link(obj)
    obj.parent = parent
    obj.location = loc
    return obj


def rounded_box(name, size, loc, mat, parent, roundness=0.35, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    obj = finish(name, bm, mat, parent, loc)
    obj.rotation_euler = rot
    bevel = obj.modifiers.new("bevel", "BEVEL")
    bevel.width = roundness * min(size)
    bevel.segments = 4
    bevel.limit_method = "NONE"
    sub = obj.modifiers.new("soften", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    return obj


def ellipsoid(name, size, loc, mat, parent, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=0.5)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    obj = finish(name, bm, mat, parent, loc)
    obj.rotation_euler = rot
    return obj


def hex_cell(name, radius, depth, loc, mat, parent):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=radius, radius2=radius, depth=depth)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(30), 3, "Y"))
    obj = finish(name, bm, mat, parent, loc, smooth=False)
    bevel = obj.modifiers.new("bevel", "BEVEL")
    bevel.width = radius * 0.18
    bevel.segments = 2
    return obj


def honeycomb_size(rows: int, cols: int) -> tuple[float, float]:
    """Width and height of a pointy-top honeycomb of hex cells."""
    pitch = SQRT3 * CELL_LAYOUT
    width = pitch * (cols - 1) + (pitch / 2 if rows > 1 else 0) + 2 * CELL_RADIUS
    height = 1.5 * CELL_LAYOUT * (rows - 1) + 2 * CELL_RADIUS
    return width, height


def honeycomb(prefix, parent, center, rows, cols, lit, mats):
    """Pointy-top honeycomb rack, one cell per maximum Protect PP, lit cells first from the top."""
    pitch = SQRT3 * CELL_LAYOUT
    width, height = honeycomb_size(rows, cols)
    index = 0
    for row in range(rows):
        offset = pitch / 2 if row % 2 else 0
        for col in range(cols):
            x = center[0] - width / 2 + CELL_RADIUS + col * pitch + offset
            z = center[2] + height / 2 - CELL_RADIUS - row * 1.5 * CELL_LAYOUT
            mat = mats["lit"] if index < lit else mats["capped"]
            hex_cell(f"{prefix}-cell-{index:02d}", CELL_RADIUS, 0.02, (x, center[1], z), mat, parent)
            index += 1


def build_agent(collection, name, x, spec, mats):
    root = bpy.data.objects.new(PREFIX + name, None)
    collection.objects.link(root)
    root.location = (x, 0, 0)
    s = spec
    body, trim = mats[s["body"]], mats[s["trim"]]
    arm_left = mats[s.get("arm_left", s["body"])]

    leg_h = s["leg_h"]
    pelvis_z = leg_h + 0.06
    torso_z = pelvis_z + 0.06 + s["torso"][2] / 2
    head_z = torso_z + s["torso"][2] / 2 + 0.05 + s["head"][2] / 2

    for side in (-1, 1):
        rounded_box(f"{name}-foot-{side}", (0.15, 0.22, 0.08), (side * s["hip"], -0.03, 0.04), trim, root, 0.45)
        ellipsoid(f"{name}-leg-{side}", (0.11, 0.11, leg_h), (side * s["hip"], 0, 0.06 + leg_h / 2), body, root)
    rounded_box(f"{name}-pelvis", (s["torso"][0] * 0.8, s["torso"][1] * 0.85, 0.12), (0, 0, pelvis_z), trim, root, 0.4)
    rounded_box(f"{name}-torso", s["torso"], (0, 0, torso_z), body, root, s["round"])

    shoulder_x = s["torso"][0] / 2 + 0.06
    shoulder_z = torso_z + s["torso"][2] * 0.32
    for side in (-1, 1):
        mat = arm_left if side < 0 else body
        swing = math.radians(s["arm_swing"][0 if side < 0 else 1])
        shoulder = bpy.data.objects.new(f"{PREFIX}{name}-shoulder-{side}", None)
        collection.objects.link(shoulder)
        shoulder.parent = root
        shoulder.location = (side * shoulder_x, 0, shoulder_z)
        shoulder.rotation_euler = (0, -side * swing, 0)
        ellipsoid(f"{name}-arm-{side}", (0.1, 0.1, s["arm_h"]), (0, 0, -s["arm_h"] / 2 + 0.03), mat, shoulder)
        ellipsoid(f"{name}-hand-{side}", (0.12, 0.12, 0.12), (0, 0, -s["arm_h"] + 0.02), trim, shoulder)

    neck_z = head_z - s["head"][2] / 2 - 0.02
    rounded_box(f"{name}-neck", (0.12, 0.1, 0.08), (0, 0, neck_z), trim, root, 0.45)
    head = bpy.data.objects.new(f"{PREFIX}{name}-head-pivot", None)
    collection.objects.link(head)
    head.parent = root
    head.location = (0, 0, neck_z)
    head.rotation_euler = tuple(math.radians(a) for a in s["head_tilt"])
    hz = head_z - neck_z
    rounded_box(f"{name}-head", s["head"], (0, 0, hz), body, head, s["round"])
    face_y = -s["head"][1] / 2
    rounded_box(f"{name}-visor", (s["head"][0] * 0.8, 0.05, s["head"][2] * 0.5), (0, face_y + 0.005, hz - 0.005), mats["visor"], head, 0.45)
    for side, style in zip((-1, 1), s["eyes"]):
        loc = (side * 0.075, face_y - 0.024, hz)
        if style == "bar":
            ellipsoid(f"{name}-eye-{side}", (0.085, 0.02, 0.026), loc, mats[s["eye_mat"]], head)
        else:
            hex_cell(f"{name}-eye-{side}", 0.032, 0.02, loc, mats["lime"], head)

    if s.get("headset"):
        for side in (-1, 1):
            rounded_box(f"{name}-ear-{side}", (0.06, 0.15, 0.15), (side * (s["head"][0] / 2 + 0.02), 0, hz), trim, head, 0.5)
    if s.get("antenna"):
        top = hz + s["head"][2] / 2
        ellipsoid(f"{name}-antenna-stalk", (0.022, 0.022, 0.12), (0, 0, top + 0.05), trim, head)
        hex_cell(f"{name}-antenna-tip", 0.04, 0.025, (0, 0, top + 0.13), mats["lime"], head)

    rows, cols = s["rack"]
    grid_w, grid_h = honeycomb_size(rows, cols)
    rack_z = torso_z + s["torso"][2] * 0.08
    rack_y = -s["torso"][1] / 2 - 0.01
    rounded_box(f"{name}-rack", (grid_w + 0.05, 0.03, grid_h + 0.05), (0, rack_y, rack_z), mats["rack"], root, 0.3)
    honeycomb(name, root, (0, rack_y - 0.02, rack_z), rows, cols, s["lit"], {"lit": mats[s["cells"]], "capped": mats["capped"]})
    return root


SPECS = {
    "source": {
        "body": "amber", "trim": "violet", "eye_mat": "amber_glow", "eyes": ("bar", "bar"), "cells": "amber_glow",
        "torso": (0.5, 0.32, 0.44), "head": (0.42, 0.34, 0.32), "round": 0.32,
        "leg_h": 0.24, "arm_h": 0.36, "hip": 0.12, "headset": True,
        "head_tilt": (8, 0, 4), "arm_swing": (10, 14),
        "rack": (4, 4), "lit": 16,
    },
    "adapted": {
        "body": "amber", "trim": "indigo", "arm_left": "lavender", "eye_mat": "amber_glow", "eyes": ("bar", "hex"), "cells": "cyan_glow",
        "torso": (0.5, 0.32, 0.44), "head": (0.42, 0.34, 0.32), "round": 0.32,
        "leg_h": 0.24, "arm_h": 0.36, "hip": 0.12, "headset": True, "antenna": True,
        "head_tilt": (0, -10, 0), "arm_swing": (14, 8),
        "rack": (4, 4), "lit": 8,
    },
    "native": {
        "body": "lavender", "trim": "indigo", "eye_mat": "lime", "eyes": ("hex", "hex"), "cells": "cyan_glow",
        "torso": (0.4, 0.27, 0.48), "head": (0.36, 0.32, 0.32), "round": 0.45,
        "leg_h": 0.34, "arm_h": 0.42, "hip": 0.1, "antenna": True,
        "head_tilt": (-6, 0, -6), "arm_swing": (6, 6),
        "rack": (2, 4), "lit": 8,
    },
}


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def area_light(collection, name, loc, target, power, size, color="#FFFFFF"):
    light = bpy.data.lights.new(PREFIX + name, "AREA")
    light.energy = power
    light.size = size
    light.color = linear(color)[:3]
    obj = bpy.data.objects.new(PREFIX + name, light)
    collection.objects.link(obj)
    obj.location = loc
    look_at(obj, target)
    return obj


def build() -> dict:
    scene, collection = reset_scene()
    mats = {
        "amber": material("amber", "#E8823A", 0.42),
        "violet": material("violet", "#4B2E8C", 0.5),
        "lavender": material("lavender", "#E4E1FF", 0.35),
        "indigo": material("indigo", "#2B2670", 0.45),
        "visor": material("visor", "#0E0C24", 0.12),
        "rack": material("rack", "#1A1740", 0.5),
        "capped": material("capped", "#3A3650", 0.6),
        "amber_glow": material("amber-glow", "#FF9F2E", 0.3, emission=0.9),
        "cyan_glow": material("cyan-glow", "#45D6EE", 0.3, emission=0.9),
        "lime": material("lime", "#C8F031", 0.3, emission=0.8),
    }
    order = [("source", -0.82), ("adapted", 0.0), ("native", 0.82)]
    for name, x in order:
        build_agent(collection, f"{name}", x, SPECS[name], mats)

    cam_data = bpy.data.cameras.new(PREFIX + "camera")
    cam_data.lens = 50
    cam = bpy.data.objects.new(PREFIX + "camera", cam_data)
    collection.objects.link(cam)
    cam.location = (0.9, -3.9, 1.35)
    look_at(cam, (0, 0, 0.62))
    scene.camera = cam

    area_light(collection, "key", (-2.2, -2.6, 2.8), (0, 0, 0.7), 420, 2.0)
    area_light(collection, "fill", (2.6, -2.0, 1.4), (0, 0, 0.6), 160, 2.5, "#B9B4FF")
    area_light(collection, "rim", (0.4, 2.4, 2.2), (0, 0, 0.8), 380, 1.5, "#6FE0F0")

    world = bpy.data.worlds.new(PREFIX + "world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = linear("#1E1A4D")
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = world

    floor_mesh = bpy.data.meshes.new(PREFIX + "floor")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=12.0)
    bm.to_mesh(floor_mesh)
    bm.free()
    floor = bpy.data.objects.new(PREFIX + "floor", floor_mesh)
    collection.objects.link(floor)
    floor.is_shadow_catcher = True

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.unit_settings.system = "METRIC"
    return {"scene": scene.name, "objects": len(collection.all_objects)}


AGENT_X = {"source": -0.82, "adapted": 0.0, "native": 0.82}


def render_all(out_dir: str) -> list[str]:
    """Render the lineup and one portrait per agent, then save this scene alone as agents.blend."""
    scene = bpy.data.scenes[SCENE]
    cam = scene.camera
    roots = {name: bpy.data.objects[PREFIX + name] for name in AGENT_X}
    written = []

    def shoot(filename, width, height):
        scene.render.resolution_x, scene.render.resolution_y = width, height
        scene.render.resolution_percentage = 100
        scene.render.filepath = f"{out_dir}/{filename}"
        bpy.ops.render.render(write_still=True, scene=SCENE)
        written.append(filename)

    shoot("agents-lineup.png", 1800, 1100)
    for name, x in AGENT_X.items():
        for other, root in roots.items():
            for obj in [root, *root.children_recursive]:
                obj.hide_render = other != name
        cam.location = (x + 0.45, -2.7, 1.1)
        look_at(cam, (x, 0, 0.66))
        shoot(f"agent-{name}.png", 900, 1200)
    for root in roots.values():
        for obj in [root, *root.children_recursive]:
            obj.hide_render = False
    cam.location = (0.9, -3.9, 1.35)
    look_at(cam, (0, 0, 0.62))
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1100

    bpy.data.libraries.write(f"{out_dir}/agents.blend", {scene}, path_remap="NONE", compress=True)
    written.append("agents.blend")
    return written


result = build()
