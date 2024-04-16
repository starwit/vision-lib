package de.starwit.pipeline;

import java.io.Closeable;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.google.protobuf.InvalidProtocolBufferException;

import de.starwit.visionapi.Messages.SaeMessage;
import redis.clients.jedis.JedisPooled;
import redis.clients.jedis.StreamEntryID;
import redis.clients.jedis.exceptions.JedisConnectionException;
import redis.clients.jedis.params.XReadParams;
import redis.clients.jedis.resps.StreamEntry;

/**
 * Reads {@code SaeMessage} protobufs from a Redis stream.
 * Allocates a network connection to Jedis and must therefore be (auto)closed.
 */
public class SaeReader implements Closeable {

    private static final Logger log = LoggerFactory.getLogger(SaeReader.class);

    private Map<String,StreamEntryID> streamPointerById;
    private JedisPooled redisClient;

    /**
     * Create a new instance, attaching at the end of all given streams (i.e. reading only messages appended after reader init).
     * @param streamIds A list of stream ids of streams that should be read / attached to.
     * @param host Redis host.
     * @param port Redis port.
     */
    public SaeReader(List<String> streamIds, String host, int port) {
        this(streamIds, host, port, StreamEntryID.LAST_ENTRY);
    }
    
    /**
     * Create a new instance, attaching to all given streams at a certain point.
     * @param streamIds A list of stream ids of streams that should be read / attached to.
     * @param host Redis host.
     * @param port Redis port.
     * @param startAfter Start reading the stream after this id (i.e. return messages with a higher id).
     */
    public SaeReader(List<String> streamIds, String host, int port, StreamEntryID startAfter) {
        this.redisClient = new JedisPooled(host, port);
        this.streamPointerById = streamIds.stream()
                .collect(Collectors.toMap(id -> id, id -> startAfter));
    }

    /**
     * Read a number of messages from all configured streams.
     * @param maxCountPerStream How many messages should be retrieved per stream.
     * @param timeout How long to wait before returning an empty result, if no new messages have arrived.
     * @return A list of {@code SaeMessage}. Empty, if any kind of problem was encountered.
     * @throws RedisConnectionNotAvailableException 
     */
    public List<SaeMessage> read(int maxCountPerStream, int timeout) throws RedisConnectionNotAvailableException {
        XReadParams xReadParams = new XReadParams().count(maxCountPerStream).block(timeout);
        List<Map.Entry<String, List<StreamEntry>>> result = null;
        try {
            result = this.redisClient.xread(xReadParams, this.streamPointerById);
        } catch (JedisConnectionException ex) {
            log.warn("Could not read from redis", ex);
            throw new RedisConnectionNotAvailableException(ex);
        }

        if (result == null) {
            return new ArrayList<>();
        }

        List<SaeMessage> parsedResults = new ArrayList<>();

        for (Map.Entry<String,List<StreamEntry>> resultEntry : result) {
            String streamId = resultEntry.getKey();
            List<StreamEntry> messages = resultEntry.getValue();
            for (StreamEntry message : messages) {
                // Set last retrieved id
                updateStreamPointers(streamId, message);
                String proto_b64 = message.getFields().get("proto_data_b64");
                try {
                    SaeMessage msg = SaeMessage.parseFrom(Base64.getDecoder().decode(proto_b64));
                    parsedResults.add(msg);
                } catch (InvalidProtocolBufferException ex) {
                    log.error("Error decoding proto from message. streamId=" + streamId, ex);
                }
            }
        }

        return parsedResults;
    }

    private void updateStreamPointers(String streamId, StreamEntry msg) {
        this.streamPointerById.put(streamId, msg.getID());

        // Set any remaining '$' stream pointers (i.e. LAST_ENTRY) to a concrete timestamp
        // If we do not do this, some streams are not picked up when listening to multiple streams
        List<String> lastEntryStreamIds = this.streamPointerById.entrySet().stream()
                .filter(e -> e.getValue().equals(StreamEntryID.LAST_ENTRY))
                .map(Map.Entry::getKey)
                .toList();
            
        lastEntryStreamIds.stream()
                .forEach(id -> this.streamPointerById.put(id, msg.getID()));
    }

    @Override
    public void close() {
        try {
            this.redisClient.close();
        } catch (Exception ex) {
            log.warn("Error while closing Redis client", ex);
        }
    }

}
