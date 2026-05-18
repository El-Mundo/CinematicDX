package com.elmundo;

import java.util.ArrayList;
import java.util.List;

public class CsvFilmRow {
    private final int rowId;
    private final int sourceLineNumber;
    private final FilmDraft draft;
    private final List<String> warnings = new ArrayList<>();
    private CsvFilmRowStatus status;
    private Integer mergedIntoRowId;

    public CsvFilmRow(int rowId, int sourceLineNumber, FilmDraft draft) {
        this.rowId = rowId;
        this.sourceLineNumber = sourceLineNumber;
        this.draft = draft;
        this.status = CsvFilmRowStatus.ACTIVE;
    }

    public int getRowId() {
        return rowId;
    }

    public int getSourceLineNumber() {
        return sourceLineNumber;
    }

    public FilmDraft getDraft() {
        return draft;
    }

    public CsvFilmRowStatus getStatus() {
        return status;
    }

    public void setStatus(CsvFilmRowStatus status) {
        this.status = status;
    }

    public Integer getMergedIntoRowId() {
        return mergedIntoRowId;
    }

    public void markMergedInto(int targetRowId) {
        this.status = CsvFilmRowStatus.MERGED;
        this.mergedIntoRowId = targetRowId;
    }

    public List<String> getWarnings() {
        return warnings;
    }

    public boolean isImportable() {
        return status == CsvFilmRowStatus.ACTIVE && draft.hasTitle();
    }

    public String getTitleOriginal() {
        return draft.getTitleOriginal();
    }

    public String getTitleTranslated() {
        return draft.getTitleTranslated();
    }

    public Integer getProductionYear() {
        return draft.getProductionYear();
    }

    public String getProduction() {
        return draft.getProduction();
    }

    public String getColorFormat() {
        return draft.getColorFormat();
    }

    public String getWarningText() {
        if (warnings.isEmpty()) {
            return "";
        }

        return String.join("; ", warnings);
    }
}
