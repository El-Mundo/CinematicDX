package com.elmundo;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class FilmCatalogFilterTest {
    private final FilmEntry film = new FilmEntry(1L, "shang gan ling", "上甘岭",
            "The Battle of Sangkumryung Ridge", 1956, "Changchun Film Studio",
            "B&W", "Shang Gan Ling", null);

    @Test
    void findsChineseTitlesAndCaseInsensitiveTermsAcrossFields() {
        assertTrue(FilmCatalogFilter.matches(film, "上甘岭", null, null));
        assertTrue(FilmCatalogFilter.matches(film, "  CHANGCHUN   1956  ", null, null));
        assertTrue(FilmCatalogFilter.matches(film, "battle ridge", null, null));
    }

    @Test
    void combinesSearchWithExactYearAndStudioFilters() {
        assertTrue(FilmCatalogFilter.matches(film, "上", "1956", "Changchun Film Studio"));
        assertFalse(FilmCatalogFilter.matches(film, "上", "1955", "Changchun Film Studio"));
        assertFalse(FilmCatalogFilter.matches(film, "上", "1956", "Beijing Film Studio"));
        assertFalse(FilmCatalogFilter.matches(film, "battle unknown", null, null));
    }

    @Test
    void treatsSearchAsLiteralTextAndSupportsAnUnknownYear() {
        FilmEntry unknown = new FilmEntry(2L, "test", "[Restored]", null,
                null, null, null, null, null);
        assertTrue(FilmCatalogFilter.matches(unknown, "[", FilmCatalogFilter.UNKNOWN_YEAR, null));
        assertTrue(FilmCatalogFilter.matches(unknown, "", FilmCatalogFilter.ALL_YEARS,
                FilmCatalogFilter.ALL_STUDIOS));
        assertFalse(FilmCatalogFilter.matches(unknown, "", "1956", null));
        assertFalse(FilmCatalogFilter.matches(film, "", FilmCatalogFilter.UNKNOWN_YEAR, null));
    }
}
