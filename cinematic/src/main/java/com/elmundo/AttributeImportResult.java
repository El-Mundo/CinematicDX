package com.elmundo;

public class AttributeImportResult {
    private int updatedValues;
    private int skippedValues;
    private int invalidValues;

    public int getUpdatedValues() {
        return updatedValues;
    }

    public void incrementUpdatedValues() {
        updatedValues++;
    }

    public int getSkippedValues() {
        return skippedValues;
    }

    public void incrementSkippedValues() {
        skippedValues++;
    }

    public int getInvalidValues() {
        return invalidValues;
    }

    public void incrementInvalidValues() {
        invalidValues++;
    }
}
