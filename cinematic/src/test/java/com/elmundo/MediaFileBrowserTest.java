package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class MediaFileBrowserTest {
    @TempDir
    Path tempDir;

    @Test
    void localFileResolvesToParentDirectory() throws IOException {
        Path file = tempDir.resolve("bridge.mp4");
        Files.writeString(file, "");
        MediaStorageEntry entry = new MediaStorageEntry(
                1L,
                "bridge",
                "local-file",
                file.toString(),
                "original_video",
                "mp4");

        assertEquals(tempDir.toAbsolutePath().normalize(), MediaFileBrowser.resolveBrowserTarget(entry));
    }

    @Test
    void localDirectoryResolvesToItself() {
        MediaStorageEntry entry = new MediaStorageEntry(
                1L,
                "bridge",
                "local-file",
                tempDir.toString(),
                "annotations",
                "txt");

        assertEquals(tempDir.toAbsolutePath().normalize(), MediaFileBrowser.resolveBrowserTarget(entry));
    }

    @Test
    void ftpUrlCannotOpenInSystemBrowser() {
        MediaStorageEntry entry = new MediaStorageEntry(
                1L,
                "bridge",
                "ftp-url",
                "ftp://example.com/bridge.mp4",
                "original_video",
                "mp4");

        assertThrows(IllegalArgumentException.class, () -> MediaFileBrowser.resolveBrowserTarget(entry));
    }
}
