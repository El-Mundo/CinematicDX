package com.elmundo;

public class AttributeImportValue {
    private final long filmId;
    private final String filmKey;
    private final String rawValue;

    public AttributeImportValue(long filmId, String filmKey, String rawValue) {
        this.filmId = filmId;
        this.filmKey = filmKey;
        this.rawValue = rawValue;
    }

    public long getFilmId() {
        return filmId;
    }

    public String getFilmKey() {
        return filmKey;
    }

    public String getRawValue() {
        return rawValue;
    }

    public boolean hasValue() {
        return FilmDraft.hasText(rawValue);
    }
}
