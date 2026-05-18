package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

class FilmRepositoryTest {
    @Test
    void insertsUniqueKeysForDuplicateTitleAndYear() throws SQLException {
        try (Connection connection = openConnection()) {
            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);

            repository.insertAsUnique(connection, draft("桥", 1949, "The Bridge"));
            repository.insertAsUnique(connection, draft("桥", 1949, "Bridge Variant"));

            List<FilmEntry> films = repository.findAll(connection);

            assertEquals(2, films.size());
            assertEquals("桥-1949", films.get(0).getFilmKey());
            assertEquals("桥-1949-1", films.get(1).getFilmKey());
        }
    }

    @Test
    void overwriteKeepsExistingValuesWhenIncomingFieldsAreBlank() throws SQLException {
        try (Connection connection = openConnection()) {
            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);
            FilmEntry existing = repository.insertAsUnique(connection, draft("桥", 1949, "The Bridge"));

            FilmDraft incoming = new FilmDraft();
            incoming.setTitleOriginal("桥");
            incoming.setProductionYear(1949);
            incoming.setProduction("Northeast Film Studio");

            repository.overwriteWithNonBlankValues(connection, existing.getId(), incoming);
            FilmEntry updated = repository.findById(connection, existing.getId()).orElseThrow();

            assertEquals("The Bridge", updated.getTitleTranslated());
            assertEquals("Northeast Film Studio", updated.getProduction());
        }
    }

    @Test
    void findsConflictsByTitleAndMissingYear() throws SQLException {
        try (Connection connection = openConnection()) {
            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);
            repository.insertAsUnique(connection, draft("桥", null, "The Bridge"));

            FilmDraft incoming = draft(" 桥 ", null, null);

            assertTrue(repository.findMatchingTitleAndYear(connection, incoming).isPresent());
        }
    }

    @Test
    void importsCustomAttributeValuesAsJson() throws SQLException {
        try (Connection connection = openConnection()) {
            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);
            FilmEntry film = repository.insertAsUnique(connection, draft("桥", 1949, "The Bridge"));

            AttributeImportColumn column = new AttributeImportColumn(
                    "score",
                    "score",
                    AttributeTargetKind.CUSTOM,
                    null,
                    AttributeFieldType.INTEGER,
                    null);
            column.addValue(new AttributeImportValue(film.getId(), film.getFilmKey(), "10"));
            AttributeImportData data = new AttributeImportData(List.of(column), List.of(), List.of());

            AttributeImportResult result = repository.importAttributes(
                    connection,
                    data,
                    Map.of(column, AttributeOverwriteChoice.OVERWRITE));

            assertEquals(1, result.getUpdatedValues());
            assertEquals("10", readCustomValue(connection, "score"));
            assertEquals(AttributeFieldType.INTEGER, repository.findCustomFieldTypes(connection).get("score"));
        }
    }

    @Test
    void importsPreservedAttributeValuesAndKeepsExistingWhenRequested() throws SQLException {
        try (Connection connection = openConnection()) {
            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);
            FilmEntry film = repository.insertAsUnique(connection, draft("桥", 1949, "The Bridge"));

            AttributeImportColumn column = new AttributeImportColumn(
                    "color format",
                    "colorformat",
                    AttributeTargetKind.PRESERVED,
                    "color_format",
                    null,
                    null);
            column.addValue(new AttributeImportValue(film.getId(), film.getFilmKey(), "B&W"));
            AttributeImportData data = new AttributeImportData(List.of(column), List.of(), List.of());
            repository.importAttributes(connection, data, Map.of(column, AttributeOverwriteChoice.OVERWRITE));

            AttributeImportColumn replacement = new AttributeImportColumn(
                    "color format",
                    "colorformat",
                    AttributeTargetKind.PRESERVED,
                    "color_format",
                    null,
                    null);
            replacement.addValue(new AttributeImportValue(film.getId(), film.getFilmKey(), "Colour"));
            repository.importAttributes(
                    connection,
                    new AttributeImportData(List.of(replacement), List.of(), List.of()),
                    Map.of(replacement, AttributeOverwriteChoice.KEEP_EXISTING));

            FilmEntry updated = repository.findById(connection, film.getId()).orElseThrow();
            assertEquals("B&W", updated.getColorFormat());
        }
    }

    @Test
    void migratesLegacyCustomFieldRowsToJsonValues() throws SQLException {
        try (Connection connection = openConnection()) {
            try (Statement statement = connection.createStatement()) {
                statement.executeUpdate("CREATE TABLE film_custom_fields ("
                        + "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                        + "film_id BIGINT NOT NULL, "
                        + "field_name VARCHAR(255), "
                        + "field_value TEXT)");
            }

            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);
            FilmEntry film = repository.insertAsUnique(connection, draft("桥", 1949, "The Bridge"));

            try (PreparedStatement statement = connection.prepareStatement(
                    "INSERT INTO film_custom_fields (film_id, field_name, field_value) VALUES (?, ?, ?)")) {
                statement.setLong(1, film.getId());
                statement.setString(2, "Archive Note");
                statement.setString(3, "kept");
                statement.executeUpdate();
            }

            repository.initializeDatabase(connection);

            assertEquals("\"kept\"", readCustomValue(connection, "archivenote"));
        }
    }

    @Test
    void importsMultipleMediaStorageRowsForSameKeyAndSkipsDuplicates() throws SQLException {
        try (Connection connection = openConnection()) {
            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);
            FilmEntry film = repository.insertAsUnique(connection, draft("桥", 1949, "The Bridge"));

            MediaImportRow video = mediaRow(film.getFilmKey(), "/tmp/bridge.mp4", MediaType.ORIGINAL_VIDEO);
            MediaImportRow audio = mediaRow(film.getFilmKey(), "/tmp/bridge.wav", MediaType.AUDIO_TRACK);
            MediaImportRow duplicateVideo = mediaRow(film.getFilmKey(), "/tmp/../tmp/bridge.mp4", MediaType.ORIGINAL_VIDEO);
            MediaImportData data = new MediaImportData(List.of(video, audio, duplicateVideo));
            repository.populateExistingMediaDuplicates(connection, data);

            MediaImportResult firstResult = repository.importMediaStorage(connection, data);
            repository.populateExistingMediaDuplicates(connection, data);
            MediaImportResult secondResult = repository.importMediaStorage(connection, data);

            assertEquals(2, firstResult.getImportedRows());
            assertEquals(1, firstResult.getSkippedRows());
            assertEquals(0, secondResult.getImportedRows());
            assertEquals(3, secondResult.getSkippedRows());
            assertEquals(2, repository.findMediaStorageByFilmKey(connection, film.getFilmKey()).size());
        }
    }

    @Test
    void mediaStorageTableExistsAfterInitialization() throws SQLException {
        try (Connection connection = openConnection()) {
            FilmRepository repository = new FilmRepository();
            repository.initializeDatabase(connection);

            try (ResultSet resultSet = connection.getMetaData()
                    .getTables(connection.getCatalog(), null, "film_media_storage", null)) {
                assertTrue(resultSet.next());
            }
        }
    }

    private Connection openConnection() throws SQLException {
        return DriverManager.getConnection("jdbc:h2:mem:" + System.nanoTime()
                + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE");
    }

    private FilmDraft draft(String title, Integer year, String translated) {
        FilmDraft draft = new FilmDraft();
        draft.setTitleOriginal(title);
        draft.setProductionYear(year);
        draft.setTitleTranslated(translated);
        return draft;
    }

    private MediaImportRow mediaRow(String filmKey, String path, MediaType mediaType) {
        MediaStorageFormat storageFormat = MediaStorageFormat.LOCAL_FILE;
        String normalizedPath = MediaPathUtil.normalizePathForStorage(storageFormat, path);
        return new MediaImportRow(
                1,
                filmKey,
                storageFormat,
                path,
                normalizedPath,
                MediaPathUtil.hashNormalizedPath(normalizedPath),
                mediaType,
                MediaPathUtil.detectExtension(storageFormat, path),
                MediaImportRowStatus.ACTIVE,
                "");
    }

    private String readCustomValue(Connection connection, String normalizedName) throws SQLException {
        String sql = "SELECT fcf.value_json FROM film_custom_fields fcf "
                + "JOIN custom_field_definitions cfd ON cfd.id = fcf.custom_field_id "
                + "WHERE cfd.normalized_name = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, normalizedName);
            try (ResultSet resultSet = statement.executeQuery()) {
                resultSet.next();
                return resultSet.getString(1);
            }
        }
    }
}
