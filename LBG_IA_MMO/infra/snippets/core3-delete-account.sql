-- Suppression complète d'un compte Core3 / SWGEmu (MariaDB swgemu).
-- Usage : remplacer @USERNAME puis exécuter sur la VM :
--   mysql -u swgemu -p swgemu < core3-delete-account.sql
-- Ou : mysql -u swgemu -p swgemu -e "SET @USERNAME='steve'; SOURCE core3-delete-account.sql;"

SET @USERNAME = 'steve';

SELECT account_id, username, admin_level, active
FROM accounts WHERE LOWER(username) = LOWER(@USERNAME);

SET @AID = (SELECT account_id FROM accounts WHERE LOWER(username) = LOWER(@USERNAME) LIMIT 1);

SELECT IF(@AID IS NULL, 'Compte introuvable — rien à supprimer', CONCAT('Suppression account_id=', @AID)) AS status;

DELETE FROM sessions WHERE account_id = @AID;
DELETE FROM account_bans WHERE account_id = @AID OR issuer_id = @AID;
DELETE FROM account_log WHERE account_id = @AID;
DELETE FROM account_ips WHERE account_id = @AID;
DELETE FROM galaxy_bans WHERE account_id = @AID OR issuer_id = @AID;
DELETE FROM character_bans WHERE account_id = @AID OR issuer_id = @AID;
DELETE FROM characters WHERE account_id = @AID;
DELETE FROM characters_dirty WHERE account_id = @AID;
DELETE FROM deleted_characters WHERE account_id = @AID;
DELETE FROM accounts WHERE account_id = @AID;

SELECT account_id, username FROM accounts WHERE LOWER(username) = LOWER(@USERNAME);
