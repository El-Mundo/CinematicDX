package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

/** The same user-visible metadata operations must work with either storage source. */
class MetadataStoreContractTest {
    @TempDir
    Path temporaryDirectory;
    private Connection openedJdbcConnection;
    private Path openedLocalDirectory;

    enum Backend { JDBC, LOCAL_DIRECTORY }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void duplicateFilmsHaveDistinctStableKeysAndImportTargets(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry first = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            FilmEntry second = store.insertAsUnique(draft("桥", 1949, "Bridge Variant"));

            assertEquals("桥-1949", first.getFilmKey());
            assertEquals("桥-1949-1", second.getFilmKey());
            assertNotEquals(first.getId(), second.getId());
            assertEquals(2, store.findAll().size());
            assertEquals(Map.of(first.getFilmKey(), first.getId(), second.getFilmKey(), second.getId()),
                    store.findFilmIdsByKey());
            List<AttributeFilmTarget> targets = store.findAttributeFilmTargets();
            assertEquals(2, targets.size());
            assertTrue(targets.stream().anyMatch(target -> target.getFilmId() == first.getId()
                    && target.getFilmKey().equals(first.getFilmKey())
                    && target.getTitleOriginal().equals("桥")
                    && target.getProductionYear().equals(1949)));
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void titleMatchingDistinguishesYearsAndHandlesMissingYear(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry undated = store.insertAsUnique(draft("桥", null, "Undated"));
            FilmEntry dated = store.insertAsUnique(draft("桥", 1949, "The Bridge"));

            assertEquals(undated.getId(), store.findMatchingTitleAndYear(draft(" 桥 ", null, null))
                    .orElseThrow().getId());
            assertEquals(dated.getId(), store.findMatchingTitleAndYear(draft(" 桥 ", 1949, null))
                    .orElseThrow().getId());
            assertTrue(store.findMatchingTitleAndYear(draft("桥", 1950, null)).isEmpty());
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void renamingUpdatesTitleMatchingAndKeepsStableFilmKey(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry original = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            store.renameFilmTitle(original.getId(), " 新桥 ");

            FilmEntry renamed = store.findMatchingTitleAndYear(draft("新桥", 1949, null)).orElseThrow();
            assertEquals(original.getId(), renamed.getId());
            assertEquals(original.getFilmKey(), renamed.getFilmKey());
            assertEquals("新桥", renamed.getTitleOriginal());
            assertTrue(store.findMatchingTitleAndYear(draft("桥", 1949, null)).isEmpty());
            assertEquals(original.getId(), store.findFilmIdsByKey().get(original.getFilmKey()));
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void overwriteFillsValuesWithoutErasingExistingFieldsWithBlanks(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmDraft initial = draft("桥", 1949, "The Bridge");
            initial.setColorFormat("B&W");
            initial.setRomanized("Qiao");
            initial.setSpecialAspects("Archive copy");
            FilmEntry film = store.insertAsUnique(initial);
            FilmDraft incoming = draft("桥", null, "  ");
            incoming.setProduction("Northeast Film Studio");
            incoming.setColorFormat(" ");
            store.overwriteWithNonBlankValues(film.getId(), incoming);

            FilmEntry updated = film(store, film.getId());
            assertEquals(film.getFilmKey(), updated.getFilmKey());
            assertEquals(1949, updated.getProductionYear());
            assertEquals("The Bridge", updated.getTitleTranslated());
            assertEquals("B&W", updated.getColorFormat());
            assertEquals("Qiao", updated.getRomanized());
            assertEquals("Archive copy", updated.getSpecialAspects());
            assertEquals("Northeast Film Studio", updated.getProduction());
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void typedCustomAttributesRejectInvalidValuesAndExposeExistingCounts(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            AttributeImportColumn score = custom(film, "score", AttributeFieldType.INTEGER, "10");
            AttributeImportColumn vector = custom(film, "vector", AttributeFieldType.INTEGER_VECTOR, "1|2|3");
            AttributeImportColumn reviewed = custom(film, "reviewed", AttributeFieldType.BOOLEAN, "true");
            AttributeImportColumn invalid = custom(film, "invalid", AttributeFieldType.INTEGER, "not a number");
            AttributeImportData data = data(score, vector, reviewed, invalid);

            AttributeImportResult result = store.importAttributes(data, Map.of());

            assertEquals(3, result.getUpdatedValues());
            assertEquals(1, result.getInvalidValues());
            assertEquals(AttributeFieldType.INTEGER, store.findCustomFieldTypes().get("score"));
            assertEquals(AttributeFieldType.INTEGER_VECTOR, store.findCustomFieldTypes().get("vector"));
            assertEquals(AttributeFieldType.BOOLEAN, store.findCustomFieldTypes().get("reviewed"));
            store.populateAttributeExistingValueCounts(data);
            assertEquals(1, score.getExistingValueCount());
            assertEquals(1, vector.getExistingValueCount());
            assertEquals(1, reviewed.getExistingValueCount());
            assertEquals(0, invalid.getExistingValueCount());

            AttributeImportResult kept = store.importAttributes(data(score), Map.of());
            assertEquals(0, kept.getUpdatedValues());
            assertEquals(1, kept.getSkippedValues());
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void floatingPointImportsRejectNonfiniteScalarVectorAndOverflowValues(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            List<AttributeImportColumn> columns = new ArrayList<>();
            for (AttributeFieldType type : List.of(AttributeFieldType.FLOAT, AttributeFieldType.DOUBLE,
                    AttributeFieldType.FLOAT_VECTOR, AttributeFieldType.DOUBLE_VECTOR)) {
                for (String invalid : List.of("NaN", "Infinity", "-Infinity", "1e999")) {
                    String raw = type.isVector() ? "1|" + invalid + "|3" : invalid;
                    columns.add(custom(film, "invalid" + columns.size(), type, raw));
                }
            }
            columns.add(custom(film, "floatoverflow", AttributeFieldType.FLOAT, "3.5e38"));
            columns.add(custom(film, "floatvectoroverflow", AttributeFieldType.FLOAT_VECTOR, "1|3.5e38"));
            AttributeImportData data = new AttributeImportData(columns, List.of(), List.of());

            AttributeImportResult result = store.importAttributes(data, Map.of());

            assertEquals(0, result.getUpdatedValues());
            assertEquals(18, result.getInvalidValues());
            store.populateAttributeExistingValueCounts(data);
            for (AttributeImportColumn column : columns) {
                assertEquals(0, column.getExistingValueCount(), column.getHeader());
                assertNull(readCustomJson(backend, column.getNormalizedName()));
            }
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void blankDraftCustomValuesRetainPreviouslyTypedValues(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            AttributeImportColumn score = custom(film, "score", AttributeFieldType.INTEGER, "10");
            store.importAttributes(data(score), Map.of());

            for (String blank : new String[] {null, "", "  "}) {
                FilmDraft incoming = new FilmDraft();
                incoming.setProduction("Northeast Film Studio");
                incoming.getCustomFields().put("score", blank);
                store.overwriteWithNonBlankValues(film.getId(), incoming);

                assertEquals("10", readCustomJson(backend, "score"));
                store.populateAttributeExistingValueCounts(data(score));
                assertEquals(1, score.getExistingValueCount());
                assertEquals(AttributeFieldType.INTEGER, store.findCustomFieldTypes().get("score"));
            }
            assertEquals("Northeast Film Studio", film(store, film.getId()).getProduction());
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void incompatibleAttributeTypeIsRejectedBeforeAnyColumnCommits(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            AttributeImportColumn score = custom(film, "score", AttributeFieldType.INTEGER, "10");
            store.importAttributes(data(score), Map.of());
            AttributeImportColumn color = preserved(film, "color_format", "Must not commit");
            AttributeImportColumn wrongType = custom(film, "score", AttributeFieldType.STRING, "replacement");

            assertThrows(MetadataStoreException.class, () -> store.importAttributes(data(color, wrongType),
                    Map.of(color, AttributeOverwriteChoice.OVERWRITE,
                            wrongType, AttributeOverwriteChoice.OVERWRITE)));

            assertNull(film(store, film.getId()).getColorFormat());
            assertEquals("10", readCustomJson(backend, "score"));
            assertEquals(AttributeFieldType.INTEGER, store.findCustomFieldTypes().get("score"));
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void draftStringCannotReplaceAnExistingNumericDefinitionOrCommitOtherFields(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            store.importAttributes(data(custom(film, "score", AttributeFieldType.INTEGER, "10")), Map.of());
            FilmDraft incoming = new FilmDraft();
            incoming.setProduction("Must not commit");
            incoming.getCustomFields().put("score", "11");

            assertThrows(MetadataStoreException.class,
                    () -> store.overwriteWithNonBlankValues(film.getId(), incoming));

            assertNull(film(store, film.getId()).getProduction());
            assertEquals("10", readCustomJson(backend, "score"));
            assertEquals(AttributeFieldType.INTEGER, store.findCustomFieldTypes().get("score"));
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void preservedFieldsAndPersonnelRespectKeepOverwriteAndCancel(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            AttributeImportColumn color = preserved(film, "color_format", "B&W");
            AttributeImportColumn director = preserved(film, "director", "Wang Bin");
            assertEquals(2, store.importAttributes(data(color, director), Map.of()).getUpdatedValues());

            AttributeImportColumn replacementColor = preserved(film, "color_format", "Colour");
            AttributeImportColumn replacementDirector = preserved(film, "director", "Replacement director");
            AttributeImportData replacement = data(replacementColor, replacementDirector);
            store.populateAttributeExistingValueCounts(replacement);
            assertEquals(1, replacementColor.getExistingValueCount());
            assertEquals(1, replacementDirector.getExistingValueCount());
            AttributeImportResult kept = store.importAttributes(replacement, Map.of());
            assertEquals(2, kept.getSkippedValues());
            assertEquals("B&W", film(store, film.getId()).getColorFormat());

            assertEquals(2, store.importAttributes(replacement, Map.of(
                    replacementColor, AttributeOverwriteChoice.OVERWRITE,
                    replacementDirector, AttributeOverwriteChoice.OVERWRITE)).getUpdatedValues());
            assertEquals("Colour", film(store, film.getId()).getColorFormat());

            AttributeImportColumn pendingColor = preserved(film, "color_format", "Cancelled value");
            AttributeImportColumn cancelledDirector = preserved(film, "director", "Cancelled director");
            AttributeImportResult cancelled = store.importAttributes(data(pendingColor, cancelledDirector), Map.of(
                    pendingColor, AttributeOverwriteChoice.OVERWRITE,
                    cancelledDirector, AttributeOverwriteChoice.CANCEL));
            assertEquals(0, cancelled.getUpdatedValues());
            assertEquals("Colour", film(store, film.getId()).getColorFormat());
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void cancellationRollsBackEarlierCustomDefinitionsAndValues(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            AttributeImportColumn pending = custom(film, "pending", AttributeFieldType.STRING, "uncommitted");
            AttributeImportColumn cancel = custom(film, "cancel", AttributeFieldType.INTEGER, "42");

            AttributeImportResult cancelled = store.importAttributes(data(pending, cancel),
                    Map.of(cancel, AttributeOverwriteChoice.CANCEL));

            assertEquals(0, cancelled.getUpdatedValues());
            assertFalse(store.findCustomFieldTypes().containsKey("pending"));
            assertFalse(store.findCustomFieldTypes().containsKey("cancel"));
            store.populateAttributeExistingValueCounts(data(pending));
            assertEquals(0, pending.getExistingValueCount());
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void mediaImportsNormalizeDuplicatePathsAndRemainIdempotent(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            MediaImportData firstBatch = new MediaImportData(List.of(
                    media(film.getFilmKey(), "/tmp/bridge.mp4", MediaType.ORIGINAL_VIDEO),
                    media(film.getFilmKey(), "/tmp/bridge.wav", MediaType.AUDIO_TRACK),
                    media(film.getFilmKey(), "/tmp/../tmp/bridge.mp4", MediaType.ORIGINAL_VIDEO)));
            store.populateExistingMediaDuplicates(firstBatch);
            MediaImportResult imported = store.importMediaStorage(firstBatch);
            assertEquals(2, imported.getImportedRows());
            assertEquals(1, imported.getSkippedRows());

            MediaImportData repeated = new MediaImportData(List.of(
                    media(film.getFilmKey(), "/tmp/bridge.mp4", MediaType.ORIGINAL_VIDEO),
                    media(film.getFilmKey(), "/tmp/bridge.wav", MediaType.AUDIO_TRACK)));
            store.populateExistingMediaDuplicates(repeated);
            assertTrue(repeated.getRows().stream().allMatch(row -> row.getStatus() == MediaImportRowStatus.DUPLICATE));
            MediaImportResult skipped = store.importMediaStorage(repeated);
            assertEquals(0, skipped.getImportedRows());
            assertEquals(2, skipped.getSkippedRows());
            assertEquals(2, store.findMediaStorageByFilmKey(film.getFilmKey()).size());
        }
    }

    @ParameterizedTest
    @EnumSource(Backend.class)
    void failedMediaBatchRollsBackMappingsAndPreviewStatuses(Backend backend) throws Exception {
        try (MetadataStore store = open(backend)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949, "The Bridge"));
            MediaImportRow valid = media(film.getFilmKey(), "/tmp/valid.mp4", MediaType.ORIGINAL_VIDEO);
            MediaImportRow unknownFilm = media("unknown-film-key", "/tmp/unknown.mp4", MediaType.ORIGINAL_VIDEO);

            assertThrows(MetadataStoreException.class,
                    () -> store.importMediaStorage(new MediaImportData(List.of(valid, unknownFilm))));

            assertTrue(store.findMediaStorageByFilmKey(film.getFilmKey()).isEmpty());
            assertEquals(MediaImportRowStatus.ACTIVE, valid.getStatus());
            assertEquals(MediaImportRowStatus.ACTIVE, unknownFilm.getStatus());
        }
    }

    private MetadataStore open(Backend backend) throws Exception {
        if (backend == Backend.LOCAL_DIRECTORY) {
            openedLocalDirectory = Files.createTempDirectory(temporaryDirectory, "metadata-");
            return LocalDirectoryMetadataStore.create(openedLocalDirectory);
        }
        Connection connection = DriverManager.getConnection("jdbc:h2:mem:contract_" + System.nanoTime()
                + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE");
        try {
            new FilmRepository().initializeDatabase(connection);
            openedJdbcConnection = connection;
            return new JdbcMetadataStore(connection);
        } catch (Exception failure) {
            connection.close();
            throw failure;
        }
    }

    private FilmDraft draft(String title, Integer year, String translated) {
        FilmDraft draft = new FilmDraft();
        draft.setTitleOriginal(title);
        draft.setProductionYear(year);
        draft.setTitleTranslated(translated);
        return draft;
    }

    private String readCustomJson(Backend backend, String normalizedName) throws Exception {
        if (backend == Backend.JDBC) {
            try (PreparedStatement query = openedJdbcConnection.prepareStatement(
                    "SELECT v.value_json FROM film_custom_fields v "
                            + "JOIN custom_field_definitions d ON d.id = v.custom_field_id "
                            + "WHERE d.normalized_name = ?")) {
                query.setString(1, normalizedName);
                try (ResultSet rows = query.executeQuery()) {
                    return rows.next() ? rows.getString(1) : null;
                }
            }
        }
        JsonNode catalog = new ObjectMapper().readTree(
                openedLocalDirectory.resolve(LocalDirectoryMetadataStore.CATALOG_FILE_NAME).toFile());
        for (JsonNode definition : catalog.path("custom_field_definitions")) {
            if (normalizedName.equals(definition.path("normalized_name").asText())) {
                for (JsonNode value : catalog.path("film_custom_fields")) {
                    if (value.path("custom_field_id").asLong() == definition.path("id").asLong()) {
                        return value.path("value_json").toString();
                    }
                }
            }
        }
        return null;
    }

    private FilmEntry film(MetadataStore store, long id) throws MetadataStoreException {
        return store.findAll().stream().filter(entry -> entry.getId() == id).findFirst().orElseThrow();
    }

    private AttributeImportColumn custom(FilmEntry film, String name, AttributeFieldType type, String value) {
        AttributeImportColumn column = new AttributeImportColumn(name, name,
                AttributeTargetKind.CUSTOM, null, type, null);
        column.addValue(new AttributeImportValue(film.getId(), film.getFilmKey(), value));
        return column;
    }

    private AttributeImportColumn preserved(FilmEntry film, String name, String value) {
        AttributeImportColumn column = new AttributeImportColumn(name, name.replace("_", ""),
                AttributeTargetKind.PRESERVED, name, null, null);
        column.addValue(new AttributeImportValue(film.getId(), film.getFilmKey(), value));
        return column;
    }

    private AttributeImportData data(AttributeImportColumn... columns) {
        return new AttributeImportData(List.of(columns), List.of(), List.of());
    }

    private MediaImportRow media(String filmKey, String path, MediaType type) {
        MediaStorageFormat format = MediaStorageFormat.LOCAL_FILE;
        String normalized = MediaPathUtil.normalizePathForStorage(format, path);
        return new MediaImportRow(1, filmKey, format, path, normalized,
                MediaPathUtil.hashNormalizedPath(normalized), type,
                MediaPathUtil.detectExtension(format, path), MediaImportRowStatus.ACTIVE, "");
    }
}
