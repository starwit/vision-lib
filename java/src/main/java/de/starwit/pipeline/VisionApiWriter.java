package de.starwit.pipeline;

import java.io.Closeable;
import java.util.Base64;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import de.starwit.visionapi.Sae.SaeMessage;
import io.valkey.JedisPooled;
import io.valkey.exceptions.JedisConnectionException;
import io.valkey.params.XAddParams;

/**
 * Writes a {@code SaeMessage} protobuf to a Redis stream.
 * Allocates a network connection to Jedis and must therefore be (auto)closed.
 */
public class VisionApiWriter implements Closeable {

    private static final Logger log = LoggerFactory.getLogger(VisionApiWriter.class);

    private JedisPooled valkeyClient;

    public VisionApiWriter(String host, int port) {
        this.valkeyClient = new JedisPooled(host, port);
    }

    /**
     * Write a message to the specified stream.
     * @param streamKey The full key of the stream to write to.
     * @param message The message that should be written.
     * @param maxLen Limit the stream length to {@code maxLen} messages (old messages are discarded accordingly)
     * @throws VisionApiConnectionNotAvailableException 
     */
    public void write(String streamKey, SaeMessage message, int maxLen) throws VisionApiConnectionNotAvailableException {
        XAddParams xAddParams = new XAddParams().maxLen(maxLen);
        try {
            byte[] messagePayload = Base64.getEncoder().encode(message.toByteArray());
            this.valkeyClient.xadd(streamKey.getBytes(), xAddParams, Map.of("proto_data_b64".getBytes(), messagePayload));
        } catch (JedisConnectionException ex) {
            log.warn("Could not write to redis", ex);
            throw new VisionApiConnectionNotAvailableException(ex);
        }
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
