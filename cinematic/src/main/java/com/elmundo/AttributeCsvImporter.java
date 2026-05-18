package com.elmundo;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

public class AttributeCsvImporter {
    public AttributeImportData parse(
            Path path,
            Map<String, Long> filmIdsByKey,
            Map<String, AttributeFieldType> existingCustomFieldTypes) throws IOException {
        String csv = Files.readString(path, StandardCharsets.UTF_8);
        List<List<String>> records = parseRecords(csv);
        if (records.isEmpty()) {
            throw new IllegalArgumentException("The selected CSV file is empty.");
        }

        List<String> headers = records.get(0);
        int keyColumnIndex = findKeyColumnIndex(headers);
        if (keyColumnIndex < 0) {
            throw new IllegalArgumentException("Attribute CSV import requires a key column.");
        }

        List<AttributeImportColumn> columns = new ArrayList<>();
        List<Integer> columnIndexes = new ArrayList<>();
        List<String> ignoredHeaders = new ArrayList<>();
        for (int i = 0; i < headers.size(); i++) {
            if (i == keyColumnIndex) {
                continue;
            }

            AttributeImportColumn column = AttributeHeaderMapper.columnForHeader(
                    headers.get(i),
                    existingCustomFieldTypes);
            columns.add(column);
            columnIndexes.add(i);
            if (column.getTargetKind() == AttributeTargetKind.IGNORED) {
                ignoredHeaders.add(column.getHeader());
            }
        }

        Set<String> unknownKeys = new LinkedHashSet<>();
        for (int rowIndex = 1; rowIndex < records.size(); rowIndex++) {
            List<String> record = records.get(rowIndex);
            if (record.stream().allMatch(value -> value == null || value.isBlank())) {
                continue;
            }

            String filmKey = valueAt(record, keyColumnIndex).trim();
            Long filmId = filmIdsByKey.get(filmKey);
            if (filmId == null) {
                if (!filmKey.isEmpty()) {
                    unknownKeys.add(filmKey);
                }
                continue;
            }

            for (int columnPosition = 0; columnPosition < columns.size(); columnPosition++) {
                AttributeImportColumn column = columns.get(columnPosition);
                String value = valueAt(record, columnIndexes.get(columnPosition));
                if (!FilmDraft.hasText(value)) {
                    if (column.getTargetKind() != AttributeTargetKind.IGNORED) {
                        column.incrementEmptyValueCount();
                    }
                    continue;
                }
                if (column.getTargetKind() != AttributeTargetKind.IGNORED) {
                    column.addValue(new AttributeImportValue(filmId, filmKey, value.trim()));
                }
            }
        }

        inferCustomFieldTypes(columns);
        return new AttributeImportData(columns, new ArrayList<>(unknownKeys), ignoredHeaders);
    }

    private void inferCustomFieldTypes(List<AttributeImportColumn> columns) {
        for (AttributeImportColumn column : columns) {
            if (column.getTargetKind() != AttributeTargetKind.CUSTOM || column.isExistingDefinition()) {
                continue;
            }

            List<String> values = column.getValues().stream()
                    .map(AttributeImportValue::getRawValue)
                    .collect(Collectors.toList());
            column.setFieldType(AttributeValueConverter.inferType(values));
        }
    }

    private int findKeyColumnIndex(List<String> headers) {
        for (int i = 0; i < headers.size(); i++) {
            if (AttributeHeaderMapper.isKeyColumn(AttributeHeaderMapper.normalizeHeader(headers.get(i)))) {
                return i;
            }
        }
        return -1;
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
}
