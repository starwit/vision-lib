package de.starwit.pipeline;

public class RedisConnectionNotAvailableException extends Exception {
    public RedisConnectionNotAvailableException(Throwable cause) {
        super(cause);
    }
}