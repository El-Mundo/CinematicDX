package com.elmundo;

import java.util.Locale;

public enum MediaStorageFormat {
    FTP_URL("ftp-url"),
    LOCAL_FILE("local-file");

    private final String storageName;

    MediaStorageFormat(String storageName) {
        this.storageName = storageName;
    }

    public String getStorageName() {
        return storageName;
    }

    @Override
    public String toString() {
        return storageName;
    }

    public static MediaStorageFormat fromCsvValue(String value) {
        if (value == null) {
            throw new IllegalArgumentException("Storage format is required.");
        }

        String normalized = value.trim().toLowerCase(Locale.ROOT).replace('_', '-');
        for (MediaStorageFormat format : values()) {
            if (format.storageName.equals(normalized)) {
                return format;
            }
        }
        throw new IllegalArgumentException("Unsupported storage format: " + value);
    }
}
