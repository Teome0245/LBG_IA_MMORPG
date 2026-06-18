-- Galaxie instance Core3 « Second » (ports 4465x, galaxy_id = 4) — VM 192.168.0.246
-- DB partagée sur 245 (comptes / personnages communs, monde distinct).
-- Exécuter sur la VM DB (245) :
--   mysql -u swgemu -p swgemu < core3-galaxy-second-lan246.sql

INSERT INTO galaxy (galaxy_id, name, address, port, pingport)
VALUES (4, 'LBG MMO Serveur Second', '192.168.0.246', 44663, 44662)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  address = VALUES(address),
  port = VALUES(port),
  pingport = VALUES(pingport);

SELECT galaxy_id, name, address, port, pingport FROM galaxy ORDER BY galaxy_id;
