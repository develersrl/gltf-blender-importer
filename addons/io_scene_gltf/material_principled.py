import bpy
from io_scene_gltf.material_utils import load_image_from_source

def create_material_from_properties(op, material, material_name):
    """
    Create a PBR Material by compbining a 'ShaderNodeBsdfPrincipled' node
    and, possibly, textures and/ or values declared into 'op'.

    In case of 'alphaMode' not 'OPAQUE', the 'ShaderNodeBsdfPrincipled' node
    is combined with a 'ShaderNodeBsdfTransparent' node by mixing the result of
    the former with the output of the latter by the alpha factor defined in 'op'.
    """
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
    clr = _add_color_group(
        tree,
        base_factor=material.get('baseColorFactor', [1, 1, 1, 1]),
        texture=texture,
        alpha=alpha_mode,
        alpha_cutoff=alpha_cutoff,
    )
    links.new(clr.outputs['Color'], pbr.inputs['Base Color'])

    if alpha_cutoff is None:
        links.new(pbr.outputs['BSDF'], mo.inputs['Surface'])
    else:
        trp = tree.nodes.new('ShaderNodeBsdfTransparent')
        mix = tree.nodes.new('ShaderNodeMixShader')
        mix.label = "Transparent Mix"
        tree.links.new(clr.outputs['Alpha Factor'], mix.inputs['Fac'])
        tree.links.new(trp.outputs['BSDF'], mix.inputs[1])
        tree.links.new(pbr.outputs['BSDF'], mix.inputs[2])
        links.new(mix.outputs['Shader'], mo.inputs['Surface'])
    
    return mat


def _add_color_group(material_tree, base_factor, texture=None, alpha='OPAQUE', alpha_cutoff=None):
    """
    Add to the material tree the nodes needed to implement the color specified

    In glTF a color is described by:

    - a base factor (4 floats in the range 0..1)
    - a texture

    The final color is obtained multiplying every pixel in the texture with the
    base factor component wise.

    The texture argument is a dict with two keys:
    - image, a Blender Image instance
    - sampler, the sampler object retrieved by the gltf document

    A missing texture is interpreted as a white image.

    The alpha argument is an enum with only three values:
    'OPAQUE' | 'MASK' | 'BLEND'.

    - if 'OPAQUE' the alpha channel is ignored
    - if 'BLEND' the pixel color must be blended with the background
    - if 'MASK' the pixel color is completly opaque if the alpha channel is
      lesser than `alpha_cutoff`, opaque otherwise.

    The return value is a node with two outputs: "Color" and "Alpha Factor".

    The "Color" output is an RGB ready to be linked to the "Base Color" input
    of a "PrincipledBSDF".

    The "Alpha Factor" output can be used only if the alpha argument is not 'OPAQUE';
    the caller should mix the "BSDF" ouput of a "PrincipledBSDF" with the
    output of a "TransparentBSDF" using the "Alpha Factor" output as the mix factor.
    """
    tree = bpy.data.node_groups.new("Color Group", 'ShaderNodeTree')
    tree.outputs.new('NodeSocketColor', "Color")
    tree.outputs["Color"].default_value = base_factor
    tree.outputs.new('NodeSocketFloatFactor', "Alpha Factor")
    if alpha is 'OPAQUE':
        tree.outputs["Alpha Factor"].default_value = 1
    else:
        tree.outputs["Alpha Factor"].default_value = base_factor[3]
    outputs = tree.nodes.new('NodeGroupOutput')

    if texture is not None:
        factor = tree.nodes.new('ShaderNodeRGB')
        factor.label = "Color Multiplier"
        factor.outputs['Color'].default_value = base_factor

        tex_node = tree.nodes.new('ShaderNodeTexImage')
        tex_node.color_space = 'COLOR'
        tex_node.image = texture['image']
        _configure_sampling(tex_node, texture['sampler'])

        mixer = tree.nodes.new('ShaderNodeMixRGB')
        mixer.blend_type = 'MULTIPLY'
        mixer.inputs["Fac"].default_value = 1

        tree.links.new(factor.outputs['Color'], mixer.inputs['Color1'])
        tree.links.new(tex_node.outputs['Color'], mixer.inputs['Color2'])

        tree.links.new(mixer.outputs['Color'], outputs.inputs['Color'])
    
        if alpha is not 'OPAQUE':
            alpha_node = _create_alpha_factor_pipeline(
                tree,
                tex_node.outputs['Alpha'],
                base_factor[3],
                alpha_cutoff
            )
            tree.links.new(alpha_node.outputs['Value'], outputs.inputs['Alpha Factor'])


    color_group = material_tree.nodes.new('ShaderNodeGroup')
    color_group.label = "Material Base Color"
    color_group.node_tree = tree
    return color_group


def _create_alpha_factor_pipeline(node_tree, tex_alpha_output, base_alpha, alpha_cutoff=None):
    """
    Create some nodes computing the final alpha factor by multiplying the base_alpha
    with the alpha channel of the texture, if any.
    
    If alpha_cutoff is not None, than the output alpha factor is either 0 (when
    the final alpha is less than or equal to alpha_cutoff) or 1 (otherwise)
    """
    multiplier = node_tree.nodes.new('ShaderNodeMath')
    multiplier.label = "Alpha Multiplier"
    multiplier.operation = 'MULTIPLY'
    multiplier.inputs[0].default_value = base_alpha
    node_tree.links.new(tex_alpha_output, multiplier.inputs[1])

    if alpha_cutoff is None:
        return multiplier
    
    cutter = node_tree.nodes.new('ShaderNodeMath')
    cutter.label = "Cut Off"
    cutter.operation = 'GREATER_THAN'
    node_tree.links.new(multiplier.outputs['Value'], cutter.inputs[0])
    cutter.inputs[1].default_value = alpha_cutoff
    return cutter


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
