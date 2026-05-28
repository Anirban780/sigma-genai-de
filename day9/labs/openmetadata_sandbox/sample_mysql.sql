CREATE DATABASE IF NOT EXISTS sigma_demo;

CREATE USER IF NOT EXISTS 'sigma_user'@'%' IDENTIFIED BY 'sigma_password';
GRANT ALL PRIVILEGES ON sigma_demo.* TO 'sigma_user'@'%';
GRANT SELECT ON mysql.general_log TO 'sigma_user'@'%';
FLUSH PRIVILEGES;

USE sigma_demo;

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    email VARCHAR(150),
    signup_date DATE NOT NULL,
    customer_tier VARCHAR(20) NOT NULL
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    order_status VARCHAR(30) NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

INSERT INTO customers (customer_id, customer_name, email, signup_date, customer_tier) VALUES
    (1, 'Asha Rao', 'asha.rao@example.com', '2025-01-10', 'gold'),
    (2, 'Ben Carter', 'ben.carter@example.com', '2025-02-18', 'silver'),
    (3, 'Chen Li', 'chen.li@example.com', '2025-03-04', 'bronze'),
    (4, 'Diya Shah', 'diya.shah@example.com', '2025-04-21', 'gold');

INSERT INTO orders (order_id, customer_id, order_date, amount, order_status) VALUES
    (1001, 1, '2026-05-01', 125.50, 'paid'),
    (1002, 2, '2026-05-02', 79.99, 'paid'),
    (1003, 1, '2026-05-04', 42.00, 'refunded'),
    (1004, 3, '2026-05-05', 300.00, 'paid'),
    (1005, 4, '2026-05-07', 18.75, 'pending');
