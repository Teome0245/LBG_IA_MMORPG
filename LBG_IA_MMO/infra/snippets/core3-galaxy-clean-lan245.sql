-- Galaxie instance Core3 clean / Antigravity (ports 4455x, galaxy_id = 3).
-- VM LAN : 192.168.0.245
-- Exécuter : mysql -u swgemu -p swgemu < core3-galaxy-clean-lan245.sql

INSERT INTO galaxy (galaxy_id, name, address, port, pingport)
VALUES (3, 'LBG MMO Serveur Prime', '192.168.0.245', 44563, 44562)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  address = VALUES(address),
  port = VALUES(port),
  pingport = VALUES(pingport);

SELECT galaxy_id, name, address, port, pingport FROM galaxy ORDER BY galaxy_id;
