package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class AttributeCsvImporterTest {
    @TempDir
    Path tempDir;

    @Test
    void missingKeyColumnRejectsImport() throws IOException {
        Path csv = tempDir.resolve("attributes.csv");
        Files.writeString(csv, "film,score\n桥-1949,10\n");

        AttributeCsvImporter importer = new AttributeCsvImporter();

        assertThrows(IllegalArgumentException.class, () ->
                importer.parse(csv, Map.of("桥-1949", 1L), Collections.emptyMap()));
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
