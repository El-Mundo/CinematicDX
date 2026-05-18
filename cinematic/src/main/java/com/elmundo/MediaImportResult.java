package com.elmundo;

public class MediaImportResult {
    private int importedRows;
    private int skippedRows;

    public int getImportedRows() {
        return importedRows;
    }

    public void incrementImportedRows() {
        importedRows++;
    }

    public int getSkippedRows() {
        return skippedRows;
    }

    public void incrementSkippedRows() {
        skippedRows++;
    }
}
