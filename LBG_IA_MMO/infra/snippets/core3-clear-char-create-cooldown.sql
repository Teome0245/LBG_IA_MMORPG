-- Débloque la création de perso (côté SQL) pour un compte sur une galaxie.
-- Utile après tests Bot_IA / suppressions rapides. Redémarrer core3 si le cache mémoire bloque encore.
--
-- Usage (ex. Bot_IA, Prime galaxy_id = 3) :
--   SET @user = 'Bot_IA';
--   SET @gid = 3;

SET @user = 'Bot_IA';
SET @gid = 3;

SELECT account_id, username FROM accounts WHERE username = @user;

DELETE FROM deleted_characters
WHERE account_id = (SELECT account_id FROM accounts WHERE username = @user LIMIT 1)
  AND galaxy_id = @gid;

-- Option : ne garder que les persos existants (ne supprime pas les persos actifs)
-- UPDATE characters SET creation_date = DATE_SUB(NOW(), INTERVAL 2 DAY)
-- WHERE account_id = (SELECT account_id FROM accounts WHERE username = @user LIMIT 1)
--   AND galaxy_id = @gid;
