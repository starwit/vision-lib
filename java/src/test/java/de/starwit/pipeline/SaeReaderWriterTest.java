package de.starwit.pipeline;

import java.util.Arrays;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import com.google.protobuf.ByteString;
import com.redis.testcontainers.RedisContainer;
import static org.assertj.core.api.Assertions.*;

import de.starwit.visionapi.Sae.Detection;
import de.starwit.visionapi.Sae.SaeMessage;
import redis.clients.jedis.StreamEntryID;

@Testcontainers
public class SaeReaderWriterTest {

    @Container
    static RedisContainer redisContainer = new RedisContainer("redis:7.0");
    
    @Test
    public void test() throws InterruptedException, ValkeyConnectionNotAvailableException {
        SaeMessage testMessage = makeMessage("msg1");
        
        try (
            ValkeyWriter writer = new ValkeyWriter(redisContainer.getRedisHost(), redisContainer.getRedisPort());
        ) {
            writer.write("testStream1", testMessage, 10);
        }

        try (
            ValkeyReader reader = new ValkeyReader(Arrays.asList("testStream1"), redisContainer.getRedisHost(), redisContainer.getRedisPort(), new StreamEntryID(0));
        ) {
            List<SaeMessage> msg = reader.read(1, 100);
            assertThat(msg.size()).isEqualTo(1);
            assertThat(msg.get(0).getDetections(0).getObjectId()).isEqualTo(testMessage.getDetections(0).getObjectId());
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
