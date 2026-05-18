package com.elmundo;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

public class CsvImportData {
    private final List<CsvFilmRow> rows;
    private final Set<String> unsupportedHeaders;

    public CsvImportData(List<CsvFilmRow> rows, Set<String> unsupportedHeaders) {
        this.rows = rows;
        this.unsupportedHeaders = new LinkedHashSet<>(unsupportedHeaders);
    }

    public List<CsvFilmRow> getRows() {
        return rows;
    }

    public Set<String> getUnsupportedHeaders() {
        return Collections.unmodifiableSet(unsupportedHeaders);
    }

    public List<CsvFilmRow> getImportableRows() {
        return rows.stream()
                .filter(CsvFilmRow::isImportable)
                .collect(Collectors.toList());
    }
}
