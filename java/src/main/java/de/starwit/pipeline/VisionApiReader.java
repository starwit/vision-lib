package de.starwit.pipeline;

import java.io.Closeable;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import io.valkey.JedisPooled;
import io.valkey.StreamEntryID;
import io.valkey.exceptions.JedisConnectionException;
import io.valkey.params.XReadParams;
import io.valkey.resps.StreamEntry;

/**
 * Reads vision-api protobuf payloads from a Valkey stream.
 * Allocates a network connection through Jedis and must therefore be (auto)closed.
 */
public class VisionApiReader implements Closeable {

    private static final Logger log = LoggerFactory.getLogger(VisionApiReader.class);

    private Map<String,StreamEntryID> streamPointerById;
    private JedisPooled valkeyClient;

    /**
     * Create a new instance, attaching at the end of all given streams (i.e. reading only messages appended after reader init).
     * @param streamIds A list of stream ids of streams that should be read / attached to.
     * @param host Redis host.
     * @param port Redis port.
     */
    public VisionApiReader(List<String> streamIds, String host, int port) {
        this(streamIds, host, port, StreamEntryID.XREAD_NEW_ENTRY);
    }
    
    /**
     * Create a new instance, attaching to all given streams at a certain point.
     * @param streamIds A list of stream ids of streams that should be read / attached to.
     * @param host Redis host.
     * @param port Redis port.
     * @param startAfter Start reading the stream after this id (i.e. return messages with a higher id).
     */
    public VisionApiReader(List<String> streamIds, String host, int port, StreamEntryID startAfter) {
        this.valkeyClient = new JedisPooled(host, port);
        this.streamPointerById = streamIds.stream()
                .collect(Collectors.toMap(id -> id, id -> startAfter));
    }

    /**
     * Read a number of raw vision-api messages from all configured streams.
     * @param maxCountPerStream How many messages should be retrieved per stream.
     * @param timeout How long to wait before returning an empty result, if no new messages have arrived.
     * @return A list of byte arrays containing the serialized protobufs. Empty, if any kind of problem was encountered.
     * @throws VisionApiConnectionNotAvailableException 
     */
    public List<byte[]> read(int maxCountPerStream, int timeout) throws VisionApiConnectionNotAvailableException {
        XReadParams xReadParams = new XReadParams().count(maxCountPerStream).block(timeout);
        List<Map.Entry<String, List<StreamEntry>>> result = null;
        try {
            result = this.valkeyClient.xread(xReadParams, this.streamPointerById);
        } catch (JedisConnectionException ex) {
            log.warn("Could not read from redis", ex);
            throw new VisionApiConnectionNotAvailableException(ex);
        }

        if (result == null) {
            return new ArrayList<>();
        }

        List<byte[]> payloads = new ArrayList<>();

        for (Map.Entry<String,List<StreamEntry>> resultEntry : result) {
            String streamId = resultEntry.getKey();
            List<StreamEntry> messages = resultEntry.getValue();
            for (StreamEntry message : messages) {
                // Set last retrieved id
                updateStreamPointers(streamId, message);
                String proto_b64 = message.getFields().get("proto_data_b64");
                if (proto_b64.length() > 0) {
                    payloads.add(Base64.getDecoder().decode(proto_b64));
                }
            }
        }

        return payloads;
    }

    private void updateStreamPointers(String streamId, StreamEntry msg) {
        this.streamPointerById.put(streamId, msg.getID());

        // Set any remaining '$' stream pointers (i.e. LAST_ENTRY) to a concrete timestamp
        // If we do not do this, some streams are not picked up when listening to multiple streams
        List<String> lastEntryStreamIds = this.streamPointerById.entrySet().stream()
                .filter(e -> e.getValue().equals(StreamEntryID.XREAD_NEW_ENTRY))
                .map(Map.Entry::getKey)
                .toList();
            
        lastEntryStreamIds.stream()
                .forEach(id -> this.streamPointerById.put(id, msg.getID()));
    }

    @Override
    public void close() {
        try {
            this.valkeyClient.close();
        } catch (Exception ex) {
            log.warn("Error while closing Redis client", ex);
        }
    }

}
