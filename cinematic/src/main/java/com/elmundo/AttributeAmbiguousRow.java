package com.elmundo;

import java.util.Collections;
import java.util.List;

public class AttributeAmbiguousRow {
    private final int rowNumber;
    private final String identifierDisplay;
    private final List<AttributeFilmTarget> targets;

    public AttributeAmbiguousRow(
            int rowNumber,
            String identifierDisplay,
            List<AttributeFilmTarget> targets) {
        this.rowNumber = rowNumber;
        this.identifierDisplay = identifierDisplay;
        this.targets = List.copyOf(targets);
    }

    public int getRowNumber() {
        return rowNumber;
    }

    public String getIdentifierDisplay() {
        return identifierDisplay;
    }

    public List<AttributeFilmTarget> getTargets() {
        return Collections.unmodifiableList(targets);
    }
}
