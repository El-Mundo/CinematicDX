package com.elmundo;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.StandardCopyOption;
import java.util.Properties;

public class AppConfig {
    private static final String CONFIG_FILE_NAME = "cinematicdx.properties";
    private static final String METADATA_SOURCE = "metadata.source";
    private static final String LOCAL_DIRECTORY = "metadata.localDirectory";
    private static final String PYTHON_RUNTIME = "python.runtime";
    private static final String SAVE_URL = "db.saveUrl";
    private static final String DB_URL = "db.url";
    private static final String SAVE_USERNAME = "db.saveUsername";
    private static final String DB_USERNAME = "db.username";
    private static final String SAVE_PASSWORD = "db.savePassword";
    private static final String DB_PASSWORD = "db.password";

    private final Path configPath;
    private final Properties properties;

    private AppConfig(Path configPath, Properties properties) {
        this.configPath = configPath;
        this.properties = properties;
    }

    public static AppConfig load() {
        String explicitPath = System.getProperty("cinematicdx.config", "").trim();
        if (!explicitPath.isEmpty()) {
            return load(Path.of(explicitPath), null);
        }
        Path configPath = Path.of(System.getProperty("user.home"), ".cinematicdx", CONFIG_FILE_NAME);
        return load(configPath, resolveLegacyConfigPath());
    }

    public static AppConfig load(Path target, Path legacy) {
        Path configPath = target.toAbsolutePath().normalize();
        Path readPath = Files.exists(configPath) ? configPath : legacy;
        Properties properties = new Properties();

        if (readPath != null && Files.exists(readPath)) {
            try (InputStream input = Files.newInputStream(readPath)) {
                properties.load(input);
            } catch (IOException | IllegalArgumentException e) {
                System.err.println("Could not load config file " + readPath + ": " + e.getMessage());
            }
        }

        return new AppConfig(configPath, properties);
    }

    public Path getConfigPath() {
        return configPath;
    }

    public MetadataSourceType getMetadataSourceType() {
        String value = properties.getProperty(METADATA_SOURCE, "").trim();
        if (value.isEmpty()) {
            return null;
        }
        try {
            return MetadataSourceType.valueOf(value);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    public String getLocalDirectoryPath() {
        return properties.getProperty(LOCAL_DIRECTORY, "");
    }

    public void updateMetadataSourceSettings(MetadataSourceType type, String directory) {
        setOrRemove(METADATA_SOURCE, type == null ? "" : type.name());
        setOrRemove(LOCAL_DIRECTORY, directory);
    }

    public String getPythonRuntimePath() {
        return properties.getProperty(PYTHON_RUNTIME, "");
    }

    public void setPythonRuntimePath(String pythonRuntimePath) {
        setOrRemove(PYTHON_RUNTIME, pythonRuntimePath);
    }

    public boolean shouldSaveUrl() {
        return Boolean.parseBoolean(properties.getProperty(SAVE_URL, "false"));
    }

    public String getSavedUrl() {
        return properties.getProperty(DB_URL, "");
    }

    public boolean shouldSaveUsername() {
        return Boolean.parseBoolean(properties.getProperty(SAVE_USERNAME, "false"));
    }

    public String getSavedUsername() {
        return properties.getProperty(DB_USERNAME, "");
    }

    public boolean shouldSavePassword() {
        return Boolean.parseBoolean(properties.getProperty(SAVE_PASSWORD, "false"));
    }

    public String getSavedPassword() {
        return properties.getProperty(DB_PASSWORD, "");
    }

    public void updateDatabaseSettings(
            String url,
            String username,
            String password,
            boolean saveUrl,
            boolean saveUsername,
            boolean savePassword) {
        properties.setProperty(SAVE_URL, Boolean.toString(saveUrl));
        properties.setProperty(SAVE_USERNAME, Boolean.toString(saveUsername));
        properties.setProperty(SAVE_PASSWORD, Boolean.toString(savePassword));

        setOrRemove(DB_URL, saveUrl ? url : "");
        setOrRemove(DB_USERNAME, saveUsername ? username : "");
        if (savePassword) {
            properties.setProperty(DB_PASSWORD, password == null ? "" : password);
        } else {
            properties.remove(DB_PASSWORD);
        }
    }

    public void save() throws IOException {
        Path parent = configPath.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Path temporary = Files.createTempFile(parent, "cinematicdx-config-", ".tmp");
        try {
            try (OutputStream output = Files.newOutputStream(temporary)) {
                properties.store(output, "CinematicDX configuration");
            }
            try {
                Files.move(temporary, configPath,
                        StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            } catch (AtomicMoveNotSupportedException e) {
                Files.move(temporary, configPath, StandardCopyOption.REPLACE_EXISTING);
            }
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    private void setOrRemove(String key, String value) {
        if (value == null || value.isBlank()) {
            properties.remove(key);
            return;
        }

        properties.setProperty(key, value.trim());
    }

    private static Path resolveLegacyConfigPath() {
        try {
            Path location = Path.of(AppConfig.class.getProtectionDomain()
                    .getCodeSource()
                    .getLocation()
                    .toURI()).toAbsolutePath().normalize();
            Path directory = Files.isRegularFile(location) ? location.getParent() : location;
            return directory.resolve(CONFIG_FILE_NAME);
        } catch (URISyntaxException | IllegalArgumentException | NullPointerException e) {
            return Path.of(System.getProperty("user.dir"))
                    .toAbsolutePath()
                    .normalize()
                    .resolve(CONFIG_FILE_NAME);
        }
    }
}
