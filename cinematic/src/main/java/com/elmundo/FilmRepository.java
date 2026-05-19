package com.elmundo;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Types;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public class FilmRepository {
    public void initializeDatabase(Connection connection) throws SQLException {
        createFilmsTable(connection);
        createMediaStorageTable(connection);
        ensurePreservedFilmColumns(connection);
        createCustomFieldDefinitionsTable(connection);
        createCustomFieldsTable(connection);
        migrateLegacyCustomFieldsIfNeeded(connection);
        migrateLegacyRowsIfNeeded(connection);
    }

    public List<FilmEntry> findAll(Connection connection) throws SQLException {
        List<FilmEntry> films = new ArrayList<>();
        String sql = "SELECT id, film_key, title_original, title_translated, production_year, "
                + "production, color_format, romanized, special_aspects "
                + "FROM films ORDER BY production_year IS NULL, production_year, title_original, id";

        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            while (resultSet.next()) {
                films.add(readFilm(resultSet));
            }
        }

        return films;
    }

    public Optional<FilmEntry> findMatchingTitleAndYear(Connection connection, FilmDraft draft)
            throws SQLException {
        String sql = "SELECT id, film_key, title_original, title_translated, production_year, "
                + "production, color_format, romanized, special_aspects "
                + "FROM films WHERE title_match_key = ? "
                + "AND ((production_year IS NULL AND ? IS NULL) OR production_year = ?) "
                + "ORDER BY id LIMIT 1";

        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, FilmKeyGenerator.normalizeTitleForMatch(draft.getTitleOriginal()));
            setInteger(statement, 2, draft.getProductionYear());
            setInteger(statement, 3, draft.getProductionYear());
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return Optional.of(readFilm(resultSet));
                }
            }
        }

        return Optional.empty();
    }

    public List<FilmEntry> findByTitle(Connection connection, String titleOriginal) throws SQLException {
        List<FilmEntry> films = new ArrayList<>();
        String sql = "SELECT id, film_key, title_original, title_translated, production_year, "
                + "production, color_format, romanized, special_aspects "
                + "FROM films WHERE title_match_key = ? ORDER BY production_year, id";

        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, FilmKeyGenerator.normalizeTitleForMatch(titleOriginal));
            try (ResultSet resultSet = statement.executeQuery()) {
                while (resultSet.next()) {
                    films.add(readFilm(resultSet));
                }
            }
        }

        return films;
    }

    public FilmEntry insertAsUnique(Connection connection, FilmDraft draft) throws SQLException {
        requireTitle(draft);
        boolean originalAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);

        try {
            String filmKey = FilmKeyGenerator.generateUniqueKey(
                    draft.getTitleOriginal(),
                    draft.getProductionYear(),
                    key -> filmKeyExists(connection, key));
            long id = insertFilm(connection, filmKey, draft);
            saveCustomFields(connection, id, draft);
            connection.commit();
            return findById(connection, id).orElseThrow(() ->
                    new SQLException("Inserted film could not be read back."));
        } catch (SQLException e) {
            connection.rollback();
            throw e;
        } finally {
            connection.setAutoCommit(originalAutoCommit);
        }
    }

    public void overwriteWithNonBlankValues(Connection connection, long filmId, FilmDraft draft)
            throws SQLException {
        boolean originalAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);

        try {
            updateFilmValues(connection, filmId, draft);
            saveCustomFields(connection, filmId, draft);
            connection.commit();
        } catch (SQLException e) {
            connection.rollback();
            throw e;
        } finally {
            connection.setAutoCommit(originalAutoCommit);
        }
    }

    public Optional<FilmEntry> findById(Connection connection, long id) throws SQLException {
        String sql = "SELECT id, film_key, title_original, title_translated, production_year, "
                + "production, color_format, romanized, special_aspects FROM films WHERE id = ?";

        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setLong(1, id);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return Optional.of(readFilm(resultSet));
                }
            }
        }

        return Optional.empty();
    }

    public Map<String, Long> findFilmIdsByKey(Connection connection) throws SQLException {
        Map<String, Long> filmIdsByKey = new LinkedHashMap<>();
        String sql = "SELECT id, film_key FROM films";

        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            while (resultSet.next()) {
                filmIdsByKey.put(resultSet.getString("film_key"), resultSet.getLong("id"));
            }
        }

        return filmIdsByKey;
    }

    public List<AttributeFilmTarget> findAttributeFilmTargets(Connection connection) throws SQLException {
        List<AttributeFilmTarget> targets = new ArrayList<>();
        String sql = "SELECT id, film_key, title_original, production_year "
                + "FROM films ORDER BY production_year IS NULL, production_year, title_original, id";

        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            while (resultSet.next()) {
                targets.add(new AttributeFilmTarget(
                        resultSet.getLong("id"),
                        resultSet.getString("film_key"),
                        resultSet.getString("title_original"),
                        getInteger(resultSet, "production_year")));
            }
        }

        return targets;
    }

    public void renameFilmTitle(Connection connection, long filmId, String titleOriginal) throws SQLException {
        if (!FilmDraft.hasText(titleOriginal)) {
            throw new IllegalArgumentException("Original-language title is required.");
        }

        String sql = "UPDATE films SET title_original = ?, title_match_key = ? WHERE id = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, titleOriginal.trim());
            statement.setString(2, FilmKeyGenerator.normalizeTitleForMatch(titleOriginal));
            statement.setLong(3, filmId);
            statement.executeUpdate();
        }
    }

    public Map<String, AttributeFieldType> findCustomFieldTypes(Connection connection) throws SQLException {
        Map<String, AttributeFieldType> fieldTypes = new HashMap<>();
        String sql = "SELECT normalized_name, field_type FROM custom_field_definitions";

        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            while (resultSet.next()) {
                fieldTypes.put(
                        resultSet.getString("normalized_name"),
                        AttributeFieldType.fromStorageName(resultSet.getString("field_type")));
            }
        }

        return fieldTypes;
    }

    public void populateAttributeExistingValueCounts(Connection connection, AttributeImportData data)
            throws SQLException {
        Map<String, Long> definitionIdsByName = findCustomFieldDefinitionIds(connection);
        for (AttributeImportColumn column : data.getImportableColumns()) {
            int count = 0;
            for (AttributeImportValue value : column.getValues()) {
                if (!value.hasValue()) {
                    continue;
                }
                if (column.getTargetKind() == AttributeTargetKind.PRESERVED) {
                    if (hasPreservedAttributeValue(connection, value.getFilmId(), column.getPreservedColumnName())) {
                        count++;
                    }
                } else if (column.getTargetKind() == AttributeTargetKind.CUSTOM) {
                    Long definitionId = definitionIdsByName.get(column.getNormalizedName());
                    if (definitionId != null && hasCustomAttributeValue(connection, value.getFilmId(), definitionId)) {
                        count++;
                    }
                }
            }
            column.setExistingValueCount(count);
        }
    }

    public AttributeImportResult importAttributes(
            Connection connection,
            AttributeImportData data,
            Map<AttributeImportColumn, AttributeOverwriteChoice> overwriteChoices) throws SQLException {
        AttributeImportResult result = new AttributeImportResult();
        boolean originalAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);

        try {
            Map<String, Long> definitionIdsByName = findCustomFieldDefinitionIds(connection);
            for (AttributeImportColumn column : data.getImportableColumns()) {
                AttributeOverwriteChoice choice = overwriteChoices.getOrDefault(
                        column,
                        AttributeOverwriteChoice.KEEP_EXISTING);
                if (choice == AttributeOverwriteChoice.CANCEL) {
                    connection.rollback();
                    return result;
                }

                Long definitionId = null;
                if (column.getTargetKind() == AttributeTargetKind.CUSTOM) {
                    definitionId = definitionIdsByName.get(column.getNormalizedName());
                    if (definitionId == null) {
                        definitionId = getOrCreateCustomFieldDefinition(
                                connection,
                                column.getHeader(),
                                column.getNormalizedName(),
                                column.getFieldType());
                        definitionIdsByName.put(column.getNormalizedName(), definitionId);
                    }
                }

                for (AttributeImportValue value : column.getValues()) {
                    if (!value.hasValue()) {
                        result.incrementSkippedValues();
                        continue;
                    }

                    boolean hasExistingValue = column.getTargetKind() == AttributeTargetKind.PRESERVED
                            ? hasPreservedAttributeValue(connection, value.getFilmId(), column.getPreservedColumnName())
                            : hasCustomAttributeValue(connection, value.getFilmId(), definitionId);
                    if (hasExistingValue && choice == AttributeOverwriteChoice.KEEP_EXISTING) {
                        result.incrementSkippedValues();
                        continue;
                    }

                    if (column.getTargetKind() == AttributeTargetKind.PRESERVED) {
                        updatePreservedAttributeValue(
                                connection,
                                value.getFilmId(),
                                column.getPreservedColumnName(),
                                value.getRawValue());
                        result.incrementUpdatedValues();
                    } else {
                        try {
                            String json = AttributeValueConverter.toJson(value.getRawValue(), column.getFieldType());
                            upsertCustomAttributeValue(connection, value.getFilmId(), definitionId, json);
                            result.incrementUpdatedValues();
                        } catch (IllegalArgumentException e) {
                            column.incrementInvalidValueCount();
                            result.incrementInvalidValues();
                        }
                    }
                }
            }

            connection.commit();
            return result;
        } catch (SQLException e) {
            connection.rollback();
            throw e;
        } finally {
            connection.setAutoCommit(originalAutoCommit);
        }
    }

    public List<MediaStorageEntry> findMediaStorageByFilmKey(Connection connection, String filmKey)
            throws SQLException {
        List<MediaStorageEntry> entries = new ArrayList<>();
        String sql = "SELECT id, film_key, storage_format, path, media_type, file_extension "
                + "FROM film_media_storage WHERE film_key = ? ORDER BY media_type, storage_format, path";

        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, filmKey);
            try (ResultSet resultSet = statement.executeQuery()) {
                while (resultSet.next()) {
                    entries.add(readMediaStorageEntry(resultSet));
                }
            }
        }

        return entries;
    }

    public void populateExistingMediaDuplicates(Connection connection, MediaImportData data)
            throws SQLException {
        for (MediaImportRow row : data.getImportableRows()) {
            if (mediaStorageExists(connection, row)) {
                row.setStatus(MediaImportRowStatus.DUPLICATE);
                row.setWarning("Media storage object already exists.");
            }
        }
    }

    public MediaImportResult importMediaStorage(Connection connection, MediaImportData data)
            throws SQLException {
        MediaImportResult result = new MediaImportResult();
        boolean originalAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);

        try {
            for (MediaImportRow row : data.getRows()) {
                if (!row.isImportable()) {
                    result.incrementSkippedRows();
                    continue;
                }

                if (mediaStorageExists(connection, row)) {
                    row.setStatus(MediaImportRowStatus.DUPLICATE);
                    row.setWarning("Media storage object already exists.");
                    result.incrementSkippedRows();
                    continue;
                }

                insertMediaStorage(connection, row);
                row.setStatus(MediaImportRowStatus.IMPORTED);
                result.incrementImportedRows();
            }

            connection.commit();
            return result;
        } catch (SQLException e) {
            connection.rollback();
            throw e;
        } finally {
            connection.setAutoCommit(originalAutoCommit);
        }
    }

    private void createFilmsTable(Connection connection) throws SQLException {
        String sql = "CREATE TABLE IF NOT EXISTS films ("
                + "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                + "film_key VARCHAR(255) NOT NULL UNIQUE, "
                + "title_original VARCHAR(512) NOT NULL, "
                + "title_match_key VARCHAR(512) NOT NULL, "
                + "title_translated VARCHAR(512), "
                + "production_year INT NULL, "
                + "production VARCHAR(512), "
                + "color_format VARCHAR(128), "
                + "romanized VARCHAR(512), "
                + "special_aspects TEXT, "
                + "director TEXT, "
                + "scriptwriter TEXT, "
                + "actors TEXT, "
                + "staff TEXT, "
                + "other_staff TEXT, "
                + "media_path VARCHAR(1024), "
                + "storage_format VARCHAR(128), "
                + "media_type VARCHAR(128), "
                + "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                + "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                + ")";

        try (Statement statement = connection.createStatement()) {
            statement.executeUpdate(sql);
        }

        createIndexIfMissing(connection, "films", "idx_films_title_year",
                "CREATE INDEX idx_films_title_year ON films (title_match_key, production_year)");
    }

    private void createMediaStorageTable(Connection connection) throws SQLException {
        String sql = "CREATE TABLE IF NOT EXISTS film_media_storage ("
                + "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                + "film_key VARCHAR(255) NOT NULL, "
                + "storage_format VARCHAR(32) NOT NULL, "
                + "path TEXT NOT NULL, "
                + "path_hash CHAR(64) NOT NULL, "
                + "media_type VARCHAR(64) NOT NULL, "
                + "file_extension VARCHAR(16) NOT NULL, "
                + "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                + "CONSTRAINT fk_film_media_storage_film FOREIGN KEY (film_key) "
                + "REFERENCES films(film_key) ON DELETE CASCADE, "
                + "CONSTRAINT uniq_film_media_storage UNIQUE "
                + "(film_key, storage_format, media_type, path_hash)"
                + ")";

        try (Statement statement = connection.createStatement()) {
            statement.executeUpdate(sql);
        }

        createIndexIfMissing(connection, "film_media_storage", "idx_film_media_storage_film_key",
                "CREATE INDEX idx_film_media_storage_film_key ON film_media_storage (film_key)");
    }

    private void ensurePreservedFilmColumns(Connection connection) throws SQLException {
        addColumnIfMissing(connection, "films", "director", "TEXT");
        addColumnIfMissing(connection, "films", "scriptwriter", "TEXT");
        addColumnIfMissing(connection, "films", "actors", "TEXT");
        addColumnIfMissing(connection, "films", "staff", "TEXT");
        addColumnIfMissing(connection, "films", "other_staff", "TEXT");
        addColumnIfMissing(connection, "films", "media_path", "VARCHAR(1024)");
        addColumnIfMissing(connection, "films", "storage_format", "VARCHAR(128)");
        addColumnIfMissing(connection, "films", "media_type", "VARCHAR(128)");
    }

    private void createCustomFieldDefinitionsTable(Connection connection) throws SQLException {
        String sql = "CREATE TABLE IF NOT EXISTS custom_field_definitions ("
                + "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                + "field_name VARCHAR(255) NOT NULL, "
                + "normalized_name VARCHAR(255) NOT NULL UNIQUE, "
                + "field_type VARCHAR(64) NOT NULL, "
                + "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                + ")";

        try (Statement statement = connection.createStatement()) {
            statement.executeUpdate(sql);
        }
    }

    private void createCustomFieldsTable(Connection connection) throws SQLException {
        if (!tableExists(connection, "film_custom_fields")) {
            String sql = "CREATE TABLE IF NOT EXISTS film_custom_fields ("
                    + "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                    + "film_id BIGINT NOT NULL, "
                    + "custom_field_id BIGINT NOT NULL, "
                    + "value_json TEXT, "
                    + "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    + "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    + "CONSTRAINT uniq_film_custom_field_value UNIQUE (film_id, custom_field_id), "
                    + "CONSTRAINT fk_film_custom_fields_film FOREIGN KEY (film_id) "
                    + "REFERENCES films(id) ON DELETE CASCADE, "
                    + "CONSTRAINT fk_film_custom_fields_definition FOREIGN KEY (custom_field_id) "
                    + "REFERENCES custom_field_definitions(id) ON DELETE CASCADE"
                    + ")";

            try (Statement statement = connection.createStatement()) {
                statement.executeUpdate(sql);
            }
            return;
        }

        addColumnIfMissing(connection, "film_custom_fields", "custom_field_id", "BIGINT NULL");
        addColumnIfMissing(connection, "film_custom_fields", "value_json", "TEXT");
        addColumnIfMissing(connection, "film_custom_fields", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP");
        addColumnIfMissing(connection, "film_custom_fields", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP");
        createIndexIfMissing(connection, "film_custom_fields", "idx_film_custom_field_value_unique",
                "CREATE UNIQUE INDEX idx_film_custom_field_value_unique "
                        + "ON film_custom_fields (film_id, custom_field_id)");
    }

    private void migrateLegacyRowsIfNeeded(Connection connection) throws SQLException {
        if (countFilms(connection) > 0 || !tableExists(connection, "chn_film_test_db")) {
            return;
        }

        String sql = "SELECT Romanized, Title, Year, Translated, Production, Colour, "
                + "`Special Aspects` AS special_aspects FROM `chn_film_test_db`";

        List<FilmDraft> legacyDrafts = new ArrayList<>();
        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            while (resultSet.next()) {
                FilmDraft draft = new FilmDraft();
                draft.setRomanized(resultSet.getString("Romanized"));
                draft.setTitleOriginal(resultSet.getString("Title"));
                draft.setProductionYear(getInteger(resultSet, "Year"));
                draft.setTitleTranslated(resultSet.getString("Translated"));
                draft.setProduction(resultSet.getString("Production"));
                draft.setColorFormat(resultSet.getString("Colour"));
                draft.setSpecialAspects(resultSet.getString("special_aspects"));

                if (draft.hasTitle()) {
                    legacyDrafts.add(draft);
                }
            }
        }

        for (FilmDraft draft : legacyDrafts) {
            insertAsUnique(connection, draft);
        }
    }

    private void migrateLegacyCustomFieldsIfNeeded(Connection connection) throws SQLException {
        if (!columnExists(connection, "film_custom_fields", "field_name")
                || !columnExists(connection, "film_custom_fields", "field_value")
                || !columnExists(connection, "film_custom_fields", "custom_field_id")
                || !columnExists(connection, "film_custom_fields", "value_json")) {
            return;
        }

        String selectSql = "SELECT id, field_name, field_value FROM film_custom_fields "
                + "WHERE custom_field_id IS NULL AND field_name IS NOT NULL";
        List<LegacyCustomField> legacyFields = new ArrayList<>();
        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(selectSql)) {
            while (resultSet.next()) {
                legacyFields.add(new LegacyCustomField(
                        resultSet.getLong("id"),
                        resultSet.getString("field_name"),
                        resultSet.getString("field_value")));
            }
        }

        String updateSql = "UPDATE film_custom_fields SET custom_field_id = ?, value_json = ? WHERE id = ?";
        try (PreparedStatement statement = connection.prepareStatement(updateSql)) {
            for (LegacyCustomField legacyField : legacyFields) {
                if (!FilmDraft.hasText(legacyField.fieldName)) {
                    continue;
                }
                long definitionId = getOrCreateCustomFieldDefinition(
                        connection,
                        legacyField.fieldName,
                        AttributeHeaderMapper.normalizeHeader(legacyField.fieldName),
                        AttributeFieldType.STRING);
                statement.setLong(1, definitionId);
                statement.setString(2, AttributeValueConverter.quoteJsonString(
                        legacyField.fieldValue == null ? "" : legacyField.fieldValue));
                statement.setLong(3, legacyField.id);
                statement.addBatch();
            }
            statement.executeBatch();
        }
    }

    private long insertFilm(Connection connection, String filmKey, FilmDraft draft) throws SQLException {
        String sql = "INSERT INTO films (film_key, title_original, title_match_key, title_translated, "
                + "production_year, production, color_format, romanized, special_aspects) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";

        try (PreparedStatement statement = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            statement.setString(1, filmKey);
            statement.setString(2, draft.getTitleOriginal());
            statement.setString(3, FilmKeyGenerator.normalizeTitleForMatch(draft.getTitleOriginal()));
            statement.setString(4, draft.getTitleTranslated());
            setInteger(statement, 5, draft.getProductionYear());
            statement.setString(6, draft.getProduction());
            statement.setString(7, draft.getColorFormat());
            statement.setString(8, draft.getRomanized());
            statement.setString(9, draft.getSpecialAspects());
            statement.executeUpdate();

            try (ResultSet keys = statement.getGeneratedKeys()) {
                if (keys.next()) {
                    return keys.getLong(1);
                }
            }
        }

        throw new SQLException("No generated id returned for inserted film.");
    }

    private void updateFilmValues(Connection connection, long filmId, FilmDraft draft) throws SQLException {
        StringBuilder sql = new StringBuilder("UPDATE films SET ");
        List<SqlValue> values = new ArrayList<>();

        if (FilmDraft.hasText(draft.getTitleOriginal())) {
            sql.append("title_original = ?, title_match_key = ?, ");
            values.add(new SqlValue(draft.getTitleOriginal(), Types.VARCHAR));
            values.add(new SqlValue(FilmKeyGenerator.normalizeTitleForMatch(draft.getTitleOriginal()), Types.VARCHAR));
        }
        if (FilmDraft.hasText(draft.getTitleTranslated())) {
            sql.append("title_translated = ?, ");
            values.add(new SqlValue(draft.getTitleTranslated(), Types.VARCHAR));
        }
        if (draft.getProductionYear() != null) {
            sql.append("production_year = ?, ");
            values.add(new SqlValue(draft.getProductionYear(), Types.INTEGER));
        }
        if (FilmDraft.hasText(draft.getProduction())) {
            sql.append("production = ?, ");
            values.add(new SqlValue(draft.getProduction(), Types.VARCHAR));
        }
        if (FilmDraft.hasText(draft.getColorFormat())) {
            sql.append("color_format = ?, ");
            values.add(new SqlValue(draft.getColorFormat(), Types.VARCHAR));
        }
        if (FilmDraft.hasText(draft.getRomanized())) {
            sql.append("romanized = ?, ");
            values.add(new SqlValue(draft.getRomanized(), Types.VARCHAR));
        }
        if (FilmDraft.hasText(draft.getSpecialAspects())) {
            sql.append("special_aspects = ?, ");
            values.add(new SqlValue(draft.getSpecialAspects(), Types.VARCHAR));
        }

        if (values.isEmpty()) {
            return;
        }

        sql.setLength(sql.length() - 2);
        sql.append(" WHERE id = ?");

        try (PreparedStatement statement = connection.prepareStatement(sql.toString())) {
            for (int i = 0; i < values.size(); i++) {
                values.get(i).bind(statement, i + 1);
            }
            statement.setLong(values.size() + 1, filmId);
            statement.executeUpdate();
        }
    }

    private void saveCustomFields(Connection connection, long filmId, FilmDraft draft) throws SQLException {
        if (draft.getCustomFields().isEmpty()) {
            return;
        }

        for (Map.Entry<String, String> entry : draft.getCustomFields().entrySet()) {
            if (!FilmDraft.hasText(entry.getKey())) {
                continue;
            }
            long definitionId = getOrCreateCustomFieldDefinition(
                    connection,
                    entry.getKey().trim(),
                    AttributeHeaderMapper.normalizeHeader(entry.getKey()),
                    AttributeFieldType.STRING);
            upsertCustomAttributeValue(
                    connection,
                    filmId,
                    definitionId,
                    AttributeValueConverter.quoteJsonString(entry.getValue() == null ? "" : entry.getValue()));
        }
    }

    private boolean filmKeyExists(Connection connection, String filmKey) throws SQLException {
        String sql = "SELECT COUNT(*) FROM films WHERE film_key = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, filmKey);
            try (ResultSet resultSet = statement.executeQuery()) {
                resultSet.next();
                return resultSet.getLong(1) > 0;
            }
        }
    }

    private long getOrCreateCustomFieldDefinition(
            Connection connection,
            String fieldName,
            String normalizedName,
            AttributeFieldType fieldType) throws SQLException {
        Optional<Long> existingId = findCustomFieldDefinitionId(connection, normalizedName);
        if (existingId.isPresent()) {
            return existingId.get();
        }

        String sql = "INSERT INTO custom_field_definitions (field_name, normalized_name, field_type) "
                + "VALUES (?, ?, ?)";
        try (PreparedStatement statement = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            statement.setString(1, fieldName);
            statement.setString(2, normalizedName);
            statement.setString(3, fieldType.getStorageName());
            statement.executeUpdate();

            try (ResultSet keys = statement.getGeneratedKeys()) {
                if (keys.next()) {
                    return keys.getLong(1);
                }
            }
        }

        return findCustomFieldDefinitionId(connection, normalizedName).orElseThrow(() ->
                new SQLException("Custom field definition could not be created: " + fieldName));
    }

    private Optional<Long> findCustomFieldDefinitionId(Connection connection, String normalizedName)
            throws SQLException {
        String sql = "SELECT id FROM custom_field_definitions WHERE normalized_name = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, normalizedName);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return Optional.of(resultSet.getLong("id"));
                }
            }
        }
        return Optional.empty();
    }

    private Map<String, Long> findCustomFieldDefinitionIds(Connection connection) throws SQLException {
        Map<String, Long> definitionIds = new HashMap<>();
        String sql = "SELECT id, normalized_name FROM custom_field_definitions";

        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            while (resultSet.next()) {
                definitionIds.put(resultSet.getString("normalized_name"), resultSet.getLong("id"));
            }
        }

        return definitionIds;
    }

    private boolean hasPreservedAttributeValue(Connection connection, long filmId, String columnName)
            throws SQLException {
        String sql = "SELECT " + columnName + " FROM films WHERE id = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setLong(1, filmId);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return FilmDraft.hasText(resultSet.getString(1));
                }
            }
        }
        return false;
    }

    private void updatePreservedAttributeValue(
            Connection connection,
            long filmId,
            String columnName,
            String value) throws SQLException {
        String sql = "UPDATE films SET " + columnName + " = ? WHERE id = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, value);
            statement.setLong(2, filmId);
            statement.executeUpdate();
        }
    }

    private boolean hasCustomAttributeValue(Connection connection, long filmId, Long definitionId)
            throws SQLException {
        if (definitionId == null) {
            return false;
        }

        String sql = "SELECT value_json FROM film_custom_fields WHERE film_id = ? AND custom_field_id = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setLong(1, filmId);
            statement.setLong(2, definitionId);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return FilmDraft.hasText(resultSet.getString("value_json"));
                }
            }
        }
        return false;
    }

    private void upsertCustomAttributeValue(
            Connection connection,
            long filmId,
            long definitionId,
            String valueJson) throws SQLException {
        String sql = "INSERT INTO film_custom_fields (film_id, custom_field_id, value_json) VALUES (?, ?, ?) "
                + "ON DUPLICATE KEY UPDATE value_json = VALUES(value_json)";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setLong(1, filmId);
            statement.setLong(2, definitionId);
            statement.setString(3, valueJson);
            statement.executeUpdate();
        }
    }

    private boolean mediaStorageExists(Connection connection, MediaImportRow row) throws SQLException {
        String sql = "SELECT COUNT(*) FROM film_media_storage "
                + "WHERE film_key = ? AND storage_format = ? AND media_type = ? AND path_hash = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, row.getFilmKey());
            statement.setString(2, row.getStorageFormat());
            statement.setString(3, row.getMediaType());
            statement.setString(4, row.getPathHash());
            try (ResultSet resultSet = statement.executeQuery()) {
                resultSet.next();
                return resultSet.getLong(1) > 0;
            }
        }
    }

    private void insertMediaStorage(Connection connection, MediaImportRow row) throws SQLException {
        String sql = "INSERT INTO film_media_storage "
                + "(film_key, storage_format, path, path_hash, media_type, file_extension) "
                + "VALUES (?, ?, ?, ?, ?, ?)";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, row.getFilmKey());
            statement.setString(2, row.getStorageFormat());
            statement.setString(3, row.getPath());
            statement.setString(4, row.getPathHash());
            statement.setString(5, row.getMediaType());
            statement.setString(6, row.getFileExtension());
            statement.executeUpdate();
        }
    }

    private MediaStorageEntry readMediaStorageEntry(ResultSet resultSet) throws SQLException {
        return new MediaStorageEntry(
                resultSet.getLong("id"),
                resultSet.getString("film_key"),
                resultSet.getString("storage_format"),
                resultSet.getString("path"),
                resultSet.getString("media_type"),
                resultSet.getString("file_extension"));
    }

    private int countFilms(Connection connection) throws SQLException {
        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery("SELECT COUNT(*) FROM films")) {
            resultSet.next();
            return resultSet.getInt(1);
        }
    }

    private boolean tableExists(Connection connection, String tableName) throws SQLException {
        DatabaseMetaData metaData = connection.getMetaData();
        try (ResultSet resultSet = metaData.getTables(connection.getCatalog(), null, tableName, null)) {
            if (resultSet.next()) {
                return true;
            }
        }
        try (ResultSet resultSet = metaData.getTables(connection.getCatalog(), null, tableName.toUpperCase(), null)) {
            return resultSet.next();
        }
    }

    private boolean columnExists(Connection connection, String tableName, String columnName) throws SQLException {
        DatabaseMetaData metaData = connection.getMetaData();
        if (columnExists(metaData, connection.getCatalog(), tableName, columnName)
                || columnExists(metaData, connection.getCatalog(), tableName.toUpperCase(), columnName)
                || columnExists(metaData, connection.getCatalog(), tableName.toLowerCase(), columnName)) {
            return true;
        }
        return false;
    }

    private boolean columnExists(
            DatabaseMetaData metaData,
            String catalog,
            String tableName,
            String columnName) throws SQLException {
        try (ResultSet resultSet = metaData.getColumns(catalog, null, tableName, columnName)) {
            if (resultSet.next()) {
                return true;
            }
        }
        try (ResultSet resultSet = metaData.getColumns(catalog, null, tableName, columnName.toUpperCase())) {
            return resultSet.next();
        }
    }

    private void addColumnIfMissing(
            Connection connection,
            String tableName,
            String columnName,
            String sqlType) throws SQLException {
        if (columnExists(connection, tableName, columnName)) {
            return;
        }

        try (Statement statement = connection.createStatement()) {
            statement.executeUpdate("ALTER TABLE " + tableName + " ADD COLUMN " + columnName + " " + sqlType);
        }
    }

    private void createIndexIfMissing(
            Connection connection,
            String tableName,
            String indexName,
            String createSql) throws SQLException {
        DatabaseMetaData metaData = connection.getMetaData();
        if (indexExists(metaData, connection.getCatalog(), tableName, indexName)
                || indexExists(metaData, connection.getCatalog(), tableName.toUpperCase(), indexName)
                || indexExists(metaData, connection.getCatalog(), tableName.toLowerCase(), indexName)) {
            return;
        }

        try (Statement statement = connection.createStatement()) {
            statement.executeUpdate(createSql);
        }
    }

    private boolean indexExists(
            DatabaseMetaData metaData,
            String catalog,
            String tableName,
            String indexName) throws SQLException {
        try (ResultSet resultSet = metaData.getIndexInfo(catalog, null, tableName, false, false)) {
            while (resultSet.next()) {
                String existingName = resultSet.getString("INDEX_NAME");
                if (existingName != null && indexName.equalsIgnoreCase(existingName)) {
                    return true;
                }
            }
        }
        return false;
    }

    private FilmEntry readFilm(ResultSet resultSet) throws SQLException {
        return new FilmEntry(
                resultSet.getLong("id"),
                resultSet.getString("film_key"),
                resultSet.getString("title_original"),
                resultSet.getString("title_translated"),
                getInteger(resultSet, "production_year"),
                resultSet.getString("production"),
                resultSet.getString("color_format"),
                resultSet.getString("romanized"),
                resultSet.getString("special_aspects"));
    }

    private void requireTitle(FilmDraft draft) {
        if (!draft.hasTitle()) {
            throw new IllegalArgumentException("Original-language title is required.");
        }
    }

    private Integer getInteger(ResultSet resultSet, String columnName) throws SQLException {
        Number value = (Number) resultSet.getObject(columnName);
        return value == null ? null : value.intValue();
    }

    private void setInteger(PreparedStatement statement, int index, Integer value) throws SQLException {
        if (value == null) {
            statement.setNull(index, Types.INTEGER);
            return;
        }

        statement.setInt(index, value);
    }

    private static final class SqlValue {
        private final Object value;
        private final int type;

        private SqlValue(Object value, int type) {
            this.value = value;
            this.type = type;
        }

        private void bind(PreparedStatement statement, int index) throws SQLException {
            if (value == null) {
                statement.setNull(index, type);
            } else {
                statement.setObject(index, value, type);
            }
        }
    }

    private static final class LegacyCustomField {
        private final long id;
        private final String fieldName;
        private final String fieldValue;

        private LegacyCustomField(long id, String fieldName, String fieldValue) {
            this.id = id;
            this.fieldName = fieldName;
            this.fieldValue = fieldValue;
        }
    }
}
