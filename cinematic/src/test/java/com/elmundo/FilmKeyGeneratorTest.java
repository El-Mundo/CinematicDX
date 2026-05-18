package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.sql.SQLException;
import java.util.HashSet;
import java.util.Set;

import org.junit.jupiter.api.Test;

class FilmKeyGeneratorTest {
    @Test
    void missingYearUsesUnknown() {
        assertEquals("桥-unknown", FilmKeyGenerator.baseKey("桥", null));
    }

    @Test
    void duplicateTitleAndYearUsesNumericAffixes() throws SQLException {
        Set<String> existingKeys = new HashSet<>();
        existingKeys.add("桥-1949");
        existingKeys.add("桥-1949-1");

        String key = FilmKeyGenerator.generateUniqueKey("桥", 1949, existingKeys::contains);

        assertEquals("桥-1949-2", key);
    }

    @Test
    void sameTitleDifferentYearsHaveDifferentBaseKeys() {
        assertEquals("桥-1949", FilmKeyGenerator.baseKey("桥", 1949));
        assertEquals("桥-1950", FilmKeyGenerator.baseKey("桥", 1950));
    }
}
