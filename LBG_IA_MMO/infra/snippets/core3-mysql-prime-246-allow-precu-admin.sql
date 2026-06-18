-- Autorise l'UI comptes (VM 245) à lire/écrire la MariaDB Prime sur 246.
-- Usage sur 246 : sudo mysql < core3-mysql-prime-246-allow-precu-admin.sql
-- PRECU_IP et DB_PASS à adapter si besoin.

SET @precu_ip = '192.168.0.245';
SET @db_pass = '123456';

SET @sql = CONCAT(
  "CREATE USER IF NOT EXISTS 'swgemu'@'", @precu_ip,
  "' IDENTIFIED BY '", @db_pass, "'"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

GRANT ALL PRIVILEGES ON swgemu.* TO 'swgemu'@'192.168.0.245';
FLUSH PRIVILEGES;

SELECT user, host FROM mysql.user WHERE user = 'swgemu';
