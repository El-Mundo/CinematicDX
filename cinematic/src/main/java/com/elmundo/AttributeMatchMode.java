package com.elmundo;

public enum AttributeMatchMode {
    KEY("key"),
    TITLE("title/title-year");

    private final String displayName;

    AttributeMatchMode(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
