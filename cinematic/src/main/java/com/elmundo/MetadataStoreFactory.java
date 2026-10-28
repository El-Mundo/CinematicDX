package com.elmundo;

import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/** Opens only the source explicitly selected during setup. */
public class MetadataStoreFactory {
    public MetadataStore open(MetadataSourceType type, Path directory,
            String url, String username, String password) throws MetadataStoreException {
        if (type == null) {
            throw new MetadataStoreException("Choose a metadata source.");
        }
        switch (type) {
            case LOCAL_DIRECTORY:
                return openLocalDirectory(directory);
            case DATABASE:
                return openDatabase(url, username, password);
            default:
                throw new MetadataStoreException("Unsupported metadata source: " + type);
        }
    }

    public MetadataStore openLocalDirectory(Path directory) throws MetadataStoreException {
        return LocalDirectoryMetadataStore.open(directory);
    }

    public MetadataStore createLocalDirectory(Path directory) throws MetadataStoreException {
        return LocalDirectoryMetadataStore.create(directory);
    }

    public MetadataStore openDatabase(String url, String username, String password) throws MetadataStoreException {
        if (!FilmDraft.hasText(url)) {
            throw new MetadataStoreException("Please enter a database URL.");
        }
        Connection connection = null;
        try {
            connection = DriverManager.getConnection(url.trim(), username, password);
            new FilmRepository().initializeDatabase(connection);
            return new JdbcMetadataStore(connection);
        } catch (SQLException | RuntimeException e) {
            if (connection != null) {
                try {
                    connection.close();
                } catch (SQLException closeFailure) {
                    e.addSuppressed(closeFailure);
                }
            }
            throw new MetadataStoreException("Could not open database metadata: " + e.getMessage(), e);
        }
    }
}
