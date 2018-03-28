import bpy
from io_scene_gltf.material_utils import load_image_from_source

def create_material_from_properties(op, material, material_name):
    pbr_mr = material.get('pbrMetallicRoughness', {})

    mat = bpy.data.materials.new(material_name)
    op.materials[material_name] = mat
    mat.use_nodes = True

    tree = mat.node_tree
    links = tree.links

    for n in tree.nodes:
        tree.nodes.remove(n)

    pbr = tree.nodes.new('ShaderNodeBsdfPrincipled')
    mo = tree.nodes.new('ShaderNodeOutputMaterial')
    links.new(pbr.outputs['BSDF'], mo.inputs['Surface'])

    if 'baseColorTexture' in pbr_mr:
        index = pbr_mr['baseColorTexture']['index']
        texture_data = op.gltf['textures'][index]
        texture = {
            'image': load_image_from_source(op, op.gltf['images'][texture_data['source']]),
            'sampler': op.gltf['samplers'][texture_data['sampler']],
        }
    else:
        texture = None

    alpha_mode = material.get('alphaMode', 'OPAQUE')
    alpha_cutoff = None if alpha_mode != 'MASK' else material.get('alphaCutoff', 0.5)
    node = _add_color_node(
        tree,
        base_factor=material.get('baseColorFactor', [1, 1, 1, 1]),
        texture=texture,
        alpha=alpha_mode,
        alpha_cutoff=alpha_cutoff,
    )
    links.new(node.outputs['Color'], pbr.inputs['Base Color'])
    return mat


def _add_color_node(tree, base_factor, texture=None, alpha='OPAQUE', alpha_cutoff=None):
    """
    Add to the tree the nodes needed to implement the color specified

    In glTF a color is described by:

    - a base factor (4 floats in the range 0..1)
    - a texture

    The final color is obtained multiplying every pixel in the texture with the
    base factor component wise.

    The texture argument is a dict with two keys:
    - image, a Blender Image instance
    - sampler, the sampler object retrieved by the gltf document

    A missing texture is interpreted as a white image.

    The return value is a Blender node with a "Color" output.
    """
    factor = tree.nodes.new('ShaderNodeRGB')
    factor.label = "Color multiplier"
    factor.outputs['Color'].default_value = base_factor

    if texture is None:
        return factor

    tex_node = tree.nodes.new('ShaderNodeTexImage')
    tex_node.color_space = 'COLOR'
    tex_node.image = texture['image']
    _configure_sampling(tex_node, texture['sampler'])

    mixer = tree.nodes.new('ShaderNodeMixRGB')
    mixer.blend_type = 'MULTIPLY'
    tree.links.new(tex_node.outputs['Color'], mixer.inputs['Color1'])
    tree.links.new(factor.outputs['Color'], mixer.inputs['Color2'])

    return mixer


_sampler_filter = {
    9728: {
        'description': 'NEAREST',
        'value': 'Closest',
    },
    9729: {
        'description': 'LINEAR',
        'value': 'Linear',
    },
    9984: {
        'description': 'NEAREST_MIPMAP_NEAREST',
        'value': 'Closest',
    },
    9985: {
        'description': 'LINEAR_MIPMAP_NEAREST',
        'value': 'Closest',
    },
    9986: {
        'description': 'NEAREST_MIPMAP_LINEAR',
        'value': 'Linear',
    },
    9987: {
        'description': 'LINEAR_MIPMAP_LINEAR',
        'value': 'Linear',
    },
}

_sampler_wrap = {
    33071: {
        'description': 'CLAMP_TO_EDGE',
        'value': 'EXTEND',
    },
    33648: {
        'description': 'MIRRORED_REPEAT',
        'value': 'REPEAT',
    },
    10497: {
        'description': 'REPEAT',
        'value': 'REPEAT',
    },
}


def _configure_sampling(image, sampler_data):
    """
    Configure a Blender ShaderNodeTexImage using the sampler data from the gltf
    document.
    """
    mag_filter = sampler_data.get('magFilter', 9729)
    min_filter = sampler_data.get('minFilter', 9729)
    wrap_s = sampler_data.get('wrapS', 10497)
    wrap_t = sampler_data.get('wrapT', 10497)

    try:
        mag_intrp = _sampler_filter[mag_filter]['value']
        min_intrp = _sampler_filter[min_filter]['value']
    except KeyError:
        intrp = 'Linear'
    else:
        intrp = 'Linear' if mag_intrp != min_intrp else mag_intrp

    image.interpolation = intrp

    try:
        s_extend = _sampler_wrap[wrap_s]['value']
        t_extend = _sampler_wrap[wrap_t]['value']
    except KeyError:
        extend = 'REPEAT'
    else:
        extend = 'REPEAT' if s_extend != t_extend else s_extend

    image.extension = extend
    return image
