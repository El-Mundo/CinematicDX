package com.elmundo;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public class MediaCsvImporter {
    public MediaImportData parse(Path path, Map<String, Long> filmIdsByKey) throws IOException {
        String csv = Files.readString(path, StandardCharsets.UTF_8);
        List<List<String>> records = parseRecords(csv);
        if (records.isEmpty()) {
            throw new IllegalArgumentException("The selected CSV file is empty.");
        }

        HeaderIndexes headers = findRequiredHeaders(records.get(0));
        List<MediaImportRow> rows = new ArrayList<>();
        Set<String> seenObjects = new LinkedHashSet<>();
        for (int i = 1; i < records.size(); i++) {
            List<String> record = records.get(i);
            if (record.stream().allMatch(value -> value == null || value.isBlank())) {
                continue;
            }
            rows.add(parseRow(i + 1, record, headers, filmIdsByKey, seenObjects));
        }

        return new MediaImportData(rows);
    }

    private MediaImportRow parseRow(
            int rowNumber,
            List<String> record,
            HeaderIndexes headers,
            Map<String, Long> filmIdsByKey,
            Set<String> seenObjects) {
        String filmKey = valueAt(record, headers.keyIndex).trim();
        String storageFormatText = valueAt(record, headers.storageFormatIndex).trim();
        String pathText = valueAt(record, headers.pathIndex).trim();
        String mediaTypeText = valueAt(record, headers.mediaTypeIndex).trim();

        if (!FilmDraft.hasText(filmKey)
                || !FilmDraft.hasText(storageFormatText)
                || !FilmDraft.hasText(pathText)
                || !FilmDraft.hasText(mediaTypeText)) {
            return invalidRow(rowNumber, filmKey, "Missing required value.");
        }

        if (!filmIdsByKey.containsKey(filmKey)) {
            return new MediaImportRow(
                    rowNumber,
                    filmKey,
                    null,
                    pathText,
                    null,
                    null,
                    null,
                    "",
                    MediaImportRowStatus.UNKNOWN_KEY,
                    "Unknown film key.");
        }

        try {
            MediaStorageFormat storageFormat = MediaStorageFormat.fromCsvValue(storageFormatText);
            MediaType mediaType = MediaType.fromCsvValue(mediaTypeText);
            String normalizedPath = MediaPathUtil.normalizePathForStorage(storageFormat, pathText);
            String pathHash = MediaPathUtil.hashNormalizedPath(normalizedPath);
            String extension = MediaPathUtil.detectExtension(storageFormat, pathText);
            String warning = "";
            if (storageFormat == MediaStorageFormat.LOCAL_FILE
                    && !Files.exists(Path.of(normalizedPath))) {
                warning = "Local file does not exist.";
            }
            MediaImportRow row = new MediaImportRow(
                    rowNumber,
                    filmKey,
                    storageFormat,
                    pathText,
                    normalizedPath,
                    pathHash,
                    mediaType,
                    extension,
                    MediaImportRowStatus.ACTIVE,
                    warning);
            if (!seenObjects.add(row.duplicateKey())) {
                row.setStatus(MediaImportRowStatus.DUPLICATE);
                row.setWarning("Duplicate row in CSV.");
            }
            return row;
        } catch (IllegalArgumentException e) {
            return invalidRow(rowNumber, filmKey, e.getMessage());
        }
    }

    private MediaImportRow invalidRow(int rowNumber, String filmKey, String warning) {
        return new MediaImportRow(
                rowNumber,
                filmKey == null ? "" : filmKey,
                null,
                "",
                null,
                null,
                null,
                "",
                MediaImportRowStatus.INVALID,
                warning);
    }

    private HeaderIndexes findRequiredHeaders(List<String> headers) {
        int keyIndex = -1;
        int storageFormatIndex = -1;
        int pathIndex = -1;
        int mediaTypeIndex = -1;

        for (int i = 0; i < headers.size(); i++) {
            String normalized = normalizeHeader(headers.get(i));
            switch (normalized) {
                case "key":
                case "filmkey":
                    keyIndex = i;
                    break;
                case "storageformat":
                    storageFormatIndex = i;
                    break;
                case "path":
                case "mediapath":
                    pathIndex = i;
                    break;
                case "mediatype":
                    mediaTypeIndex = i;
                    break;
                default:
                    break;
            }
        }

        List<String> missing = new ArrayList<>();
        if (keyIndex < 0) {
            missing.add("key");
        }
        if (storageFormatIndex < 0) {
            missing.add("storage_format");
        }
        if (pathIndex < 0) {
            missing.add("path");
        }
        if (mediaTypeIndex < 0) {
            missing.add("media_type");
        }
        if (!missing.isEmpty()) {
            throw new IllegalArgumentException("Media CSV is missing required column(s): "
                    + String.join(", ", missing));
        }

        return new HeaderIndexes(keyIndex, storageFormatIndex, pathIndex, mediaTypeIndex);
    }

    private String normalizeHeader(String header) {
        if (header == null) {
            return "";
        }

        return header.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }

    private String valueAt(List<String> record, int index) {
        return index < record.size() ? record.get(index) : "";
    }

    private List<List<String>> parseRecords(String csv) {
        List<List<String>> records = new ArrayList<>();
        List<String> record = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean quoted = false;

        for (int i = 0; i < csv.length(); i++) {
            char c = csv.charAt(i);
            if (c == '"') {
                if (quoted && i + 1 < csv.length() && csv.charAt(i + 1) == '"') {
                    field.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
            } else if (c == ',' && !quoted) {
                record.add(field.toString());
                field.setLength(0);
            } else if ((c == '\n' || c == '\r') && !quoted) {
                if (c == '\r' && i + 1 < csv.length() && csv.charAt(i + 1) == '\n') {
                    i++;
                }
                record.add(field.toString());
                field.setLength(0);
                records.add(record);
                record = new ArrayList<>();
            } else {
                field.append(c);
            }
        }

        if (field.length() > 0 || !record.isEmpty()) {
            record.add(field.toString());
            records.add(record);
        }

        return records;
    }

    private static final class HeaderIndexes {
        private final int keyIndex;
        private final int storageFormatIndex;
        private final int pathIndex;
        private final int mediaTypeIndex;

        private HeaderIndexes(int keyIndex, int storageFormatIndex, int pathIndex, int mediaTypeIndex) {
            this.keyIndex = keyIndex;
            this.storageFormatIndex = storageFormatIndex;
            this.pathIndex = pathIndex;
            this.mediaTypeIndex = mediaTypeIndex;
        }
    }
}
