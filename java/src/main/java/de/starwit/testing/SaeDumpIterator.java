package de.starwit.testing;

import java.io.BufferedReader;
import java.io.Closeable;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.Iterator;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.protobuf.InvalidProtocolBufferException;

import de.starwit.testing.messages.SaeDumpEvent;
import de.starwit.testing.messages.SaeDumpMeta;
import de.starwit.visionapi.Sae.SaeMessage;

/**
 * Reads an .saedump file and produces SaeMessage objects.
 * Needs to be properly closed! Should therefore be used with try-with-resources.
 */
public class SaeDumpIterator implements Iterator<SaeMessage>, Closeable {
    private static String MSG_SEPARATOR = ";";
    private static int EOF = -1;
    
    private BufferedReader reader;
    private SaeDumpMeta dumpMeta;
    private ObjectMapper objectMapper = new ObjectMapper();
    
    /** 
    * Constructor taking the path to the dump file.
     */
    public SaeDumpIterator(Path path) {
        try {
            this.reader = Files.newBufferedReader(path);
        } catch (IOException e) {
            throw new SaeDumpReadException("Could not open dump file at " + path, e);
        }

        try {
            this.dumpMeta = readMetaHeader();
        } catch (IOException e) {
            throw new SaeDumpReadException("Could not read dump meta header", e);
        }
    }

    private SaeDumpMeta readMetaHeader() throws IOException {
        String firstMsg = this.readUntilNextSeparator();
        return this.objectMapper.readValue(firstMsg, SaeDumpMeta.class);
    }

    @Override
    public boolean hasNext() {
        int nextChar;
        
        try {
            this.reader.mark(1);
            nextChar = this.reader.read();
            this.reader.reset();
        } catch (IOException e) {
            throw new SaeDumpReadException("Could not read from file", e);
        }

        return nextChar != -1;
    }

    @Override
    public SaeMessage next() {
        String nextMsgStr;
        try {
            nextMsgStr = this.readUntilNextSeparator();
        } catch (IOException e) {
            throw new SaeDumpReadException("Could not read from file", e);
        }
        
        SaeDumpEvent nextEvent;
        try {
            nextEvent = this.objectMapper.readValue(nextMsgStr, SaeDumpEvent.class);
        } catch (JsonProcessingException e) {
            throw new SaeDumpReadException("Could not parse dump event JSON", e);
        }

        SaeMessage message;
        try {
            message = SaeMessage.parseFrom(Base64.getDecoder().decode(nextEvent.getDataB64()));
        } catch (InvalidProtocolBufferException e) {
            throw new SaeDumpReadException("Could not parse SaeMessage proto", e);
        }

        return message;
    }

    private String readUntilNextSeparator() throws IOException {
        int nextInt;
        String nextChar;
        StringBuffer buffer = new StringBuffer();
        
        do {
            nextInt = this.reader.read();

            nextChar = Character.toString(nextInt);
            if (nextChar.equals(MSG_SEPARATOR)) {
                break;
            }
            
            buffer.append(nextChar);
        } while (nextInt != EOF);

        return buffer.toString();
    }

    @Override
    public void close() {
        try {
            this.reader.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

}
