# Builds the floodlit stadium from scratch, in metres (the other models use 36 mm units):
#   blender --python assets-src/3d/stadium.py
# then, in Blender's Python console, export() writes stadium.glb and posters() renders the night
# and day posters into the web app; save the file as stadium.blend. The ground, pitch, creases and
# stumps follow the Laws' sizes; the stands and floodlights are a generic oval stadium, not any
# real ground.

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
scene.name = "Stadium"


def srgb(h):
    c = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def material(name, color, rough=0.8, metal=0.0, emit=None):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*srgb(color), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        # Exported as the lamps' emissive colour; the site turns them on at night.
        b.inputs["Emission Color"].default_value = (*srgb(emit), 1)
        b.inputs["Emission Strength"].default_value = 1.0
    return m


M = {
    "grass_a": material("GrassLight", "#4a9444", 0.9),
    "grass_b": material("GrassDark", "#3b8138", 0.9),
    "pitch": material("Pitch", "#cdb98e", 0.95),
    "chalk": material("Chalk", "#f4f4f0", 0.7),
    "rope": material("Rope", "#ece6d2", 0.6),
    "concrete": material("Concrete", "#8f969e", 0.9),
    "concourse": material("Concourse", "#4a525c", 0.95),
    "facade": material("Facade", "#5b6672", 0.8),
    "stand_low": material("StandLower", "#3b4758", 0.85),
    "stand_mid": material("StandMiddle", "#2c6e8e", 0.8),
    "stand_top": material("StandUpper", "#26384c", 0.85),
    "roof": material("Roof", "#d9dde2", 0.5, 0.2),
    "steel": material("Steel", "#7d858e", 0.45, 0.7),
    "lamp": material("Floodlamp", "#eef2fb", 0.3, 0.0, "#f6f8ff"),
    "ribbon": material("Ribbon", "#2f7d5c", 0.4, 0.0, "#4fd59a"),
    "screen": material("SightScreen", "#f2f2ee", 0.8),
    "willow": material("Stumps", "#efe2c4", 0.5),
    "leather": material("Ball", "#b3121f", 0.35),
}


def mesh_object(name, bm, mats, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth:
        me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    return o


def box(name, size, loc, m):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    o = mesh_object(name, bm, [m])
    o.location = loc
    return o


def lathe(name, profile, m, steps=96, sx=1.0, sy=1.0, start=0.0, sweep=2 * math.pi, riser=None):
    """Turns a (radius, height) profile around the middle, squashed to the oval by sx, sy.
    With `riser`, the vertical faces (the steps' fronts) take that material."""
    closed = abs(sweep - 2 * math.pi) < 1e-6
    bm = bmesh.new()
    n = steps if closed else steps + 1
    rings = []
    for i in range(n):
        a = start + sweep * i / steps
        rings.append(
            [bm.verts.new((r * math.cos(a) * sx, r * math.sin(a) * sy, z)) for r, z in profile]
        )
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(len(profile) - 1):
            bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if riser:
        bm.normal_update()
        for f in bm.faces:
            f.material_index = 1 if abs(f.normal.z) < 0.5 else 0
        return mesh_object(name, bm, [m, riser])
    return mesh_object(name, bm, [m])


# The outfield: an oval with mowing stripes across the pitch.
RX, RY = 78.0, 72.0
STRIPE = 6.0
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=128, radius=1.0)
for v in bm.verts:
    v.co.x *= RX
    v.co.y *= RY
bmesh.ops.triangulate(bm, faces=bm.faces[:])
x = -RX + STRIPE
while x < RX:
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(x, 0, 0), plane_no=(1, 0, 0))
    x += STRIPE
for f in bm.faces:
    f.material_index = math.floor((f.calc_center_median().x + RX) / STRIPE) % 2
mesh_object("Outfield", bm, [M["grass_a"], M["grass_b"]])

# The pitch runs along Y: 20.12 m between the stumps, 3.05 m wide, the cut strip a little longer.
box("Pitch", (3.2, 24.0, 0.02), (0, 0, 0.01), M["pitch"])
for sign, end in ((1, "N"), (-1, "S")):
    y0 = sign * 10.06
    for part, size, loc in (
        ("Bowling", (2.64, 0.05, 0.01), (0, y0, 0.025)),
        ("Popping", (3.66, 0.05, 0.01), (0, y0 - sign * 1.22, 0.025)),
        ("ReturnL", (0.05, 2.44, 0.01), (-1.32, y0, 0.025)),
        ("ReturnR", (0.05, 2.44, 0.01), (1.32, y0, 0.025)),
    ):
        box(f"Crease{part}{end}", size, loc, M["chalk"])

# The boundary rope: a thin tube around the oval.
bm = bmesh.new()
SEG, SIDES, R = 160, 6, 0.16
rings = []
for i in range(SEG):
    a = 2 * math.pi * i / SEG
    centre = Vector((66.0 * math.cos(a), 61.0 * math.sin(a), R))
    out = Vector((math.cos(a), math.sin(a), 0)).normalized()
    rings.append(
        [
            bm.verts.new(
                centre
                + out * R * math.cos(2 * math.pi * k / SIDES)
                + Vector((0, 0, R * math.sin(2 * math.pi * k / SIDES)))
            )
            for k in range(SIDES)
        ]
    )
for i in range(SEG):
    a, b = rings[i], rings[(i + 1) % SEG]
    for k in range(SIDES):
        bm.faces.new((a[k], b[k], b[(k + 1) % SIDES], a[(k + 1) % SIDES]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
mesh_object("Boundary", bm, [M["rope"]], smooth=True)

# The stands: three stepped tiers turned around the ground, then roofs over the two side stands.
SY = 0.93


def steps(r0, z0, r1, z1, rows):
    """The rows of a tier rising from (r0, z0) to (r1, z1): a riser up, then a tread out."""
    pts = []
    for k in range(rows):
        r = r0 + (r1 - r0) * (k + 1) / rows
        z = z0 + (z1 - z0) * (k + 1) / rows
        pts += [(r - (r1 - r0) / rows, z), (r, z)]
    return pts


RISE = M["concrete"]
lathe("Apron", [(RX - 0.5, 0.005), (80.5, 0.005)], M["concrete"], sy=SY)
lathe("Concourse", [(110, 0.0), (128, 0.0)], M["concourse"], sy=SY)
lower = [(80, 0), (80, 2.4), *steps(80, 2.4, 92, 9.0, 8)]
lathe("StandLower", lower, M["stand_low"], sy=SY, riser=RISE)
middle = [(92, 9.0), (92, 11.5), *steps(92, 11.5, 101, 19.0, 6)]
lathe("StandMiddle", middle, M["stand_mid"], sy=SY, riser=RISE)
upper = [
    (101, 19.0),
    (101, 21.0),
    *steps(101, 21.0, 108, 28.0, 5),
    (108, 30.0),
    (110, 30.0),
    (110, 0),
]
lathe("StandUpper", upper, M["stand_top"], sy=SY, riser=M["facade"])
# The outside: fins up the wall and a ribbon of light under the rim (the site's turf green).
lathe("Ribbon", [(110.25, 25.5), (110.25, 27.0)], M["ribbon"], sy=SY)
FINS = 72
bm = bmesh.new()
for i in range(FINS):
    a = 2 * math.pi * (i + 0.5) / FINS
    turn = Matrix.Rotation(math.atan2(math.sin(a) * SY, math.cos(a)), 4, "Z")
    place = Matrix.Translation((110.4 * math.cos(a), 110.4 * math.sin(a) * SY, 15.0))
    size = Matrix.Diagonal((0.5, 1.6, 30.0, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=place @ turn @ size)
mesh_object("Fins", bm, [M["facade"]])
for side, a0 in (("East", -0.55), ("West", math.pi - 0.55)):
    lathe(f"Roof{side}", [(90, 33.0), (112, 35.5)], M["roof"], steps=24, sy=SY, start=a0, sweep=1.1)

# Sight screens on the boundary behind each end.
for sign, end in ((1, "N"), (-1, "S")):
    box(f"SightScreen{end}", (14.0, 0.4, 7.0), (0, sign * 71.0, 3.5), M["screen"])

# Four floodlight towers at the corners, their lamp banks angled at the square.
for i, deg in enumerate((45, 135, 225, 315)):
    a = math.radians(deg)
    px, py = 116 * math.cos(a), 116 * math.sin(a) * SY
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=1.1, radius2=0.55, depth=56)
    for v in bm.verts:
        v.co.z += 28
    mesh_object(f"Tower{i}", bm, [M["steel"]]).location = (px, py, 0)
    aim = Vector((-px, -py, -60)).normalized()
    rot = aim.to_track_quat("-Y", "Z").to_euler()
    for name, size, m, offset in (
        (f"TowerHead{i}", (14, 1.2, 8), M["steel"], 0.0),
        (f"Floodlamps{i}", (13, 0.3, 7), M["lamp"], 0.75),
    ):
        o = box(name, size, (0, 0, 0), m)
        o.rotation_euler = rot
        o.location = Vector((px, py, 60)) + aim * offset

# Stumps at both ends (71.1 cm tall, 22.86 cm across) and the ball by the striker's crease.
for sign, end in ((1, "N"), (-1, "S")):
    for k, dx in enumerate((-0.0915, 0.0, 0.0915)):
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm, cap_ends=True, segments=12, radius1=0.018, radius2=0.018, depth=0.711
        )
        mesh_object(f"Stump{end}{k}", bm, [M["willow"]], smooth=True).location = (
            dx,
            sign * 10.06,
            0.3555,
        )
    for k, dx in enumerate((-0.0457, 0.0457)):
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm, cap_ends=True, segments=8, radius1=0.008, radius2=0.008, depth=0.109
        )
        o = mesh_object(f"Bail{end}{k}", bm, [M["willow"]], smooth=True)
        o.location = (dx, sign * 10.06, 0.72)
        o.rotation_euler = (0, math.pi / 2, 0)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.036)
mesh_object("Ball", bm, [M["leather"]], smooth=True).location = (0.35, -8.6, 0.036)


# The camera the site and the posters share, looking across the ground from over long-on.
def look_at(o, target):
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()


cam = bpy.data.objects.new("HeroCamera", bpy.data.cameras.new("HeroCamera"))
cam.data.lens = 35
cam.data.clip_end = 2000
scene.collection.objects.link(cam)
cam.location = (120, -215, 108)
look_at(cam, (0, 0, -6))
scene.camera = cam

# Poster lighting only (the site lights the scene itself), kept out of the export: a spotlight
# and a glare in front of each lamp bank, and the sun.
lights = bpy.data.collections.new("PosterLights")
scene.collection.children.link(lights)
glare = bpy.data.materials.new("Glare")
b = glare.node_tree.nodes["Principled BSDF"]
b.inputs["Emission Color"].default_value = (1.0, 0.98, 0.94, 1)
b.inputs["Emission Strength"].default_value = 60.0
for i in range(4):
    lamp = scene.objects[f"Floodlamps{i}"]
    aim = (Vector((0, 0, 0)) - lamp.location).normalized()
    spot = bpy.data.objects.new(f"Spot{i}", bpy.data.lights.new(f"Spot{i}", "SPOT"))
    spot.data.spot_size = math.radians(100)
    spot.data.spot_blend = 0.8
    spot.data.color = (0.95, 0.97, 1.0)
    spot.location = lamp.location + aim * 6
    look_at(spot, (0, 0, 0))
    lights.objects.link(spot)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=2.6)
    me = bpy.data.meshes.new(f"Glare{i}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(glare)
    g = bpy.data.objects.new(f"Glare{i}", me)
    g.location = lamp.location + aim * 3
    g.visible_shadow = False
    lights.objects.link(g)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.rotation_euler = (math.radians(40), 0, math.radians(-35))
sun.data.angle = math.radians(3)
lights.objects.link(sun)

scene.world = bpy.data.worlds.new("Sky")
scene.render.engine = "CYCLES"
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.view_settings.view_transform = "AgX"
scene.render.resolution_x, scene.render.resolution_y = 1200, 900

# A soft bloom around the lamps. The background is transparent, so the glow outside the
# geometry goes into the alpha channel too (above a floor, so no haze fills the frame).
comp = bpy.data.node_groups.new("PosterGlare", "CompositorNodeTree")
comp.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
layers = comp.nodes.new("CompositorNodeRLayers")
bloom = comp.nodes.new("CompositorNodeGlare")
bloom.inputs["Type"].default_value = "Bloom"
bloom.inputs["Threshold"].default_value = 3.0
bloom.inputs["Strength"].default_value = 0.9
bloom.inputs["Size"].default_value = 0.5
comp.links.new(layers.outputs["Image"], bloom.inputs["Image"])
glow = comp.nodes.new("ShaderNodeMix")
glow.data_type = "RGBA"
glow.blend_type = "SUBTRACT"
glow.inputs[0].default_value = 1.0
comp.links.new(bloom.outputs["Image"], glow.inputs[6])
comp.links.new(layers.outputs["Image"], glow.inputs[7])
grey = comp.nodes.new("CompositorNodeRGBToBW")
comp.links.new(glow.outputs[2], grey.inputs[0])
floor = comp.nodes.new("ShaderNodeMath")
floor.operation = "MULTIPLY_ADD"
floor.use_clamp = True
floor.inputs[1].default_value = 1.6
floor.inputs[2].default_value = -0.22
comp.links.new(grey.outputs[0], floor.inputs[0])
alpha = comp.nodes.new("ShaderNodeMath")
alpha.operation = "MAXIMUM"
alpha.use_clamp = True
comp.links.new(layers.outputs["Alpha"], alpha.inputs[0])
comp.links.new(floor.outputs[0], alpha.inputs[1])
with_alpha = comp.nodes.new("CompositorNodeSetAlpha")
with_alpha.inputs["Type"].default_value = "Replace Alpha"
comp.links.new(bloom.outputs["Image"], with_alpha.inputs["Image"])
comp.links.new(alpha.outputs[0], with_alpha.inputs["Alpha"])
out = comp.nodes.new("NodeGroupOutput")
comp.links.new(with_alpha.outputs[0], out.inputs[0])
scene.compositing_node_group = comp


def look(mode):
    """'night': floodlights on, the lamps glowing; 'day': sunshine, the lamps off."""
    night = mode == "night"
    for o in lights.objects:
        if o.type == "LIGHT":
            on = night if o.data.type == "SPOT" else not night
            o.data.energy = (3.5e5 if night else 4.0) if on else 0.0
        else:
            o.hide_render = not night
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.012, 0.018, 0.035, 1) if night else (0.55, 0.68, 0.85, 1)
    for name, strength in (("Floodlamp", 25.0), ("Ribbon", 6.0)):
        bsdf = bpy.data.materials[name].node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Emission Strength"].default_value = strength if night else 0.0


look("night")


def export():
    """stadium.glb: everything but the poster lights, with the camera; the lamps at strength 1
    (the site sets how bright they glow)."""
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("Floodlamp", "Ribbon"):
        bsdf = bpy.data.materials[name].node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Emission Strength"].default_value = 1.0
    poster_only = set(lights.objects)
    for o in scene.objects:
        o.select_set(o.type in ("MESH", "CAMERA") and o not in poster_only)
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, scene=scene, view_layer=scene.view_layers[0]):
        scene.view_layers[0].objects.active = scene.objects["Outfield"]
        bpy.ops.export_scene.gltf(
            filepath=os.path.join(here, "stadium.glb"),
            export_format="GLB",
            use_selection=True,
            export_cameras=True,
            export_lights=False,
            export_apply=True,
        )
    look("night")


def posters():
    """The night and day posters, from the hero camera, into the web app."""
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    scene.render.image_settings.file_format = "WEBP"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.quality = 82
    for mode in ("night", "day"):
        look(mode)
        scene.render.filepath = os.path.join(
            here, "..", "..", "public", "3d", "posters", f"stadium-{mode}.webp"
        )
        bpy.ops.render.render(write_still=True)
    look("night")
