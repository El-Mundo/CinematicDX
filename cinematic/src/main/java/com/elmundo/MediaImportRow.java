package com.elmundo;

public class MediaImportRow {
    private final int rowNumber;
    private final String filmKey;
    private final MediaStorageFormat storageFormat;
    private final String path;
    private final String normalizedPath;
    private final String pathHash;
    private final MediaType mediaType;
    private final String fileExtension;
    private MediaImportRowStatus status;
    private String warning;

    public MediaImportRow(
            int rowNumber,
            String filmKey,
            MediaStorageFormat storageFormat,
            String path,
            String normalizedPath,
            String pathHash,
            MediaType mediaType,
            String fileExtension,
            MediaImportRowStatus status,
            String warning) {
        this.rowNumber = rowNumber;
        this.filmKey = filmKey;
        this.storageFormat = storageFormat;
        this.path = path;
        this.normalizedPath = normalizedPath;
        this.pathHash = pathHash;
        this.mediaType = mediaType;
        this.fileExtension = fileExtension;
        this.status = status;
        this.warning = warning == null ? "" : warning;
    }

    public int getRowNumber() {
        return rowNumber;
    }

    public String getFilmKey() {
        return filmKey;
    }

    public MediaStorageFormat getStorageFormatValue() {
        return storageFormat;
    }

    public String getStorageFormat() {
        return storageFormat == null ? "" : storageFormat.getStorageName();
    }

    public String getPath() {
        return path;
    }

    public String getNormalizedPath() {
        return normalizedPath;
    }

    public String getPathHash() {
        return pathHash;
    }

    public MediaType getMediaTypeValue() {
        return mediaType;
    }

    public String getMediaType() {
        return mediaType == null ? "" : mediaType.getStorageName();
    }

    public String getFileExtension() {
        return fileExtension;
    }

    public MediaImportRowStatus getStatus() {
        return status;
    }

    public void setStatus(MediaImportRowStatus status) {
        this.status = status;
    }

    public String getWarning() {
        return warning;
    }

    public void setWarning(String warning) {
        this.warning = warning == null ? "" : warning;
    }

    public boolean isImportable() {
        return status == MediaImportRowStatus.ACTIVE;
    }

    public String duplicateKey() {
        if (storageFormat == null || mediaType == null || pathHash == null) {
            return "";
        }
        return filmKey + "|" + storageFormat.getStorageName() + "|"
                + mediaType.getStorageName() + "|" + pathHash;
    }
}
