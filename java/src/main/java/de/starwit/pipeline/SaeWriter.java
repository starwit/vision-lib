package de.starwit.pipeline;

import java.io.Closeable;
import java.util.Base64;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.google.protobuf.GeneratedMessage;

import redis.clients.jedis.JedisPooled;
import redis.clients.jedis.exceptions.JedisConnectionException;
import redis.clients.jedis.params.XAddParams;

/**
 * Writes a {@code SaeMessage} protobuf to a Redis stream.
 * Allocates a network connection to Jedis and must therefore be (auto)closed.
 */
public class SaeWriter implements Closeable {

    private static final Logger log = LoggerFactory.getLogger(SaeWriter.class);

    private JedisPooled redisClient;

    public SaeWriter(String host, int port) {
        this.redisClient = new JedisPooled(host, port);
    }

    /**
     * Write a message to the specified stream.
     * @param streamKey The full key of the stream to write to.
     * @param message The message that should be written.
     * @param maxLen Limit the stream length to {@code maxLen} messages (old messages are discarded accordingly)
     * @throws RedisConnectionNotAvailableException 
     */
    public void write(String streamKey, GeneratedMessage message, int maxLen) throws RedisConnectionNotAvailableException {
        XAddParams xAddParams = new XAddParams().maxLen(maxLen);
        try {
            byte[] messagePayload = Base64.getEncoder().encode(message.toByteArray());
            this.redisClient.xadd(streamKey.getBytes(), xAddParams, Map.of("proto_data_b64".getBytes(), messagePayload));
        } catch (JedisConnectionException ex) {
            log.warn("Could not write to redis", ex);
            throw new RedisConnectionNotAvailableException(ex);
        }
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
