package com.elmundo;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

public final class AttributeHeaderMapper {
    private static final Map<String, String> PRESERVED_COLUMNS = new LinkedHashMap<>();

    static {
        PRESERVED_COLUMNS.put("translated", "title_translated");
        PRESERVED_COLUMNS.put("translatedtitle", "title_translated");
        PRESERVED_COLUMNS.put("titletranslated", "title_translated");
        PRESERVED_COLUMNS.put("englishtitle", "title_translated");
        PRESERVED_COLUMNS.put("production", "production");
        PRESERVED_COLUMNS.put("studio", "production");
        PRESERVED_COLUMNS.put("productionstudio", "production");
        PRESERVED_COLUMNS.put("color", "color_format");
        PRESERVED_COLUMNS.put("colour", "color_format");
        PRESERVED_COLUMNS.put("colorformat", "color_format");
        PRESERVED_COLUMNS.put("colourformat", "color_format");
        PRESERVED_COLUMNS.put("romanized", "romanized");
        PRESERVED_COLUMNS.put("romanised", "romanized");
        PRESERVED_COLUMNS.put("romanizedtitle", "romanized");
        PRESERVED_COLUMNS.put("romanisedtitle", "romanized");
        PRESERVED_COLUMNS.put("special", "special_aspects");
        PRESERVED_COLUMNS.put("specialaspect", "special_aspects");
        PRESERVED_COLUMNS.put("specialaspects", "special_aspects");
        PRESERVED_COLUMNS.put("director", "director");
        PRESERVED_COLUMNS.put("directors", "director");
        PRESERVED_COLUMNS.put("scriptwriter", "scriptwriter");
        PRESERVED_COLUMNS.put("scriptwriters", "scriptwriter");
        PRESERVED_COLUMNS.put("writer", "scriptwriter");
        PRESERVED_COLUMNS.put("writers", "scriptwriter");
        PRESERVED_COLUMNS.put("actor", "actors");
        PRESERVED_COLUMNS.put("actors", "actors");
        PRESERVED_COLUMNS.put("cast", "actors");
        PRESERVED_COLUMNS.put("staff", "staff");
        PRESERVED_COLUMNS.put("otherstaff", "other_staff");
        PRESERVED_COLUMNS.put("path", "media_path");
        PRESERVED_COLUMNS.put("mediapath", "media_path");
        PRESERVED_COLUMNS.put("storageformat", "storage_format");
        PRESERVED_COLUMNS.put("mediaformat", "storage_format");
        PRESERVED_COLUMNS.put("mediatype", "media_type");
    }

    private AttributeHeaderMapper() {
    }

    public static AttributeImportColumn columnForHeader(
            String header,
            Map<String, AttributeFieldType> existingCustomFieldTypes) {
        String normalized = normalizeHeader(header);
        if (isKeyColumn(normalized) || isProtectedKeyingColumn(normalized)) {
            return new AttributeImportColumn(
                    header,
                    normalized,
                    AttributeTargetKind.IGNORED,
                    null,
                    null,
                    "Keying field");
        }

        String preservedColumn = PRESERVED_COLUMNS.get(normalized);
        if (preservedColumn != null) {
            return new AttributeImportColumn(
                    header,
                    normalized,
                    AttributeTargetKind.PRESERVED,
                    preservedColumn,
                    null,
                    null);
        }

        AttributeFieldType existingType = existingCustomFieldTypes.get(normalized);
        AttributeImportColumn column = new AttributeImportColumn(
                header,
                normalized,
                AttributeTargetKind.CUSTOM,
                null,
                existingType == null ? AttributeFieldType.STRING : existingType,
                null);
        column.setExistingDefinition(existingType != null);
        return column;
    }

    public static boolean isKeyColumn(String normalizedHeader) {
        return "key".equals(normalizedHeader) || "filmkey".equals(normalizedHeader);
    }

    public static boolean isProtectedKeyingColumn(String normalizedHeader) {
        return isTitleColumn(normalizedHeader) || isYearColumn(normalizedHeader);
    }

    public static boolean isTitleColumn(String normalizedHeader) {
        switch (normalizedHeader) {
            case "title":
            case "originaltitle":
            case "titleoriginal":
            case "originalfilmtitle":
            case "titleinoriginallanguage":
            case "titleoriginallanguage":
                return true;
            default:
                return false;
        }
    }

    public static boolean isYearColumn(String normalizedHeader) {
        switch (normalizedHeader) {
            case "year":
            case "productionyear":
            case "yearofproduction":
                return true;
            default:
                return false;
        }
    }

    public static String normalizeHeader(String header) {
        if (header == null) {
            return "";
        }

        return header.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }
}
