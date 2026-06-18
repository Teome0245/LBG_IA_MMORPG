-- PreCU sur VM 246 (galaxy_id = 2) — DB partagée sur 245.
-- Retire la galaxie « Second » (id 4) devenue obsolète.
-- Exécuter sur 245 : sudo mysql swgemu < core3-galaxy-precu-lan246.sql

UPDATE galaxy
SET name = 'LBG SWGEMU PreCu',
    address = '192.168.0.246',
    port = 44463,
    pingport = 44462
WHERE galaxy_id = 2;

DELETE FROM galaxy WHERE galaxy_id = 4;

SELECT galaxy_id, name, address, port, pingport FROM galaxy ORDER BY galaxy_id;
