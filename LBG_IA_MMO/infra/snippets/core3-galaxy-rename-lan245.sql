-- SWGEmu Core3 — noms de galaxie affichés au client (liste serveurs).
-- VM LAN 245 — galaxy_id 2 = instance stock SWGEmu (ports 4445x)
-- Exécuter : mysql -u swgemu -p swgemu < core3-galaxy-rename-lan245.sql

UPDATE swgemu.galaxy
SET name = 'LBG SWGEMU PreCu'
WHERE galaxy_id = 2;

SELECT galaxy_id, name, address, port, pingport FROM swgemu.galaxy WHERE galaxy_id = 2;
