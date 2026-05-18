package com.elmundo;

import java.util.LinkedHashMap;
import java.util.Map;

public class FilmDraft {
    private String titleOriginal;
    private String titleTranslated;
    private Integer productionYear;
    private String production;
    private String colorFormat;
    private String romanized;
    private String specialAspects;
    private final Map<String, String> customFields = new LinkedHashMap<>();

    public String getTitleOriginal() {
        return titleOriginal;
    }

    public void setTitleOriginal(String titleOriginal) {
        this.titleOriginal = clean(titleOriginal);
    }

    public String getTitleTranslated() {
        return titleTranslated;
    }

    public void setTitleTranslated(String titleTranslated) {
        this.titleTranslated = clean(titleTranslated);
    }

    public Integer getProductionYear() {
        return productionYear;
    }

    public void setProductionYear(Integer productionYear) {
        this.productionYear = productionYear;
    }

    public String getProduction() {
        return production;
    }

    public void setProduction(String production) {
        this.production = clean(production);
    }

    public String getColorFormat() {
        return colorFormat;
    }

    public void setColorFormat(String colorFormat) {
        this.colorFormat = clean(colorFormat);
    }

    public String getRomanized() {
        return romanized;
    }

    public void setRomanized(String romanized) {
        this.romanized = clean(romanized);
    }

    public String getSpecialAspects() {
        return specialAspects;
    }

    public void setSpecialAspects(String specialAspects) {
        this.specialAspects = clean(specialAspects);
    }

    public Map<String, String> getCustomFields() {
        return customFields;
    }

    public boolean hasTitle() {
        return titleOriginal != null && !titleOriginal.isBlank();
    }

    public boolean hasNonBlankValues() {
        return hasTitle()
                || hasText(titleTranslated)
                || productionYear != null
                || hasText(production)
                || hasText(colorFormat)
                || hasText(romanized)
                || hasText(specialAspects)
                || !customFields.isEmpty();
    }

    public void fillBlanksFrom(FilmDraft other) {
        if (!hasText(titleOriginal)) {
            setTitleOriginal(other.getTitleOriginal());
        }
        if (!hasText(titleTranslated)) {
            setTitleTranslated(other.getTitleTranslated());
        }
        if (productionYear == null) {
            setProductionYear(other.getProductionYear());
        }
        if (!hasText(production)) {
            setProduction(other.getProduction());
        }
        if (!hasText(colorFormat)) {
            setColorFormat(other.getColorFormat());
        }
        if (!hasText(romanized)) {
            setRomanized(other.getRomanized());
        }
        if (!hasText(specialAspects)) {
            setSpecialAspects(other.getSpecialAspects());
        }
        other.getCustomFields().forEach(customFields::putIfAbsent);
    }

    public static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private String clean(String value) {
        if (value == null) {
            return null;
        }

        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
