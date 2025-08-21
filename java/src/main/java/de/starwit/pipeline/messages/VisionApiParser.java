package de.starwit.pipeline.messages;

import com.google.protobuf.InvalidProtocolBufferException;

import de.starwit.visionapi.Analytics.DetectionCountMessage;
import de.starwit.visionapi.Common.MessageType;
import de.starwit.visionapi.Common.TypeMessage;
import de.starwit.visionapi.Sae.PositionMessage;
import de.starwit.visionapi.Sae.SaeMessage;

public class VisionApiParser {
    public static TypeMessage parseTypeMessage(byte[] protoBytes) throws InvalidProtocolBufferException {
        TypeMessage typeMsg = TypeMessage.parseFrom(protoBytes);
        return typeMsg;
    }
    
    public static SaeMessage parseSaeMessage(byte[] protoBytes) throws InvalidProtocolBufferException, InvalidMessageTypeException {
        SaeMessage saeMsg = SaeMessage.parseFrom(protoBytes);
        if (saeMsg.getType() != MessageType.SAE) {
            throw new InvalidMessageTypeException("MessageType.SAE needed but was " + saeMsg.getType().name());
        }
        return saeMsg;
    }

    public static DetectionCountMessage parseDetectionCountMessage(byte[] protoBytes) throws InvalidProtocolBufferException, InvalidMessageTypeException {
        DetectionCountMessage countMsg = DetectionCountMessage.parseFrom(protoBytes);
        if (countMsg.getType() != MessageType.DETECTION_COUNT) {
            throw new InvalidMessageTypeException("MessageType.DETECTION_COUNT needed but was " + countMsg.getType().name());
        }
        return countMsg;
    }

    public static PositionMessage parsePositionMessage(byte[] protoBytes) throws InvalidProtocolBufferException, InvalidMessageTypeException {
        PositionMessage posMsg = PositionMessage.parseFrom(protoBytes);
        if (posMsg.getType() != MessageType.POSITION) {
            throw new InvalidMessageTypeException("MessageType.POSITION needed but was " + posMsg.getType().name());
        }
        return posMsg;
    }
}
