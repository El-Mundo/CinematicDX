package com.elmundo;

public enum PythonWorkerStatus {
    DISABLED("Disabled"),
    STARTING("Starting"),
    RUNNING("Running"),
    FAILED("Failed"),
    STOPPED("Stopped");

    private final String displayName;

    PythonWorkerStatus(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
