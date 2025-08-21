package de.starwit.pipeline;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;
import com.redis.testcontainers.RedisContainer;

import de.starwit.visionapi.Sae.Detection;
import de.starwit.visionapi.Sae.SaeMessage;
import io.valkey.StreamEntryID;

@Testcontainers
public class VisionApiReaderWriterTest {

    @Container
    static RedisContainer redisContainer = new RedisContainer("redis:7.0");
    
    @Test
    public void test() throws InterruptedException, VisionApiConnectionNotAvailableException, InvalidProtocolBufferException {
        SaeMessage testMessage = makeMessage("msg1");
        
        try (
            VisionApiWriter writer = new VisionApiWriter(redisContainer.getRedisHost(), redisContainer.getRedisPort());
        ) {
            writer.write("testStream1", testMessage, 10);
        }

        try (
            VisionApiReader reader = new VisionApiReader(Arrays.asList("testStream1"), redisContainer.getRedisHost(), redisContainer.getRedisPort(), new StreamEntryID(0));
        ) {
            List<byte[]> byteMessages = reader.read(1, 100);
            
            List<SaeMessage> saeMessages = new ArrayList<>();
            for (byte[] byteMsg : byteMessages) {
                SaeMessage saeMsg = SaeMessage.parseFrom(byteMsg);
                saeMessages.add(saeMsg);
            }

            assertThat(saeMessages.size()).isEqualTo(1);
            assertThat(saeMessages.get(0).getDetections(0).getObjectId()).isEqualTo(testMessage.getDetections(0).getObjectId());
        }
    }

    private SaeMessage makeMessage(String objectId) {
        Detection det = Detection.newBuilder()
            .setObjectId(ByteString.copyFromUtf8(objectId))
            .build();
        
        SaeMessage msg = SaeMessage.newBuilder()
            .addDetections(det)
            .build();

        return msg;
    }
}
