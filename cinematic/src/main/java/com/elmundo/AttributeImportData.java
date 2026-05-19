package com.elmundo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

public class AttributeImportData {
    private final List<AttributeImportColumn> columns;
    private final List<String> unknownKeys;
    private final List<String> ignoredHeaders;
    private final AttributeMatchMode matchMode;
    private final int ambiguousRowsImportedToAll;
    private final int ambiguousRowsSkipped;

    public AttributeImportData(
            List<AttributeImportColumn> columns,
            List<String> unknownKeys,
            List<String> ignoredHeaders) {
        this(columns, unknownKeys, ignoredHeaders, AttributeMatchMode.KEY, 0, 0);
    }

    public AttributeImportData(
            List<AttributeImportColumn> columns,
            List<String> unknownKeys,
            List<String> ignoredHeaders,
            AttributeMatchMode matchMode,
            int ambiguousRowsImportedToAll,
            int ambiguousRowsSkipped) {
        this.columns = columns;
        this.unknownKeys = unknownKeys;
        this.ignoredHeaders = ignoredHeaders;
        this.matchMode = matchMode;
        this.ambiguousRowsImportedToAll = ambiguousRowsImportedToAll;
        this.ambiguousRowsSkipped = ambiguousRowsSkipped;
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

    public List<String> getUnmatchedIdentifiers() {
        return getUnknownKeys();
    }

    public List<String> getIgnoredHeaders() {
        return Collections.unmodifiableList(ignoredHeaders);
    }

    public AttributeMatchMode getMatchMode() {
        return matchMode;
    }

    public int getAmbiguousRowsImportedToAll() {
        return ambiguousRowsImportedToAll;
    }

    public int getAmbiguousRowsSkipped() {
        return ambiguousRowsSkipped;
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
