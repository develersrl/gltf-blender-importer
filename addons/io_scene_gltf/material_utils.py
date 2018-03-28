import base64
import os
import tempfile
from bpy_extras.image_utils import load_image


def load_image_from_source(op, source):
    """
    Returns a Blender image from the source description.

    The source can use:
    - an uri to a file relative to the gltf document
    - a base64 encoded data uri
    - a view on a different buffer

    None is returned if the source cannot be decoded

    """
    # Don't know how to load an image from memory, so if the data is
    # in a buffer or data URI, we'll write it to a temp file and use
    # this to load it from the temp file's path.
    # Yes, this is kind of a hack :)
    if 'uri' in source:
        uri = source['uri']
        is_data_uri = uri[:5] == 'data:'
        if is_data_uri:
            found_at = uri.find(';base64,')
            if found_at == -1:
                print("Couldn't read data URI; not base64?")
                return None

            buf = base64.b64decode(uri[found_at + 8:])
            return call_on_tempfile(load_image, buf)
        else:
            image_path = os.path.join(op.base_path, uri)
            print(">", image_path)
            return load_image(image_path)
    else:
        buf, _ = op.get_buffer_view(source['bufferView'])
        return call_on_tempfile(load_image, buf)


def call_on_tempfile(func, contents):
    """
    Call func with the path to a temp file containing contents.

    The temp file will be deleted before this function returns.
    """
    path = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = tmp.name
        tmp.write(contents)
        tmp.close()  # Have to close so func can open it
        return func(path)
    finally:
        if path:
            os.remove(path)
