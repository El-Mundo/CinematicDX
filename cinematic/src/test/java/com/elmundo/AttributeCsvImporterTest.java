package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class AttributeCsvImporterTest {
    @TempDir
    Path tempDir;

    @Test
    void missingIdentifierColumnsRejectImport() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "score\n10\n");

        AttributeCsvImporter importer = new AttributeCsvImporter();

        assertThrows(IllegalArgumentException.class, () ->
                importer.parse(csv, Map.of("桥-1949", 1L), Collections.emptyMap()));
    }

    @Test
    void titleAndYearMatchImportsToMatchingFilm() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "title,year,score\n桥,1949,10\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                List.of(
                        new AttributeFilmTarget(1L, "桥-1949", "桥", 1949),
                        new AttributeFilmTarget(2L, "桥-1950", "桥", 1950)),
                Collections.emptyMap());

        AttributeImportColumn scoreColumn = data.getImportableColumns().get(0);
        assertEquals(AttributeMatchMode.TITLE, data.getMatchMode());
        assertEquals(1, scoreColumn.getValues().size());
        assertEquals(1L, scoreColumn.getValues().get(0).getFilmId());
    }

    @Test
    void titleOnlyMatchImportsToSingleMatchingFilm() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "title,score\n独生,8\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                List.of(
                        new AttributeFilmTarget(1L, "桥-1949", "桥", 1949),
                        new AttributeFilmTarget(2L, "独生-unknown", "独生", null)),
                Collections.emptyMap());

        AttributeImportColumn scoreColumn = data.getImportableColumns().get(0);
        assertEquals(1, scoreColumn.getValues().size());
        assertEquals(2L, scoreColumn.getValues().get(0).getFilmId());
    }

    @Test
    void ambiguousTitleOnlyMatchCanImportToAllMatchingFilms() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "title,score\n桥,10\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                List.of(
                        new AttributeFilmTarget(1L, "桥-1949", "桥", 1949),
                        new AttributeFilmTarget(2L, "桥-1950", "桥", 1950)),
                Collections.emptyMap(),
                row -> AttributeAmbiguityChoice.IMPORT_TO_ALL);

        AttributeImportColumn scoreColumn = data.getImportableColumns().get(0);
        assertEquals(1, data.getAmbiguousRowsImportedToAll());
        assertEquals(2, scoreColumn.getValues().size());
        assertEquals(1L, scoreColumn.getValues().get(0).getFilmId());
        assertEquals(2L, scoreColumn.getValues().get(1).getFilmId());
    }

    @Test
    void ambiguousTitleYearMatchCanBeSkipped() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "title,year,score\n桥,1949,10\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                List.of(
                        new AttributeFilmTarget(1L, "桥-1949", "桥", 1949),
                        new AttributeFilmTarget(2L, "桥-1949-1", "桥", 1949)),
                Collections.emptyMap(),
                row -> AttributeAmbiguityChoice.SKIP);

        assertEquals(1, data.getAmbiguousRowsSkipped());
        assertTrue(data.getImportableColumns().isEmpty());
    }

    @Test
    void unknownTitleRowsAreIgnored() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "title,year,score\n不存在,1949,10\n桥,1949,20\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                List.of(new AttributeFilmTarget(1L, "桥-1949", "桥", 1949)),
                Collections.emptyMap());

        assertEquals(1, data.getUnmatchedIdentifiers().size());
        assertEquals(1, data.getImportableColumns().get(0).getNonEmptyValueCount());
    }

    @Test
    void unknownKeysAreIgnored() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "key,score\nunknown-key,10\n桥-1949,20\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                Map.of("桥-1949", 1L),
                Collections.emptyMap());

        assertEquals(1, data.getUnknownKeys().size());
        assertEquals("unknown-key", data.getUnknownKeys().get(0));
        assertEquals(1, data.getImportableColumns().get(0).getNonEmptyValueCount());
    }

    @Test
    void emptyValuesAreCountedAndSkipped() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "key,score\n桥-1949,\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                Map.of("桥-1949", 1L),
                Collections.emptyMap());

        assertEquals(1, data.getEmptyValueCount());
        assertTrue(data.getImportableColumns().isEmpty());
    }

    @Test
    void pipeVectorsPreserveOrderAsJsonArrays() {
        AttributeFieldType type = AttributeValueConverter.inferType(
                java.util.List.of("1|2|3", "4|5|6"));

        assertEquals(AttributeFieldType.INTEGER_VECTOR, type);
        assertEquals("[1,2,3]", AttributeValueConverter.toJson("1|2|3", type));
    }

    @Test
    void preservedAndProtectedHeadersAreClassified() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "key,color format,title,actors,score\n桥-1949,B&W,ignored,Actor A,9.5\n");

        AttributeImportData data = new AttributeCsvImporter().parse(
                csv,
                Map.of("桥-1949", 1L),
                Collections.emptyMap());

        assertEquals(AttributeTargetKind.PRESERVED, data.getColumns().get(0).getTargetKind());
        assertEquals("color_format", data.getColumns().get(0).getPreservedColumnName());
        assertEquals(AttributeTargetKind.IGNORED, data.getColumns().get(1).getTargetKind());
        assertEquals(AttributeTargetKind.PRESERVED, data.getColumns().get(2).getTargetKind());
        assertEquals("actors", data.getColumns().get(2).getPreservedColumnName());
        assertEquals(AttributeFieldType.DOUBLE, data.getColumns().get(3).getFieldType());
    }
}
