package com.elmundo;

public class AttributeFilmTarget {
    private final long filmId;
    private final String filmKey;
    private final String titleOriginal;
    private final Integer productionYear;

    public AttributeFilmTarget(long filmId, String filmKey, String titleOriginal, Integer productionYear) {
        this.filmId = filmId;
        this.filmKey = filmKey;
        this.titleOriginal = titleOriginal;
        this.productionYear = productionYear;
    }

    public long getFilmId() {
        return filmId;
    }

    public String getFilmKey() {
        return filmKey;
    }

    public String getTitleOriginal() {
        return titleOriginal;
    }

    public Integer getProductionYear() {
        return productionYear;
    }

    public String getDisplayText() {
        return titleOriginal + " (" + FilmKeyGenerator.yearPart(productionYear) + ") [" + filmKey + "]";
    }
}
