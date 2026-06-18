-- Galaxie Prime (galaxy_id = 3) sur VM 246 — MariaDB sur 245.
-- Exécuter sur 245 : sudo mysql swgemu < core3-galaxy-prime-lan246.sql

UPDATE galaxy
SET name = 'LBG MMO Serveur Prime',
    address = '192.168.0.246',
    port = 44563,
    pingport = 44562
WHERE galaxy_id = 3;

SELECT galaxy_id, name, address, port, pingport FROM galaxy ORDER BY galaxy_id;
