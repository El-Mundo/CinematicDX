package com.elmundo;

public class AttributeImportCancelledException extends RuntimeException {
    public AttributeImportCancelledException() {
        super("Attribute import cancelled.");
    }
}
