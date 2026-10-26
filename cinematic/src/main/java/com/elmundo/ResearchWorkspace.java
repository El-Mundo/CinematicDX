package com.elmundo;

import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.util.Optional;

/** Locates local evidence without coupling the metadata store to research outputs. */
final class ResearchWorkspace {
    private ResearchWorkspace() { }

    static Optional<Path> findRoot() {
        try {
            String configured = System.getProperty("cinematicdx.workspace", "").trim();
            if (!configured.isEmpty()) {
                Path path = Path.of(configured).toAbsolutePath().normalize();
                return Files.isDirectory(path) ? Optional.of(path) : Optional.empty();
            }
            Path path = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
            while (path != null) {
                if (Files.isDirectory(path.resolve("cinematic"))
                        && Files.isDirectory(path.resolve("analysis-python"))) {
                    return Optional.of(path);
                }
                path = path.getParent();
            }
        } catch (InvalidPathException e) {
            return Optional.empty();
        }
        return Optional.empty();
    }

    static Optional<Path> existingPath(String relative) {
        return findRoot().map(root -> root.resolve(relative).normalize())
                .filter(path -> Files.exists(path));
    }
}
