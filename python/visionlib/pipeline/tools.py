from turbojpeg import TurboJPEG
from visionapi.messages_pb2 import VideoFrame

jpeg = TurboJPEG()

def get_raw_frame_data(proto: VideoFrame):
    try:
        jpeg_field_defined = proto.HasField('frame_data_jpeg')
        jpeg_field_set = len(proto.frame_data_jpeg) > 0
        if jpeg_field_defined and jpeg_field_set:
            return jpeg.decode(proto.frame_data_jpeg)
    except ValueError:
        pass
    
    return proto.frame_data