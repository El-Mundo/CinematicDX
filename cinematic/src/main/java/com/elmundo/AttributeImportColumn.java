package com.elmundo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class AttributeImportColumn {
    private final String header;
    private final String normalizedName;
    private final AttributeTargetKind targetKind;
    private final String preservedColumnName;
    private final String ignoreReason;
    private final List<AttributeImportValue> values = new ArrayList<>();
    private AttributeFieldType fieldType;
    private boolean existingDefinition;
    private int emptyValueCount;
    private int existingValueCount;
    private int invalidValueCount;

    public AttributeImportColumn(
            String header,
            String normalizedName,
            AttributeTargetKind targetKind,
            String preservedColumnName,
            AttributeFieldType fieldType,
            String ignoreReason) {
        this.header = header;
        this.normalizedName = normalizedName;
        this.targetKind = targetKind;
        this.preservedColumnName = preservedColumnName;
        this.fieldType = fieldType;
        this.ignoreReason = ignoreReason;
    }

    public String getHeader() {
        return header;
    }

    public String getNormalizedName() {
        return normalizedName;
    }

    public AttributeTargetKind getTargetKind() {
        return targetKind;
    }

    public String getPreservedColumnName() {
        return preservedColumnName;
    }

    public AttributeFieldType getFieldType() {
        return fieldType;
    }

    public void setFieldType(AttributeFieldType fieldType) {
        this.fieldType = fieldType;
    }

    public boolean isExistingDefinition() {
        return existingDefinition;
    }

    public void setExistingDefinition(boolean existingDefinition) {
        this.existingDefinition = existingDefinition;
    }

    public int getEmptyValueCount() {
        return emptyValueCount;
    }

    public void incrementEmptyValueCount() {
        emptyValueCount++;
    }

    public int getExistingValueCount() {
        return existingValueCount;
    }

    public void setExistingValueCount(int existingValueCount) {
        this.existingValueCount = existingValueCount;
    }

    public int getInvalidValueCount() {
        return invalidValueCount;
    }

    public void incrementInvalidValueCount() {
        invalidValueCount++;
    }

    public List<AttributeImportValue> getValues() {
        return Collections.unmodifiableList(values);
    }

    public void addValue(AttributeImportValue value) {
        values.add(value);
    }

    public int getMatchedValueCount() {
        return values.size();
    }

    public int getNonEmptyValueCount() {
        int count = 0;
        for (AttributeImportValue value : values) {
            if (value.hasValue()) {
                count++;
            }
        }
        return count;
    }

    public String getTargetDisplay() {
        switch (targetKind) {
            case PRESERVED:
                return "Preserved field";
            case CUSTOM:
                return existingDefinition ? "Custom field (existing)" : "Custom field (new)";
            case IGNORED:
            default:
                return "Ignored";
        }
    }

    public String getTypeDisplay() {
        if (targetKind == AttributeTargetKind.PRESERVED) {
            return "preserved";
        }
        if (targetKind == AttributeTargetKind.IGNORED) {
            return "";
        }
        return fieldType == null ? "" : fieldType.getDisplayName();
    }

    public String getIgnoreReason() {
        return ignoreReason == null ? "" : ignoreReason;
    }

    public boolean hasExistingValues() {
        return existingValueCount > 0;
    }

    public boolean isImportable() {
        return targetKind != AttributeTargetKind.IGNORED && getNonEmptyValueCount() > 0;
    }
}
