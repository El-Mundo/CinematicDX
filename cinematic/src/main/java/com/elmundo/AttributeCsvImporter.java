package com.elmundo;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
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
        List<AttributeFilmTarget> targets = filmIdsByKey.entrySet().stream()
                .map(entry -> new AttributeFilmTarget(entry.getValue(), entry.getKey(), entry.getKey(), null))
                .collect(Collectors.toList());
        return parse(path, targets, existingCustomFieldTypes);
    }

    public AttributeImportData parse(
            Path path,
            List<AttributeFilmTarget> filmTargets,
            Map<String, AttributeFieldType> existingCustomFieldTypes) throws IOException {
        return parse(
                path,
                filmTargets,
                existingCustomFieldTypes,
                row -> AttributeAmbiguityChoice.IMPORT_TO_ALL);
    }

    public AttributeImportData parse(
            Path path,
            List<AttributeFilmTarget> filmTargets,
            Map<String, AttributeFieldType> existingCustomFieldTypes,
            AttributeAmbiguityResolver ambiguityResolver) throws IOException {
        String csv = Files.readString(path, StandardCharsets.UTF_8);
        List<List<String>> records = parseRecords(csv);
        if (records.isEmpty()) {
            throw new IllegalArgumentException("The selected CSV file is empty.");
        }

        List<String> headers = records.get(0);
        int keyColumnIndex = findKeyColumnIndex(headers);
        int titleColumnIndex = findTitleColumnIndex(headers);
        int yearColumnIndex = findYearColumnIndex(headers);
        if (keyColumnIndex < 0 && titleColumnIndex < 0) {
            throw new IllegalArgumentException(
                    "Attribute CSV import requires a key column or an original-title/title column.");
        }
        AttributeMatchMode matchMode = keyColumnIndex >= 0 ? AttributeMatchMode.KEY : AttributeMatchMode.TITLE;
        AttributeTargetIndex targetIndex = new AttributeTargetIndex(filmTargets);
        AttributeAmbiguityResolver resolver = ambiguityResolver == null
                ? row -> AttributeAmbiguityChoice.CANCEL
                : ambiguityResolver;

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

        Set<String> unmatchedIdentifiers = new LinkedHashSet<>();
        int ambiguousRowsImportedToAll = 0;
        int ambiguousRowsSkipped = 0;
        for (int rowIndex = 1; rowIndex < records.size(); rowIndex++) {
            List<String> record = records.get(rowIndex);
            if (record.stream().allMatch(value -> value == null || value.isBlank())) {
                continue;
            }

            ResolvedTargets resolvedTargets = resolveTargets(
                    record,
                    rowIndex + 1,
                    matchMode,
                    keyColumnIndex,
                    titleColumnIndex,
                    yearColumnIndex,
                    targetIndex);
            if (resolvedTargets.getTargets().isEmpty()) {
                if (!resolvedTargets.getIdentifierDisplay().isBlank()) {
                    unmatchedIdentifiers.add(resolvedTargets.getIdentifierDisplay());
                }
                continue;
            }

            List<AttributeFilmTarget> rowTargets = resolvedTargets.getTargets();
            if (rowTargets.size() > 1) {
                AttributeAmbiguityChoice choice = resolver.resolve(new AttributeAmbiguousRow(
                        rowIndex + 1,
                        resolvedTargets.getIdentifierDisplay(),
                        rowTargets));
                if (choice == AttributeAmbiguityChoice.CANCEL || choice == null) {
                    throw new AttributeImportCancelledException();
                }
                if (choice == AttributeAmbiguityChoice.SKIP) {
                    ambiguousRowsSkipped++;
                    continue;
                }
                ambiguousRowsImportedToAll++;
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
                    for (AttributeFilmTarget target : rowTargets) {
                        column.addValue(new AttributeImportValue(
                                target.getFilmId(),
                                target.getFilmKey(),
                                value.trim()));
                    }
                }
            }
        }

        inferCustomFieldTypes(columns);
        return new AttributeImportData(
                columns,
                new ArrayList<>(unmatchedIdentifiers),
                ignoredHeaders,
                matchMode,
                ambiguousRowsImportedToAll,
                ambiguousRowsSkipped);
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

    private int findTitleColumnIndex(List<String> headers) {
        for (int i = 0; i < headers.size(); i++) {
            if (AttributeHeaderMapper.isTitleColumn(AttributeHeaderMapper.normalizeHeader(headers.get(i)))) {
                return i;
            }
        }
        return -1;
    }

    private int findYearColumnIndex(List<String> headers) {
        for (int i = 0; i < headers.size(); i++) {
            if (AttributeHeaderMapper.isYearColumn(AttributeHeaderMapper.normalizeHeader(headers.get(i)))) {
                return i;
            }
        }
        return -1;
    }

    private ResolvedTargets resolveTargets(
            List<String> record,
            int rowNumber,
            AttributeMatchMode matchMode,
            int keyColumnIndex,
            int titleColumnIndex,
            int yearColumnIndex,
            AttributeTargetIndex targetIndex) {
        if (matchMode == AttributeMatchMode.KEY) {
            String filmKey = valueAt(record, keyColumnIndex).trim();
            if (!FilmDraft.hasText(filmKey)) {
                return ResolvedTargets.unmatched("row " + rowNumber + ": blank key");
            }
            return new ResolvedTargets(
                    targetIndex.findByKey(filmKey),
                    filmKey);
        }

        String title = valueAt(record, titleColumnIndex).trim();
        if (!FilmDraft.hasText(title)) {
            return ResolvedTargets.unmatched("row " + rowNumber + ": blank title");
        }

        if (yearColumnIndex >= 0) {
            String yearText = valueAt(record, yearColumnIndex).trim();
            if (FilmDraft.hasText(yearText)) {
                try {
                    Integer productionYear = Integer.valueOf(yearText);
                    return new ResolvedTargets(
                            targetIndex.findByTitleAndYear(title, productionYear),
                            "title '" + title + "' year " + productionYear);
                } catch (NumberFormatException e) {
                    return ResolvedTargets.unmatched(
                            "row " + rowNumber + ": title '" + title + "' invalid year '" + yearText + "'");
                }
            }
        }

        return new ResolvedTargets(
                targetIndex.findByTitle(title),
                "title '" + title + "'");
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

    private static class AttributeTargetIndex {
        private final Map<String, AttributeFilmTarget> targetsByKey = new LinkedHashMap<>();
        private final Map<String, List<AttributeFilmTarget>> targetsByTitle = new LinkedHashMap<>();

        AttributeTargetIndex(List<AttributeFilmTarget> targets) {
            for (AttributeFilmTarget target : targets) {
                targetsByKey.put(target.getFilmKey(), target);
                String titleKey = FilmKeyGenerator.normalizeTitleForMatch(target.getTitleOriginal());
                targetsByTitle.computeIfAbsent(titleKey, key -> new ArrayList<>()).add(target);
            }
        }

        List<AttributeFilmTarget> findByKey(String filmKey) {
            AttributeFilmTarget target = targetsByKey.get(filmKey);
            if (target == null) {
                return Collections.emptyList();
            }
            return Collections.singletonList(target);
        }

        List<AttributeFilmTarget> findByTitle(String title) {
            return targetsByTitle.getOrDefault(
                    FilmKeyGenerator.normalizeTitleForMatch(title),
                    Collections.emptyList());
        }

        List<AttributeFilmTarget> findByTitleAndYear(String title, Integer productionYear) {
            return findByTitle(title).stream()
                    .filter(target -> productionYear.equals(target.getProductionYear()))
                    .collect(Collectors.toList());
        }
    }

    private static class ResolvedTargets {
        private final List<AttributeFilmTarget> targets;
        private final String identifierDisplay;

        ResolvedTargets(List<AttributeFilmTarget> targets, String identifierDisplay) {
            this.targets = targets;
            this.identifierDisplay = identifierDisplay;
        }

        static ResolvedTargets unmatched(String identifierDisplay) {
            return new ResolvedTargets(Collections.emptyList(), identifierDisplay);
        }

        List<AttributeFilmTarget> getTargets() {
            return targets;
        }

        String getIdentifierDisplay() {
            return identifierDisplay;
        }
    }
}
