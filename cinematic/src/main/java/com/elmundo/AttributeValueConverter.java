package com.elmundo;

import java.util.List;
import java.util.Locale;
import java.util.stream.Collectors;

public final class AttributeValueConverter {
    private AttributeValueConverter() {
    }

    public static AttributeFieldType inferType(List<String> values) {
        List<String> nonEmptyValues = values.stream()
                .filter(FilmDraft::hasText)
                .map(String::trim)
                .collect(Collectors.toList());
        if (nonEmptyValues.isEmpty()) {
            return AttributeFieldType.STRING;
        }

        boolean anyVector = nonEmptyValues.stream().anyMatch(value -> value.contains("|"));
        if (anyVector) {
            if (!nonEmptyValues.stream().allMatch(value -> value.contains("|"))) {
                return AttributeFieldType.STRING;
            }
            if (nonEmptyValues.stream().allMatch(AttributeValueConverter::isIntegerVector)) {
                return AttributeFieldType.INTEGER_VECTOR;
            }
            if (nonEmptyValues.stream().allMatch(AttributeValueConverter::isDoubleVector)) {
                return AttributeFieldType.DOUBLE_VECTOR;
            }
            return AttributeFieldType.STRING;
        }

        if (nonEmptyValues.stream().allMatch(AttributeValueConverter::isBoolean)) {
            return AttributeFieldType.BOOLEAN;
        }
        if (nonEmptyValues.stream().allMatch(AttributeValueConverter::isInteger)) {
            return AttributeFieldType.INTEGER;
        }
        if (nonEmptyValues.stream().allMatch(AttributeValueConverter::isDouble)) {
            return AttributeFieldType.DOUBLE;
        }
        return AttributeFieldType.STRING;
    }

    public static String toJson(String rawValue, AttributeFieldType type) {
        if (rawValue == null) {
            throw new IllegalArgumentException("Attribute value is empty.");
        }

        String value = rawValue.trim();
        if (value.isEmpty()) {
            throw new IllegalArgumentException("Attribute value is empty.");
        }

        switch (type) {
            case INTEGER:
                return Long.toString(parseLong(value));
            case FLOAT:
                return Float.toString(parseFloat(value));
            case DOUBLE:
                return Double.toString(parseDouble(value));
            case BOOLEAN:
                return Boolean.toString(parseBoolean(value));
            case INTEGER_VECTOR:
                return vectorToJson(value, AttributeFieldType.INTEGER);
            case FLOAT_VECTOR:
                return vectorToJson(value, AttributeFieldType.FLOAT);
            case DOUBLE_VECTOR:
                return vectorToJson(value, AttributeFieldType.DOUBLE);
            case STRING:
            default:
                return quoteJsonString(value);
        }
    }

    public static String quoteJsonString(String value) {
        StringBuilder builder = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"':
                    builder.append("\\\"");
                    break;
                case '\\':
                    builder.append("\\\\");
                    break;
                case '\b':
                    builder.append("\\b");
                    break;
                case '\f':
                    builder.append("\\f");
                    break;
                case '\n':
                    builder.append("\\n");
                    break;
                case '\r':
                    builder.append("\\r");
                    break;
                case '\t':
                    builder.append("\\t");
                    break;
                default:
                    if (c < 0x20) {
                        builder.append(String.format("\\u%04x", (int) c));
                    } else {
                        builder.append(c);
                    }
                    break;
            }
        }
        builder.append('"');
        return builder.toString();
    }

    private static String vectorToJson(String value, AttributeFieldType scalarType) {
        String[] parts = value.split("\\|", -1);
        if (parts.length == 0) {
            throw new IllegalArgumentException("Vector cannot be empty.");
        }

        StringBuilder builder = new StringBuilder("[");
        for (int i = 0; i < parts.length; i++) {
            String part = parts[i].trim();
            if (part.isEmpty()) {
                throw new IllegalArgumentException("Vector contains an empty entry.");
            }
            if (i > 0) {
                builder.append(',');
            }
            builder.append(toJson(part, scalarType));
        }
        builder.append(']');
        return builder.toString();
    }

    private static boolean isIntegerVector(String value) {
        return isVectorOf(value, AttributeValueConverter::isInteger);
    }

    private static boolean isDoubleVector(String value) {
        return isVectorOf(value, AttributeValueConverter::isDouble);
    }

    private static boolean isVectorOf(String value, ValuePredicate predicate) {
        String[] parts = value.split("\\|", -1);
        if (parts.length == 0) {
            return false;
        }
        for (String part : parts) {
            if (!predicate.test(part.trim())) {
                return false;
            }
        }
        return true;
    }

    private static boolean isInteger(String value) {
        try {
            parseLong(value);
            return true;
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    private static boolean isDouble(String value) {
        try {
            parseDouble(value);
            return true;
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    private static boolean isBoolean(String value) {
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        return "true".equals(normalized) || "false".equals(normalized);
    }

    private static long parseLong(String value) {
        try {
            return Long.parseLong(value.trim());
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Expected an integer: " + value);
        }
    }

    private static float parseFloat(String value) {
        try {
            float parsed = Float.parseFloat(value.trim());
            if (!Float.isFinite(parsed)) {
                throw new IllegalArgumentException("Expected a finite float: " + value);
            }
            return parsed;
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Expected a float: " + value);
        }
    }

    private static double parseDouble(String value) {
        try {
            double parsed = Double.parseDouble(value.trim());
            if (!Double.isFinite(parsed)) {
                throw new IllegalArgumentException("Expected a finite double: " + value);
            }
            return parsed;
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Expected a double: " + value);
        }
    }

    private static boolean parseBoolean(String value) {
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        if ("true".equals(normalized)) {
            return true;
        }
        if ("false".equals(normalized)) {
            return false;
        }
        throw new IllegalArgumentException("Expected a boolean: " + value);
    }

    @FunctionalInterface
    private interface ValuePredicate {
        boolean test(String value);
    }
}
