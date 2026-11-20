import numpy as np
from turbojpeg import TurboJPEG

# Created lazily, so that libturbojpeg (a system library) is only required if JPEG frames are actually decoded
_jpeg = None

def get_jpeg() -> TurboJPEG:
    '''
        Returns a shared TurboJPEG instance. Raises a RuntimeError if libturbojpeg is not installed.
    '''
    global _jpeg
    if _jpeg is None:
        try:
            _jpeg = TurboJPEG()
        except RuntimeError as e:
            raise RuntimeError('JPEG frame decoding requires the libturbojpeg system library, which could not be found '
                               '(e.g. on Debian/Ubuntu: sudo apt install libturbojpeg)') from e
    return _jpeg

def __getattr__(name):
    # Keeps the former module attribute `jpeg` working (now created on first access)
    if name == 'jpeg':
        return get_jpeg()
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

def is_valid_video_frame(proto):
    try:
        # ListFields() returns all defined fields that are set (for primitive values: do not have their default value)
        set_fields = list(map(lambda f: f[0].name, proto.ListFields()))
        if 'shape' in set_fields and any(('frame_data_jpeg' in set_fields, 'frame_data' in set_fields)):
            return True
        else:
            return False
    except:
        return False
    
def is_jpeg_frame(proto):
    set_fields = list(map(lambda f: f[0].name, proto.ListFields()))
    if 'frame_data_jpeg' in set_fields:
        return True
    else:
        return False

def get_raw_frame_data(proto):
    '''
        Gets image data as NDArray from a VideoFrame proto. JPEG frames are handled (i.e. decompressed) transparently.
        If necessary fields are missing returns None.
    '''
    if not is_valid_video_frame(proto):
        return None
    
    if is_jpeg_frame(proto):
        return get_jpeg().decode(proto.frame_data_jpeg)
    else:
        image_dims = (proto.shape.height, proto.shape.width, proto.shape.channels)
        np_image = np.frombuffer(proto.frame_data, dtype=np.uint8).reshape(image_dims)
        return np_image