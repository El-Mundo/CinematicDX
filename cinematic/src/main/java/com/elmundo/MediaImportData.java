package com.elmundo;

import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

public class MediaImportData {
    private final List<MediaImportRow> rows;

    public MediaImportData(List<MediaImportRow> rows) {
        this.rows = rows;
    }

    public List<MediaImportRow> getRows() {
        return Collections.unmodifiableList(rows);
    }

    public List<MediaImportRow> getImportableRows() {
        return rows.stream()
                .filter(MediaImportRow::isImportable)
                .collect(Collectors.toList());
    }

    public int getTotalRowCount() {
        return rows.size();
    }

    public int getValidRowCount() {
        return count(MediaImportRowStatus.ACTIVE);
    }

    public int getUnknownKeyCount() {
        return count(MediaImportRowStatus.UNKNOWN_KEY);
    }

    public int getInvalidRowCount() {
        return count(MediaImportRowStatus.INVALID);
    }

    public int getDuplicateRowCount() {
        return count(MediaImportRowStatus.DUPLICATE);
    }

    private int count(MediaImportRowStatus status) {
        int count = 0;
        for (MediaImportRow row : rows) {
            if (row.getStatus() == status) {
                count++;
            }
        }
        return count;
    }
}
