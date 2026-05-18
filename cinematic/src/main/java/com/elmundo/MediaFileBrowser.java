package com.elmundo;

import java.awt.Desktop;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;

public final class MediaFileBrowser {
    private MediaFileBrowser() {
    }

    public static Path resolveBrowserTarget(MediaStorageEntry entry) {
        if (entry == null) {
            throw new IllegalArgumentException("Select a media mapping first.");
        }
        if (!MediaStorageFormat.LOCAL_FILE.getStorageName().equals(entry.getStorageFormat())) {
            throw new IllegalArgumentException("Only local-file media can be shown in the system file browser.");
        }

        try {
            Path path = Path.of(entry.getPath()).toAbsolutePath().normalize();
            if (!Files.exists(path)) {
                throw new IllegalArgumentException("Local media path does not exist: " + path);
            }
            if (Files.isDirectory(path)) {
                return path;
            }

            Path parent = path.getParent();
            if (parent == null || !Files.exists(parent)) {
                throw new IllegalArgumentException("Local media parent folder does not exist: " + path);
            }
            return parent;
        } catch (InvalidPathException e) {
            throw new IllegalArgumentException("Invalid local media path: " + entry.getPath());
        }
    }

    public static void showInSystemFileBrowser(MediaStorageEntry entry) throws IOException {
        Path target = resolveBrowserTarget(entry);
        if (!Desktop.isDesktopSupported() || !Desktop.getDesktop().isSupported(Desktop.Action.OPEN)) {
            throw new IllegalStateException("System file browser is not supported in this environment.");
        }

        File targetFile = target.toFile();
        Desktop.getDesktop().open(targetFile);
    }
}
