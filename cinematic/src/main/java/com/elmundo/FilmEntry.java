package com.elmundo;

public class FilmEntry {
    private final Long id;
    private final String filmKey;
    private final String titleOriginal;
    private final String titleTranslated;
    private final Integer productionYear;
    private final String production;
    private final String colorFormat;
    private final String romanized;
    private final String specialAspects;

    public FilmEntry(
            Long id,
            String filmKey,
            String titleOriginal,
            String titleTranslated,
            Integer productionYear,
            String production,
            String colorFormat,
            String romanized,
            String specialAspects) {
        this.id = id;
        this.filmKey = filmKey;
        this.titleOriginal = titleOriginal;
        this.titleTranslated = titleTranslated;
        this.productionYear = productionYear;
        this.production = production;
        this.colorFormat = colorFormat;
        this.romanized = romanized;
        this.specialAspects = specialAspects;
    }

    public Long getId() {
        return id;
    }

    public String getFilmKey() {
        return filmKey;
    }

    public String getTitleOriginal() {
        return titleOriginal;
    }

    public String getTitleTranslated() {
        return titleTranslated;
    }

    public Integer getProductionYear() {
        return productionYear;
    }

    public String getProductionYearDisplay() {
        return FilmKeyGenerator.yearPart(productionYear);
    }

    public String getProduction() {
        return production;
    }

    public String getColorFormat() {
        return colorFormat;
    }

    public String getRomanized() {
        return romanized;
    }

    public String getSpecialAspects() {
        return specialAspects;
    }

    public String getTitle() {
        return titleOriginal;
    }

    public Integer getYear() {
        return productionYear;
    }

    public String getTranslated() {
        return titleTranslated;
    }

    public String getColour() {
        return colorFormat;
    }
}
