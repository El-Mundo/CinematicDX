package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class CsvFilmImporterTest {
    @TempDir
    Path tempDir;

    @Test
    void unsupportedHeadersAreIgnoredAndReported() throws IOException {
        Path csv = tempDir.resolve("films.csv");
        Files.writeString(csv, "title,year,archive note\n桥,1949,ignored\n");

        CsvImportData data = new CsvFilmImporter().parse(csv);

        assertTrue(data.getUnsupportedHeaders().contains("archive note"));
        assertEquals(1, data.getRows().size());
        assertEquals("桥", data.getRows().get(0).getTitleOriginal());
    }

    @Test
    void blankTitleRowsAreInvalid() throws IOException {
        Path csv = tempDir.resolve("films.csv");
        Files.writeString(csv, "title,year\n,1949\n");

        CsvImportData data = new CsvFilmImporter().parse(csv);

        assertEquals(CsvFilmRowStatus.INVALID, data.getRows().get(0).getStatus());
        assertFalse(data.getRows().get(0).isImportable());
    }

    @Test
    void duplicateGroupsIncludeCsvAndDatabaseMatches() {
        CsvFilmImporter importer = new CsvFilmImporter();
        CsvFilmRow first = row(1, "桥", 1949);
        CsvFilmRow second = row(2, "桥", 1950);
        FilmEntry databaseFilm = new FilmEntry(
                1L,
                "桥-unknown",
                "桥",
                "The Bridge",
                null,
                null,
                null,
                null,
                null);

        List<CsvDuplicateGroup> groups = importer.buildDuplicateGroups(
                List.of(first, second),
                List.of(databaseFilm));

        assertEquals(1, groups.size());
        assertEquals(2, groups.get(0).getCsvRows().size());
        assertEquals(1, groups.get(0).getDatabaseFilms().size());
    }

    @Test
    void mergedRowsAreExcludedFromImportableRows() {
        CsvFilmImporter importer = new CsvFilmImporter();
        CsvFilmRow target = row(1, "桥", 1949);
        CsvFilmRow source = row(2, "桥", 1949);
        CsvImportData data = new CsvImportData(List.of(target, source), Collections.emptySet());

        importer.mergeRows(target, source);

        assertEquals(CsvFilmRowStatus.MERGED, source.getStatus());
        assertEquals(1, data.getImportableRows().size());
        assertEquals(target, data.getImportableRows().get(0));
    }

    private CsvFilmRow row(int rowId, String title, Integer year) {
        FilmDraft draft = new FilmDraft();
        draft.setTitleOriginal(title);
        draft.setProductionYear(year);
        return new CsvFilmRow(rowId, rowId + 1, draft);
    }

}
