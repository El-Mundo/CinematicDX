package com.elmundo;

import java.util.Locale;

public enum MediaType {
    ORIGINAL_VIDEO("original_video"),
    PROXY_VIDEO("proxy_video"),
    AUDIO_TRACK("audio_track"),
    SUBTITLES("subtitles"),
    ANNOTATIONS("annotations");

    private final String storageName;

    MediaType(String storageName) {
        this.storageName = storageName;
    }

    public String getStorageName() {
        return storageName;
    }

    @Override
    public String toString() {
        return storageName;
    }

    public static MediaType fromCsvValue(String value) {
        if (value == null) {
            throw new IllegalArgumentException("Media type is required.");
        }

        String normalized = value.trim().toLowerCase(Locale.ROOT).replace('-', '_').replace(' ', '_');
        for (MediaType mediaType : values()) {
            if (mediaType.storageName.equals(normalized)) {
                return mediaType;
            }
        }
        throw new IllegalArgumentException("Unsupported media type: " + value);
    }
}
