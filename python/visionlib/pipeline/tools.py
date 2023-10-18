from turbojpeg import TurboJPEG
from visionapi.messages_pb2 import VideoFrame

jpeg = TurboJPEG()

def get_raw_frame_data(proto: VideoFrame):
    # ListFields() returns all defined fields that are set (for primitive values: do not have their default value)
    jpeg_field_set = 'frame_data_jpeg' in map(lambda f: f[0].name, proto.ListFields())
    if jpeg_field_set:
        return jpeg.decode(proto.frame_data_jpeg)
    else:
        return proto.frame_data