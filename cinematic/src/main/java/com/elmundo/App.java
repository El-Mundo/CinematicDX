package com.elmundo;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.stage.Stage;
import javafx.stage.Screen;
import javafx.geometry.Rectangle2D;

import java.io.IOException;

/**
 * JavaFX App
 */
public class App extends Application {

    private static Scene scene;
    private static MetadataStore metadataStore;
    private static final AppConfig appConfig = AppConfig.load();
    private static final PythonWorkerManager pythonWorkerManager = new PythonWorkerManager();

    @Override
    public void start(Stage stage) throws IOException {
        scene = new Scene(loadFXML("login"), 940, 810);
        scene.getStylesheets().add(App.class.getResource("workspace.css").toExternalForm());
        stage.setTitle("CinematicDX Setup");
        stage.setScene(scene);
        sizeWindow(stage, false);
        stage.setOnCloseRequest(event -> shutdown());
        stage.show();
    }

    @Override
    public void stop() {
        shutdown();
    }

    static void setRoot(String fxml) throws IOException {
        scene.setRoot(loadFXML(fxml));
        if (scene.getWindow() instanceof Stage) {
            ((Stage) scene.getWindow()).setTitle("login".equals(fxml) ? "CinematicDX Setup" : "CinematicDX");
            sizeWindow((Stage) scene.getWindow(), !"login".equals(fxml));
        }
    }

    private static void sizeWindow(Stage stage, boolean workspace) {
        Rectangle2D bounds = Screen.getPrimary().getVisualBounds();
        stage.setMinWidth(Math.min(workspace ? 1060 : 850, bounds.getWidth() - 40));
        stage.setMinHeight(Math.min(workspace ? 720 : 650, bounds.getHeight() - 50));
        stage.setWidth(Math.min(workspace ? 1280 : 940, bounds.getWidth() - 40));
        stage.setHeight(Math.min(workspace ? 850 : 810, bounds.getHeight() - 50));
        stage.centerOnScreen();
    }

    static MetadataStore getMetadataStore() {
        return metadataStore;
    }

    static void setMetadataStore(MetadataStore newStore) throws MetadataStoreException {
        if (metadataStore == newStore) {
            return;
        }
        closeMetadataStore();
        metadataStore = newStore;
    }

    static PythonWorkerManager getPythonWorkerManager() {
        return pythonWorkerManager;
    }

    static AppConfig getConfig() {
        return appConfig;
    }

    private static void shutdown() {
        pythonWorkerManager.stopWorker();
        try {
            closeMetadataStore();
        } catch (MetadataStoreException e) {
            System.err.println("Could not close metadata source: " + e.getMessage());
        }
    }

    static void closeMetadataStore() throws MetadataStoreException {
        MetadataStore previous = metadataStore;
        metadataStore = null;
        if (previous != null) {
            previous.close();
        }
    }

    private static Parent loadFXML(String fxml) throws IOException {
        FXMLLoader fxmlLoader = new FXMLLoader(App.class.getResource(fxml + ".fxml"));
        return fxmlLoader.load();
    }

    public static void main(String[] args) {
        launch();
    }

}
