package com.elmundo;

import java.sql.SQLException;
import java.text.Normalizer;
import java.util.Locale;

public final class FilmKeyGenerator {
    private FilmKeyGenerator() {
    }

    @FunctionalInterface
    public interface KeyExists {
        boolean exists(String key) throws SQLException;
    }

    public static String generateUniqueKey(String titleOriginal, Integer productionYear, KeyExists keyExists)
            throws SQLException {
        String baseKey = baseKey(titleOriginal, productionYear);
        if (!keyExists.exists(baseKey)) {
            return baseKey;
        }

        int suffix = 1;
        while (true) {
            String candidate = baseKey + "-" + suffix;
            if (!keyExists.exists(candidate)) {
                return candidate;
            }
            suffix++;
        }
    }

    public static String baseKey(String titleOriginal, Integer productionYear) {
        return normalizeTitleForKey(titleOriginal) + "-" + yearPart(productionYear);
    }

    public static String normalizeTitleForKey(String titleOriginal) {
        if (titleOriginal == null) {
            return "untitled";
        }

        String normalized = Normalizer.normalize(titleOriginal.trim(), Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT)
                .replaceAll("\\s+", "-")
                .replaceAll("[^\\p{L}\\p{N}._-]+", "-")
                .replaceAll("-+", "-")
                .replaceAll("^-|-$", "");
        return normalized.isEmpty() ? "untitled" : normalized;
    }

    public static String normalizeTitleForMatch(String titleOriginal) {
        if (titleOriginal == null) {
            return "";
        }

        return Normalizer.normalize(titleOriginal.trim(), Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT)
                .replaceAll("\\s+", " ");
    }

    public static String yearPart(Integer productionYear) {
        return productionYear == null ? "unknown" : productionYear.toString();
    }
}
