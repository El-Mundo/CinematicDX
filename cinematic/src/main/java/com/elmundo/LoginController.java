package com.elmundo;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.control.CheckBox;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.PasswordField;
import javafx.scene.control.RadioButton;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleGroup;
import javafx.scene.layout.VBox;
import javafx.stage.DirectoryChooser;
import javafx.stage.FileChooser;

public class LoginController {
    @FXML private RadioButton databaseSourceRadio;
    @FXML private RadioButton localDirectorySourceRadio;
    @FXML private VBox databaseSettings;
    @FXML private VBox localDirectorySettings;
    @FXML private TextField localDirectoryField;
    @FXML private TextField urlField;
    @FXML private TextField usernameField;
    @FXML private PasswordField passwordField;
    @FXML private CheckBox enablePythonWorkerCheckBox;
    @FXML private TextField pythonRuntimeField;
    @FXML private CheckBox saveUrlCheckBox;
    @FXML private CheckBox saveUsernameCheckBox;
    @FXML private CheckBox savePasswordCheckBox;
    @FXML private Label statusLabel;
    @FXML private VBox localSourceCard;
    @FXML private VBox databaseSourceCard;
    @FXML private VBox sourceSelectionHint;
    @FXML private Button openWorkspaceButton;

    private final MetadataStoreFactory storeFactory = new MetadataStoreFactory();

    @FXML
    private void initialize() {
        statusLabel.managedProperty().bind(statusLabel.textProperty().isNotEmpty());
        statusLabel.visibleProperty().bind(statusLabel.managedProperty());
        statusLabel.textProperty().addListener((observable, previous, message) -> {
            statusLabel.getStyleClass().remove("error");
            if (message.startsWith("Could not") || message.startsWith("Choose ")) {
                statusLabel.getStyleClass().add("error");
            }
        });
        ToggleGroup sourceChoices = new ToggleGroup();
        databaseSourceRadio.setToggleGroup(sourceChoices);
        localDirectorySourceRadio.setToggleGroup(sourceChoices);
        sourceChoices.selectedToggleProperty().addListener(
                (observable, previous, selected) -> updateSourceControls());

        AppConfig config = App.getConfig();
        pythonRuntimeField.setText(config.getPythonRuntimePath());
        localDirectoryField.setText(config.getLocalDirectoryPath());
        saveUrlCheckBox.setSelected(config.shouldSaveUrl());
        saveUsernameCheckBox.setSelected(config.shouldSaveUsername());
        savePasswordCheckBox.setSelected(config.shouldSavePassword());
        if (config.shouldSaveUrl()) {
            urlField.setText(config.getSavedUrl());
        }
        if (config.shouldSaveUsername()) {
            usernameField.setText(config.getSavedUsername());
        }
        if (config.shouldSavePassword()) {
            passwordField.setText(config.getSavedPassword());
        }
        if (config.getMetadataSourceType() == MetadataSourceType.DATABASE) {
            databaseSourceRadio.setSelected(true);
        } else if (config.getMetadataSourceType() == MetadataSourceType.LOCAL_DIRECTORY) {
            localDirectorySourceRadio.setSelected(true);
        }
        updateSourceControls();
    }

    private void updateSourceControls() {
        setSelectedCard(databaseSourceCard, databaseSourceRadio.isSelected());
        setSelectedCard(localSourceCard, localDirectorySourceRadio.isSelected());
        boolean selected = selectedSourceType() != null;
        openWorkspaceButton.setDisable(!selected);
        sourceSelectionHint.setVisible(!selected);
        sourceSelectionHint.setManaged(!selected);
        databaseSettings.setDisable(!databaseSourceRadio.isSelected());
        databaseSettings.setVisible(databaseSourceRadio.isSelected());
        databaseSettings.setManaged(databaseSourceRadio.isSelected());
        localDirectorySettings.setDisable(!localDirectorySourceRadio.isSelected());
        localDirectorySettings.setVisible(localDirectorySourceRadio.isSelected());
        localDirectorySettings.setManaged(localDirectorySourceRadio.isSelected());
    }

    private void setSelectedCard(VBox card, boolean selected) {
        card.getStyleClass().remove("selected");
        if (selected) {
            card.getStyleClass().add("selected");
        }
    }

    @FXML
    private void selectLocalSource() {
        localDirectorySourceRadio.setSelected(true);
    }

    @FXML
    private void selectDatabaseSource() {
        databaseSourceRadio.setSelected(true);
    }

    @FXML
    private void openCinematicDx() {
        MetadataSourceType type = selectedSourceType();
        if (type == null) {
            statusLabel.setText("Choose Database or Local directory before opening CinematicDX.");
            return;
        }

        MetadataStore candidate = null;
        boolean installed = false;
        try {
            Path directory = type == MetadataSourceType.LOCAL_DIRECTORY ? localDirectoryPath() : null;
            PythonWorkerManager worker = App.getPythonWorkerManager();
            MetadataSetupService setup = new MetadataSetupService(
                    storeFactory, worker::startWorker, worker::disable);
            candidate = setup.open(type, directory,
                    urlField.getText().trim(), usernameField.getText().trim(), passwordField.getText(),
                    enablePythonWorkerCheckBox.isSelected(), pythonRuntimeField.getText().trim());
            saveConfig(type, directory);
            App.setMetadataStore(candidate);
            candidate = null;
            installed = true;
            App.setRoot("primary");
        } catch (MetadataStoreException | IOException | RuntimeException e) {
            cleanupFailedOpen(candidate, installed, e);
            statusLabel.setText("Could not open CinematicDX: " + e.getMessage());
        }
    }

    private MetadataSourceType selectedSourceType() {
        if (databaseSourceRadio.isSelected()) {
            return MetadataSourceType.DATABASE;
        }
        if (localDirectorySourceRadio.isSelected()) {
            return MetadataSourceType.LOCAL_DIRECTORY;
        }
        return null;
    }

    private Path localDirectoryPath() {
        String value = localDirectoryField.getText().trim();
        if (value.isEmpty()) {
            throw new IllegalArgumentException("Choose a metadata directory.");
        }
        return Path.of(value).toAbsolutePath().normalize();
    }

    private void cleanupFailedOpen(MetadataStore candidate, boolean installed, Exception failure) {
        try {
            App.getPythonWorkerManager().disable();
        } catch (RuntimeException cleanupFailure) {
            failure.addSuppressed(cleanupFailure);
        }
        try {
            if (installed) {
                App.closeMetadataStore();
            } else if (candidate != null) {
                candidate.close();
            }
        } catch (MetadataStoreException | RuntimeException cleanupFailure) {
            failure.addSuppressed(cleanupFailure);
            System.err.println("Could not close metadata source after setup failed: "
                    + cleanupFailure.getMessage());
        }
    }

    @FXML
    private void chooseLocalDirectory() {
        DirectoryChooser chooser = new DirectoryChooser();
        chooser.setTitle("Choose Metadata Directory");
        String value = localDirectoryField.getText().trim();
        if (!value.isEmpty()) {
            try {
                Path current = Path.of(value).toAbsolutePath().normalize();
                if (Files.isDirectory(current)) {
                    chooser.setInitialDirectory(current.toFile());
                }
            } catch (IllegalArgumentException e) {
                // A replacement can still be selected when the typed path is invalid.
            }
        }
        File selected = chooser.showDialog(localDirectoryField.getScene().getWindow());
        if (selected != null) {
            localDirectoryField.setText(selected.toPath().toAbsolutePath().normalize().toString());
        }
    }

    @FXML
    private void createLocalDirectory() {
        try {
            Path directory = localDirectoryPath();
            try (MetadataStore created = storeFactory.createLocalDirectory(directory)) {
                localDirectoryField.setText(directory.toString());
            }
            statusLabel.setText("Local catalog created. Open CinematicDX to use it.");
        } catch (MetadataStoreException | IllegalArgumentException e) {
            statusLabel.setText("Could not create local catalog: " + e.getMessage());
        }
    }

    @FXML
    private void exit() {
        Platform.exit();
    }

    @FXML
    private void choosePythonRuntime() {
        FileChooser chooser = new FileChooser();
        chooser.setTitle("Select Python Runtime");
        String currentPath = pythonRuntimeField.getText().trim();
        if (!currentPath.isEmpty()) {
            try {
                Path parent = Path.of(currentPath).toAbsolutePath().normalize().getParent();
                if (parent != null && Files.isDirectory(parent)) {
                    chooser.setInitialDirectory(parent.toFile());
                }
            } catch (IllegalArgumentException e) {
                // A replacement can still be selected when the typed path is invalid.
            }
        }
        File selected = chooser.showOpenDialog(pythonRuntimeField.getScene().getWindow());
        if (selected == null) {
            return;
        }
        String selectedPath = selected.toPath().toAbsolutePath().normalize().toString();
        pythonRuntimeField.setText(selectedPath);
        AppConfig config = App.getConfig();
        config.setPythonRuntimePath(selectedPath);
        try {
            config.save();
            statusLabel.setText("Saved Python runtime path.");
        } catch (IOException e) {
            statusLabel.setText("Could not save Python runtime path: " + e.getMessage());
        }
    }

    private void saveConfig(MetadataSourceType type, Path directory) throws IOException {
        AppConfig config = App.getConfig();
        config.setPythonRuntimePath(pythonRuntimeField.getText().trim());
        config.updateMetadataSourceSettings(type,
                directory == null ? config.getLocalDirectoryPath() : directory.toString());
        if (type == MetadataSourceType.DATABASE) {
            config.updateDatabaseSettings(
                    urlField.getText().trim(), usernameField.getText().trim(), passwordField.getText(),
                    saveUrlCheckBox.isSelected(), saveUsernameCheckBox.isSelected(),
                    savePasswordCheckBox.isSelected());
        }
        config.save();
    }
}
