package de.starwit.testing;

import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

import org.junit.Test;
import static org.assertj.core.api.Assertions.*;

import de.starwit.visionapi.Messages.SaeMessage;

public class SaeDumpIteratorTest {
    
    @Test
    public void testIterator() {
        SaeDumpIterator testee = new SaeDumpIterator(Paths.get("src/test/resources/stream1.saedump"));

        List<SaeMessage> messages = new ArrayList<>();
        testee.forEachRemaining(messages::add);

        testee.close();

        assertThat(messages.stream().filter( m -> m.getFrame().getSourceId().equals("stream1") ).count()).isEqualTo(200);
        assertThat(messages.get(0)).extracting("frame.sourceId").isEqualTo("stream1");

        assertThat(messages.stream().map(SaeMessage::getDetectionsCount).reduce(0, Integer::sum)).isEqualTo(3746);
    }
}
