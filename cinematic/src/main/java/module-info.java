module com.elmundo {
    requires javafx.controls;
    requires javafx.fxml;
    requires java.sql;
    requires org.mariadb.jdbc;

    opens com.elmundo to javafx.fxml, javafx.base;
    exports com.elmundo;
}
