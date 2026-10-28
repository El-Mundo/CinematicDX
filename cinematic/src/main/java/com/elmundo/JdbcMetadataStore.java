package com.elmundo;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/** Owns a JDBC connection while retaining the existing SQL repository. */
public class JdbcMetadataStore implements MetadataStore {
    private final Connection connection;
    private final FilmRepository repository;

    public JdbcMetadataStore(Connection connection) {
        this.connection = Objects.requireNonNull(connection, "connection");
        this.repository = new FilmRepository();
    }

    @Override
    public String getDescription() {
        return "Database";
    }

    @Override
    public List<FilmEntry> findAll() throws MetadataStoreException {
        return execute(() -> repository.findAll(connection));
    }

    @Override
    public Optional<FilmEntry> findMatchingTitleAndYear(FilmDraft draft) throws MetadataStoreException {
        return execute(() -> repository.findMatchingTitleAndYear(connection, draft));
    }

    @Override
    public FilmEntry insertAsUnique(FilmDraft draft) throws MetadataStoreException {
        FilmDraft prepared = MetadataValueRules.prepareDraft(draft, findCustomFieldTypes());
        return execute(() -> repository.insertAsUnique(connection, prepared));
    }

    @Override
    public void overwriteWithNonBlankValues(long filmId, FilmDraft draft) throws MetadataStoreException {
        FilmDraft prepared = MetadataValueRules.prepareDraft(draft, findCustomFieldTypes());
        execute(() -> {
            repository.overwriteWithNonBlankValues(connection, filmId, prepared);
            return null;
        });
    }

    @Override
    public void renameFilmTitle(long filmId, String titleOriginal) throws MetadataStoreException {
        execute(() -> {
            repository.renameFilmTitle(connection, filmId, titleOriginal);
            return null;
        });
    }

    @Override
    public Map<String, Long> findFilmIdsByKey() throws MetadataStoreException {
        return execute(() -> repository.findFilmIdsByKey(connection));
    }

    @Override
    public List<AttributeFilmTarget> findAttributeFilmTargets() throws MetadataStoreException {
        return execute(() -> repository.findAttributeFilmTargets(connection));
    }

    @Override
    public Map<String, AttributeFieldType> findCustomFieldTypes() throws MetadataStoreException {
        return execute(() -> repository.findCustomFieldTypes(connection));
    }

    @Override
    public void populateAttributeExistingValueCounts(AttributeImportData data) throws MetadataStoreException {
        execute(() -> {
            repository.populateAttributeExistingValueCounts(connection, data);
            return null;
        });
    }

    @Override
    public AttributeImportResult importAttributes(AttributeImportData data,
            Map<AttributeImportColumn, AttributeOverwriteChoice> choices) throws MetadataStoreException {
        if (data.getImportableColumns().stream().anyMatch(column ->
                choices.get(column) == AttributeOverwriteChoice.CANCEL)) {
            return new AttributeImportResult();
        }
        MetadataValueRules.validateAttributeTypes(data, findCustomFieldTypes());
        return execute(() -> repository.importAttributes(connection, data, choices));
    }

    @Override
    public List<MediaStorageEntry> findMediaStorageByFilmKey(String filmKey) throws MetadataStoreException {
        return execute(() -> repository.findMediaStorageByFilmKey(connection, filmKey));
    }

    @Override
    public void populateExistingMediaDuplicates(MediaImportData data) throws MetadataStoreException {
        execute(() -> {
            repository.populateExistingMediaDuplicates(connection, data);
            return null;
        });
    }

    @Override
    public MediaImportResult importMediaStorage(MediaImportData data) throws MetadataStoreException {
        List<MediaImportRowStatus> statuses = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        for (MediaImportRow row : data.getRows()) {
            statuses.add(row.getStatus());
            warnings.add(row.getWarning());
        }
        try {
            return execute(() -> repository.importMediaStorage(connection, data));
        } catch (MetadataStoreException e) {
            // The repository rolled back; the preview must not claim rows were imported.
            for (int i = 0; i < data.getRows().size(); i++) {
                data.getRows().get(i).setStatus(statuses.get(i));
                data.getRows().get(i).setWarning(warnings.get(i));
            }
            throw e;
        }
    }

    @Override
    public void close() throws MetadataStoreException {
        execute(() -> {
            connection.close();
            return null;
        });
    }

    private <T> T execute(SqlOperation<T> operation) throws MetadataStoreException {
        try {
            return operation.run();
        } catch (SQLException e) {
            throw new MetadataStoreException("Database metadata operation failed: " + e.getMessage(), e);
        }
    }

    @FunctionalInterface
    private interface SqlOperation<T> {
        T run() throws SQLException;
    }
}
