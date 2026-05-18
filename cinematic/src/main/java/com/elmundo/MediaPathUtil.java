package com.elmundo;

import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.Set;

public final class MediaPathUtil {
    private static final Set<String> SUPPORTED_EXTENSIONS = Set.of("mp4", "mov", "mp3", "wav", "txt");

    private MediaPathUtil() {
    }

    public static String normalizePathForStorage(MediaStorageFormat storageFormat, String rawPath) {
        if (!FilmDraft.hasText(rawPath)) {
            throw new IllegalArgumentException("Path is required.");
        }

        String path = rawPath.trim();
        if (storageFormat == MediaStorageFormat.LOCAL_FILE) {
            try {
                return Path.of(path).toAbsolutePath().normalize().toString();
            } catch (InvalidPathException e) {
                throw new IllegalArgumentException("Invalid local file path: " + path);
            }
        }

        try {
            URI uri = new URI(path).normalize();
            if (!"ftp".equalsIgnoreCase(uri.getScheme())) {
                throw new IllegalArgumentException("FTP URL must use ftp://");
            }
            if (!FilmDraft.hasText(uri.getHost())) {
                throw new IllegalArgumentException("FTP URL must include a host.");
            }
            return uri.toString();
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("Invalid FTP URL: " + path);
        }
    }

    public static String detectExtension(MediaStorageFormat storageFormat, String rawPath) {
        String target = rawPath == null ? "" : rawPath.trim();
        if (storageFormat == MediaStorageFormat.FTP_URL) {
            try {
                target = new URI(target).getPath();
            } catch (URISyntaxException e) {
                throw new IllegalArgumentException("Invalid FTP URL: " + rawPath);
            }
        }

        int slash = Math.max(target.lastIndexOf('/'), target.lastIndexOf('\\'));
        String fileName = slash >= 0 ? target.substring(slash + 1) : target;
        int dot = fileName.lastIndexOf('.');
        if (dot < 0 || dot == fileName.length() - 1) {
            throw new IllegalArgumentException("Media path must include a supported file extension.");
        }

        String extension = fileName.substring(dot + 1).toLowerCase(Locale.ROOT);
        if (!SUPPORTED_EXTENSIONS.contains(extension)) {
            throw new IllegalArgumentException("Unsupported media extension: " + extension);
        }
        return extension;
    }

    public static String hashNormalizedPath(String normalizedPath) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(normalizedPath.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                builder.append(String.format("%02x", b));
            }
            return builder.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is not available.", e);
        }
    }
}
