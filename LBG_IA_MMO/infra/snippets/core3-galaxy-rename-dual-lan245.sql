-- Renommage dual Core3 VM 245 (2026-05) :
--   galaxy 2 (stock / core3-swgemu)  → LBG SWGEMU PreCu
--   galaxy 3 (clean / core3-clean)   → LBG MMO Serveur Prime
-- Exécuter : mysql -u swgemu -p swgemu < core3-galaxy-rename-dual-lan245.sql

UPDATE swgemu.galaxy SET name = 'LBG SWGEMU PreCu' WHERE galaxy_id = 2;
UPDATE swgemu.galaxy SET name = 'LBG MMO Serveur Prime' WHERE galaxy_id = 3;

SELECT galaxy_id, name, address, port, pingport FROM swgemu.galaxy ORDER BY galaxy_id;
