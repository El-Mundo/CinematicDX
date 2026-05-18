package com.elmundo;

import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;

public class MediaStorageEntry {
    private final Long id;
    private final String filmKey;
    private final String storageFormat;
    private final String path;
    private final String mediaType;
    private final String fileExtension;

    public MediaStorageEntry(
            Long id,
            String filmKey,
            String storageFormat,
            String path,
            String mediaType,
            String fileExtension) {
        this.id = id;
        this.filmKey = filmKey;
        this.storageFormat = storageFormat;
        this.path = path;
        this.mediaType = mediaType;
        this.fileExtension = fileExtension;
    }

    public Long getId() {
        return id;
    }

    public String getFilmKey() {
        return filmKey;
    }

    public String getStorageFormat() {
        return storageFormat;
    }

    public String getPath() {
        return path;
    }

    public String getMediaType() {
        return mediaType;
    }

    public String getFileExtension() {
        return fileExtension;
    }

    public String getStatus() {
        if (!MediaStorageFormat.LOCAL_FILE.getStorageName().equals(storageFormat)) {
            return "Remote";
        }

        try {
            return Files.exists(Path.of(path)) ? "Available" : "Missing local file";
        } catch (InvalidPathException e) {
            return "Invalid local path";
        }
    }
}
