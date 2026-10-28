package com.elmundo;

/** A backend-neutral failure while opening or accessing film metadata. */
public class MetadataStoreException extends Exception {
    public MetadataStoreException(String message) {
        super(message);
    }

    public MetadataStoreException(String message, Throwable cause) {
        super(message, cause);
    }
}
