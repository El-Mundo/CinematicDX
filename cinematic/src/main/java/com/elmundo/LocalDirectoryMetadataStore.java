package com.elmundo;

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.StreamReadFeature;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/** A single-writer, inspectable metadata catalog. Media and source inventories are never copied. */
public final class LocalDirectoryMetadataStore implements MetadataStore {
    public static final String CATALOG_FILE_NAME = "catalog.json";
    public static final String BACKUP_FILE_NAME = "catalog.json.bak";
    private static final String LOCK_FILE_NAME = ".cinematicdx.lock";
    private static final int SCHEMA_VERSION = 1;
    private static final Set<String> TEXT_FILM_FIELDS = Set.of(
            "title_translated", "production", "color_format", "romanized", "special_aspects",
            "director", "scriptwriter", "actors", "staff", "other_staff", "media_path",
            "storage_format", "media_type");
    private static final Set<String> PRESERVED_FIELDS = Set.of(
            "title_translated", "production", "color_format", "romanized", "special_aspects",
            "director", "scriptwriter", "actors", "staff", "other_staff", "media_path",
            "storage_format", "media_type");
    private static final ObjectMapper JSON = new ObjectMapper(JsonFactory.builder()
            .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION).build())
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
            .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);

    private final Path directory;
    private final Path catalogPath;
    private final FileChannel lockChannel;
    private final FileLock lock;
    private ObjectNode snapshot;
    private byte[] fingerprint;
    private boolean closed;

    private LocalDirectoryMetadataStore(Path directory, FileChannel channel, FileLock lock) {
        this.directory = directory;
        this.catalogPath = directory.resolve(CATALOG_FILE_NAME);
        this.lockChannel = channel;
        this.lock = lock;
    }

    /** Opens an existing catalog, without creating or repairing metadata. */
    public static LocalDirectoryMetadataStore open(Path directory) throws MetadataStoreException {
        return acquire(directory, false);
    }

    /** Explicitly creates a catalog in an already-existing directory; never overwrites a catalog. */
    public static LocalDirectoryMetadataStore create(Path directory) throws MetadataStoreException {
        return acquire(directory, true);
    }

    private static LocalDirectoryMetadataStore acquire(Path requested, boolean create)
            throws MetadataStoreException {
        LocalDirectoryMetadataStore store = null;
        FileChannel channel = null;
        FileLock held = null;
        try {
            if (requested == null || !Files.isDirectory(requested)) {
                throw new IOException("Select an existing directory.");
            }
            Path directory = requested.toRealPath();
            Path lockPath = directory.resolve(LOCK_FILE_NAME);
            if (Files.isSymbolicLink(lockPath)) {
                throw new IOException("The catalog lock must not be a symbolic link.");
            }
            channel = FileChannel.open(lockPath, StandardOpenOption.CREATE, StandardOpenOption.WRITE);
            held = channel.tryLock();
            if (held == null) {
                throw new IOException("This catalog is already open in another application session.");
            }
            store = new LocalDirectoryMetadataStore(directory, channel, held);
            if (create) {
                if (Files.exists(store.catalogPath, LinkOption.NOFOLLOW_LINKS)) {
                    throw new IOException("A catalog already exists in this directory. Use Open instead.");
                }
                if (Files.exists(directory.resolve(BACKUP_FILE_NAME), LinkOption.NOFOLLOW_LINKS)) {
                    throw new IOException("A previous catalog backup exists in this directory. "
                            + "Recover it or choose another directory before creating a catalog.");
                }
                store.snapshot = emptySnapshot();
                byte[] bytes = encode(store.snapshot);
                Path temporary = writeTemporary(directory, bytes);
                try {
                    // Linking a fully written sibling provides atomic, no-clobber creation.
                    Files.createLink(store.catalogPath, temporary);
                } finally {
                    deleteTemporary(temporary);
                }
                store.fingerprint = digest(bytes);
            } else {
                byte[] bytes = store.readCatalog();
                JsonNode parsed = JSON.readTree(bytes);
                if (!(parsed instanceof ObjectNode)) {
                    throw new IOException("The catalog must be a JSON object.");
                }
                store.snapshot = (ObjectNode) parsed;
                validate(store.snapshot);
                store.fingerprint = digest(bytes);
            }
            return store;
        } catch (IOException | RuntimeException e) {
            if (held != null) {
                try { held.release(); } catch (IOException ignored) { }
            }
            if (channel != null) {
                try { channel.close(); } catch (IOException ignored) { }
            }
            String detail = e instanceof OverlappingFileLockException
                    ? "This catalog is already open in another application session." : e.getMessage();
            throw new MetadataStoreException("Could not " + (create ? "create" : "open")
                    + " local metadata catalog: " + detail, e);
        }
    }

    @Override
    public String getDescription() {
        return "Local directory: " + directory;
    }

    @Override
    public synchronized List<FilmEntry> findAll() throws MetadataStoreException {
        ensureCurrent();
        List<FilmEntry> films = new ArrayList<>();
        for (JsonNode film : snapshot.withArray("films")) {
            films.add(toFilm(film));
        }
        films.sort(Comparator.comparing(FilmEntry::getProductionYear,
                Comparator.nullsLast(Comparator.naturalOrder()))
                .thenComparing(FilmEntry::getTitleOriginal).thenComparing(FilmEntry::getId));
        return films;
    }

    @Override
    public synchronized Optional<FilmEntry> findMatchingTitleAndYear(FilmDraft draft)
            throws MetadataStoreException {
        ensureCurrent();
        String key = FilmKeyGenerator.normalizeTitleForMatch(draft.getTitleOriginal());
        FilmEntry match = null;
        for (JsonNode film : snapshot.withArray("films")) {
            if (key.equals(film.path("title_match_key").asText())
                    && Objects.equals(draft.getProductionYear(), integer(film, "production_year"))) {
                FilmEntry candidate = toFilm(film);
                if (match == null || candidate.getId() < match.getId()) {
                    match = candidate;
                }
            }
        }
        return Optional.ofNullable(match);
    }

    @Override
    public synchronized FilmEntry insertAsUnique(FilmDraft draft) throws MetadataStoreException {
        if (draft == null || !draft.hasTitle()) {
            throw new IllegalArgumentException("Original-language title is required.");
        }
        draft = MetadataValueRules.prepareDraft(draft, findCustomFieldTypes());
        ensureCurrent();
        ObjectNode next = snapshot.deepCopy();
        Set<String> keys = new HashSet<>();
        next.withArray("films").forEach(film -> keys.add(film.path("film_key").asText()));
        String filmKey;
        try {
            filmKey = FilmKeyGenerator.generateUniqueKey(
                    draft.getTitleOriginal(), draft.getProductionYear(), keys::contains);
        } catch (SQLException impossible) {
            throw new MetadataStoreException("Could not generate a film key.", impossible);
        }
        ObjectNode film = JSON.createObjectNode();
        film.put("id", takeId(next, "next_film_id"));
        film.put("film_key", filmKey);
        film.put("title_original", draft.getTitleOriginal());
        film.put("title_match_key", FilmKeyGenerator.normalizeTitleForMatch(draft.getTitleOriginal()));
        TEXT_FILM_FIELDS.forEach(field -> film.putNull(field));
        film.putNull("production_year");
        updateCore(film, draft);
        film.put("created_at", Instant.now().toString());
        film.put("updated_at", film.path("created_at").asText());
        film.putObject("extensions");
        next.withArray("films").add(film);
        saveDraftCustomFields(next, film.path("id").asLong(), draft);
        commit(next);
        return toFilm(film);
    }

    @Override
    public synchronized void overwriteWithNonBlankValues(long filmId, FilmDraft draft)
            throws MetadataStoreException {
        draft = MetadataValueRules.prepareDraft(draft, findCustomFieldTypes());
        ensureCurrent();
        ObjectNode next = snapshot.deepCopy();
        ObjectNode film = filmById(next, filmId);
        if (film != null) {
            updateCore(film, draft);
        }
        saveDraftCustomFields(next, filmId, draft);
        commit(next);
    }

    @Override
    public synchronized void renameFilmTitle(long filmId, String titleOriginal)
            throws MetadataStoreException {
        if (!FilmDraft.hasText(titleOriginal)) {
            throw new IllegalArgumentException("Original-language title is required.");
        }
        ensureCurrent();
        ObjectNode next = snapshot.deepCopy();
        ObjectNode film = filmById(next, filmId);
        if (film != null) {
            film.put("title_original", titleOriginal.trim());
            film.put("title_match_key", FilmKeyGenerator.normalizeTitleForMatch(titleOriginal));
            film.put("updated_at", Instant.now().toString());
        }
        commit(next);
    }

    @Override
    public synchronized Map<String, Long> findFilmIdsByKey() throws MetadataStoreException {
        ensureCurrent();
        Map<String, Long> ids = new LinkedHashMap<>();
        snapshot.withArray("films").forEach(film -> ids.put(
                film.path("film_key").asText(), film.path("id").asLong()));
        return ids;
    }

    @Override
    public synchronized List<AttributeFilmTarget> findAttributeFilmTargets() throws MetadataStoreException {
        List<AttributeFilmTarget> targets = new ArrayList<>();
        for (FilmEntry film : findAll()) {
            targets.add(new AttributeFilmTarget(film.getId(), film.getFilmKey(),
                    film.getTitleOriginal(), film.getProductionYear()));
        }
        return targets;
    }

    @Override
    public synchronized Map<String, AttributeFieldType> findCustomFieldTypes() throws MetadataStoreException {
        ensureCurrent();
        Map<String, AttributeFieldType> types = new LinkedHashMap<>();
        snapshot.withArray("custom_field_definitions").forEach(definition -> types.put(
                definition.path("normalized_name").asText(),
                AttributeFieldType.fromStorageName(definition.path("field_type").asText())));
        return types;
    }

    @Override
    public synchronized void populateAttributeExistingValueCounts(AttributeImportData data)
            throws MetadataStoreException {
        ensureCurrent();
        for (AttributeImportColumn column : data.getImportableColumns()) {
            int count = 0;
            for (AttributeImportValue value : column.getValues()) {
                if (value.hasValue() && hasAttribute(snapshot, column, value.getFilmId())) {
                    count++;
                }
            }
            column.setExistingValueCount(count);
        }
    }

    @Override
    public synchronized AttributeImportResult importAttributes(AttributeImportData data,
            Map<AttributeImportColumn, AttributeOverwriteChoice> overwriteChoices)
            throws MetadataStoreException {
        for (AttributeImportColumn column : data.getImportableColumns()) {
            if (overwriteChoices.getOrDefault(column, AttributeOverwriteChoice.KEEP_EXISTING)
                    == AttributeOverwriteChoice.CANCEL) {
                return new AttributeImportResult();
            }
        }
        ensureCurrent();
        MetadataValueRules.validateAttributeTypes(data, findCustomFieldTypes());
        ObjectNode next = snapshot.deepCopy();
        AttributeImportResult result = new AttributeImportResult();
        List<AttributeImportColumn> invalidColumns = new ArrayList<>();
        for (AttributeImportColumn column : data.getImportableColumns()) {
            AttributeOverwriteChoice choice = overwriteChoices.getOrDefault(
                    column, AttributeOverwriteChoice.KEEP_EXISTING);
            if (choice == AttributeOverwriteChoice.CANCEL) {
                return new AttributeImportResult();
            }
            ObjectNode definition = column.getTargetKind() == AttributeTargetKind.CUSTOM
                    ? getOrCreateDefinition(next, column.getHeader(), column.getNormalizedName(),
                            column.getFieldType()) : null;
            for (AttributeImportValue value : column.getValues()) {
                if (!value.hasValue() || (choice == AttributeOverwriteChoice.KEEP_EXISTING
                        && hasAttribute(next, column, value.getFilmId()))) {
                    result.incrementSkippedValues();
                    continue;
                }
                if (column.getTargetKind() == AttributeTargetKind.PRESERVED) {
                    String field = column.getPreservedColumnName();
                    if (!PRESERVED_FIELDS.contains(field)) {
                        throw failure("Unsupported preserved field: " + field);
                    }
                    ObjectNode film = filmById(next, value.getFilmId());
                    if (film != null) {
                        film.put(field, value.getRawValue());
                        film.put("updated_at", Instant.now().toString());
                    }
                    result.incrementUpdatedValues();
                } else {
                    try {
                        String converted = AttributeValueConverter.toJson(
                                value.getRawValue(), column.getFieldType());
                        JsonNode json = JSON.readTree(converted);
                        upsertCustomValue(next, value.getFilmId(), definition.path("id").asLong(), json);
                        result.incrementUpdatedValues();
                    } catch (IllegalArgumentException | IOException e) {
                        invalidColumns.add(column);
                        result.incrementInvalidValues();
                    }
                }
            }
        }
        commit(next);
        invalidColumns.forEach(AttributeImportColumn::incrementInvalidValueCount);
        return result;
    }

    @Override
    public synchronized List<MediaStorageEntry> findMediaStorageByFilmKey(String filmKey)
            throws MetadataStoreException {
        ensureCurrent();
        List<MediaStorageEntry> media = new ArrayList<>();
        for (JsonNode entry : snapshot.withArray("film_media_storage")) {
            if (filmKey.equals(entry.path("film_key").asText())) {
                media.add(new MediaStorageEntry(entry.path("id").asLong(), filmKey,
                        text(entry, "storage_format"), text(entry, "path"),
                        text(entry, "media_type"), text(entry, "file_extension")));
            }
        }
        media.sort(Comparator.comparing(MediaStorageEntry::getMediaType)
                .thenComparing(MediaStorageEntry::getStorageFormat).thenComparing(MediaStorageEntry::getPath));
        return media;
    }

    @Override
    public synchronized void populateExistingMediaDuplicates(MediaImportData data)
            throws MetadataStoreException {
        ensureCurrent();
        for (MediaImportRow row : data.getImportableRows()) {
            if (mediaExists(snapshot, row)) {
                row.setStatus(MediaImportRowStatus.DUPLICATE);
                row.setWarning("Media storage object already exists.");
            }
        }
    }

    @Override
    public synchronized MediaImportResult importMediaStorage(MediaImportData data)
            throws MetadataStoreException {
        ensureCurrent();
        ObjectNode next = snapshot.deepCopy();
        MediaImportResult result = new MediaImportResult();
        List<MediaImportRow> imported = new ArrayList<>();
        List<MediaImportRow> duplicates = new ArrayList<>();
        for (MediaImportRow row : data.getRows()) {
            if (!row.isImportable()) {
                result.incrementSkippedRows();
            } else if (mediaExists(next, row)) {
                duplicates.add(row);
                result.incrementSkippedRows();
            } else {
                ObjectNode entry = next.withArray("film_media_storage").addObject();
                entry.put("id", takeId(next, "next_media_id"));
                entry.put("film_key", row.getFilmKey());
                entry.put("storage_format", row.getStorageFormat());
                entry.put("path", row.getNormalizedPath());
                entry.put("path_hash", row.getPathHash());
                entry.put("media_type", row.getMediaType());
                entry.put("file_extension", row.getFileExtension());
                entry.put("created_at", Instant.now().toString());
                entry.putObject("extensions");
                imported.add(row);
                result.incrementImportedRows();
            }
        }
        commit(next);
        imported.forEach(row -> row.setStatus(MediaImportRowStatus.IMPORTED));
        duplicates.forEach(row -> {
            row.setStatus(MediaImportRowStatus.DUPLICATE);
            row.setWarning("Media storage object already exists.");
        });
        return result;
    }

    @Override
    public synchronized void close() throws MetadataStoreException {
        if (closed) { return; }
        closed = true;
        try {
            lock.release();
        } catch (IOException e) {
            throw new MetadataStoreException("Could not release the local catalog lock.", e);
        } finally {
            try {
                lockChannel.close();
            } catch (IOException e) {
                throw new MetadataStoreException("Could not close the local catalog lock.", e);
            }
        }
    }

    private static ObjectNode emptySnapshot() {
        ObjectNode root = JSON.createObjectNode();
        root.put("schema_version", SCHEMA_VERSION);
        root.put("catalog_id", UUID.randomUUID().toString());
        root.put("revision", 0);
        root.put("next_film_id", 1);
        root.put("next_custom_field_id", 1);
        root.put("next_media_id", 1);
        for (String collection : List.of("films", "custom_field_definitions", "film_custom_fields",
                "film_media_storage")) {
            root.putArray(collection);
        }
        root.putObject("extensions");
        return root;
    }

    private void ensureCurrent() throws MetadataStoreException {
        if (closed) { throw failure("The local catalog is closed."); }
        try {
            if (!Arrays.equals(fingerprint, digest(readCatalog()))) {
                throw failure("The catalog changed outside this session. Close and reopen it before continuing.");
            }
        } catch (IOException e) {
            throw new MetadataStoreException("Could not verify the local catalog; no changes were saved.", e);
        }
    }

    private byte[] readCatalog() throws IOException {
        if (!Files.isRegularFile(catalogPath, LinkOption.NOFOLLOW_LINKS)) {
            throw new IOException("The directory must contain a regular " + CATALOG_FILE_NAME
                    + " file. Create a new catalog explicitly if needed.");
        }
        return Files.readAllBytes(catalogPath);
    }

    private void commit(ObjectNode next) throws MetadataStoreException {
        ensureCurrent();
        long revision = snapshot.path("revision").asLong();
        if (revision == Long.MAX_VALUE) { throw failure("The catalog revision limit was reached."); }
        next.put("revision", revision + 1);
        Path temporary = null;
        try {
            validate(next);
            byte[] bytes = encode(next);
            temporary = writeTemporary(directory, bytes);
            byte[] previous = readCatalog();
            if (!Arrays.equals(fingerprint, digest(previous))) {
                throw failure("The catalog changed outside this session; no changes were saved.");
            }
            Path backup = directory.resolve(BACKUP_FILE_NAME);
            if (Files.exists(backup, LinkOption.NOFOLLOW_LINKS)
                    && !Files.isRegularFile(backup, LinkOption.NOFOLLOW_LINKS)) {
                throw new IOException("The catalog backup path is not a regular file.");
            }
            Path backupTemporary = writeTemporary(directory, previous);
            try {
                Files.move(backupTemporary, backup, StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING);
            } finally {
                deleteTemporary(backupTemporary);
            }
            ensureCurrent();
            Files.move(temporary, catalogPath, StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
            snapshot = next;
            fingerprint = digest(bytes);
        } catch (IOException | IllegalArgumentException e) {
            throw new MetadataStoreException("Could not save the local catalog; the previous catalog is intact.", e);
        } finally {
            deleteTemporary(temporary);
        }
    }

    private static Path writeTemporary(Path directory, byte[] bytes) throws IOException {
        Path temporary = Files.createTempFile(directory, ".cinematicdx-", ".tmp");
        try (FileChannel output = FileChannel.open(temporary, StandardOpenOption.WRITE)) {
            ByteBuffer buffer = ByteBuffer.wrap(bytes);
            while (buffer.hasRemaining()) { output.write(buffer); }
            output.force(true);
            return temporary;
        } catch (IOException e) {
            deleteTemporary(temporary);
            throw e;
        }
    }

    private static void deleteTemporary(Path path) {
        if (path != null) {
            try { Files.deleteIfExists(path); } catch (IOException ignored) { }
        }
    }

    private static byte[] encode(ObjectNode snapshot) throws IOException {
        return JSON.writerWithDefaultPrettyPrinter().writeValueAsBytes(snapshot);
    }

    private static byte[] digest(byte[] bytes) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(bytes);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable.", e);
        }
    }

    private static void updateCore(ObjectNode film, FilmDraft draft) {
        if (FilmDraft.hasText(draft.getTitleOriginal())) {
            film.put("title_original", draft.getTitleOriginal());
            film.put("title_match_key", FilmKeyGenerator.normalizeTitleForMatch(draft.getTitleOriginal()));
        }
        if (draft.getProductionYear() != null) { film.put("production_year", draft.getProductionYear()); }
        putNonBlank(film, "title_translated", draft.getTitleTranslated());
        putNonBlank(film, "production", draft.getProduction());
        putNonBlank(film, "color_format", draft.getColorFormat());
        putNonBlank(film, "romanized", draft.getRomanized());
        putNonBlank(film, "special_aspects", draft.getSpecialAspects());
        film.put("updated_at", Instant.now().toString());
    }

    private static void putNonBlank(ObjectNode film, String key, String value) {
        if (FilmDraft.hasText(value)) { film.put(key, value); }
    }

    private static void saveDraftCustomFields(ObjectNode root, long filmId, FilmDraft draft)
            throws MetadataStoreException {
        for (Map.Entry<String, String> field : draft.getCustomFields().entrySet()) {
            if (!FilmDraft.hasText(field.getKey())) { continue; }
            ObjectNode definition = getOrCreateDefinition(root, field.getKey().trim(),
                    AttributeHeaderMapper.normalizeHeader(field.getKey()), AttributeFieldType.STRING);
            upsertCustomValue(root, filmId, definition.path("id").asLong(),
                    JSON.getNodeFactory().textNode(field.getValue() == null ? "" : field.getValue()));
        }
    }

    private static ObjectNode getOrCreateDefinition(ObjectNode root, String name, String normalized,
            AttributeFieldType type) throws MetadataStoreException {
        for (JsonNode definition : root.withArray("custom_field_definitions")) {
            if (Objects.equals(normalized, definition.path("normalized_name").asText())) {
                return (ObjectNode) definition;
            }
        }
        if (normalized == null || type == null) { throw failure("A custom field requires a name and type."); }
        ObjectNode definition = root.withArray("custom_field_definitions").addObject();
        definition.put("id", takeId(root, "next_custom_field_id"));
        definition.put("field_name", name);
        definition.put("normalized_name", normalized);
        definition.put("field_type", type.getStorageName());
        definition.put("created_at", Instant.now().toString());
        definition.putObject("extensions");
        return definition;
    }

    private static void upsertCustomValue(ObjectNode root, long filmId, long definitionId, JsonNode value) {
        ObjectNode existing = customValue(root, filmId, definitionId);
        if (existing == null) {
            existing = root.withArray("film_custom_fields").addObject();
            existing.put("film_id", filmId);
            existing.put("custom_field_id", definitionId);
            existing.put("created_at", Instant.now().toString());
            existing.putObject("extensions");
        }
        existing.set("value_json", value);
        existing.put("updated_at", Instant.now().toString());
    }

    private static boolean hasAttribute(ObjectNode root, AttributeImportColumn column, long filmId)
            throws MetadataStoreException {
        if (column.getTargetKind() == AttributeTargetKind.PRESERVED) {
            if (!PRESERVED_FIELDS.contains(column.getPreservedColumnName())) {
                throw failure("Unsupported preserved field: " + column.getPreservedColumnName());
            }
            ObjectNode film = filmById(root, filmId);
            return film != null && FilmDraft.hasText(text(film, column.getPreservedColumnName()));
        }
        for (JsonNode definition : root.withArray("custom_field_definitions")) {
            if (column.getNormalizedName().equals(definition.path("normalized_name").asText())) {
                return customValue(root, filmId, definition.path("id").asLong()) != null;
            }
        }
        return false;
    }

    private static ObjectNode customValue(ObjectNode root, long filmId, long definitionId) {
        for (JsonNode value : root.withArray("film_custom_fields")) {
            if (filmId == value.path("film_id").asLong()
                    && definitionId == value.path("custom_field_id").asLong()) {
                return (ObjectNode) value;
            }
        }
        return null;
    }

    private static boolean mediaExists(ObjectNode root, MediaImportRow row) {
        for (JsonNode media : root.withArray("film_media_storage")) {
            if (Objects.equals(row.getFilmKey(), text(media, "film_key"))
                    && Objects.equals(row.getStorageFormat(), text(media, "storage_format"))
                    && Objects.equals(row.getMediaType(), text(media, "media_type"))
                    && Objects.equals(row.getPathHash(), text(media, "path_hash"))) {
                return true;
            }
        }
        return false;
    }

    private static ObjectNode filmById(ObjectNode root, long id) {
        for (JsonNode film : root.withArray("films")) {
            if (film.path("id").asLong() == id) { return (ObjectNode) film; }
        }
        return null;
    }

    private static FilmEntry toFilm(JsonNode film) {
        return new FilmEntry(film.path("id").asLong(), text(film, "film_key"),
                text(film, "title_original"), text(film, "title_translated"),
                integer(film, "production_year"), text(film, "production"), text(film, "color_format"),
                text(film, "romanized"), text(film, "special_aspects"));
    }

    private static Integer integer(JsonNode object, String field) {
        JsonNode value = object.get(field);
        return value == null || value.isNull() ? null : value.intValue();
    }

    private static String text(JsonNode object, String field) {
        JsonNode value = object.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    private static long takeId(ObjectNode root, String counter) throws MetadataStoreException {
        long id = root.path(counter).asLong();
        if (id <= 0 || id == Long.MAX_VALUE) { throw failure("The catalog ID limit was reached."); }
        root.put(counter, id + 1);
        return id;
    }

    private static void validate(ObjectNode root) throws IOException {
        if (!root.path("schema_version").isIntegralNumber()
                || !root.path("schema_version").canConvertToInt()
                || root.path("schema_version").intValue() != SCHEMA_VERSION) {
            throw new IOException("Unsupported or missing catalog schema version.");
        }
        try {
            UUID.fromString(requiredText(root, "catalog_id"));
        } catch (IllegalArgumentException e) {
            throw new IOException("The catalog ID must be a UUID.", e);
        }
        nonNegativeLong(root, "revision");
        Set<Long> filmIds = new HashSet<>();
        Set<String> filmKeys = new HashSet<>();
        long maxFilm = 0;
        for (JsonNode film : requiredArray(root, "films")) {
            requireObject(film);
            long id = positiveLong(film, "id");
            String key = requiredText(film, "film_key");
            if (!filmIds.add(id) || !filmKeys.add(key)) { throw new IOException("Duplicate film ID or key."); }
            maxFilm = Math.max(maxFilm, id);
            String title = requiredText(film, "title_original");
            if (!FilmKeyGenerator.normalizeTitleForMatch(title).equals(requiredText(film, "title_match_key"))) {
                throw new IOException("A title matching key is inconsistent with its film title.");
            }
            JsonNode year = film.get("production_year");
            if (year == null || (!year.isNull() && (!year.isIntegralNumber() || !year.canConvertToInt()))) {
                throw new IOException("Film production_year must be an integer or null.");
            }
            for (String field : TEXT_FILM_FIELDS) {
                JsonNode value = film.get(field);
                if (value == null || (!value.isNull() && !value.isTextual())) {
                    throw new IOException("Film field " + field + " must be text or null.");
                }
            }
        }
        requireNextId(root, "next_film_id", maxFilm);
        Set<Long> definitionIds = new HashSet<>();
        Map<Long, AttributeFieldType> valueTypes = new LinkedHashMap<>();
        Set<String> names = new HashSet<>();
        long maxDefinition = 0;
        for (JsonNode definition : requiredArray(root, "custom_field_definitions")) {
            requireObject(definition);
            long id = positiveLong(definition, "id");
            if (!definitionIds.add(id)) { throw new IOException("Duplicate custom field ID."); }
            maxDefinition = Math.max(maxDefinition, id);
            requiredText(definition, "field_name");
            // Empty normalized names are legacy-compatible, but still unique.
            JsonNode normalized = definition.get("normalized_name");
            if (normalized == null || !normalized.isTextual() || !names.add(normalized.textValue())) {
                throw new IOException("Missing or duplicate custom field normalized name.");
            }
            String type = requiredText(definition, "field_type");
            boolean known = Arrays.stream(AttributeFieldType.values())
                    .anyMatch(candidate -> candidate.getStorageName().equals(type));
            if (!known) { throw new IOException("Unknown custom field type: " + type); }
            valueTypes.put(id, AttributeFieldType.fromStorageName(type));
        }
        requireNextId(root, "next_custom_field_id", maxDefinition);
        Set<String> customPairs = new HashSet<>();
        for (JsonNode value : requiredArray(root, "film_custom_fields")) {
            requireObject(value);
            long filmId = positiveLong(value, "film_id");
            long definitionId = positiveLong(value, "custom_field_id");
            if (!filmIds.contains(filmId) || !definitionIds.contains(definitionId)
                    || !customPairs.add(filmId + ":" + definitionId) || !value.has("value_json")) {
                throw new IOException("Invalid, missing or duplicate custom field reference/value.");
            }
            validateCustomValue(value.get("value_json"), valueTypes.get(definitionId));
        }
        Set<Long> mediaIds = new HashSet<>();
        Set<String> mediaKeys = new HashSet<>();
        long maxMedia = 0;
        for (JsonNode media : requiredArray(root, "film_media_storage")) {
            requireObject(media);
            long id = positiveLong(media, "id");
            maxMedia = Math.max(maxMedia, id);
            String filmKey = requiredText(media, "film_key");
            String storage = requiredText(media, "storage_format");
            String path = requiredText(media, "path");
            String mediaType = requiredText(media, "media_type");
            String hash = requiredText(media, "path_hash");
            String extension = requiredText(media, "file_extension");
            try {
                MediaStorageFormat format = MediaStorageFormat.fromCsvValue(storage);
                if (!format.getStorageName().equals(storage)
                        || !MediaType.fromCsvValue(mediaType).getStorageName().equals(mediaType)
                        || !MediaPathUtil.normalizePathForStorage(format, path).equals(path)
                        || !MediaPathUtil.detectExtension(format, path).equals(extension)
                        || !MediaPathUtil.hashNormalizedPath(path).equals(hash)) {
                    throw new IOException("Inconsistent media path, hash, type or extension.");
                }
            } catch (IllegalArgumentException e) {
                throw new IOException("Invalid media metadata.", e);
            }
            if (!filmKeys.contains(filmKey) || !mediaIds.add(id)
                    || !mediaKeys.add(filmKey + "|" + storage + "|" + mediaType + "|" + hash)) {
                throw new IOException("Invalid or duplicate media reference.");
            }
        }
        requireNextId(root, "next_media_id", maxMedia);
    }

    private static void validateCustomValue(JsonNode value, AttributeFieldType type) throws IOException {
        if (value == null || value.isNull()) {
            throw new IOException("Custom field values must not be null.");
        }
        if (type.isVector()) {
            if (!value.isArray() || value.isEmpty()) {
                throw new IOException("A custom vector value must be a non-empty JSON array.");
            }
            AttributeFieldType scalarType = type == AttributeFieldType.INTEGER_VECTOR
                    ? AttributeFieldType.INTEGER : type == AttributeFieldType.FLOAT_VECTOR
                    ? AttributeFieldType.FLOAT : AttributeFieldType.DOUBLE;
            for (JsonNode component : value) {
                validateCustomValue(component, scalarType);
            }
            return;
        }
        boolean valid;
        switch (type) {
            case STRING:
                valid = value.isTextual();
                break;
            case INTEGER:
                valid = value.isIntegralNumber() && value.canConvertToLong();
                break;
            case BOOLEAN:
                valid = value.isBoolean();
                break;
            case FLOAT:
                valid = value.isNumber() && Float.isFinite(value.floatValue())
                        && (value.floatValue() != 0 || value.decimalValue().signum() == 0);
                break;
            case DOUBLE:
                valid = value.isNumber() && Double.isFinite(value.doubleValue())
                        && (value.doubleValue() != 0 || value.decimalValue().signum() == 0);
                break;
            default:
                valid = false;
        }
        if (!valid) {
            throw new IOException("A custom field value does not match its declared "
                    + type.getStorageName() + " type or numeric range.");
        }
    }

    private static ArrayNode requiredArray(JsonNode object, String field) throws IOException {
        JsonNode array = object.get(field);
        if (!(array instanceof ArrayNode)) { throw new IOException("Missing catalog array: " + field); }
        return (ArrayNode) array;
    }

    private static void requireObject(JsonNode node) throws IOException {
        if (!node.isObject()) { throw new IOException("Catalog records must be JSON objects."); }
    }

    private static String requiredText(JsonNode object, String field) throws IOException {
        JsonNode value = object.get(field);
        if (value == null || !value.isTextual() || value.textValue().isBlank()) {
            throw new IOException("Missing or invalid text field: " + field);
        }
        return value.textValue();
    }

    private static long nonNegativeLong(JsonNode object, String field) throws IOException {
        JsonNode value = object.get(field);
        if (value == null || !value.isIntegralNumber() || !value.canConvertToLong() || value.longValue() < 0) {
            throw new IOException("Invalid non-negative catalog number: " + field);
        }
        return value.longValue();
    }

    private static long positiveLong(JsonNode object, String field) throws IOException {
        long value = nonNegativeLong(object, field);
        if (value == 0) { throw new IOException("Catalog ID must be positive: " + field); }
        return value;
    }

    private static void requireNextId(JsonNode root, String field, long maximum) throws IOException {
        if (positiveLong(root, field) <= maximum) {
            throw new IOException("Catalog ID counter would reuse an existing ID: " + field);
        }
    }

    private static MetadataStoreException failure(String message) {
        return new MetadataStoreException(message, null);
    }
}
