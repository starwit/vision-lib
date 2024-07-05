package de.starwit.testing.messages;

import com.fasterxml.jackson.annotation.JsonProperty;

public class SaeDumpEvent {

    private SaeDumpEventMeta meta;

    @JsonProperty("data_b64")
    private String dataB64;
    
    public SaeDumpEventMeta getMeta() {
        return meta;
    }

    public void setMeta(SaeDumpEventMeta meta) {
        this.meta = meta;
    }

    public String getDataB64() {
        return dataB64;
    }

    public void setDataB64(String dataB64) {
        this.dataB64 = dataB64;
    }
}
