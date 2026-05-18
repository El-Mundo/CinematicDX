package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class MediaCsvImporterTest {
    @TempDir
    Path tempDir;

    @Test
    void missingRequiredHeadersRejectImport() throws IOException {
        Path csv = tempDir.resolve("media.csv");
        Files.writeString(csv, "key,path\nbridge,/tmp/bridge.mp4\n");

        assertThrows(IllegalArgumentException.class, () ->
                new MediaCsvImporter().parse(csv, Map.of("bridge", 1L)));
    }

    @Test
    void repeatedKeysCanCreateMultipleMediaRows() throws IOException {
        Path csv = tempDir.resolve("media.csv");
        Files.writeString(csv, "key,storage_format,path,media_type\n"
                + "bridge,local-file,/tmp/bridge.mp4,original_video\n"
                + "bridge,local-file,/tmp/bridge.wav,audio_track\n");

        MediaImportData data = new MediaCsvImporter().parse(csv, Map.of("bridge", 1L));

        assertEquals(2, data.getValidRowCount());
        assertEquals(0, data.getDuplicateRowCount());
    }

    @Test
    void unsupportedStorageFormatMediaTypeAndExtensionAreInvalid() throws IOException {
        Path csv = tempDir.resolve("media.csv");
        Files.writeString(csv, "key,storage_format,path,media_type\n"
                + "bridge,http-url,/tmp/bridge.mp4,original_video\n"
                + "bridge,local-file,/tmp/bridge.avi,original_video\n"
                + "bridge,local-file,/tmp/bridge.mp4,poster\n");

        MediaImportData data = new MediaCsvImporter().parse(csv, Map.of("bridge", 1L));

        assertEquals(3, data.getInvalidRowCount());
    }

    @Test
    void ftpUrlAndTxtExtensionsAreAccepted() throws IOException {
        Path csv = tempDir.resolve("media.csv");
        Files.writeString(csv, "key,storage_format,path,media_type\n"
                + "bridge,ftp-url,ftp://example.com/subtitles/bridge.txt,subtitles\n");

        MediaImportData data = new MediaCsvImporter().parse(csv, Map.of("bridge", 1L));

        assertEquals(1, data.getValidRowCount());
        assertEquals("txt", data.getRows().get(0).getFileExtension());
    }

    @Test
    void duplicateStorageObjectsInCsvAreSkipped() throws IOException {
        Path csv = tempDir.resolve("media.csv");
        Files.writeString(csv, "key,storage_format,path,media_type\n"
                + "bridge,local-file,/tmp/../tmp/bridge.mp4,original_video\n"
                + "bridge,local-file,/tmp/bridge.mp4,original_video\n");

        MediaImportData data = new MediaCsvImporter().parse(csv, Map.of("bridge", 1L));

        assertEquals(1, data.getValidRowCount());
        assertEquals(1, data.getDuplicateRowCount());
    }

    @Test
    void unknownKeysAreReported() throws IOException {
        Path csv = tempDir.resolve("media.csv");
        Files.writeString(csv, "key,storage_format,path,media_type\n"
                + "missing,local-file,/tmp/bridge.mp4,original_video\n");

        MediaImportData data = new MediaCsvImporter().parse(csv, Map.of("bridge", 1L));

        assertEquals(1, data.getUnknownKeyCount());
    }
}
