-- Migration one-shot / maintenance : anciens admin_level SWGEmu (0–15) → LBG (0–4)
-- ADR 0006. Exécuter après la période de double lecture si souhaité.
--   mysql -u swgemu -p swgemu < core3-admin-level-migrate-lbg.sql

SELECT account_id, username, admin_level AS avant FROM accounts ORDER BY account_id;

UPDATE accounts SET admin_level = CASE
  WHEN admin_level IN (0) THEN 0
  WHEN admin_level IN (1, 2, 3, 6) THEN 1
  WHEN admin_level IN (7, 8, 9, 10, 11, 12) THEN 2
  WHEN admin_level IN (13, 14) THEN 3
  WHEN admin_level >= 15 THEN 4
  ELSE 0
END;

SELECT account_id, username, admin_level AS apres FROM accounts ORDER BY account_id;
