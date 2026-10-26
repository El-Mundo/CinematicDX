package com.elmundo;

import java.nio.file.Path;
import java.util.Objects;
import java.util.function.Consumer;

/** Shared startup ordering for both metadata sources, without JavaFX dependencies. */
public class MetadataSetupService {
    private final MetadataStoreFactory factory;
    private final Consumer<String> startWorker;
    private final Runnable disableWorker;

    public MetadataSetupService(MetadataStoreFactory factory,
            Consumer<String> startWorker, Runnable disableWorker) {
        this.factory = Objects.requireNonNull(factory, "factory");
        this.startWorker = Objects.requireNonNull(startWorker, "startWorker");
        this.disableWorker = Objects.requireNonNull(disableWorker, "disableWorker");
    }

    public MetadataStore open(MetadataSourceType type, Path directory,
            String url, String username, String password,
            boolean enableWorker, String runtime) throws MetadataStoreException {
        MetadataStore store = factory.open(type, directory, url, username, password);
        try {
            if (enableWorker) {
                startWorker.accept(runtime);
            } else {
                disableWorker.run();
            }
            return store;
        } catch (RuntimeException e) {
            try {
                disableWorker.run();
            } catch (RuntimeException cleanupFailure) {
                if (cleanupFailure != e) {
                    e.addSuppressed(cleanupFailure);
                }
            }
            try {
                store.close();
            } catch (MetadataStoreException cleanupFailure) {
                e.addSuppressed(cleanupFailure);
            }
            throw new MetadataStoreException("Could not complete metadata setup: " + e.getMessage(), e);
        }
    }
}
