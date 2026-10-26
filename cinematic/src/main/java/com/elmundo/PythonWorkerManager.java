package com.elmundo;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import javafx.application.Platform;
import javafx.beans.property.ReadOnlyObjectProperty;
import javafx.beans.property.SimpleObjectProperty;

public class PythonWorkerManager {
    private static final String DEFAULT_WORKER_SCRIPT = "analysis-python/worker.py";

    @FunctionalInterface
    interface ProcessStarter {
        Process start(ProcessBuilder builder) throws IOException;
    }

    private final String workerScript;
    private final ProcessStarter processStarter;
    private final SimpleObjectProperty<PythonWorkerStatus> status =
            new SimpleObjectProperty<>(PythonWorkerStatus.DISABLED);

    private volatile PythonWorkerStatus currentStatus = PythonWorkerStatus.DISABLED;
    private volatile Process process;
    private volatile String lastMessage = "";
    private long generation;

    public PythonWorkerManager() {
        this(DEFAULT_WORKER_SCRIPT);
    }

    public PythonWorkerManager(String workerScript) {
        this(workerScript, ProcessBuilder::start);
    }

    PythonWorkerManager(String workerScript, ProcessStarter processStarter) {
        this.workerScript = workerScript;
        this.processStarter = Objects.requireNonNull(processStarter, "processStarter");
    }

    public synchronized void startWorker(String pythonRuntimePath) {
        if (currentStatus == PythonWorkerStatus.STARTING || isRunning()) {
            return;
        }

        long workerGeneration = ++generation;
        process = null;
        Path pythonRuntime = validatePythonRuntimePath(pythonRuntimePath, workerGeneration);
        if (pythonRuntime == null) {
            return;
        }

        lastMessage = "";
        setStatus(workerGeneration, PythonWorkerStatus.STARTING);

        Thread starter = new Thread(() -> startWorkerInBackground(pythonRuntime, workerGeneration),
                "python-worker-starter");
        starter.setDaemon(true);
        starter.start();
    }

    public void stopWorker() {
        Process runningProcess;
        synchronized (this) {
            long stopGeneration = ++generation;
            runningProcess = process;
            process = null;
            setStatus(stopGeneration, currentStatus == PythonWorkerStatus.DISABLED
                    ? PythonWorkerStatus.DISABLED : PythonWorkerStatus.STOPPED);
        }
        stopProcess(runningProcess);
    }

    public void disable() {
        Process runningProcess;
        synchronized (this) {
            long disabledGeneration = ++generation;
            runningProcess = process;
            process = null;
            lastMessage = "";
            setStatus(disabledGeneration, PythonWorkerStatus.DISABLED);
        }
        stopProcess(runningProcess);
    }

    private static void stopProcess(Process runningProcess) {
        if (runningProcess == null) {
            return;
        }
        runningProcess.destroy();
        try {
            if (!runningProcess.waitFor(2, TimeUnit.SECONDS)) {
                runningProcess.destroyForcibly();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            runningProcess.destroyForcibly();
        }
    }

    public boolean isRunning() {
        Process runningProcess = process;
        return runningProcess != null && runningProcess.isAlive();
    }

    public PythonWorkerStatus getStatus() {
        return currentStatus;
    }

    public String getLastMessage() {
        return lastMessage;
    }

    public ReadOnlyObjectProperty<PythonWorkerStatus> statusProperty() {
        return status;
    }

    private synchronized boolean isCurrent(long workerGeneration) {
        return generation == workerGeneration;
    }

    private void startWorkerInBackground(Path pythonRuntime, long workerGeneration) {
        if (!isCurrent(workerGeneration)) {
            return;
        }
        Path scriptPath = resolveWorkerScriptPath();
        if (!Files.exists(scriptPath)) {
            fail(workerGeneration, "Python worker script not found: " + scriptPath);
            return;
        }

        try {
            startProcess(pythonRuntime, scriptPath, workerGeneration);
        } catch (IOException | RuntimeException e) {
            fail(workerGeneration, "Python worker failed to start with runtime '" + pythonRuntime
                    + "'. Set a valid absolute Python path on the login screen.", e);
        }
    }

    private void startProcess(Path pythonRuntime, Path scriptPath, long workerGeneration) throws IOException {
        ProcessBuilder processBuilder = new ProcessBuilder(
                pythonRuntime.toString(),
                scriptPath.toString());
        Path scriptDirectory = scriptPath.getParent();
        if (scriptDirectory != null) {
            processBuilder.directory(scriptDirectory.toFile());
        }
        if (!isCurrent(workerGeneration)) {
            return;
        }

        Process startedProcess = processStarter.start(processBuilder);
        synchronized (this) {
            if (generation == workerGeneration) {
                process = startedProcess;
                startStreamLogger(startedProcess.getInputStream(), "stdout", workerGeneration);
                startStreamLogger(startedProcess.getErrorStream(), "stderr", workerGeneration);
                setStatus(workerGeneration, PythonWorkerStatus.RUNNING);
                startExitWatcher(startedProcess, workerGeneration);
                return;
            }
        }
        // Cancellation can happen while the operating system is starting the process.
        stopProcess(startedProcess);
    }

    private Path resolveWorkerScriptPath() {
        Path configuredPath = Path.of(workerScript);
        if (configuredPath.isAbsolute()) {
            return configuredPath.normalize();
        }

        Path workingDirectory = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        List<Path> candidates = List.of(
            workingDirectory.resolve(configuredPath).normalize(),
            workingDirectory.resolve("..").resolve(configuredPath).normalize()
        );

        return candidates.stream().filter(Files::exists).findFirst().orElse(candidates.get(0));
    }

    private Path validatePythonRuntimePath(String pythonRuntimePath, long workerGeneration) {
        if (pythonRuntimePath == null || pythonRuntimePath.isBlank()) {
            fail(workerGeneration, "Python worker failed: set a Python absolute path on the login screen before enabling Python ML worker.");
            return null;
        }

        Path runtime = Path.of(pythonRuntimePath.trim()).normalize();
        if (!runtime.isAbsolute() || !Files.exists(runtime) || Files.isDirectory(runtime)) {
            fail(workerGeneration, "Python worker failed: '" + pythonRuntimePath
                    + "' is not a valid Python executable. Set a Python absolute path on the login screen.");
            return null;
        }

        return runtime;
    }

    private void startStreamLogger(InputStream stream, String streamName, long workerGeneration) {
        Thread logger = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (!isCurrent(workerGeneration)) {
                        return;
                    }
                    if ("stderr".equals(streamName)) {
                        System.err.println("[python-worker " + streamName + "] " + line);
                    } else {
                        System.out.println("[python-worker " + streamName + "] " + line);
                    }
                }
            } catch (IOException e) {
                if (isCurrent(workerGeneration)) {
                    System.err.println("[python-worker " + streamName + "] log reader failed: "
                            + e.getMessage());
                }
            }
        }, "python-worker-" + streamName + "-logger");
        logger.setDaemon(true);
        logger.start();
    }

    private void startExitWatcher(Process watchedProcess, long workerGeneration) {
        Thread watcher = new Thread(() -> {
            try {
                int exitCode = watchedProcess.waitFor();
                synchronized (this) {
                    if (generation != workerGeneration || process != watchedProcess) {
                        return;
                    }
                    process = null;
                    if (exitCode == 0) {
                        setStatus(workerGeneration, PythonWorkerStatus.STOPPED);
                    } else {
                        fail(workerGeneration, "Python worker exited with code " + exitCode + ".");
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                fail(workerGeneration, "Python worker exit watcher was interrupted.", e);
            }
        }, "python-worker-exit-watcher");
        watcher.setDaemon(true);
        watcher.start();
    }

    private void fail(long workerGeneration, String message) {
        Process failedProcess;
        synchronized (this) {
            if (generation != workerGeneration) {
                return;
            }
            failedProcess = process;
            process = null;
            lastMessage = message;
            System.err.println("[python-worker] " + message);
            setStatus(workerGeneration, PythonWorkerStatus.FAILED);
        }
        stopProcess(failedProcess);
    }

    private void fail(long workerGeneration, String message, Exception exception) {
        fail(workerGeneration, message + " " + exception.getMessage());
    }

    private synchronized void setStatus(long workerGeneration, PythonWorkerStatus nextStatus) {
        if (generation != workerGeneration) {
            return;
        }
        currentStatus = nextStatus;

        Runnable update = () -> {
            synchronized (PythonWorkerManager.this) {
                if (generation == workerGeneration && currentStatus == nextStatus) {
                    status.set(nextStatus);
                }
            }
        };
        try {
            // Do not query the toolkit before it exists: some JavaFX versions
            // initialise native graphics just to answer isFxApplicationThread().
            Platform.runLater(update);
        } catch (IllegalStateException e) {
            // No toolkit yet, or it is shutting down; volatile status is current.
        }
    }
}
