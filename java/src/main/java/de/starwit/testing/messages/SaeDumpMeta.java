package de.starwit.testing.messages;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

public class SaeDumpMeta {

    @JsonProperty("start_time")
    private float startTime;
    
    @JsonProperty("recorded_streams")
    private List<String> recordedStreams;

    public float getStartTime() {
        return startTime;
    }

    public void setStartTime(float startTime) {
        this.startTime = startTime;
    }

    public List<String> getRecordedStreams() {
        return recordedStreams;
    }

    public void setRecordedStreams(List<String> recordedStreams) {
        this.recordedStreams = recordedStreams;
    }
}
