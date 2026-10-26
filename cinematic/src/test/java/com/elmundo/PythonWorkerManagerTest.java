package com.elmundo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class PythonWorkerManagerTest {
    @TempDir
    Path tempDir;

    @Test
    void disableCancelsPendingStartupAndDestroysALateProcess() throws Exception {
        FakeProcess process = new FakeProcess(true);
        PendingStart pending = new PendingStart(process, null);
        PythonWorkerManager manager = manager(pending);
        try {
            manager.startWorker(runtime());
            pending.awaitStarted();

            manager.disable();
            pending.releaseAndJoin();

            assertTrue(process.destroyed);
            assertFalse(process.isAlive());
            assertFalse(manager.isRunning());
            assertEquals(PythonWorkerStatus.DISABLED, manager.getStatus());
        } finally {
            pending.releaseAndJoin();
            manager.disable();
        }
    }

    @Test
    void stopCancelsPendingStartupAndKeepsStoppedStatus() throws Exception {
        FakeProcess process = new FakeProcess(true);
        PendingStart pending = new PendingStart(process, null);
        PythonWorkerManager manager = manager(pending);
        try {
            manager.startWorker(runtime());
            pending.awaitStarted();

            manager.stopWorker();
            pending.releaseAndJoin();

            assertTrue(process.destroyed);
            assertFalse(manager.isRunning());
            assertEquals(PythonWorkerStatus.STOPPED, manager.getStatus());
        } finally {
            pending.releaseAndJoin();
            manager.disable();
        }
    }

    @Test
    void obsoleteStartupFailureCannotOverwriteANewerWorker() throws Exception {
        PendingStart pending = new PendingStart(null, new IOException("obsolete startup failure"));
        FakeProcess replacement = new FakeProcess(true);
        AtomicInteger launches = new AtomicInteger();
        PythonWorkerManager manager = manager(builder ->
                launches.getAndIncrement() == 0 ? pending.start(builder) : replacement);
        try {
            manager.startWorker(runtime());
            pending.awaitStarted();
            manager.disable();
            manager.startWorker(runtime());
            replacement.awaitWatcher();

            pending.releaseAndJoin();

            assertTrue(manager.isRunning());
            assertEquals(PythonWorkerStatus.RUNNING, manager.getStatus());
            assertEquals("", manager.getLastMessage());
        } finally {
            pending.releaseAndJoin();
            manager.disable();
            replacement.finishAndJoin(0);
        }
    }

    @Test
    void obsoleteExitWatcherCannotClearOrFailANewerWorker() throws Exception {
        FakeProcess original = new FakeProcess(false);
        FakeProcess replacement = new FakeProcess(true);
        AtomicInteger launches = new AtomicInteger();
        PythonWorkerManager manager = manager(builder ->
                launches.getAndIncrement() == 0 ? original : replacement);
        try {
            manager.startWorker(runtime());
            original.awaitWatcher();
            manager.stopWorker();
            manager.startWorker(runtime());
            replacement.awaitWatcher();

            original.finishAndJoin(19);

            assertTrue(manager.isRunning());
            assertEquals(PythonWorkerStatus.RUNNING, manager.getStatus());
            assertEquals("", manager.getLastMessage());
        } finally {
            manager.disable();
            original.finishAndJoin(0);
            replacement.finishAndJoin(0);
        }
    }

    @ParameterizedTest
    @ValueSource(ints = {0, 7})
    void currentWorkerExitStillReportsItsResult(int exitCode) throws Exception {
        FakeProcess process = new FakeProcess(true);
        PythonWorkerManager manager = manager(builder -> process);
        try {
            manager.startWorker(runtime());
            process.awaitWatcher();

            process.finishAndJoin(exitCode);

            assertFalse(manager.isRunning());
            assertEquals(exitCode == 0 ? PythonWorkerStatus.STOPPED : PythonWorkerStatus.FAILED,
                    manager.getStatus());
            assertEquals(exitCode == 0 ? "" : "Python worker exited with code 7.",
                    manager.getLastMessage());
        } finally {
            manager.disable();
            process.finishAndJoin(0);
        }
    }

    private PythonWorkerManager manager(PythonWorkerManager.ProcessStarter starter) throws IOException {
        Path script = tempDir.resolve("worker.py");
        Files.writeString(script, "# never executed\n");
        Files.writeString(tempDir.resolve("python"), "not an executable\n");
        return new PythonWorkerManager(script.toString(), starter);
    }

    private String runtime() {
        return tempDir.resolve("python").toString();
    }

    private static void join(Thread thread) throws InterruptedException {
        if (thread != null) {
            thread.join(3000);
            assertFalse(thread.isAlive(), "Worker supervision thread did not finish");
        }
    }

    private static final class PendingStart implements PythonWorkerManager.ProcessStarter {
        private final CountDownLatch started = new CountDownLatch(1);
        private final CountDownLatch released = new CountDownLatch(1);
        private final Process result;
        private final IOException failure;
        private volatile Thread starterThread;

        private PendingStart(Process result, IOException failure) {
            this.result = result;
            this.failure = failure;
        }

        @Override
        public Process start(ProcessBuilder builder) throws IOException {
            starterThread = Thread.currentThread();
            started.countDown();
            try {
                if (!released.await(5, TimeUnit.SECONDS)) {
                    throw new IOException("Test process start was not released");
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IOException(e);
            }
            if (failure != null) {
                throw failure;
            }
            return result;
        }

        private void awaitStarted() throws InterruptedException {
            assertTrue(started.await(3, TimeUnit.SECONDS), "Process start was not reached");
        }

        private void releaseAndJoin() throws InterruptedException {
            released.countDown();
            join(starterThread);
        }
    }

    private static final class FakeProcess extends Process {
        private final boolean releaseOnDestroy;
        private final CountDownLatch watcherStarted = new CountDownLatch(1);
        private final CountDownLatch exitReleased = new CountDownLatch(1);
        private volatile Thread watcher;
        private volatile boolean alive = true;
        private volatile boolean destroyed;
        private volatile int exitCode;

        private FakeProcess(boolean releaseOnDestroy) {
            this.releaseOnDestroy = releaseOnDestroy;
        }

        @Override public OutputStream getOutputStream() { return new ByteArrayOutputStream(); }
        @Override public InputStream getInputStream() { return new ByteArrayInputStream(new byte[0]); }
        @Override public InputStream getErrorStream() { return new ByteArrayInputStream(new byte[0]); }

        @Override
        public int waitFor() throws InterruptedException {
            watcher = Thread.currentThread();
            watcherStarted.countDown();
            exitReleased.await();
            return exitCode;
        }

        @Override public boolean waitFor(long timeout, TimeUnit unit) { return !alive; }

        @Override
        public int exitValue() {
            if (alive) {
                throw new IllegalThreadStateException("Still running");
            }
            return exitCode;
        }

        @Override
        public void destroy() {
            destroyed = true;
            alive = false;
            if (releaseOnDestroy) {
                exitReleased.countDown();
            }
        }

        @Override public Process destroyForcibly() { destroy(); return this; }
        @Override public boolean isAlive() { return alive; }

        private void awaitWatcher() throws InterruptedException {
            assertTrue(watcherStarted.await(3, TimeUnit.SECONDS), "Exit watcher was not started");
        }

        private void finishAndJoin(int code) throws InterruptedException {
            exitCode = code;
            alive = false;
            exitReleased.countDown();
            join(watcher);
        }
    }
}
