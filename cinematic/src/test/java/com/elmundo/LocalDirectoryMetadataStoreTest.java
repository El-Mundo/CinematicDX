package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.cfg.JsonNodeFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LocalDirectoryMetadataStoreTest {
    private static final ObjectMapper JSON = new ObjectMapper()
            .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
            .configure(JsonNodeFeature.STRIP_TRAILING_BIGDECIMAL_ZEROES, false);

    @TempDir
    Path directory;

    @Test
    void explicitCreateAndReopenKeepIdentityIdsAndRawInventory() throws Exception {
        Path inventory = directory.resolve("research-inventory.json");
        Files.writeString(inventory, "{\"source\":\"untouched\"}");
        byte[] raw = Files.readAllBytes(inventory);
        String catalogId;
        FilmEntry first;
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            first = store.insertAsUnique(draft("桥", 1949));
            store.renameFilmTitle(first.getId(), "新桥");
            catalogId = catalog().path("catalog_id").asText();
            assertTrue(store.getDescription().contains(directory.toString()));
        }
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.open(directory)) {
            FilmEntry restored = store.findAll().get(0);
            assertEquals(first.getId(), restored.getId());
            assertEquals(first.getFilmKey(), restored.getFilmKey());
            assertEquals("新桥", restored.getTitleOriginal());
            FilmEntry second = store.insertAsUnique(draft("桥", 1949));
            assertNotEquals(first.getId(), second.getId());
            assertEquals("桥-1949-1", second.getFilmKey());
            assertEquals(catalogId, catalog().path("catalog_id").asText());
        }
        assertArrayEquals(raw, Files.readAllBytes(inventory));
    }

    @Test
    void openingMissingCatalogDoesNotCreateOneOrDirectory() throws Exception {
        assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.open(directory));
        assertFalse(Files.exists(catalogPath()));
        Path missingDirectory = directory.resolve("missing");
        assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.create(missingDirectory));
        assertFalse(Files.exists(missingDirectory));
    }

    @Test
    void createNeverOverwritesAnExistingCatalog() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            store.insertAsUnique(draft("桥", 1949));
        }
        byte[] before = Files.readAllBytes(catalogPath());
        assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.create(directory));
        assertArrayEquals(before, Files.readAllBytes(catalogPath()));
        try (LocalDirectoryMetadataStore reopened = LocalDirectoryMetadataStore.open(directory)) {
            assertEquals(1, reopened.findAll().size());
        }
    }

    @Test
    void createPreservesAnOrphanedRecoveryBackup() throws Exception {
        Files.writeString(backupPath(), "recoverable previous catalog");
        assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.create(directory));
        assertFalse(Files.exists(catalogPath()));
        assertEquals("recoverable previous catalog", Files.readString(backupPath()));
    }

    @Test
    void secondWriterIsRejectedAndCloseReleasesLock() throws Exception {
        LocalDirectoryMetadataStore first = LocalDirectoryMetadataStore.create(directory);
        try {
            assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.open(directory));
            assertThrows(MetadataStoreException.class,
                    () -> LocalDirectoryMetadataStore.open(directory.resolve(".")));
        } finally {
            first.close();
        }
        first.close();
        assertThrows(MetadataStoreException.class, first::findAll);
        try (LocalDirectoryMetadataStore second = LocalDirectoryMetadataStore.open(directory)) {
            assertEquals(0, second.findAll().size());
        }
    }

    @Test
    void detectsExternalEditWithoutOverwritingIt() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            store.insertAsUnique(draft("桥", 1949));
            String external = Files.readString(catalogPath()) + "\n";
            Files.writeString(catalogPath(), external);
            assertThrows(MetadataStoreException.class, store::findAll);
            assertThrows(MetadataStoreException.class, () -> store.insertAsUnique(draft("船", 1950)));
            assertEquals(external, Files.readString(catalogPath()));
        }
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.open(directory)) {
            assertEquals(1, store.findAll().size());
        }
    }

    @Test
    void keepsImmediatelyPreviousSnapshotAsBackup() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            byte[] empty = Files.readAllBytes(catalogPath());
            FilmEntry film = store.insertAsUnique(draft("桥", 1949));
            assertArrayEquals(empty, Files.readAllBytes(backupPath()));
            byte[] beforeRename = Files.readAllBytes(catalogPath());
            store.renameFilmTitle(film.getId(), "新桥");
            assertArrayEquals(beforeRename, Files.readAllBytes(backupPath()));
            assertEquals(2, catalog().path("revision").asLong());
        }
    }

    @Test
    void failedSavePreservesDiskMemoryIdsAndRowStatuses() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949));
            Files.delete(backupPath());
            Files.createDirectory(backupPath());
            byte[] before = Files.readAllBytes(catalogPath());
            assertThrows(MetadataStoreException.class, () -> store.insertAsUnique(draft("船", 1950)));
            MediaImportRow row = mediaRow(film.getFilmKey(), directory.resolve("bridge.mp4"));
            assertThrows(MetadataStoreException.class,
                    () -> store.importMediaStorage(new MediaImportData(List.of(row))));
            assertEquals(MediaImportRowStatus.ACTIVE, row.getStatus());
            assertArrayEquals(before, Files.readAllBytes(catalogPath()));
            assertEquals(1, store.findAll().size());
            assertEquals(0, store.findMediaStorageByFilmKey(film.getFilmKey()).size());
            Files.delete(backupPath());
            FilmEntry next = store.insertAsUnique(draft("船", 1950));
            assertEquals(film.getId() + 1, next.getId());
            try (java.util.stream.Stream<Path> files = Files.list(directory)) {
                assertFalse(files.anyMatch(path -> path.getFileName().toString().endsWith(".tmp")));
            }
        }
    }

    @Test
    void invalidReferencesRollbackAnEntireMediaBatch() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949));
            MediaImportRow valid = mediaRow(film.getFilmKey(), directory.resolve("bridge.mp4"));
            MediaImportRow invalid = mediaRow("missing-key", directory.resolve("missing.mp4"));
            byte[] before = Files.readAllBytes(catalogPath());
            assertThrows(MetadataStoreException.class,
                    () -> store.importMediaStorage(new MediaImportData(List.of(valid, invalid))));
            assertArrayEquals(before, Files.readAllBytes(catalogPath()));
            assertEquals(MediaImportRowStatus.ACTIVE, valid.getStatus());
            assertTrue(store.findMediaStorageByFilmKey(film.getFilmKey()).isEmpty());
        }
    }

    @Test
    void cancellingLaterAttributeColumnReportsNoCommittedChanges() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949));
            AttributeImportColumn first = custom("score", AttributeFieldType.INTEGER, film, "10");
            AttributeImportColumn later = custom("note", AttributeFieldType.STRING, film, "cancelled");
            byte[] before = Files.readAllBytes(catalogPath());
            AttributeImportResult result = store.importAttributes(new AttributeImportData(
                    List.of(first, later), List.of(), List.of()), Map.of(
                            first, AttributeOverwriteChoice.OVERWRITE, later, AttributeOverwriteChoice.CANCEL));
            assertEquals(0, result.getUpdatedValues());
            assertEquals(0, result.getSkippedValues());
            assertEquals(0, result.getInvalidValues());
            assertArrayEquals(before, Files.readAllBytes(catalogPath()));
            assertTrue(store.findCustomFieldTypes().isEmpty());
        }
    }

    @Test
    void personnelTypedValuesAndUnknownFieldsSurviveRenameAndReopen() throws Exception {
        FilmEntry film;
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            film = store.insertAsUnique(draft("桥", 1949));
            AttributeImportColumn director = preserved("director", "director", film, "王滨");
            AttributeImportColumn actors = preserved("cast", "actors", film, "陈强|王家乙");
            AttributeImportColumn score = custom("score", AttributeFieldType.DOUBLE_VECTOR,
                    film, "0.25|0.75");
            AttributeImportColumn flag = custom("approved", AttributeFieldType.BOOLEAN, film, "true");
            AttributeImportData data = new AttributeImportData(List.of(director, actors, score, flag),
                    List.of(), List.of());
            store.importAttributes(data, Map.of(director, AttributeOverwriteChoice.OVERWRITE,
                    actors, AttributeOverwriteChoice.OVERWRITE, score, AttributeOverwriteChoice.OVERWRITE,
                    flag, AttributeOverwriteChoice.OVERWRITE));
        }
        ObjectNode source = catalog();
        source.putObject("unmapped_source").put("历史备注", "原始内容");
        ((ObjectNode) source.withArray("films").get(0)).put("unmapped_film_value", "preserved");
        writeCatalog(source);
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.open(directory)) {
            store.renameFilmTitle(film.getId(), "新桥");
        }
        ObjectNode saved = catalog();
        assertEquals("原始内容", saved.path("unmapped_source").path("历史备注").asText());
        assertEquals("preserved", saved.path("films").get(0).path("unmapped_film_value").asText());
        assertEquals("王滨", saved.path("films").get(0).path("director").asText());
        assertEquals("陈强|王家乙", saved.path("films").get(0).path("actors").asText());
        JsonNode values = saved.path("film_custom_fields");
        assertTrue(values.get(0).path("value_json").isArray());
        assertEquals(0.25, values.get(0).path("value_json").get(0).doubleValue());
        assertTrue(values.get(1).path("value_json").isBoolean());
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.open(directory)) {
            assertEquals(AttributeFieldType.DOUBLE_VECTOR, store.findCustomFieldTypes().get("score"));
            assertEquals(AttributeFieldType.BOOLEAN, store.findCustomFieldTypes().get("approved"));
            assertEquals(film.getFilmKey(), store.findAll().get(0).getFilmKey());
        }
    }

    @Test
    void malformedJsonAndDuplicateKeysAreRejectedWithoutRepair() throws Exception {
        for (String invalid : List.of("{", "[]", "{\"schema_version\":1,\"schema_version\":2}",
                "{} {}", "null")) {
            Files.writeString(catalogPath(), invalid);
            assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.open(directory));
            assertEquals(invalid, Files.readString(catalogPath()));
        }
    }

    @Test
    void invalidSchemaReferencesIdsCountersAndTypesAreRejected() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            store.insertAsUnique(draft("桥", 1949));
        }
        ObjectNode original = catalog();
        assertRejected(original, node -> node.put("schema_version", 99));
        assertRejected(original, node -> node.put("schema_version", 4294967297L));
        assertRejected(original, node -> node.put("catalog_id", "not-a-uuid"));
        assertRejected(original, node -> node.put("revision", -1));
        assertRejected(original, node -> node.put("next_film_id", 1));
        assertRejected(original, node -> node.withArray("films").add(node.withArray("films").get(0).deepCopy()));
        assertRejected(original, node -> ((ObjectNode) node.withArray("films").get(0))
                .put("production_year", "1949"));
        assertRejected(original, node -> ((ObjectNode) node.withArray("films").get(0))
                .put("title_match_key", "wrong"));
        assertRejected(original, node -> node.withArray("film_custom_fields").addObject()
                .put("film_id", 1).put("custom_field_id", 999).put("value_json", "unknown"));
        assertRejected(original, node -> {
            node.put("next_custom_field_id", 2);
            node.withArray("custom_field_definitions").addObject().put("id", 1)
                    .put("field_name", "note").put("normalized_name", "note").put("field_type", "unknown");
        });
    }

    @Test
    void malformedNativeCustomValueTypesAndRangesAreRejected() throws Exception {
        try (LocalDirectoryMetadataStore store = LocalDirectoryMetadataStore.create(directory)) {
            FilmEntry film = store.insertAsUnique(draft("桥", 1949));
            AttributeImportColumn note = custom("note", AttributeFieldType.STRING, film, "text");
            store.importAttributes(new AttributeImportData(List.of(note), List.of(), List.of()),
                    Map.of(note, AttributeOverwriteChoice.OVERWRITE));
        }
        ObjectNode original = catalog();
        assertRejectedCustomValue(original, "string", "42");
        assertRejectedCustomValue(original, "string", "null");
        assertRejectedCustomValue(original, "integer", "\"42\"");
        assertRejectedCustomValue(original, "integer", "42.0");
        assertRejectedCustomValue(original, "integer", "9223372036854775808");
        assertRejectedCustomValue(original, "boolean", "\"true\"");
        assertRejectedCustomValue(original, "boolean", "1");
        assertRejectedCustomValue(original, "float", "\"0.5\"");
        assertRejectedCustomValue(original, "float", "3.5e38");
        assertRejectedCustomValue(original, "float", "1e-100");
        assertRejectedCustomValue(original, "double", "1e309");
        assertRejectedCustomValue(original, "double", "1e-500");
        assertRejectedCustomValue(original, "integer_vector", "[1,\"2\"]");
        assertRejectedCustomValue(original, "integer_vector", "[1,9223372036854775808]");
        assertRejectedCustomValue(original, "float_vector", "[1,3.5e38]");
        assertRejectedCustomValue(original, "double_vector", "[1,null]");
        assertRejectedCustomValue(original, "double_vector", "[1,[2]]");
        assertRejectedCustomValue(original, "double_vector", "[]");
        assertRejectedCustomValue(original, "double_vector", "2");
    }

    private void assertRejectedCustomValue(ObjectNode original, String type, String json) throws Exception {
        JsonNode value = JSON.readTree(json);
        assertRejected(original, node -> {
            ((ObjectNode) node.withArray("custom_field_definitions").get(0)).put("field_type", type);
            ((ObjectNode) node.withArray("film_custom_fields").get(0)).set("value_json", value);
        });
    }

    @Test
    void symbolicLinkCatalogIsRejected() throws Exception {
        Path target = directory.resolve("raw-source.json");
        Files.writeString(target, "{\"raw\":true}");
        Files.createSymbolicLink(catalogPath(), target);
        assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.open(directory));
        assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.create(directory));
        assertEquals("{\"raw\":true}", Files.readString(target));
    }

    private void assertRejected(ObjectNode original, java.util.function.Consumer<ObjectNode> mutate)
            throws Exception {
        ObjectNode candidate = original.deepCopy();
        mutate.accept(candidate);
        writeCatalog(candidate);
        byte[] before = Files.readAllBytes(catalogPath());
        assertThrows(MetadataStoreException.class, () -> LocalDirectoryMetadataStore.open(directory));
        assertArrayEquals(before, Files.readAllBytes(catalogPath()));
    }

    private ObjectNode catalog() throws IOException {
        return (ObjectNode) JSON.readTree(Files.readAllBytes(catalogPath()));
    }

    private void writeCatalog(ObjectNode node) throws IOException {
        Files.write(catalogPath(), JSON.writerWithDefaultPrettyPrinter().writeValueAsBytes(node));
    }

    private Path catalogPath() {
        return directory.resolve(LocalDirectoryMetadataStore.CATALOG_FILE_NAME);
    }

    private Path backupPath() {
        return directory.resolve(LocalDirectoryMetadataStore.BACKUP_FILE_NAME);
    }

    private static FilmDraft draft(String title, Integer year) {
        FilmDraft draft = new FilmDraft();
        draft.setTitleOriginal(title);
        draft.setProductionYear(year);
        return draft;
    }

    private static AttributeImportColumn preserved(String header, String target, FilmEntry film, String value) {
        AttributeImportColumn column = new AttributeImportColumn(header,
                AttributeHeaderMapper.normalizeHeader(header), AttributeTargetKind.PRESERVED, target, null, null);
        column.addValue(new AttributeImportValue(film.getId(), film.getFilmKey(), value));
        return column;
    }

    private static AttributeImportColumn custom(String name, AttributeFieldType type, FilmEntry film, String value) {
        AttributeImportColumn column = new AttributeImportColumn(name, name, AttributeTargetKind.CUSTOM,
                null, type, null);
        column.addValue(new AttributeImportValue(film.getId(), film.getFilmKey(), value));
        return column;
    }

    private static MediaImportRow mediaRow(String filmKey, Path path) {
        String normalized = MediaPathUtil.normalizePathForStorage(MediaStorageFormat.LOCAL_FILE, path.toString());
        return new MediaImportRow(1, filmKey, MediaStorageFormat.LOCAL_FILE, path.toString(), normalized,
                MediaPathUtil.hashNormalizedPath(normalized), MediaType.ORIGINAL_VIDEO,
                "mp4", MediaImportRowStatus.ACTIVE, "");
    }
}
