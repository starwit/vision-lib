package de.starwit.testing.messages;

import com.fasterxml.jackson.annotation.JsonProperty;

public class SaeDumpEventMeta {

    @JsonProperty("record_time")
    private float recordTime;
    
    @JsonProperty("source_stream")
    private String sourceStream;

    public float getRecordTime() {
        return recordTime;
    }

    public void setRecordTime(float recordTime) {
        this.recordTime = recordTime;
    }
    
    public String getSourceStream() {
        return sourceStream;
    }
    
    public void setSourceStream(String sourceStream) {
        this.sourceStream = sourceStream;
    }
}
