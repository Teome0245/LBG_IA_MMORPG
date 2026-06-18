-- Galaxie PreCU (galaxy_id = 2) sur VM 245 — MariaDB locale.
-- Exécuter sur 245 : sudo mysql swgemu < core3-galaxy-precu-lan245.sql

UPDATE galaxy
SET name = 'LBG SWGEMU PreCu',
    address = '192.168.0.245',
    port = 44463,
    pingport = 44462
WHERE galaxy_id = 2;

DELETE FROM galaxy WHERE galaxy_id = 4;

SELECT galaxy_id, name, address, port, pingport FROM galaxy ORDER BY galaxy_id;
