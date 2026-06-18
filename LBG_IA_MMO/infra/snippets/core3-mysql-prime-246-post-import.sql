-- Post-import MariaDB Prime sur VM 246 (base autonome, galaxie 3 seule).
-- Usage : sudo mysql swgemu < core3-mysql-prime-246-post-import.sql

DELETE FROM sessions;

DELETE FROM characters WHERE galaxy_id IS NULL OR galaxy_id != 3;
DELETE FROM deleted_characters WHERE galaxy_id IS NULL OR galaxy_id != 3;

DELETE FROM galaxy WHERE galaxy_id != 3;

UPDATE galaxy
SET name = 'LBG MMO Serveur Prime',
    address = '192.168.0.246',
    port = 44563,
    pingport = 44562
WHERE galaxy_id = 3;

-- Comptes sans perso Prime : conserver Bot_IA* et Teome ; retirer le reste (PreCU-only).
DELETE FROM account_ips;
DELETE FROM account_log WHERE account_id NOT IN (
  SELECT account_id FROM (
    SELECT DISTINCT account_id FROM characters WHERE galaxy_id = 3
    UNION SELECT account_id FROM accounts WHERE username IN ('Teome') OR username LIKE 'Bot_IA%'
  ) AS keep_accounts
);

DELETE FROM account_bans WHERE account_id NOT IN (
  SELECT account_id FROM (
    SELECT DISTINCT account_id FROM characters WHERE galaxy_id = 3
    UNION SELECT account_id FROM accounts WHERE username IN ('Teome') OR username LIKE 'Bot_IA%'
  ) AS keep_accounts
);

DELETE FROM accounts WHERE account_id NOT IN (
  SELECT account_id FROM (
    SELECT DISTINCT account_id FROM characters WHERE galaxy_id = 3
    UNION SELECT account_id FROM accounts WHERE username IN ('Teome') OR username LIKE 'Bot_IA%'
  ) AS keep_accounts
);

SELECT 'galaxy' AS what, galaxy_id, name, address, port, pingport FROM galaxy ORDER BY galaxy_id;
SELECT 'characters_g3' AS what, COUNT(*) AS n FROM characters WHERE galaxy_id = 3;
SELECT 'accounts' AS what, account_id, username, admin_level FROM accounts ORDER BY account_id;
