import bpy
import math


# def add_ambient_light(scene, color):
#     """
#     Add an ambient light to the scene with the RGB color
#     """
#     world = bpy.data.worlds[scene.world.name]
#     world.use_nodes = True
# 
#     tree = world.node_tree
#     try:
#         bg = tree.nodes['Background']
#     except KeyError:
#         tree.nodes.new(type='ShaderNodeBackground')
#         bg = tree.nodes['Background']
# 
#     world_output = tree.nodes['World Output']
#     tree.links.new(world_output.inputs['Surface'], bg.outputs['Background'])
#     bg.inputs['Color'].default_value = color + (1,)

incandescent_bulb = 0.0249


def cd2W(intensity, efficiency, surface):
    """
    intensity in candles
    efficency is a factor
    surface in steradians
    """
    lumens = intensity * surface
    return lumens / (efficiency * 683)


def lux2W(intensity, efficiency):
    """
    intensity in lux (lm/m2)
    efficency is a factor
    """
    return intensity / (efficiency * 683)


def add_point_light(color, intensity, name=None):
    """
    Create a new point light data object.

    `color` is an rgb tuple
    `intensity` is expressed in candles
    """
    name = name or "Point"

    lamp_data = bpy.data.lamps.new(name=name, type='POINT')
    lamp_data.use_nodes = True

    emission = lamp_data.node_tree.nodes['Emission']
    emission.inputs['Color'].default_value = tuple(color) + (1,)

    watt = cd2W(intensity, incandescent_bulb, surface=4 * math.pi)
    emission.inputs['Strength'].default_value = watt
    return lamp_data


def add_spot_light(
        color, intensity, innerConeAngle, outerConeAngle, name=None):
    """
    Create a new spot light data object.

    `color` is an rgb tuple
    `intensity` is expressed in candles
    `innerConeAngle` and `outerConeAngle` is expressed in radians
    """
    name = name or "Spot"

    lamp_data = bpy.data.lamps.new(name=name, type='SPOT')
    lamp_data.use_nodes = True
    lamp_data.spot_size = outerConeAngle
    lamp_data.spot_blend = innerConeAngle / outerConeAngle

    emission = lamp_data.node_tree.nodes['Emission']
    emission.inputs['Color'].default_value = tuple(color) + (1,)
    # for the surface calc see:
    # https://en.wikipedia.org/wiki/Solid_angle#Cone,_spherical_cap,_hemisphere
    emission.inputs['Strength'].default_value = cd2W(
        intensity,
        incandescent_bulb,
        surface=2 * math.pi * (1 - math.cos(outerConeAngle / 2)),
    )
    return lamp_data


def add_directional_light(color, intensity, name=None):
    """
    Create a new directional light data object.

    `color` is an rgb tuple
    `intensity` is expressed in candles
    """
    name = name or "Directional"

    lamp_data = bpy.data.lamps.new(name=name, type='SUN')
    lamp_data.use_nodes = True

    emission = lamp_data.node_tree.nodes['Emission']
    emission.inputs['Color'].default_value = tuple(color) + (1,)

    watt = lux2W(intensity, incandescent_bulb)
    emission.inputs['Strength'].default_value = watt
    return lamp_data
