package com.elmundo;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;

import javafx.application.Platform;
import javafx.beans.property.ReadOnlyObjectProperty;
import javafx.beans.property.SimpleObjectProperty;

public class PythonWorkerManager {
    private static final String DEFAULT_WORKER_SCRIPT = "analysis-python/worker.py";

    private final String workerScript;
    private final SimpleObjectProperty<PythonWorkerStatus> status =
            new SimpleObjectProperty<>(PythonWorkerStatus.DISABLED);

    private volatile PythonWorkerStatus currentStatus = PythonWorkerStatus.DISABLED;
    private volatile Process process;
    private volatile boolean stopRequested;
    private volatile String lastMessage = "";

    public PythonWorkerManager() {
        this(DEFAULT_WORKER_SCRIPT);
    }

    public PythonWorkerManager(String workerScript) {
        this.workerScript = workerScript;
    }

    public synchronized void startWorker(String pythonRuntimePath) {
        if (currentStatus == PythonWorkerStatus.STARTING || isRunning()) {
            return;
        }

        Path pythonRuntime = validatePythonRuntimePath(pythonRuntimePath);
        if (pythonRuntime == null) {
            return;
        }

        stopRequested = false;
        lastMessage = "";
        setStatus(PythonWorkerStatus.STARTING);

        Thread starter = new Thread(() -> startWorkerInBackground(pythonRuntime),
                "python-worker-starter");
        starter.setDaemon(true);
        starter.start();
    }

    public void stopWorker() {
        Process runningProcess = process;
        stopRequested = true;

        if (runningProcess == null) {
            if (currentStatus != PythonWorkerStatus.DISABLED) {
                setStatus(PythonWorkerStatus.STOPPED);
            }
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

    public synchronized void disable() {
        if (isRunning()) {
            stopWorker();
        }
        stopRequested = false;
        lastMessage = "";
        setStatus(PythonWorkerStatus.DISABLED);
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

    private void startWorkerInBackground(Path pythonRuntime) {
        Path scriptPath = resolveWorkerScriptPath();
        if (!Files.exists(scriptPath)) {
            fail("Python worker script not found: " + scriptPath);
            return;
        }

        try {
            startProcess(pythonRuntime, scriptPath);
        } catch (IOException e) {
            fail("Python worker failed to start with runtime '" + pythonRuntime
                    + "'. Set a valid absolute Python path on the login screen.", e);
        }
    }

    private void startProcess(Path pythonRuntime, Path scriptPath) throws IOException {
        ProcessBuilder processBuilder = new ProcessBuilder(
                pythonRuntime.toString(),
                scriptPath.toString());
        Path scriptDirectory = scriptPath.getParent();
        if (scriptDirectory != null) {
            processBuilder.directory(scriptDirectory.toFile());
        }

        Process startedProcess = processBuilder.start();
        process = startedProcess;
        startStreamLogger(startedProcess.getInputStream(), "stdout");
        startStreamLogger(startedProcess.getErrorStream(), "stderr");

        if (stopRequested) {
            startedProcess.destroy();
            setStatus(PythonWorkerStatus.STOPPED);
            return;
        }

        setStatus(PythonWorkerStatus.RUNNING);
        startExitWatcher(startedProcess);
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

    private Path validatePythonRuntimePath(String pythonRuntimePath) {
        if (pythonRuntimePath == null || pythonRuntimePath.isBlank()) {
            fail("Python worker failed: set a Python absolute path on the login screen before enabling Python ML worker.");
            return null;
        }

        Path runtime = Path.of(pythonRuntimePath.trim()).normalize();
        if (!runtime.isAbsolute() || !Files.exists(runtime) || Files.isDirectory(runtime)) {
            fail("Python worker failed: '" + pythonRuntimePath
                    + "' is not a valid Python executable. Set a Python absolute path on the login screen.");
            return null;
        }

        return runtime;
    }

    private void startStreamLogger(InputStream stream, String streamName) {
        Thread logger = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if ("stderr".equals(streamName)) {
                        System.err.println("[python-worker " + streamName + "] " + line);
                    } else {
                        System.out.println("[python-worker " + streamName + "] " + line);
                    }
                }
            } catch (IOException e) {
                if (!stopRequested) {
                    System.err.println("[python-worker " + streamName + "] log reader failed: "
                            + e.getMessage());
                }
            }
        }, "python-worker-" + streamName + "-logger");
        logger.setDaemon(true);
        logger.start();
    }

    private void startExitWatcher(Process watchedProcess) {
        Thread watcher = new Thread(() -> {
            try {
                int exitCode = watchedProcess.waitFor();
                if (process == watchedProcess) {
                    process = null;
                }

                if (stopRequested || exitCode == 0) {
                    setStatus(PythonWorkerStatus.STOPPED);
                } else {
                    fail("Python worker exited with code " + exitCode + ".");
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                fail("Python worker exit watcher was interrupted.", e);
            }
        }, "python-worker-exit-watcher");
        watcher.setDaemon(true);
        watcher.start();
    }

    private void fail(String message) {
        lastMessage = message;
        System.err.println("[python-worker] " + message);
        process = null;
        setStatus(PythonWorkerStatus.FAILED);
    }

    private void fail(String message, Exception exception) {
        lastMessage = message + " " + exception.getMessage();
        System.err.println("[python-worker] " + lastMessage);
        process = null;
        setStatus(PythonWorkerStatus.FAILED);
    }

    private void setStatus(PythonWorkerStatus nextStatus) {
        currentStatus = nextStatus;

        Runnable update = () -> status.set(nextStatus);
        if (Platform.isFxApplicationThread()) {
            update.run();
            return;
        }

        try {
            Platform.runLater(update);
        } catch (IllegalStateException e) {
            // JavaFX is already shutting down; keep the volatile status updated.
        }
    }

}
