package com.elmundo;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/** The metadata operations used by the application, independent of storage. */
public interface MetadataStore extends AutoCloseable {
    String getDescription();

    List<FilmEntry> findAll() throws MetadataStoreException;

    Optional<FilmEntry> findMatchingTitleAndYear(FilmDraft draft) throws MetadataStoreException;

    FilmEntry insertAsUnique(FilmDraft draft) throws MetadataStoreException;

    void overwriteWithNonBlankValues(long filmId, FilmDraft draft) throws MetadataStoreException;

    void renameFilmTitle(long filmId, String titleOriginal) throws MetadataStoreException;

    Map<String, Long> findFilmIdsByKey() throws MetadataStoreException;

    List<AttributeFilmTarget> findAttributeFilmTargets() throws MetadataStoreException;

    Map<String, AttributeFieldType> findCustomFieldTypes() throws MetadataStoreException;

    void populateAttributeExistingValueCounts(AttributeImportData data) throws MetadataStoreException;

    AttributeImportResult importAttributes(AttributeImportData data,
            Map<AttributeImportColumn, AttributeOverwriteChoice> overwriteChoices) throws MetadataStoreException;

    List<MediaStorageEntry> findMediaStorageByFilmKey(String filmKey) throws MetadataStoreException;

    void populateExistingMediaDuplicates(MediaImportData data) throws MetadataStoreException;

    MediaImportResult importMediaStorage(MediaImportData data) throws MetadataStoreException;

    @Override
    void close() throws MetadataStoreException;
}
