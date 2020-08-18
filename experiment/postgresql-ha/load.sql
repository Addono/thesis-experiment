BEGIN TRANSACTION;

CREATE TABLE company(
   ID INT PRIMARY KEY     NOT NULL,
   NAME           TEXT    NOT NULL,
   AGE            INT     NOT NULL,
   ADDRESS        CHAR(50),
   SALARY         REAL,
   JOIN_DATE	  DATE
);

INSERT INTO company (id, name, age) VALUES (1, 'foo', 5);

SELECT * FROM company;

DROP TABLE company;

END TRANSACTION;

