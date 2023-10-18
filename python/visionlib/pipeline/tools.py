from turbojpeg import TurboJPEG
from visionapi.messages_pb2 import VideoFrame

jpeg = TurboJPEG()

def get_raw_frame_data(proto: VideoFrame):
    if proto.HasField('frame_data_jpeg'):
        return jpeg.decode(proto.frame_data_jpeg)
    else:
        return proto.frame_data