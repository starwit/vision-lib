package de.starwit.pipeline.messages;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.google.protobuf.ByteString;

import de.starwit.visionapi.Analytics.DetectionCount;
import de.starwit.visionapi.Analytics.DetectionCountMessage;
import de.starwit.visionapi.Common.GeoCoordinate;
import de.starwit.visionapi.Common.MessageType;
import de.starwit.visionapi.Common.TypeMessage;
import de.starwit.visionapi.Sae.Detection;
import de.starwit.visionapi.Sae.PositionMessage;
import de.starwit.visionapi.Sae.SaeMessage;

public class VisionApiParserTest {
    
    @Test
    public void testParseTypeMessage() throws Exception {
        byte[] protoBytes = TypeMessage.newBuilder().setType(MessageType.SAE).build().toByteArray();

        TypeMessage typeMsg = VisionApiParser.parseTypeMessage(protoBytes);

        assertThat(typeMsg).isNotNull();
        assertThat(typeMsg.getType()).isEqualTo(MessageType.SAE);
    }

    @Test
    public void testParseSaeMessage() throws Exception {
        byte[] protoBytes = SaeMessage.newBuilder()
            .addDetections(Detection.newBuilder().setObjectId(ByteString.copyFromUtf8("testId1")).build())
            .setType(MessageType.SAE)
            .build()
            .toByteArray();

        SaeMessage saeMsg = VisionApiParser.parseSaeMessage(protoBytes);
        
        assertThat(saeMsg).isNotNull();
        assertThat(saeMsg.getType()).isEqualTo(MessageType.SAE);
        assertThat(saeMsg.getDetectionsCount()).isEqualTo(1);
        assertThat(saeMsg.getDetections(0).getObjectId().toStringUtf8()).isEqualTo("testId1");
    }

    @Test
    public void testParseDetectionCountMessage() throws Exception {
        byte[] protoBytes = DetectionCountMessage.newBuilder()
            .addDetectionCounts(DetectionCount.newBuilder()
                .setClassId(2)
                .setCount(3))
            .setType(MessageType.DETECTION_COUNT)
            .build()
            .toByteArray();

        DetectionCountMessage countMsg = VisionApiParser.parseDetectionCountMessage(protoBytes);

        assertThat(countMsg).isNotNull();
        assertThat(countMsg.getDetectionCountsCount()).isEqualTo(1);
        assertThat(countMsg.getDetectionCounts(0).getClassId()).isEqualTo(2);
        assertThat(countMsg.getDetectionCounts(0).getCount()).isEqualTo(3);
    }

        @Test
        public void testParsePositionMessage() throws Exception {
            byte[] protoBytes = PositionMessage.newBuilder()
                .setType(MessageType.POSITION)
                .setFix(true)
                .setGeoCoordinate(GeoCoordinate.newBuilder().setLatitude(12.34).setLongitude(56.78).build())
                .setType(MessageType.POSITION)
                .build()
                .toByteArray();

            PositionMessage posMsg = VisionApiParser.parsePositionMessage(protoBytes);

            assertThat(posMsg).isNotNull();
            assertThat(posMsg.getType()).isEqualTo(MessageType.POSITION);
            assertThat(posMsg.getFix()).isTrue();
            assertThat(posMsg.getGeoCoordinate().getLatitude()).isEqualTo(12.34);
            assertThat(posMsg.getGeoCoordinate().getLongitude()).isEqualTo(56.78);
        }
}
