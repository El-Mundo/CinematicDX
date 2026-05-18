package com.elmundo;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

public class CsvFilmImporter {
    private enum Field {
        TITLE_ORIGINAL,
        TITLE_TRANSLATED,
        PRODUCTION_YEAR,
        PRODUCTION,
        COLOR_FORMAT,
        ROMANIZED,
        SPECIAL_ASPECTS
    }

    public CsvImportData parse(Path path) throws IOException {
        String csv = Files.readString(path, StandardCharsets.UTF_8);
        List<List<String>> records = parseRecords(csv);
        if (records.isEmpty()) {
            return new CsvImportData(new ArrayList<>(), new LinkedHashSet<>());
        }

        List<String> headers = records.get(0);
        Map<Integer, Field> supportedColumns = new LinkedHashMap<>();
        Set<String> unsupportedHeaders = new LinkedHashSet<>();

        for (int i = 0; i < headers.size(); i++) {
            String header = headers.get(i);
            Field field = fieldForHeader(header);
            if (field == null) {
                unsupportedHeaders.add(header);
            } else {
                supportedColumns.put(i, field);
            }
        }

        List<CsvFilmRow> rows = new ArrayList<>();
        int rowId = 1;
        for (int i = 1; i < records.size(); i++) {
            List<String> record = records.get(i);
            if (record.stream().allMatch(value -> value == null || value.isBlank())) {
                continue;
            }

            FilmDraft draft = new FilmDraft();
            CsvFilmRow row = new CsvFilmRow(rowId++, i + 1, draft);
            applyRecord(record, supportedColumns, draft, row);
            if (!draft.hasTitle()) {
                row.setStatus(CsvFilmRowStatus.INVALID);
                row.getWarnings().add("Missing original-language title.");
            }
            rows.add(row);
        }

        return new CsvImportData(rows, unsupportedHeaders);
    }

    public List<CsvDuplicateGroup> buildDuplicateGroups(
            List<CsvFilmRow> rows,
            List<FilmEntry> databaseFilms) {
        Map<String, CsvDuplicateGroup> groups = new LinkedHashMap<>();

        for (CsvFilmRow row : rows) {
            if (row.getStatus() == CsvFilmRowStatus.MERGED || !row.getDraft().hasTitle()) {
                continue;
            }

            String titleKey = FilmKeyGenerator.normalizeTitleForMatch(row.getDraft().getTitleOriginal());
            groups.computeIfAbsent(titleKey, CsvDuplicateGroup::new).addCsvRow(row);
        }

        for (FilmEntry film : databaseFilms) {
            String titleKey = FilmKeyGenerator.normalizeTitleForMatch(film.getTitleOriginal());
            groups.computeIfAbsent(titleKey, CsvDuplicateGroup::new).addDatabaseFilm(film);
        }

        return groups.values().stream()
                .filter(group -> !group.getCsvRows().isEmpty() && group.totalCount() > 1)
                .collect(Collectors.toList());
    }

    public void mergeRows(CsvFilmRow target, CsvFilmRow source) {
        if (target == null || source == null || target == source || !source.isImportable()) {
            return;
        }

        target.getDraft().fillBlanksFrom(source.getDraft());
        source.markMergedInto(target.getRowId());
    }

    private void applyRecord(
            List<String> record,
            Map<Integer, Field> supportedColumns,
            FilmDraft draft,
            CsvFilmRow row) {
        for (Map.Entry<Integer, Field> column : supportedColumns.entrySet()) {
            String value = column.getKey() < record.size() ? record.get(column.getKey()) : "";
            switch (column.getValue()) {
                case TITLE_ORIGINAL:
                    draft.setTitleOriginal(value);
                    break;
                case TITLE_TRANSLATED:
                    draft.setTitleTranslated(value);
                    break;
                case PRODUCTION_YEAR:
                    draft.setProductionYear(parseYear(value, row));
                    break;
                case PRODUCTION:
                    draft.setProduction(value);
                    break;
                case COLOR_FORMAT:
                    draft.setColorFormat(value);
                    break;
                case ROMANIZED:
                    draft.setRomanized(value);
                    break;
                case SPECIAL_ASPECTS:
                    draft.setSpecialAspects(value);
                    break;
                default:
                    break;
            }
        }
    }

    private Integer parseYear(String value, CsvFilmRow row) {
        if (value == null || value.isBlank()) {
            return null;
        }

        try {
            return Integer.valueOf(value.trim());
        } catch (NumberFormatException e) {
            row.getWarnings().add("Invalid production year: " + value.trim());
            return null;
        }
    }

    private Field fieldForHeader(String header) {
        switch (normalizeHeader(header)) {
            case "title":
            case "originaltitle":
            case "titleoriginal":
            case "originalfilmtitle":
            case "titleinoriginallanguage":
            case "titleoriginallanguage":
                return Field.TITLE_ORIGINAL;
            case "translated":
            case "translatedtitle":
            case "titletranslated":
            case "englishtitle":
                return Field.TITLE_TRANSLATED;
            case "year":
            case "productionyear":
            case "yearofproduction":
                return Field.PRODUCTION_YEAR;
            case "production":
            case "studio":
            case "productionstudio":
                return Field.PRODUCTION;
            case "color":
            case "colour":
            case "colorformat":
            case "colourformat":
                return Field.COLOR_FORMAT;
            case "romanized":
            case "romanised":
            case "romanizedtitle":
            case "romanisedtitle":
                return Field.ROMANIZED;
            case "special":
            case "specialaspects":
            case "specialaspect":
                return Field.SPECIAL_ASPECTS;
            default:
                return null;
        }
    }

    private String normalizeHeader(String header) {
        if (header == null) {
            return "";
        }

        return header.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
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
