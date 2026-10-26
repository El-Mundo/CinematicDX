package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class AppConfigTest {
    @TempDir
    Path tempDir;

    @Test
    void freshSetupRequiresAChoiceAndDoesNotCreateConfiguration() {
        Path target = tempDir.resolve("global/cinematicdx.properties");

        AppConfig config = AppConfig.load(target, null);

        assertNull(config.getMetadataSourceType());
        assertEquals("", config.getLocalDirectoryPath());
        assertEquals("", config.getPythonRuntimePath());
        assertFalse(config.shouldSaveUrl());
        assertFalse(config.shouldSaveUsername());
        assertFalse(config.shouldSavePassword());
        assertFalse(Files.exists(target));
    }

    @Test
    void legacySettingsAreReadWithoutInferringOrWritingASource() throws IOException {
        Path target = tempDir.resolve("global/cinematicdx.properties");
        Path legacy = writeLegacySettings();
        String original = Files.readString(legacy);

        AppConfig config = AppConfig.load(target, legacy);

        assertEquals(target, config.getConfigPath());
        assertNull(config.getMetadataSourceType());
        assertEquals("jdbc:mariadb://saved/films", config.getSavedUrl());
        assertEquals("researcher", config.getSavedUsername());
        assertEquals("saved-value", config.getSavedPassword());
        assertEquals("/configured/python", config.getPythonRuntimePath());
        assertFalse(Files.exists(target));
        assertEquals(original, Files.readString(legacy));
    }

    @Test
    void savingLocalChoicePreservesLegacyDatabasePreferences() throws IOException {
        Path target = tempDir.resolve("global/cinematicdx.properties");
        Path legacy = writeLegacySettings();
        String original = Files.readString(legacy);
        AppConfig config = AppConfig.load(target, legacy);

        config.updateMetadataSourceSettings(MetadataSourceType.LOCAL_DIRECTORY, "/research/metadata");
        config.save();
        AppConfig reopened = AppConfig.load(target, legacy);

        assertEquals(MetadataSourceType.LOCAL_DIRECTORY, reopened.getMetadataSourceType());
        assertEquals("/research/metadata", reopened.getLocalDirectoryPath());
        assertTrue(reopened.shouldSaveUrl());
        assertTrue(reopened.shouldSaveUsername());
        assertTrue(reopened.shouldSavePassword());
        assertEquals("jdbc:mariadb://saved/films", reopened.getSavedUrl());
        assertEquals("researcher", reopened.getSavedUsername());
        assertEquals("saved-value", reopened.getSavedPassword());
        assertEquals(original, Files.readString(legacy));
    }

    @Test
    void globalConfigurationTakesPrecedenceOverLegacySettings() throws IOException {
        Path target = tempDir.resolve("cinematicdx.properties");
        Files.writeString(target, "metadata.source=LOCAL_DIRECTORY\n"
                + "metadata.localDirectory=/selected/metadata\npython.runtime=/new/python\n");
        Path legacy = writeLegacySettings();

        AppConfig config = AppConfig.load(target, legacy);

        assertEquals(MetadataSourceType.LOCAL_DIRECTORY, config.getMetadataSourceType());
        assertEquals("/selected/metadata", config.getLocalDirectoryPath());
        assertEquals("/new/python", config.getPythonRuntimePath());
        assertEquals("", config.getSavedUrl());
    }

    @Test
    void unknownSourceRequiresAnExplicitChoiceEvenWithSavedDatabaseDetails() throws IOException {
        Path target = writeLegacySettings();
        Files.writeString(target, Files.readString(target) + "metadata.source=OTHER\n");

        AppConfig config = AppConfig.load(target, null);

        assertNull(config.getMetadataSourceType());
        assertEquals("jdbc:mariadb://saved/films", config.getSavedUrl());
    }

    @Test
    void databaseChoiceRetainsRememberedLocalDirectory() throws IOException {
        Path target = tempDir.resolve("cinematicdx.properties");
        AppConfig config = AppConfig.load(target, null);
        config.updateMetadataSourceSettings(MetadataSourceType.LOCAL_DIRECTORY, "/research/metadata");
        config.save();

        config.updateMetadataSourceSettings(MetadataSourceType.DATABASE, config.getLocalDirectoryPath());
        config.updateDatabaseSettings("jdbc:mariadb://chosen/films", "user", "unused", true, true, false);
        config.save();
        AppConfig reopened = AppConfig.load(target, null);

        assertEquals(MetadataSourceType.DATABASE, reopened.getMetadataSourceType());
        assertEquals("/research/metadata", reopened.getLocalDirectoryPath());
        assertEquals("jdbc:mariadb://chosen/films", reopened.getSavedUrl());
        assertEquals("", reopened.getSavedPassword());
    }

    @Test
    void unrelatedSettingsSurviveSavingASourceChoice() throws IOException {
        Path target = tempDir.resolve("cinematicdx.properties");
        Files.writeString(target, "future.setting=retained\n");
        AppConfig config = AppConfig.load(target, null);
        config.updateMetadataSourceSettings(MetadataSourceType.LOCAL_DIRECTORY, "/research/metadata");

        config.save();

        Properties written = new Properties();
        try (InputStream input = Files.newInputStream(target)) {
            written.load(input);
        }
        assertEquals("retained", written.getProperty("future.setting"));
    }

    @Test
    void configurationSaveFailureIsReportedToCaller() throws IOException {
        Path blockedParent = tempDir.resolve("not-a-directory");
        Files.writeString(blockedParent, "preserve this file");
        AppConfig config = AppConfig.load(blockedParent.resolve("cinematicdx.properties"), null);

        assertThrows(IOException.class, config::save);
        assertEquals("preserve this file", Files.readString(blockedParent));
    }

    private Path writeLegacySettings() throws IOException {
        Path legacy = tempDir.resolve("legacy.properties");
        Files.writeString(legacy, "db.saveUrl=true\ndb.url=jdbc:mariadb://saved/films\n"
                + "db.saveUsername=true\ndb.username=researcher\n"
                + "db.savePassword=true\ndb.password=saved-value\n"
                + "python.runtime=/configured/python\n");
        return legacy;
    }
}
