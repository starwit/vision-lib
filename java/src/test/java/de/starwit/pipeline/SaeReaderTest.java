package de.starwit.pipeline;

import java.util.Arrays;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.util.JsonFormat;

import de.starwit.visionapi.Messages.SaeMessage;

public class SaeReaderTest {

    @Test
    public void test() {
        try (SaeReader reader = new SaeReader(Arrays.asList("objecttracker:stream1"), "localhost", 6379)) {
            while (true) {
                List<SaeMessage> messages = reader.read(10, 50);
                System.out.println("Read " + messages.size() + " messages");
                // messages.stream().forEach(msg -> {
                //     try {
                //         System.out.println(JsonFormat.printer().print(msg));
                //     } catch (InvalidProtocolBufferException e) {
                //         e.printStackTrace();
                //     }
                // });
            }

        }
    }
}
