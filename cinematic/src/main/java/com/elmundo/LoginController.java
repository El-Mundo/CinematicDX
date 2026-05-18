package com.elmundo;

import java.io.IOException;
import java.io.File;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.stage.FileChooser;
import javafx.scene.control.CheckBox;
import javafx.scene.control.Label;
import javafx.scene.control.PasswordField;
import javafx.scene.control.TextField;

public class LoginController {

    @FXML
    private TextField urlField;

    @FXML
    private TextField usernameField;

    @FXML
    private PasswordField passwordField;

    @FXML
    private CheckBox enablePythonWorkerCheckBox;

    @FXML
    private TextField pythonRuntimeField;

    @FXML
    private CheckBox saveUrlCheckBox;

    @FXML
    private CheckBox saveUsernameCheckBox;

    @FXML
    private CheckBox savePasswordCheckBox;

    @FXML
    private Label statusLabel;

    @FXML
    private void initialize() {
        AppConfig config = App.getConfig();

        pythonRuntimeField.setText(config.getPythonRuntimePath());
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
    }

    @FXML
    private void login() {
        String url = urlField.getText().trim();
        String username = usernameField.getText().trim();
        String password = passwordField.getText();
        String pythonRuntimePath = pythonRuntimeField.getText().trim();

        if (url.isEmpty()) {
            statusLabel.setText("Please enter a database URL.");
            return;
        }

        try {
            Connection connection = DriverManager.getConnection(url, username, password);
            App.setConnection(connection);
            App.getFilmRepository().initializeDatabase(connection);
            saveConfig(url, username, password, pythonRuntimePath);

            if (enablePythonWorkerCheckBox.isSelected()) {
                App.getPythonWorkerManager().startWorker(pythonRuntimePath);
            } else {
                App.getPythonWorkerManager().disable();
            }

            App.setRoot("primary");
        } catch (SQLException e) {
            statusLabel.setText("Login failed: " + e.getMessage());
        } catch (IOException e) {
            statusLabel.setText("Could not open the table view.");
            e.printStackTrace();
        }
    }

    @FXML
    private void exit() {
        Platform.exit();
    }

    @FXML
    private void runWithoutDb() {
    }

    @FXML
    private void choosePythonRuntime() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Select Python Runtime");

        String currentPath = pythonRuntimeField.getText().trim();
        if (!currentPath.isEmpty()) {
            Path current = Path.of(currentPath);
            Path parent = current.getParent();
            if (parent != null && parent.toFile().isDirectory()) {
                fileChooser.setInitialDirectory(parent.toFile());
            }
        }

        File selectedFile = fileChooser.showOpenDialog(pythonRuntimeField.getScene().getWindow());
        if (selectedFile == null) {
            return;
        }

        String selectedPath = selectedFile.toPath().toAbsolutePath().normalize().toString();
        pythonRuntimeField.setText(selectedPath);

        AppConfig config = App.getConfig();
        config.setPythonRuntimePath(selectedPath);
        config.save();
        statusLabel.setText("Saved Python runtime path.");
    }

    private void saveConfig(String url, String username, String password, String pythonRuntimePath) {
        AppConfig config = App.getConfig();
        config.setPythonRuntimePath(pythonRuntimePath);
        config.updateDatabaseSettings(
            url,
            username,
            password,
            saveUrlCheckBox.isSelected(),
            saveUsernameCheckBox.isSelected(),
            savePasswordCheckBox.isSelected()
        );
        config.save();
    }
}
