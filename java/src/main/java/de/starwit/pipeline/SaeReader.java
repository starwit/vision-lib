package de.starwit.pipeline;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

import de.starwit.visionapi.Messages.SaeMessage;
import redis.clients.jedis.JedisPooled;
import redis.clients.jedis.StreamEntryID;
import redis.clients.jedis.params.XReadParams;

public class SaeReader {

    private XReadParams xReadParams;
    private Map<String,StreamEntryID> streamPointerById;
    private JedisPooled jedisClient;

    public SaeReader(List<String> streamIds, String host, int port) {
        this.jedisClient = new JedisPooled(host, port);
        this.xReadParams = new XReadParams().count(10).block(200);
        this.streamPointerById = streamIds.stream()
                .collect(Collectors.toMap(id -> id, id -> StreamEntryID.LAST_ENTRY));
    }
    
    public Optional<SaeMessage> getNext() {
        return Optional.empty();
    }
}
