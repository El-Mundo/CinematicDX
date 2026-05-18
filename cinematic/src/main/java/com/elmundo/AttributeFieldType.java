package com.elmundo;

public enum AttributeFieldType {
    STRING("string"),
    INTEGER("integer"),
    INTEGER_VECTOR("integer vector"),
    FLOAT("float"),
    FLOAT_VECTOR("float vector"),
    DOUBLE("double-precision float"),
    DOUBLE_VECTOR("double-precision vector"),
    BOOLEAN("boolean");

    private final String displayName;

    AttributeFieldType(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getStorageName() {
        return name().toLowerCase();
    }

    @Override
    public String toString() {
        return displayName;
    }

    public boolean isVector() {
        return this == INTEGER_VECTOR || this == FLOAT_VECTOR || this == DOUBLE_VECTOR;
    }

    public static AttributeFieldType fromStorageName(String value) {
        if (value == null || value.isBlank()) {
            return STRING;
        }

        String normalized = value.trim().toUpperCase().replace('-', '_').replace(' ', '_');
        if ("DOUBLE_PRECISION_FLOAT".equals(normalized)) {
            return DOUBLE;
        }
        if ("DOUBLE_PRECISION_VECTOR".equals(normalized)) {
            return DOUBLE_VECTOR;
        }

        try {
            return AttributeFieldType.valueOf(normalized);
        } catch (IllegalArgumentException e) {
            return STRING;
        }
    }
}
