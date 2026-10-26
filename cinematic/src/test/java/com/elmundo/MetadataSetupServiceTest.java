package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Proxy;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class MetadataSetupServiceTest {
    private static final String REMEMBERED_DATABASE_URL = "jdbc:mariadb://127.0.0.1:1/unreachable";

    @TempDir
    Path directory;

    @Test
    void localSelectionNeverInvokesJdbcWithRememberedDatabaseSettings() throws Exception {
        TrackingFactory factory = new TrackingFactory();
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = service(factory, workerEvents);

        MetadataStore opened = service.open(MetadataSourceType.LOCAL_DIRECTORY, directory,
                REMEMBERED_DATABASE_URL, "remembered-user", "remembered-password", false, "python3");

        assertSame(factory.store, opened);
        assertEquals(1, factory.localOpens);
        assertEquals(0, factory.databaseOpens);
        assertSame(directory, factory.openedDirectory);
        assertEquals(List.of("disable"), workerEvents);
        assertEquals(0, factory.closes);
        opened.close();
        assertEquals(1, factory.closes);
    }

    @Test
    void failedLocalOpenDoesNotFallBackToJdbcOrHandleWorker() {
        TrackingFactory factory = new TrackingFactory();
        factory.openFailure = new MetadataStoreException("Invalid local metadata directory");
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = service(factory, workerEvents);

        MetadataStoreException failure = assertThrows(MetadataStoreException.class,
                () -> service.open(MetadataSourceType.LOCAL_DIRECTORY, directory,
                        REMEMBERED_DATABASE_URL, "remembered-user", "remembered-password", true, "python3"));

        assertSame(factory.openFailure, failure);
        assertEquals(1, factory.localOpens);
        assertEquals(0, factory.databaseOpens);
        assertTrue(workerEvents.isEmpty());
        assertEquals(0, factory.closes);
    }

    @Test
    void realLocalStoreOpensWithoutUsingRememberedUnreachableDatabase() throws Exception {
        MetadataStoreFactory factory = new MetadataStoreFactory();
        try (MetadataStore initial = factory.createLocalDirectory(directory)) {
            FilmDraft draft = new FilmDraft();
            draft.setTitleOriginal("桥");
            draft.setProductionYear(1949);
            initial.insertAsUnique(draft);
        }
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = service(factory, workerEvents);

        try (MetadataStore opened = service.open(MetadataSourceType.LOCAL_DIRECTORY, directory,
                REMEMBERED_DATABASE_URL, "remembered-user", "remembered-password", false, "python3")) {
            assertEquals("桥-1949", opened.findAll().get(0).getFilmKey());
            assertEquals(List.of("disable"), workerEvents);
        }
    }

    @Test
    void databaseSelectionUsesOnlyDatabaseSettings() throws Exception {
        TrackingFactory factory = new TrackingFactory();
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = service(factory, workerEvents);

        try (MetadataStore opened = service.open(MetadataSourceType.DATABASE, directory,
                "jdbc:test:selected", "selected-user", "selected-password", false, "python3")) {
            assertSame(factory.store, opened);
            assertEquals(1, factory.databaseOpens);
            assertEquals(0, factory.localOpens);
            assertEquals("jdbc:test:selected", factory.openedUrl);
            assertEquals("selected-user", factory.openedUsername);
            assertEquals("selected-password", factory.openedPassword);
            assertEquals(List.of("disable"), workerEvents);
        }
    }

    @ParameterizedTest
    @EnumSource(MetadataSourceType.class)
    void enabledWorkerStartsOnceAfterSelectedMetadataStoreOpens(MetadataSourceType type) throws Exception {
        TrackingFactory factory = new TrackingFactory();
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = new MetadataSetupService(factory, runtime -> {
            assertEquals(1, factory.localOpens + factory.databaseOpens);
            workerEvents.add("start:" + runtime);
        }, () -> workerEvents.add("disable"));

        try (MetadataStore opened = service.open(type, directory,
                REMEMBERED_DATABASE_URL, "user", "password", true, "/chosen/python")) {
            assertSame(factory.store, opened);
            assertEquals(List.of("start:/chosen/python"), workerEvents);
            assertEquals(0, factory.closes);
        }
    }

    @ParameterizedTest
    @EnumSource(MetadataSourceType.class)
    void disabledWorkerUsesTheSameDisableRouteForBothSources(MetadataSourceType type) throws Exception {
        TrackingFactory factory = new TrackingFactory();
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = service(factory, workerEvents);

        try (MetadataStore opened = service.open(type, directory,
                REMEMBERED_DATABASE_URL, "user", "password", false, "/chosen/python")) {
            assertSame(factory.store, opened);
            assertEquals(List.of("disable"), workerEvents);
        }
    }

    @ParameterizedTest
    @EnumSource(MetadataSourceType.class)
    void metadataOpenFailureDoesNotStartOrDisableWorker(MetadataSourceType type) {
        TrackingFactory factory = new TrackingFactory();
        factory.openFailure = new MetadataStoreException("Selected metadata source cannot be opened");
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = service(factory, workerEvents);

        assertSame(factory.openFailure, assertThrows(MetadataStoreException.class,
                () -> service.open(type, directory, REMEMBERED_DATABASE_URL,
                        "user", "password", true, "python3")));
        assertTrue(workerEvents.isEmpty());
        assertEquals(0, factory.closes);
    }

    @ParameterizedTest
    @EnumSource(MetadataSourceType.class)
    void workerStartFailureDisablesWorkerAndClosesSelectedStore(MetadataSourceType type) {
        TrackingFactory factory = new TrackingFactory();
        RuntimeException startupFailure = new IllegalStateException("Worker startup failed");
        List<String> workerEvents = new ArrayList<>();
        MetadataSetupService service = new MetadataSetupService(factory, runtime -> {
            workerEvents.add("start:" + runtime);
            throw startupFailure;
        }, () -> workerEvents.add("disable"));

        MetadataStoreException failure = assertThrows(MetadataStoreException.class,
                () -> service.open(type, directory, REMEMBERED_DATABASE_URL,
                        "user", "password", true, "python3"));

        assertSame(startupFailure, failure.getCause());
        assertEquals(List.of("start:python3", "disable"), workerEvents);
        assertEquals(1, factory.closes);
    }

    @Test
    void workerCleanupFailureStillClosesStoreAndPreservesOriginalFailure() {
        TrackingFactory factory = new TrackingFactory();
        RuntimeException startupFailure = new IllegalStateException("Worker startup failed");
        RuntimeException cleanupFailure = new IllegalStateException("Worker cleanup failed");
        factory.closeFailure = new MetadataStoreException("Metadata close failed");
        MetadataSetupService service = new MetadataSetupService(factory, runtime -> {
            throw startupFailure;
        }, () -> {
            throw cleanupFailure;
        });

        MetadataStoreException failure = assertThrows(MetadataStoreException.class,
                () -> service.open(MetadataSourceType.LOCAL_DIRECTORY, directory,
                        REMEMBERED_DATABASE_URL, "user", "password", true, "python3"));

        assertSame(startupFailure, failure.getCause());
        assertEquals(1, factory.closes);
        assertEquals(2, startupFailure.getSuppressed().length);
        assertSame(cleanupFailure, startupFailure.getSuppressed()[0]);
        assertSame(factory.closeFailure, startupFailure.getSuppressed()[1]);
    }

    @ParameterizedTest
    @EnumSource(MetadataSourceType.class)
    void workerDisableFailureClosesSelectedStore(MetadataSourceType type) {
        TrackingFactory factory = new TrackingFactory();
        RuntimeException disableFailure = new IllegalStateException("Worker disable failed");
        MetadataSetupService service = new MetadataSetupService(factory, runtime -> {
            throw new AssertionError("Disabled worker must not start");
        }, () -> {
            throw disableFailure;
        });

        MetadataStoreException failure = assertThrows(MetadataStoreException.class,
                () -> service.open(type, directory, REMEMBERED_DATABASE_URL,
                        "user", "password", false, "python3"));

        assertSame(disableFailure, failure.getCause());
        assertEquals(1, factory.closes);
    }

    @Test
    void missingSourceSelectionDoesNotOpenAnySourceOrHandleWorker() {
        TrackingFactory factory = new TrackingFactory();
        List<String> workerEvents = new ArrayList<>();

        assertThrows(MetadataStoreException.class,
                () -> service(factory, workerEvents).open(null, directory,
                        REMEMBERED_DATABASE_URL, "user", "password", false, "python3"));
        assertEquals(0, factory.databaseOpens + factory.localOpens);
        assertEquals(0, factory.closes);
        assertTrue(workerEvents.isEmpty());
    }

    private MetadataSetupService service(MetadataStoreFactory factory, List<String> workerEvents) {
        return new MetadataSetupService(factory, runtime -> workerEvents.add("start:" + runtime),
                () -> workerEvents.add("disable"));
    }

    /** Uses no JDBC connection or process; unexpected store operations fail immediately. */
    private static class TrackingFactory extends MetadataStoreFactory {
        int localOpens;
        int databaseOpens;
        int closes;
        Path openedDirectory;
        String openedUrl;
        String openedUsername;
        String openedPassword;
        MetadataStoreException openFailure;
        MetadataStoreException closeFailure;
        final MetadataStore store = (MetadataStore) Proxy.newProxyInstance(
                MetadataStore.class.getClassLoader(), new Class<?>[] {MetadataStore.class},
                (proxy, method, arguments) -> {
                    if (method.getName().equals("close")) {
                        closes++;
                        if (closeFailure != null) {
                            throw closeFailure;
                        }
                        return null;
                    }
                    if (method.getName().equals("getDescription")) {
                        return "Test metadata source";
                    }
                    throw new AssertionError("Unexpected store operation: " + method.getName());
                });

        @Override
        public MetadataStore openLocalDirectory(Path selectedDirectory) throws MetadataStoreException {
            localOpens++;
            openedDirectory = selectedDirectory;
            return selectedStore();
        }

        @Override
        public MetadataStore openDatabase(String url, String username, String password) throws MetadataStoreException {
            databaseOpens++;
            openedUrl = url;
            openedUsername = username;
            openedPassword = password;
            return selectedStore();
        }

        private MetadataStore selectedStore() throws MetadataStoreException {
            if (openFailure != null) {
                throw openFailure;
            }
            return store;
        }
    }
}
