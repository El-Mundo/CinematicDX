package com.elmundo;

public class FilmEntry {
    private final String romanized;
    private final String title;
    private final Integer year;
    private final String translated;
    private final String production;
    private final String colour;
    private final String specialAspects;

    public FilmEntry(
            String romanized,
            String title,
            Integer year,
            String translated,
            String production,
            String colour,
            String specialAspects) {
        this.romanized = romanized;
        this.title = title;
        this.year = year;
        this.translated = translated;
        this.production = production;
        this.colour = colour;
        this.specialAspects = specialAspects;
    }

    public String getRomanized() {
        return romanized;
    }

    public String getTitle() {
        return title;
    }

    public Integer getYear() {
        return year;
    }

    public String getTranslated() {
        return translated;
    }

    public String getProduction() {
        return production;
    }

    public String getColour() {
        return colour;
    }

    public String getSpecialAspects() {
        return specialAspects;
    }
}
