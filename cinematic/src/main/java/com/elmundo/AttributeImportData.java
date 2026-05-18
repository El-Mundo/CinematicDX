package com.elmundo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

public class AttributeImportData {
    private final List<AttributeImportColumn> columns;
    private final List<String> unknownKeys;
    private final List<String> ignoredHeaders;

    public AttributeImportData(
            List<AttributeImportColumn> columns,
            List<String> unknownKeys,
            List<String> ignoredHeaders) {
        this.columns = columns;
        this.unknownKeys = unknownKeys;
        this.ignoredHeaders = ignoredHeaders;
    }

    public List<AttributeImportColumn> getColumns() {
        return Collections.unmodifiableList(columns);
    }

    public List<AttributeImportColumn> getImportableColumns() {
        return columns.stream()
                .filter(AttributeImportColumn::isImportable)
                .collect(Collectors.toList());
    }

    public List<String> getUnknownKeys() {
        return Collections.unmodifiableList(unknownKeys);
    }

    public List<String> getIgnoredHeaders() {
        return Collections.unmodifiableList(ignoredHeaders);
    }

    public int getEmptyValueCount() {
        int count = 0;
        for (AttributeImportColumn column : columns) {
            count += column.getEmptyValueCount();
        }
        return count;
    }

    public List<AttributeImportColumn> getColumnsWithExistingValues() {
        List<AttributeImportColumn> conflicts = new ArrayList<>();
        for (AttributeImportColumn column : columns) {
            if (column.isImportable() && column.hasExistingValues()) {
                conflicts.add(column);
            }
        }
        return conflicts;
    }
}
