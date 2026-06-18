-- Retire la galaxie Prime (3) de la MariaDB PreCU sur VM 245.
-- Usage : sudo mysql swgemu < core3-mysql-precu-245-remove-prime.sql

DELETE FROM sessions;

DELETE FROM characters WHERE galaxy_id = 3;
DELETE FROM deleted_characters WHERE galaxy_id = 3;

DELETE FROM galaxy WHERE galaxy_id = 3;

UPDATE galaxy
SET name = 'LBG SWGEMU PreCu',
    address = '192.168.0.245',
    port = 44463,
    pingport = 44462
WHERE galaxy_id = 2;

SELECT 'galaxy' AS what, galaxy_id, name, address, port, pingport FROM galaxy ORDER BY galaxy_id;
SELECT 'characters' AS what, galaxy_id, COUNT(*) AS n FROM characters GROUP BY galaxy_id;
