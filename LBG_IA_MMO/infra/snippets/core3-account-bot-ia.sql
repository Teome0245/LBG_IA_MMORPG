-- Compte joueur pour tests pont IA (mot de passe à définir via procédure SWGEmu / outil habituel).
-- admin_level = 0 (joueur simple). Adapter username si besoin.

INSERT INTO accounts (username, password, salt, account_id, station_id, admin_level, active)
SELECT 'Bot_IA', '', SUBSTRING(MD5(RAND()), 1, 32), COALESCE(MAX(account_id), 0) + 1, 0, 0, 1
FROM accounts
WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE username = 'Bot_IA');

SELECT account_id, username, admin_level, active FROM accounts WHERE username = 'Bot_IA';
