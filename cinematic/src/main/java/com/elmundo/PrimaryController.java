package com.elmundo;

import java.util.ArrayList;
import java.util.List;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

import javafx.collections.FXCollections;
import javafx.fxml.FXML;
import javafx.scene.control.Alert;
import javafx.scene.control.Label;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.cell.PropertyValueFactory;

public class PrimaryController {

    @FXML
    private TableView<FilmEntry> filmTable;

    @FXML
    private TableColumn<FilmEntry, String> romanizedColumn;

    @FXML
    private TableColumn<FilmEntry, String> titleColumn;

    @FXML
    private TableColumn<FilmEntry, Integer> yearColumn;

    @FXML
    private TableColumn<FilmEntry, String> translatedColumn;

    @FXML
    private TableColumn<FilmEntry, String> productionColumn;

    @FXML
    private TableColumn<FilmEntry, String> colourColumn;

    @FXML
    private TableColumn<FilmEntry, String> specialAspectsColumn;

    @FXML
    private Label statusLabel;

    @FXML
    private Label pythonWorkerStatusLabel;

    private boolean pythonFailureWarningShown;

    @FXML
    private void initialize() {
        romanizedColumn.setCellValueFactory(new PropertyValueFactory<>("romanized"));
        titleColumn.setCellValueFactory(new PropertyValueFactory<>("title"));
        yearColumn.setCellValueFactory(new PropertyValueFactory<>("year"));
        translatedColumn.setCellValueFactory(new PropertyValueFactory<>("translated"));
        productionColumn.setCellValueFactory(new PropertyValueFactory<>("production"));
        colourColumn.setCellValueFactory(new PropertyValueFactory<>("colour"));
        specialAspectsColumn.setCellValueFactory(new PropertyValueFactory<>("specialAspects"));

        initializePythonWorkerStatus();
        loadData();
    }

    @FXML
    private void loadData() {
        Connection connection = App.getConnection();
        if (connection == null) {
            statusLabel.setText("No database connection is available.");
            filmTable.setItems(FXCollections.observableArrayList());
            return;
        }

        try {
            List<FilmEntry> films = readFilms(connection);
            filmTable.setItems(FXCollections.observableArrayList(films));
            statusLabel.setText("Loaded " + films.size() + " film rows.");
        } catch (SQLException e) {
            statusLabel.setText("Could not load film rows: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private List<FilmEntry> readFilms(Connection connection) throws SQLException {
        List<FilmEntry> films = new ArrayList<>();
        String query = "SELECT Romanized, Title, Year, Translated, Production, Colour, "
                + "`Special Aspects` AS special_aspects FROM `chn_film_test_db`";

        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(query)) {
            while (resultSet.next()) {
                films.add(new FilmEntry(
                    resultSet.getString("Romanized"),
                    resultSet.getString("Title"),
                    getInteger(resultSet, "Year"),
                    resultSet.getString("Translated"),
                    resultSet.getString("Production"),
                    resultSet.getString("Colour"),
                    resultSet.getString("special_aspects")
                ));
            }
        }

        return films;
    }

    private Integer getInteger(ResultSet resultSet, String columnName) throws SQLException {
        Number value = (Number) resultSet.getObject(columnName);
        return value == null ? null : value.intValue();
    }

    private void initializePythonWorkerStatus() {
        PythonWorkerManager manager = App.getPythonWorkerManager();
        manager.statusProperty().addListener((observable, oldStatus, newStatus) ->
                updatePythonWorkerStatus(newStatus));
        updatePythonWorkerStatus(manager.getStatus());
    }

    private void updatePythonWorkerStatus(PythonWorkerStatus status) {
        pythonWorkerStatusLabel.setText("Python worker: " + status.getDisplayName());

        if (status == PythonWorkerStatus.FAILED && !pythonFailureWarningShown) {
            pythonFailureWarningShown = true;
            showPythonWorkerWarning();
        }
    }

    private void showPythonWorkerWarning() {
        String message = App.getPythonWorkerManager().getLastMessage();
        if (message == null || message.isBlank()) {
            message = "The Python ML worker could not be started.";
        }

        Alert alert = new Alert(Alert.AlertType.WARNING);
        alert.setTitle("Python ML Worker");
        alert.setHeaderText("Python worker failed");
        alert.setContentText(message + "\n\nThe app will continue without the Python worker.");
        alert.show();
    }
}
