-- Autorise l'UI comptes (VM 246) à lire/écrire la MariaDB PreCU sur 245.
-- Usage sur 245 : sudo mysql < core3-mysql-precu-245-allow-prime-admin.sql

CREATE USER IF NOT EXISTS 'swgemu'@'192.168.0.246' IDENTIFIED BY '123456';
GRANT ALL PRIVILEGES ON swgemu.* TO 'swgemu'@'192.168.0.246';
FLUSH PRIVILEGES;

SELECT user, host FROM mysql.user WHERE user = 'swgemu';
