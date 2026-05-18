package com.elmundo;

import java.util.List;
import java.util.Optional;
import java.sql.Connection;
import java.sql.SQLException;
import java.io.File;
import java.io.IOException;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.Map;

import javafx.collections.FXCollections;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.ButtonBar;
import javafx.scene.control.ButtonType;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Dialog;
import javafx.scene.control.Label;
import javafx.scene.control.SelectionMode;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.TextArea;
import javafx.scene.control.TextField;
import javafx.scene.control.cell.PropertyValueFactory;
import javafx.scene.layout.GridPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.geometry.Insets;
import javafx.stage.FileChooser;

public class PrimaryController {
    private enum ConflictChoice {
        OVERWRITE,
        KEEP_EXISTING,
        IMPORT_AS_NEW
    }

    private enum SaveOutcome {
        INSERTED,
        OVERWRITTEN,
        SKIPPED
    }

    @FXML
    private TableView<FilmEntry> filmTable;

    @FXML
    private TableColumn<FilmEntry, String> filmKeyColumn;

    @FXML
    private TableColumn<FilmEntry, String> titleOriginalColumn;

    @FXML
    private TableColumn<FilmEntry, String> productionYearColumn;

    @FXML
    private TableColumn<FilmEntry, String> titleTranslatedColumn;

    @FXML
    private TableColumn<FilmEntry, String> romanizedColumn;

    @FXML
    private TableColumn<FilmEntry, String> productionColumn;

    @FXML
    private TableColumn<FilmEntry, String> colorFormatColumn;

    @FXML
    private TableColumn<FilmEntry, String> specialAspectsColumn;

    @FXML
    private TableView<MediaStorageEntry> mediaTable;

    @FXML
    private TableColumn<MediaStorageEntry, String> mediaStorageFormatColumn;

    @FXML
    private TableColumn<MediaStorageEntry, String> mediaTypeColumn;

    @FXML
    private TableColumn<MediaStorageEntry, String> mediaPathColumn;

    @FXML
    private TableColumn<MediaStorageEntry, String> mediaExtensionColumn;

    @FXML
    private TableColumn<MediaStorageEntry, String> mediaStatusColumn;

    @FXML
    private Label statusLabel;

    @FXML
    private Label pythonWorkerStatusLabel;

    private final CsvFilmImporter csvFilmImporter = new CsvFilmImporter();
    private final AttributeCsvImporter attributeCsvImporter = new AttributeCsvImporter();
    private final MediaCsvImporter mediaCsvImporter = new MediaCsvImporter();

    private boolean pythonFailureWarningShown;

    private final FilmRepository filmRepository = App.getFilmRepository();

    @FXML
    private void initialize() {
        filmKeyColumn.setCellValueFactory(new PropertyValueFactory<>("filmKey"));
        titleOriginalColumn.setCellValueFactory(new PropertyValueFactory<>("titleOriginal"));
        productionYearColumn.setCellValueFactory(new PropertyValueFactory<>("productionYearDisplay"));
        titleTranslatedColumn.setCellValueFactory(new PropertyValueFactory<>("titleTranslated"));
        romanizedColumn.setCellValueFactory(new PropertyValueFactory<>("romanized"));
        productionColumn.setCellValueFactory(new PropertyValueFactory<>("production"));
        colorFormatColumn.setCellValueFactory(new PropertyValueFactory<>("colorFormat"));
        specialAspectsColumn.setCellValueFactory(new PropertyValueFactory<>("specialAspects"));
        mediaStorageFormatColumn.setCellValueFactory(new PropertyValueFactory<>("storageFormat"));
        mediaTypeColumn.setCellValueFactory(new PropertyValueFactory<>("mediaType"));
        mediaPathColumn.setCellValueFactory(new PropertyValueFactory<>("path"));
        mediaExtensionColumn.setCellValueFactory(new PropertyValueFactory<>("fileExtension"));
        mediaStatusColumn.setCellValueFactory(new PropertyValueFactory<>("status"));

        filmTable.getSelectionModel().selectedItemProperty().addListener(
                (observable, oldFilm, newFilm) -> loadMediaForSelectedFilm());

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
            List<FilmEntry> films = filmRepository.findAll(connection);
            filmTable.setItems(FXCollections.observableArrayList(films));
            if (films.isEmpty()) {
                mediaTable.setItems(FXCollections.observableArrayList());
            } else if (filmTable.getSelectionModel().getSelectedItem() == null) {
                filmTable.getSelectionModel().selectFirst();
            } else {
                loadMediaForSelectedFilm();
            }
            statusLabel.setText("Loaded " + films.size() + " film rows.");
        } catch (SQLException e) {
            statusLabel.setText("Could not load film rows: " + e.getMessage());
            e.printStackTrace();
        }
    }

    @FXML
    private void refreshMedia() {
        loadMediaForSelectedFilm();
    }

    @FXML
    private void addFilm() {
        if (App.getConnection() == null) {
            showWarning("No database connection", "Connect to a database before adding films.");
            return;
        }

        Optional<FilmDraft> result = showFilmEntryDialog();
        if (result.isEmpty()) {
            return;
        }

        try {
            SaveOutcome outcome = saveFilmDraft(result.get());
            loadData();
            statusLabel.setText(statusTextForOutcome(outcome, "film"));
        } catch (SQLException e) {
            showError("Could not save film", e.getMessage());
            statusLabel.setText("Could not save film: " + e.getMessage());
        }
    }

    @FXML
    private void importFilmsCsv() {
        Connection connection = App.getConnection();
        if (connection == null) {
            showWarning("No database connection", "Connect to a database before importing CSV files.");
            return;
        }

        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Import Films from CSV");
        fileChooser.getExtensionFilters().add(
                new FileChooser.ExtensionFilter("CSV files", "*.csv"));
        File selectedFile = fileChooser.showOpenDialog(filmTable.getScene().getWindow());
        if (selectedFile == null) {
            return;
        }

        try {
            CsvImportData importData = csvFilmImporter.parse(selectedFile.toPath());
            if (!importData.getUnsupportedHeaders().isEmpty()) {
                showWarning(
                        "Incomplete CSV import support",
                        "These CSV columns are ignored for now because custom CSV fields are not imported yet:\n\n"
                                + String.join(", ", importData.getUnsupportedHeaders()));
            }
            if (importData.getRows().isEmpty()) {
                showWarning("CSV import", "The selected CSV file does not contain film rows.");
                return;
            }

            List<FilmEntry> databaseFilms = filmRepository.findAll(connection);
            showCsvReviewDialog(importData, databaseFilms);
        } catch (IOException e) {
            showError("Could not read CSV", e.getMessage());
        } catch (SQLException e) {
            showError("Could not prepare CSV import", e.getMessage());
        }
    }

    @FXML
    private void importAttributesCsv() {
        Connection connection = App.getConnection();
        if (connection == null) {
            showWarning("No database connection", "Connect to a database before importing attribute CSV files.");
            return;
        }

        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Import Attributes from CSV");
        fileChooser.getExtensionFilters().add(
                new FileChooser.ExtensionFilter("CSV files", "*.csv"));
        File selectedFile = fileChooser.showOpenDialog(filmTable.getScene().getWindow());
        if (selectedFile == null) {
            return;
        }

        try {
            AttributeImportData importData = attributeCsvImporter.parse(
                    selectedFile.toPath(),
                    filmRepository.findFilmIdsByKey(connection),
                    filmRepository.findCustomFieldTypes(connection));
            filmRepository.populateAttributeExistingValueCounts(connection, importData);

            if (importData.getEmptyValueCount() > 0 && !confirmContinueWithEmptyAttributeValues(importData)) {
                return;
            }
            if (importData.getImportableColumns().isEmpty()) {
                showWarning("Attribute CSV import", "No importable attribute values were found.");
                return;
            }
            if (!showAttributeReviewDialog(importData)) {
                return;
            }

            Optional<Map<AttributeImportColumn, AttributeOverwriteChoice>> overwriteChoices =
                    collectAttributeOverwriteChoices(importData);
            if (overwriteChoices.isEmpty()) {
                return;
            }

            AttributeImportResult result = filmRepository.importAttributes(
                    connection,
                    importData,
                    overwriteChoices.get());
            loadData();
            statusLabel.setText("Attribute import complete: " + result.getUpdatedValues()
                    + " values imported, " + result.getSkippedValues()
                    + " skipped, " + result.getInvalidValues() + " invalid.");
        } catch (IllegalArgumentException e) {
            showError("Could not import attributes", e.getMessage());
        } catch (IOException e) {
            showError("Could not read attribute CSV", e.getMessage());
        } catch (SQLException e) {
            showError("Could not import attributes", e.getMessage());
        }
    }

    @FXML
    private void importMediaCsv() {
        Connection connection = App.getConnection();
        if (connection == null) {
            showWarning("No database connection", "Connect to a database before importing media CSV files.");
            return;
        }

        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Import Media from CSV");
        fileChooser.getExtensionFilters().add(
                new FileChooser.ExtensionFilter("CSV files", "*.csv"));
        File selectedFile = fileChooser.showOpenDialog(filmTable.getScene().getWindow());
        if (selectedFile == null) {
            return;
        }

        try {
            MediaImportData importData = mediaCsvImporter.parse(
                    selectedFile.toPath(),
                    filmRepository.findFilmIdsByKey(connection));
            filmRepository.populateExistingMediaDuplicates(connection, importData);

            if (!showMediaReviewDialog(importData)) {
                return;
            }

            MediaImportResult result = filmRepository.importMediaStorage(connection, importData);
            loadMediaForSelectedFilm();
            statusLabel.setText("Media import complete: " + result.getImportedRows()
                    + " imported, " + result.getSkippedRows() + " skipped.");
        } catch (IllegalArgumentException e) {
            showError("Could not import media", e.getMessage());
        } catch (IOException e) {
            showError("Could not read media CSV", e.getMessage());
        } catch (SQLException e) {
            showError("Could not import media", e.getMessage());
        }
    }

    @FXML
    private void showSelectedMediaInSystemFileBrowser() {
        MediaStorageEntry selectedEntry = mediaTable.getSelectionModel().getSelectedItem();
        try {
            MediaFileBrowser.showInSystemFileBrowser(selectedEntry);
        } catch (IllegalArgumentException | IllegalStateException e) {
            showWarning("Show Media", e.getMessage());
        } catch (IOException e) {
            showError("Show Media", e.getMessage());
        }
    }

    private void loadMediaForSelectedFilm() {
        Connection connection = App.getConnection();
        FilmEntry selectedFilm = filmTable.getSelectionModel().getSelectedItem();
        if (connection == null || selectedFilm == null) {
            mediaTable.setItems(FXCollections.observableArrayList());
            return;
        }

        try {
            List<MediaStorageEntry> entries = filmRepository.findMediaStorageByFilmKey(
                    connection,
                    selectedFilm.getFilmKey());
            mediaTable.setItems(FXCollections.observableArrayList(entries));
        } catch (SQLException e) {
            showError("Could not load media mappings", e.getMessage());
        }
    }

    private boolean showMediaReviewDialog(MediaImportData importData) {
        Dialog<ButtonType> dialog = new Dialog<>();
        dialog.setTitle("Review Media Import");
        dialog.setHeaderText("Review media storage rows before importing");

        ButtonType importButtonType = new ButtonType("Import Media", ButtonBar.ButtonData.OK_DONE);
        dialog.getDialogPane().getButtonTypes().addAll(importButtonType, ButtonType.CANCEL);

        TableView<MediaImportRow> table = new TableView<>();
        table.setItems(FXCollections.observableArrayList(importData.getRows()));
        table.setPrefHeight(320);

        TableColumn<MediaImportRow, Integer> rowColumn = new TableColumn<>("Row");
        rowColumn.setCellValueFactory(new PropertyValueFactory<>("rowNumber"));
        rowColumn.setPrefWidth(56);
        TableColumn<MediaImportRow, String> keyColumn = new TableColumn<>("Key");
        keyColumn.setCellValueFactory(new PropertyValueFactory<>("filmKey"));
        keyColumn.setPrefWidth(130);
        TableColumn<MediaImportRow, String> storageColumn = new TableColumn<>("Storage");
        storageColumn.setCellValueFactory(new PropertyValueFactory<>("storageFormat"));
        storageColumn.setPrefWidth(100);
        TableColumn<MediaImportRow, String> typeColumn = new TableColumn<>("Media Type");
        typeColumn.setCellValueFactory(new PropertyValueFactory<>("mediaType"));
        typeColumn.setPrefWidth(120);
        TableColumn<MediaImportRow, String> pathColumn = new TableColumn<>("Path");
        pathColumn.setCellValueFactory(new PropertyValueFactory<>("path"));
        pathColumn.setPrefWidth(240);
        TableColumn<MediaImportRow, String> extensionColumn = new TableColumn<>("Ext");
        extensionColumn.setCellValueFactory(new PropertyValueFactory<>("fileExtension"));
        extensionColumn.setPrefWidth(60);
        TableColumn<MediaImportRow, MediaImportRowStatus> statusColumn = new TableColumn<>("Status");
        statusColumn.setCellValueFactory(new PropertyValueFactory<>("status"));
        statusColumn.setPrefWidth(100);
        TableColumn<MediaImportRow, String> warningColumn = new TableColumn<>("Warning");
        warningColumn.setCellValueFactory(new PropertyValueFactory<>("warning"));
        warningColumn.setPrefWidth(220);

        table.getColumns().add(rowColumn);
        table.getColumns().add(keyColumn);
        table.getColumns().add(storageColumn);
        table.getColumns().add(typeColumn);
        table.getColumns().add(pathColumn);
        table.getColumns().add(extensionColumn);
        table.getColumns().add(statusColumn);
        table.getColumns().add(warningColumn);

        TextArea summaryArea = new TextArea(mediaImportSummary(importData));
        summaryArea.setEditable(false);
        summaryArea.setWrapText(true);
        summaryArea.setPrefRowCount(5);

        VBox content = new VBox(10, table, summaryArea);
        content.setPadding(new Insets(12));
        dialog.getDialogPane().setContent(content);
        dialog.getDialogPane().setPrefWidth(980);

        Optional<ButtonType> result = dialog.showAndWait();
        return result.isPresent() && result.get() == importButtonType;
    }

    private String mediaImportSummary(MediaImportData importData) {
        return "Total rows: " + importData.getTotalRowCount()
                + "\nValid rows: " + importData.getValidRowCount()
                + "\nUnknown keys: " + importData.getUnknownKeyCount()
                + "\nInvalid rows: " + importData.getInvalidRowCount()
                + "\nDuplicate rows: " + importData.getDuplicateRowCount();
    }

    private boolean confirmContinueWithEmptyAttributeValues(AttributeImportData importData) {
        ButtonType continueButton = new ButtonType("Continue", ButtonBar.ButtonData.OK_DONE);
        ButtonType cancelButton = new ButtonType("Cancel", ButtonBar.ButtonData.CANCEL_CLOSE);

        Alert alert = new Alert(Alert.AlertType.CONFIRMATION);
        alert.setTitle("Empty Attribute Values");
        alert.setHeaderText("Empty values were found in the attribute CSV.");
        alert.setContentText(importData.getEmptyValueCount()
                + " empty value(s) will be skipped and will not erase stored values.");
        alert.getButtonTypes().setAll(continueButton, cancelButton);

        Optional<ButtonType> result = alert.showAndWait();
        return result.isPresent() && result.get() == continueButton;
    }

    private boolean showAttributeReviewDialog(AttributeImportData importData) {
        Dialog<ButtonType> dialog = new Dialog<>();
        dialog.setTitle("Review Attribute Import");
        dialog.setHeaderText("Review attributes before importing");

        ButtonType importButtonType = new ButtonType("Import Attributes", ButtonBar.ButtonData.OK_DONE);
        dialog.getDialogPane().getButtonTypes().addAll(importButtonType, ButtonType.CANCEL);

        TableView<AttributeImportColumn> table = new TableView<>();
        table.setItems(FXCollections.observableArrayList(importData.getColumns()));
        table.setPrefHeight(320);

        TableColumn<AttributeImportColumn, String> headerColumn = new TableColumn<>("CSV Header");
        headerColumn.setCellValueFactory(new PropertyValueFactory<>("header"));
        headerColumn.setPrefWidth(170);
        TableColumn<AttributeImportColumn, String> targetColumn = new TableColumn<>("Target");
        targetColumn.setCellValueFactory(new PropertyValueFactory<>("targetDisplay"));
        targetColumn.setPrefWidth(150);
        TableColumn<AttributeImportColumn, String> typeColumn = new TableColumn<>("Type");
        typeColumn.setCellValueFactory(new PropertyValueFactory<>("typeDisplay"));
        typeColumn.setPrefWidth(150);
        TableColumn<AttributeImportColumn, Integer> valueColumn = new TableColumn<>("Values");
        valueColumn.setCellValueFactory(new PropertyValueFactory<>("nonEmptyValueCount"));
        valueColumn.setPrefWidth(70);
        TableColumn<AttributeImportColumn, Integer> emptyColumn = new TableColumn<>("Empty");
        emptyColumn.setCellValueFactory(new PropertyValueFactory<>("emptyValueCount"));
        emptyColumn.setPrefWidth(70);
        TableColumn<AttributeImportColumn, Integer> existingColumn = new TableColumn<>("Existing");
        existingColumn.setCellValueFactory(new PropertyValueFactory<>("existingValueCount"));
        existingColumn.setPrefWidth(80);
        TableColumn<AttributeImportColumn, String> ignoredColumn = new TableColumn<>("Ignored Reason");
        ignoredColumn.setCellValueFactory(new PropertyValueFactory<>("ignoreReason"));
        ignoredColumn.setPrefWidth(150);

        table.getColumns().add(headerColumn);
        table.getColumns().add(targetColumn);
        table.getColumns().add(typeColumn);
        table.getColumns().add(valueColumn);
        table.getColumns().add(emptyColumn);
        table.getColumns().add(existingColumn);
        table.getColumns().add(ignoredColumn);

        ComboBox<AttributeFieldType> typeComboBox = new ComboBox<>(
                FXCollections.observableArrayList(AttributeFieldType.values()));
        typeComboBox.setValue(AttributeFieldType.STRING);
        Button applyTypeButton = new Button("Apply Type to Selected Custom Field");
        applyTypeButton.setOnAction(event -> {
            AttributeImportColumn selectedColumn = table.getSelectionModel().getSelectedItem();
            if (selectedColumn == null || selectedColumn.getTargetKind() != AttributeTargetKind.CUSTOM) {
                showWarning("Attribute type", "Select a custom attribute column first.");
                return;
            }
            if (selectedColumn.isExistingDefinition()) {
                showWarning("Attribute type", "Existing custom field definitions keep their stored type.");
                return;
            }
            selectedColumn.setFieldType(typeComboBox.getValue());
            table.refresh();
        });

        TextArea summaryArea = new TextArea(attributeImportSummary(importData));
        summaryArea.setEditable(false);
        summaryArea.setWrapText(true);
        summaryArea.setPrefRowCount(5);

        VBox content = new VBox(10, table, new HBox(8, typeComboBox, applyTypeButton), summaryArea);
        content.setPadding(new Insets(12));
        dialog.getDialogPane().setContent(content);
        dialog.getDialogPane().setPrefWidth(900);

        Optional<ButtonType> result = dialog.showAndWait();
        return result.isPresent() && result.get() == importButtonType;
    }

    private String attributeImportSummary(AttributeImportData importData) {
        StringBuilder summary = new StringBuilder();
        summary.append("Importable columns: ").append(importData.getImportableColumns().size()).append('\n');
        summary.append("Empty values: ").append(importData.getEmptyValueCount()).append('\n');
        if (!importData.getUnknownKeys().isEmpty()) {
            summary.append("Ignored unknown keys: ")
                    .append(String.join(", ", importData.getUnknownKeys()))
                    .append('\n');
        }
        if (!importData.getIgnoredHeaders().isEmpty()) {
            summary.append("Ignored protected/keying headers: ")
                    .append(String.join(", ", importData.getIgnoredHeaders()))
                    .append('\n');
        }
        return summary.toString();
    }

    private Optional<Map<AttributeImportColumn, AttributeOverwriteChoice>> collectAttributeOverwriteChoices(
            AttributeImportData importData) {
        Map<AttributeImportColumn, AttributeOverwriteChoice> choices = new LinkedHashMap<>();
        for (AttributeImportColumn column : importData.getImportableColumns()) {
            if (!column.hasExistingValues()) {
                choices.put(column, AttributeOverwriteChoice.OVERWRITE);
                continue;
            }

            AttributeOverwriteChoice choice = askAttributeOverwriteChoice(column);
            if (choice == AttributeOverwriteChoice.CANCEL) {
                return Optional.empty();
            }
            choices.put(column, choice);
        }
        return Optional.of(choices);
    }

    private AttributeOverwriteChoice askAttributeOverwriteChoice(AttributeImportColumn column) {
        ButtonType overwriteButton = new ButtonType("Overwrite", ButtonBar.ButtonData.YES);
        ButtonType keepExistingButton = new ButtonType("Keep Existing", ButtonBar.ButtonData.NO);
        ButtonType cancelButton = new ButtonType("Cancel", ButtonBar.ButtonData.CANCEL_CLOSE);

        Alert alert = new Alert(Alert.AlertType.CONFIRMATION);
        alert.setTitle("Existing Attribute Values");
        alert.setHeaderText("Existing values were found for " + column.getHeader() + ".");
        alert.setContentText(column.getExistingValueCount()
                + " matching film(s) already have values. Overwrite them or keep existing values?");
        alert.getButtonTypes().setAll(overwriteButton, keepExistingButton, cancelButton);

        Optional<ButtonType> result = alert.showAndWait();
        if (result.isPresent() && result.get() == overwriteButton) {
            return AttributeOverwriteChoice.OVERWRITE;
        }
        if (result.isPresent() && result.get() == keepExistingButton) {
            return AttributeOverwriteChoice.KEEP_EXISTING;
        }
        return AttributeOverwriteChoice.CANCEL;
    }

    private Optional<FilmDraft> showFilmEntryDialog() {
        Dialog<FilmDraft> dialog = new Dialog<>();
        dialog.setTitle("Add Film");
        dialog.setHeaderText("Record a film entry");

        ButtonType saveButtonType = new ButtonType("Save", ButtonBar.ButtonData.OK_DONE);
        dialog.getDialogPane().getButtonTypes().addAll(saveButtonType, ButtonType.CANCEL);

        TextField titleField = new TextField();
        TextField translatedField = new TextField();
        TextField yearField = new TextField();
        TextField productionField = new TextField();
        TextField colorFormatField = new TextField();
        TextField romanizedField = new TextField();
        TextArea specialAspectsArea = new TextArea();
        TextArea customFieldsArea = new TextArea();

        titleField.setPromptText("Required");
        yearField.setPromptText("Optional, e.g. 1949");
        specialAspectsArea.setPrefRowCount(3);
        customFieldsArea.setPrefRowCount(4);
        customFieldsArea.setPromptText("One field=value pair per line");

        GridPane grid = new GridPane();
        grid.setHgap(10);
        grid.setVgap(10);
        grid.setPadding(new Insets(16));
        grid.add(new Label("Original title *"), 0, 0);
        grid.add(titleField, 1, 0);
        grid.add(new Label("Translated title"), 0, 1);
        grid.add(translatedField, 1, 1);
        grid.add(new Label("Production year"), 0, 2);
        grid.add(yearField, 1, 2);
        grid.add(new Label("Production/studio"), 0, 3);
        grid.add(productionField, 1, 3);
        grid.add(new Label("Color format"), 0, 4);
        grid.add(colorFormatField, 1, 4);
        grid.add(new Label("Romanized title"), 0, 5);
        grid.add(romanizedField, 1, 5);
        grid.add(new Label("Special aspects"), 0, 6);
        grid.add(specialAspectsArea, 1, 6);
        grid.add(new Label("Custom fields"), 0, 7);
        grid.add(customFieldsArea, 1, 7);

        dialog.getDialogPane().setContent(grid);

        Button saveButton = (Button) dialog.getDialogPane().lookupButton(saveButtonType);
        saveButton.addEventFilter(ActionEvent.ACTION, event -> {
            try {
                buildDraftFromFields(
                        titleField,
                        translatedField,
                        yearField,
                        productionField,
                        colorFormatField,
                        romanizedField,
                        specialAspectsArea,
                        customFieldsArea);
            } catch (IllegalArgumentException e) {
                showWarning("Cannot save film", e.getMessage());
                event.consume();
            }
        });

        dialog.setResultConverter(button -> {
            if (button == saveButtonType) {
                return buildDraftFromFields(
                        titleField,
                        translatedField,
                        yearField,
                        productionField,
                        colorFormatField,
                        romanizedField,
                        specialAspectsArea,
                        customFieldsArea);
            }
            return null;
        });

        return dialog.showAndWait();
    }

    private FilmDraft buildDraftFromFields(
            TextField titleField,
            TextField translatedField,
            TextField yearField,
            TextField productionField,
            TextField colorFormatField,
            TextField romanizedField,
            TextArea specialAspectsArea,
            TextArea customFieldsArea) {
        FilmDraft draft = new FilmDraft();
        draft.setTitleOriginal(titleField.getText());
        if (!draft.hasTitle()) {
            throw new IllegalArgumentException("Original-language title is required.");
        }

        draft.setTitleTranslated(translatedField.getText());
        draft.setProductionYear(parseOptionalYear(yearField.getText()));
        draft.setProduction(productionField.getText());
        draft.setColorFormat(colorFormatField.getText());
        draft.setRomanized(romanizedField.getText());
        draft.setSpecialAspects(specialAspectsArea.getText());
        parseCustomFields(customFieldsArea.getText(), draft);
        return draft;
    }

    private void parseCustomFields(String text, FilmDraft draft) {
        if (text == null || text.isBlank()) {
            return;
        }

        String[] lines = text.split("\\R");
        for (String line : lines) {
            if (line.isBlank()) {
                continue;
            }
            int separator = line.indexOf('=');
            if (separator <= 0) {
                throw new IllegalArgumentException(
                        "Custom fields must use field=value format. Invalid line: " + line);
            }

            String name = line.substring(0, separator).trim();
            String value = line.substring(separator + 1).trim();
            if (name.isBlank()) {
                throw new IllegalArgumentException("Custom field names cannot be blank.");
            }
            draft.getCustomFields().put(name, value);
        }
    }

    private Integer parseOptionalYear(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }

        try {
            return Integer.valueOf(value.trim());
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Production year must be a whole number.");
        }
    }

    private void showCsvReviewDialog(CsvImportData importData, List<FilmEntry> databaseFilms) {
        Dialog<ButtonType> dialog = new Dialog<>();
        dialog.setTitle("Review CSV Import");
        dialog.setHeaderText("Review rows before importing");

        ButtonType importButtonType = new ButtonType("Import Active Rows", ButtonBar.ButtonData.OK_DONE);
        dialog.getDialogPane().getButtonTypes().addAll(importButtonType, ButtonType.CANCEL);

        TableView<CsvFilmRow> table = new TableView<>();
        table.getSelectionModel().setSelectionMode(SelectionMode.MULTIPLE);
        table.setItems(FXCollections.observableArrayList(importData.getRows()));
        table.setPrefHeight(320);

        TableColumn<CsvFilmRow, Integer> rowColumn = new TableColumn<>("Row");
        rowColumn.setCellValueFactory(new PropertyValueFactory<>("rowId"));
        rowColumn.setPrefWidth(56);
        TableColumn<CsvFilmRow, String> titleColumn = new TableColumn<>("Original Title");
        titleColumn.setCellValueFactory(new PropertyValueFactory<>("titleOriginal"));
        titleColumn.setPrefWidth(160);
        TableColumn<CsvFilmRow, Integer> yearColumn = new TableColumn<>("Year");
        yearColumn.setCellValueFactory(new PropertyValueFactory<>("productionYear"));
        yearColumn.setPrefWidth(70);
        TableColumn<CsvFilmRow, String> translatedColumn = new TableColumn<>("Translated");
        translatedColumn.setCellValueFactory(new PropertyValueFactory<>("titleTranslated"));
        translatedColumn.setPrefWidth(150);
        TableColumn<CsvFilmRow, CsvFilmRowStatus> statusColumn = new TableColumn<>("Status");
        statusColumn.setCellValueFactory(new PropertyValueFactory<>("status"));
        statusColumn.setPrefWidth(90);
        TableColumn<CsvFilmRow, String> warningColumn = new TableColumn<>("Warnings");
        warningColumn.setCellValueFactory(new PropertyValueFactory<>("warningText"));
        warningColumn.setPrefWidth(220);
        table.getColumns().add(rowColumn);
        table.getColumns().add(titleColumn);
        table.getColumns().add(yearColumn);
        table.getColumns().add(translatedColumn);
        table.getColumns().add(statusColumn);
        table.getColumns().add(warningColumn);

        TextArea duplicateSummary = new TextArea(describeDuplicateGroups(importData, databaseFilms));
        duplicateSummary.setEditable(false);
        duplicateSummary.setPrefRowCount(4);
        duplicateSummary.setWrapText(true);

        Button mergeButton = new Button("Merge Selected CSV Rows");
        mergeButton.setOnAction(event -> {
            List<CsvFilmRow> selectedRows = table.getSelectionModel().getSelectedItems().stream()
                    .filter(CsvFilmRow::isImportable)
                    .sorted(Comparator.comparingInt(CsvFilmRow::getRowId))
                    .collect(java.util.stream.Collectors.toList());
            if (selectedRows.size() < 2) {
                showWarning("CSV merge", "Select two or more active CSV rows with the same title.");
                return;
            }

            String titleKey = FilmKeyGenerator.normalizeTitleForMatch(
                    selectedRows.get(0).getDraft().getTitleOriginal());
            boolean sameTitle = selectedRows.stream()
                    .allMatch(row -> FilmKeyGenerator.normalizeTitleForMatch(
                            row.getDraft().getTitleOriginal()).equals(titleKey));
            if (!sameTitle) {
                showWarning("CSV merge", "Selected rows must have the same original-language title.");
                return;
            }

            CsvFilmRow target = selectedRows.get(0);
            selectedRows.stream().skip(1).forEach(source -> csvFilmImporter.mergeRows(target, source));
            table.refresh();
            duplicateSummary.setText(describeDuplicateGroups(importData, databaseFilms));
        });

        VBox content = new VBox(10, table, duplicateSummary, new HBox(8, mergeButton));
        content.setPadding(new Insets(12));
        dialog.getDialogPane().setContent(content);
        dialog.getDialogPane().setPrefWidth(900);

        Optional<ButtonType> result = dialog.showAndWait();
        if (result.isPresent() && result.get() == importButtonType) {
            importActiveCsvRows(importData);
        }
    }

    private String describeDuplicateGroups(CsvImportData importData, List<FilmEntry> databaseFilms) {
        List<CsvDuplicateGroup> groups = csvFilmImporter.buildDuplicateGroups(
                importData.getRows(),
                databaseFilms);
        if (groups.isEmpty()) {
            return "No duplicate-title groups found.";
        }

        StringBuilder description = new StringBuilder("Duplicate-title groups:\n");
        for (CsvDuplicateGroup group : groups) {
            description.append("- ").append(group.describe());
            if (!group.getDatabaseFilms().isEmpty()) {
                description.append(" [database keys: ");
                description.append(group.getDatabaseFilms().stream()
                        .map(FilmEntry::getFilmKey)
                        .collect(java.util.stream.Collectors.joining(", ")));
                description.append("]");
            }
            description.append('\n');
        }
        return description.toString();
    }

    private void importActiveCsvRows(CsvImportData importData) {
        int inserted = 0;
        int overwritten = 0;
        int skipped = 0;

        for (CsvFilmRow row : importData.getImportableRows()) {
            try {
                SaveOutcome outcome = saveFilmDraft(row.getDraft());
                if (outcome == SaveOutcome.INSERTED) {
                    inserted++;
                    row.setStatus(CsvFilmRowStatus.IMPORTED);
                } else if (outcome == SaveOutcome.OVERWRITTEN) {
                    overwritten++;
                    row.setStatus(CsvFilmRowStatus.IMPORTED);
                } else {
                    skipped++;
                    row.setStatus(CsvFilmRowStatus.SKIPPED);
                }
            } catch (SQLException e) {
                showError("CSV import stopped", "Row " + row.getRowId() + ": " + e.getMessage());
                break;
            }
        }

        loadData();
        statusLabel.setText("CSV import complete: " + inserted + " inserted, "
                + overwritten + " overwritten, " + skipped + " skipped.");
    }

    private SaveOutcome saveFilmDraft(FilmDraft draft) throws SQLException {
        Connection connection = App.getConnection();
        if (connection == null) {
            showWarning("No database connection", "Connect to a database before saving films.");
            return SaveOutcome.SKIPPED;
        }
        if (!draft.hasTitle()) {
            showWarning("Cannot save film", "Original-language title is required.");
            return SaveOutcome.SKIPPED;
        }

        Optional<FilmEntry> existing = filmRepository.findMatchingTitleAndYear(connection, draft);
        if (existing.isPresent()) {
            ConflictChoice choice = showConflictDialog(existing.get(), draft);
            if (choice == ConflictChoice.OVERWRITE) {
                filmRepository.overwriteWithNonBlankValues(connection, existing.get().getId(), draft);
                return SaveOutcome.OVERWRITTEN;
            }
            if (choice == ConflictChoice.KEEP_EXISTING) {
                return SaveOutcome.SKIPPED;
            }
        }

        filmRepository.insertAsUnique(connection, draft);
        return SaveOutcome.INSERTED;
    }

    private ConflictChoice showConflictDialog(FilmEntry existing, FilmDraft incoming) {
        ButtonType overwriteButton = new ButtonType("Overwrite Existing", ButtonBar.ButtonData.YES);
        ButtonType keepButton = new ButtonType("Keep Existing", ButtonBar.ButtonData.NO);
        ButtonType importNewButton = new ButtonType("Import As New", ButtonBar.ButtonData.OK_DONE);

        Alert alert = new Alert(Alert.AlertType.CONFIRMATION);
        alert.setTitle("Duplicate Film");
        alert.setHeaderText("A film with the same title and production year already exists.");
        alert.setContentText(
                "Existing key: " + existing.getFilmKey()
                        + "\nExisting title: " + existing.getTitleOriginal()
                        + "\nExisting year: " + FilmKeyGenerator.yearPart(existing.getProductionYear())
                        + "\n\nIncoming title: " + incoming.getTitleOriginal()
                        + "\nIncoming year: " + FilmKeyGenerator.yearPart(incoming.getProductionYear()));
        alert.getButtonTypes().setAll(overwriteButton, keepButton, importNewButton);

        Optional<ButtonType> result = alert.showAndWait();
        if (result.isPresent() && result.get() == overwriteButton) {
            return ConflictChoice.OVERWRITE;
        }
        if (result.isPresent() && result.get() == importNewButton) {
            return ConflictChoice.IMPORT_AS_NEW;
        }
        return ConflictChoice.KEEP_EXISTING;
    }

    private String statusTextForOutcome(SaveOutcome outcome, String label) {
        switch (outcome) {
            case INSERTED:
                return "Added " + label + ".";
            case OVERWRITTEN:
                return "Updated existing " + label + ".";
            case SKIPPED:
            default:
                return "Kept existing " + label + ".";
        }
    }

    private void showWarning(String title, String message) {
        Alert alert = new Alert(Alert.AlertType.WARNING);
        alert.setTitle(title);
        alert.setHeaderText(title);
        alert.setContentText(message);
        alert.showAndWait();
    }

    private void showError(String title, String message) {
        Alert alert = new Alert(Alert.AlertType.ERROR);
        alert.setTitle(title);
        alert.setHeaderText(title);
        alert.setContentText(message == null || message.isBlank() ? "Unknown error." : message);
        alert.showAndWait();
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
