package com.elmundo;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.stage.Stage;

import java.io.IOException;
import java.sql.Connection;
import java.sql.SQLException;

/**
 * JavaFX App
 */
public class App extends Application {

    private static Scene scene;
    private static Connection connection;
    private static final AppConfig appConfig = AppConfig.load();
    private static final PythonWorkerManager pythonWorkerManager = new PythonWorkerManager();
    private static final FilmRepository filmRepository = new FilmRepository();

    @Override
    public void start(Stage stage) throws IOException {
        scene = new Scene(loadFXML("login"), 800, 560);
        stage.setTitle("Film Test Database");
        stage.setScene(scene);
        stage.setOnCloseRequest(event -> shutdown());
        stage.show();
    }

    @Override
    public void stop() {
        shutdown();
    }

    static void setRoot(String fxml) throws IOException {
        scene.setRoot(loadFXML(fxml));
    }

    static Connection getConnection() {
        return connection;
    }

    static void setConnection(Connection newConnection) {
        closeConnection();
        connection = newConnection;
    }

    static PythonWorkerManager getPythonWorkerManager() {
        return pythonWorkerManager;
    }

    static FilmRepository getFilmRepository() {
        return filmRepository;
    }

    static AppConfig getConfig() {
        return appConfig;
    }

    private static void shutdown() {
        pythonWorkerManager.stopWorker();
        closeConnection();
    }

    private static void closeConnection() {
        if (connection == null) {
            return;
        }

        try {
            connection.close();
        } catch (SQLException e) {
            e.printStackTrace();
        } finally {
            connection = null;
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
