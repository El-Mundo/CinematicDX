package com.elmundo;

import java.util.Locale;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/** Literal, case-insensitive catalog search; all whitespace-separated terms must match. */
final class FilmCatalogFilter {
    static final String ALL_YEARS = "All years";
    static final String ALL_STUDIOS = "All studios";
    static final String UNKNOWN_YEAR = "Unknown year";

    private FilmCatalogFilter() { }

    static boolean matches(FilmEntry film, String query, String year, String studio) {
        if (year != null && !ALL_YEARS.equals(year) && !yearLabel(film).equals(year)) {
            return false;
        }
        if (studio != null && !ALL_STUDIOS.equals(studio) && !studio.equals(film.getProduction())) {
            return false;
        }
        String haystack = Stream.of(film.getTitleOriginal(), film.getTitleTranslated(),
                film.getFilmKey(), film.getRomanized(), film.getProduction(),
                film.getColorFormat(), film.getSpecialAspects(), yearLabel(film))
                .filter(value -> value != null)
                .collect(Collectors.joining(" ")).toLowerCase(Locale.ROOT);
        for (String term : (query == null ? "" : query).strip().toLowerCase(Locale.ROOT).split("\\s+")) {
            if (!haystack.contains(term)) {
                return false;
            }
        }
        return true;
    }

    static String yearLabel(FilmEntry film) {
        return film.getProductionYear() == null ? UNKNOWN_YEAR : film.getProductionYear().toString();
    }
}
