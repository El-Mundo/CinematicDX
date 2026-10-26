module com.elmundo {
    requires javafx.controls;
    requires javafx.fxml;
    requires java.sql;
    requires java.desktop;
    requires org.mariadb.jdbc;
    requires com.fasterxml.jackson.databind;

    opens com.elmundo to javafx.fxml, javafx.base;
    exports com.elmundo;
}
