package com.elmundo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class CsvDuplicateGroup {
    private final String titleMatchKey;
    private final List<CsvFilmRow> csvRows = new ArrayList<>();
    private final List<FilmEntry> databaseFilms = new ArrayList<>();

    public CsvDuplicateGroup(String titleMatchKey) {
        this.titleMatchKey = titleMatchKey;
    }

    public String getTitleMatchKey() {
        return titleMatchKey;
    }

    public List<CsvFilmRow> getCsvRows() {
        return Collections.unmodifiableList(csvRows);
    }

    public List<FilmEntry> getDatabaseFilms() {
        return Collections.unmodifiableList(databaseFilms);
    }

    void addCsvRow(CsvFilmRow row) {
        csvRows.add(row);
    }

    void addDatabaseFilm(FilmEntry film) {
        databaseFilms.add(film);
    }

    public int totalCount() {
        return csvRows.size() + databaseFilms.size();
    }

    public String describe() {
        StringBuilder description = new StringBuilder();
        description.append(titleMatchKey).append(": ");
        description.append(csvRows.size()).append(" CSV row(s)");
        if (!databaseFilms.isEmpty()) {
            description.append(", ").append(databaseFilms.size()).append(" database film(s)");
        }
        return description.toString();
    }
}
