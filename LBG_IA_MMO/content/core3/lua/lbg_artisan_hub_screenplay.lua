-- Hub artisan LBG — distributeur Mod+ (admin_level >= 2)
-- Chat spatial : lbg_artisan help | list | give <id> | kit <id>
-- Pont IA : dispense|Joueur|tatooine|0|0|0|<item_id|kit:id>
-- Doc : docs/core3_artisan_hub.md

local LBG_AH_ZONE = "tatooine"
local LBG_AH_CMD = "lbg_artisan"
local LBG_AH_MIN_ADMIN = 2
local LBG_AH_ACCOUNT_FILE = "ia_bridge/lbg_account_admin.json"
local LBG_AH_AUDIT_FILE = "ia_bridge/artisan_dispense_audit.jsonl"
local LBG_AH_SPAWN_STATE = "ia_bridge/artisan_hub_spawn.json"
local LBG_AH_JSON_PATHS = {
	"ia_bridge/core3_artisan_dispenser.json",
	"core3_artisan_dispenser.json",
	"/opt/LBG_IA_MMO/content/core3/core3_artisan_dispenser.json",
}
local LBG_AH_RESOURCE_JSON_PATHS = {
	"ia_bridge/core3_resource_samples.json",
	"core3_resource_samples.json",
	"/opt/LBG_IA_MMO/content/core3/core3_resource_samples.json",
}

LbgArtisanHubScreenPlay = ScreenPlay:new {
	numberOfActs = 1,
	screenplayName = "LbgArtisanHubScreenPlay",
}

registerScreenPlay("LbgArtisanHubScreenPlay", true)

function LbgArtisanHubScreenPlay:start()
	if (not isZoneEnabled(LBG_AH_ZONE)) then
		createEvent(5000, "LbgArtisanHubScreenPlay", "start", nil, "")
		return
	end
	self:loadCatalog()
	printf("LbgArtisanHub: actif zone=%s (Mod+ admin>=%d)\n", LBG_AH_ZONE, LBG_AH_MIN_ADMIN)
	createEvent(3000, "LbgArtisanHubScreenPlay", "ensureHubSpawned", nil, "")
	createEvent(5000, "LbgArtisanHubScreenPlay", "pollDispenseQueue", nil, "")
end

function LbgArtisanHubScreenPlay:readTextFile(path)
	local f = io.open(path, "r")
	if (f == nil) then
		return nil
	end
	local body = f:read("*a")
	f:close()
	return body
end

function LbgArtisanHubScreenPlay:loadCatalog()
	if (self._catalog ~= nil) then
		return self._catalog
	end
	for i = 1, #LBG_AH_JSON_PATHS do
		local body = self:readTextFile(LBG_AH_JSON_PATHS[i])
		if (body ~= nil and body ~= "" and type(ia_json_decode) == "function") then
			local doc, err = ia_json_decode(body)
			if (doc ~= nil) then
				self._catalog = doc
				self._itemIndex = self:buildItemIndex(doc)
				printf("LbgArtisanHub: catalogue charge (%s)\n", LBG_AH_JSON_PATHS[i])
				return doc
			end
			printf("LbgArtisanHub: JSON erreur %s — %s\n", LBG_AH_JSON_PATHS[i], tostring(err))
		end
	end
	self._catalog = {}
	self._itemIndex = {}
	return self._catalog
end

function LbgArtisanHubScreenPlay:buildItemIndex(doc)
	local idx = {}
	local cats = doc.categories
	if (cats == nil) then
		return idx
	end
	for c = 1, #cats do
		local cat = cats[c]
		local catId = tostring(cat.id or "")
		local items = cat.items
		if (items ~= nil) then
			for j = 1, #items do
				local row = items[j]
				local iid = tostring(row.id or "")
				if (iid ~= "") then
					idx[iid] = row
					if (catId ~= "") then
						idx[catId .. "." .. iid] = row
					end
				end
			end
		end
	end
	return idx
end

function LbgArtisanHubScreenPlay:loadResourceCatalog()
	if (self._resourceCatalog ~= nil) then
		return self._resourceCatalog
	end
	for i = 1, #LBG_AH_RESOURCE_JSON_PATHS do
		local body = self:readTextFile(LBG_AH_RESOURCE_JSON_PATHS[i])
		if (body ~= nil and body ~= "" and type(ia_json_decode) == "function") then
			local doc, err = ia_json_decode(body)
			if (doc ~= nil) then
				self._resourceCatalog = doc
				self._resourceIndex = self:buildResourceIndex(doc)
				printf("LbgArtisanHub: ressources chargees (%s)\n", LBG_AH_RESOURCE_JSON_PATHS[i])
				return doc
			end
			printf("LbgArtisanHub: ressources JSON erreur %s — %s\n", LBG_AH_RESOURCE_JSON_PATHS[i], tostring(err))
		end
	end
	self._resourceCatalog = {}
	self._resourceIndex = {}
	return self._resourceCatalog
end

function LbgArtisanHubScreenPlay:buildResourceIndex(doc)
	local idx = {}
	local families = doc.families
	if (families == nil) then
		return idx
	end
	for f = 1, #families do
		local fam = families[f]
		local famId = tostring(fam.id or "")
		local samples = fam.samples
		if (samples ~= nil) then
			for j = 1, #samples do
				local row = samples[j]
				local sid = tostring(row.id or "")
				if (sid ~= "") then
					idx[sid] = row
					if (famId ~= "") then
						idx[famId .. "." .. sid] = row
					end
				end
			end
		end
	end
	return idx
end

function LbgArtisanHubScreenPlay:hubCell()
	local doc = self:loadCatalog()
	local hub = doc.hub
	if (hub ~= nil and hub.cell ~= nil) then
		return tonumber(hub.cell) or 1189639
	end
	return 1189639
end

function LbgArtisanHubScreenPlay:ensureHubSpawned()
	local doc = self:loadCatalog()
	local hub = doc.hub
	if (hub == nil) then
		createEvent(60000, "LbgArtisanHubScreenPlay", "ensureHubSpawned", nil, "")
		return
	end
	local cell = tonumber(hub.cell) or 1189639
	local hubRev = 2
	if (readData("lbg_artisan_hub_spawn_rev") == hubRev) then
		createEvent(120000, "LbgArtisanHubScreenPlay", "ensureHubSpawned", nil, "")
		return
	end
	local zone = tostring(hub.zone or LBG_AH_ZONE)
	local spawned = 0
	local term = hub.terminal
	if (term ~= nil and term.template ~= nil) then
		local p = spawnSceneObject(zone, term.template, term.x, term.z, term.y, cell, 1, 0, 0, 0)
		if (p ~= nil) then
			spawned = spawned + 1
		end
	end
	local bazaar = hub.bazaar_terminal
	if (bazaar ~= nil and bazaar.template ~= nil) then
		local pB = spawnSceneObject(zone, bazaar.template, bazaar.x, bazaar.z, bazaar.y, cell, 1, 0, 0, 0)
		if (pB ~= nil) then
			spawned = spawned + 1
		end
	end
	local stations = hub.stations
	if (stations ~= nil) then
		for i = 1, #stations do
			local s = stations[i]
			if (s.template ~= nil) then
				local pObj = spawnSceneObject(zone, s.template, s.x, s.z, s.y, cell, 1, 0, 0, 0)
				if (pObj ~= nil) then
					spawned = spawned + 1
				end
			end
		end
	end
	writeData("lbg_artisan_hub_spawn_rev", hubRev)
	local stamp = string.format('{"ts":%d,"spawned":%d,"cell":%d}', os.time(), spawned, cell)
	local f = io.open(LBG_AH_SPAWN_STATE, "w")
	if (f ~= nil) then
		f:write(stamp)
		f:close()
	end
	printf("LbgArtisanHub: spawn hub cell=%d objets=%d\n", cell, spawned)
	createEvent(120000, "LbgArtisanHubScreenPlay", "ensureHubSpawned", nil, "")
end

function LbgArtisanHubScreenPlay:onPlayerLoggedIn(pPlayer)
	if (pPlayer == nil) then
		return
	end
	self:ensureSpatialObserverDelayed(pPlayer, 0)
end

function LbgArtisanHubScreenPlay:ensureSpatialObserverDelayed(pPlayer, attempt)
	if (pPlayer == nil) then
		return
	end
	local n = tonumber(attempt) or 0
	if (self:isModeratorPlus(pPlayer)) then
		self:ensureSpatialObserver(pPlayer)
		if (n == 0) then
			self:msg(pPlayer, "Hub artisan : chat Spatial → lbg_artisan help")
		end
		return
	end
	if (n < 6) then
		createEvent(4000, "LbgArtisanHubScreenPlay", "ensureSpatialObserverDelayed", pPlayer, tostring(n + 1))
	end
end

function LbgArtisanHubScreenPlay:ensureSpatialObserver(pPlayer)
	if (pPlayer == nil) then
		return
	end
	pcall(function()
		if (not hasObserver(CHAT, "LbgArtisanHubScreenPlay", "onSpatialChat", pPlayer)) then
			createObserver(CHAT, "LbgArtisanHubScreenPlay", "onSpatialChat", pPlayer, 1)
		end
		if (not hasObserver(SPATIALCHATSENT, "LbgArtisanHubScreenPlay", "onSpatialChat", pPlayer)) then
			createObserver(SPATIALCHATSENT, "LbgArtisanHubScreenPlay", "onSpatialChat", pPlayer, 1)
		end
	end)
end

function LbgArtisanHubScreenPlay:onSpatialChat(pPlayer, pChatMessage, arg2)
	if (pPlayer == nil or pChatMessage == nil) then
		return 0
	end
	if (not self:isModeratorPlus(pPlayer)) then
		return 0
	end
	local raw = getChatMessage(pChatMessage)
	if (raw == nil or raw == "") then
		return 0
	end
	local rest = self:normalizeChatLine(raw)
	if (rest == nil or string.sub(rest, 1, #LBG_AH_CMD) ~= LBG_AH_CMD) then
		return 0
	end
	local cmd = string.gsub(rest, "^" .. LBG_AH_CMD .. "%s*", "")
	pcall(function()
		self:handleCommand(pPlayer, cmd)
	end)
	return 0
end

function LbgArtisanHubScreenPlay:normalizeChatLine(raw)
	local msg = tostring(raw or "")
	msg = string.gsub(msg, "^%s+", "")
	msg = string.gsub(msg, "%s+$", "")
	msg = string.gsub(msg, "^%.+", "")
	msg = string.lower(msg)
	if (string.sub(msg, 1, 1) == "/") then
		msg = string.sub(msg, 2)
	end
	return msg
end

function LbgArtisanHubScreenPlay:handleCommand(pPlayer, line)
	line = tostring(line or "")
	if (line == "" or line == "help") then
		self:msg(pPlayer, "lbg_artisan list | listres | give <id> | res <id> [unites] | kit <id> | reskit <id> | tp")
		self:msg(pPlayer, "Ex: give weapon_tool | res steel 10000 | kit workshop_starter")
		return
	end
	if (line == "list") then
		self:cmdList(pPlayer)
		return
	end
	if (line == "listres") then
		self:cmdListResources(pPlayer)
		return
	end
	if (line == "tp" or line == "hub") then
		self:teleportToHub(pPlayer)
		return
	end
	local giveId = string.match(line, "^give%s+(.+)$")
	if (giveId ~= nil) then
		self:dispenseItemId(pPlayer, giveId)
		return
	end
	local kitId = string.match(line, "^kit%s+(.+)$")
	if (kitId ~= nil) then
		self:dispenseKit(pPlayer, kitId)
		return
	end
	local resKitId = string.match(line, "^reskit%s+(.+)$")
	if (resKitId ~= nil) then
		self:dispenseResourceKit(pPlayer, resKitId)
		return
	end
	local resLine = string.match(line, "^res%s+(.+)$")
	if (resLine ~= nil) then
		local rid, units = string.match(resLine, "^(%S+)%s+(%d+)$")
		if (rid == nil) then
			rid = resLine
			units = nil
		end
		self:dispenseResourceId(pPlayer, rid, units)
		return
	end
	self:msg(pPlayer, "Commande inconnue. lbg_artisan help")
end

function LbgArtisanHubScreenPlay:cmdList(pPlayer)
	local doc = self:loadCatalog()
	local cats = doc.categories
	if (cats == nil) then
		self:msg(pPlayer, "Catalogue vide.")
		return
	end
	for c = 1, #cats do
		local cat = cats[c]
		self:msg(pPlayer, "— " .. tostring(cat.label or cat.id))
		local items = cat.items
		if (items ~= nil) then
			for j = 1, #items do
				local row = items[j]
				self:msg(pPlayer, "  " .. tostring(row.id) .. " : " .. tostring(row.label))
			end
		end
	end
	local kits = doc.kits
	if (kits ~= nil and #kits > 0) then
		self:msg(pPlayer, "— Kits")
		for k = 1, #kits do
			self:msg(pPlayer, "  kit " .. tostring(kits[k].id) .. " : " .. tostring(kits[k].label))
		end
	end
end

function LbgArtisanHubScreenPlay:cmdListResources(pPlayer)
	local doc = self:loadResourceCatalog()
	local families = doc.families
	if (families == nil or #families == 0) then
		self:msg(pPlayer, "Catalogue ressources vide (deploy core3_resource_samples.json).")
		return
	end
	for f = 1, #families do
		local fam = families[f]
		self:msg(pPlayer, "— " .. tostring(fam.label or fam.id))
		local samples = fam.samples
		if (samples ~= nil) then
			for j = 1, #samples do
				local row = samples[j]
				self:msg(pPlayer, "  res " .. tostring(row.id) .. " : " .. tostring(row.label))
			end
		end
	end
	local kits = doc.kits
	if (kits ~= nil and #kits > 0) then
		self:msg(pPlayer, "— Kits ressources")
		for k = 1, #kits do
			self:msg(pPlayer, "  reskit " .. tostring(kits[k].id) .. " : " .. tostring(kits[k].label))
		end
	end
end

function LbgArtisanHubScreenPlay:teleportToHub(pPlayer)
	if (not self:isModeratorPlus(pPlayer)) then
		self:msg(pPlayer, "Acces refuse (Mod+ requis).")
		return
	end
	local doc = self:loadCatalog()
	local hub = doc.hub
	local cell = self:hubCell()
	local ent = hub.entry or { x = -12.5, y = -6.2, z = 1.13 }
	CreatureObject(pPlayer):teleport(ent.x, ent.z, ent.y, cell)
	self:msg(pPlayer, "Hub artisan — centre entrainement ME.")
end

function LbgArtisanHubScreenPlay:resolveItem(itemKey)
	self:loadCatalog()
	local key = tostring(itemKey or "")
	if (self._itemIndex[key] ~= nil) then
		return self._itemIndex[key]
	end
	local short = string.match(key, "^[^%.]+%.(.+)$")
	if (short ~= nil and self._itemIndex[short] ~= nil) then
		return self._itemIndex[short]
	end
	return nil
end

function LbgArtisanHubScreenPlay:giveTemplate(pPlayer, template, qty, label)
	if (pPlayer == nil or template == nil or template == "") then
		return false
	end
	qty = tonumber(qty) or 1
	if (qty < 1) then
		qty = 1
	end
	local pInv = SceneObject(pPlayer):getSlottedObject("inventory")
	if (pInv == nil) then
		self:msg(pPlayer, "Inventaire indisponible.")
		return false
	end
	local given = 0
	for _ = 1, qty do
		local ok = false
		pcall(function()
			local pItem = giveItem(pInv, template, -1, true)
			ok = (pItem ~= nil)
		end)
		if (ok) then
			given = given + 1
		end
	end
	if (given > 0) then
		self:msg(pPlayer, "Recu : " .. tostring(label or template) .. " x" .. tostring(given))
		self:auditDispense(pPlayer, template, given)
		return true
	end
	self:msg(pPlayer, "Echec distribution : " .. tostring(template))
	return false
end

function LbgArtisanHubScreenPlay:resolveResource(itemKey)
	self:loadResourceCatalog()
	local key = tostring(itemKey or "")
	if (self._resourceIndex[key] ~= nil) then
		return self._resourceIndex[key]
	end
	local short = string.match(key, "^[^%.]+%.(.+)$")
	if (short ~= nil and self._resourceIndex[short] ~= nil) then
		return self._resourceIndex[short]
	end
	return nil
end

function LbgArtisanHubScreenPlay:dispenseResourceId(pPlayer, itemKey, units)
	if (not self:isModeratorPlus(pPlayer)) then
		self:msg(pPlayer, "Acces refuse (Mod+ requis).")
		return false
	end
	local row = self:resolveResource(itemKey)
	if (row == nil) then
		self:msg(pPlayer, "Ressource inconnue : " .. tostring(itemKey) .. " — lbg_artisan listres")
		return false
	end
	local doc = self:loadResourceCatalog()
	local qty = tonumber(units) or tonumber(doc.default_units) or 10000
	local maxU = tonumber(doc.max_units) or 30000
	if (qty > maxU) then
		qty = maxU
	end
	local rtype = tostring(row.resource_type or row.id or "")
	if (type(iaGiveResourceSample) ~= "function") then
		self:msg(pPlayer, "Ressources dynamiques : rebuild core3-clean requis (iaGiveResourceSample).")
		return false
	end
	local ok = false
	pcall(function()
		ok = iaGiveResourceSample(pPlayer, rtype, qty)
	end)
	if (ok) then
		self:msg(pPlayer, "Ressource " .. tostring(row.label or row.id) .. " x" .. tostring(qty))
		self:auditDispense(pPlayer, "resource:" .. rtype, qty)
		return true
	end
	self:msg(pPlayer, "Echec ressource " .. rtype .. " (type serveur invalide ?).")
	return false
end

function LbgArtisanHubScreenPlay:dispenseResourceKit(pPlayer, kitId)
	if (not self:isModeratorPlus(pPlayer)) then
		self:msg(pPlayer, "Acces refuse (Mod+ requis).")
		return false
	end
	local doc = self:loadResourceCatalog()
	local kits = doc.kits
	if (kits == nil) then
		self:msg(pPlayer, "Aucun kit ressource.")
		return false
	end
	local kit = nil
	for i = 1, #kits do
		if (tostring(kits[i].id) == tostring(kitId)) then
			kit = kits[i]
			break
		end
	end
	if (kit == nil) then
		self:msg(pPlayer, "Kit ressource inconnu : " .. tostring(kitId))
		return false
	end
	local ids = kit.sample_ids
	if (ids == nil or #ids == 0) then
		return false
	end
	local n = 0
	for i = 1, #ids do
		if (self:dispenseResourceId(pPlayer, ids[i], nil)) then
			n = n + 1
		end
	end
	self:msg(pPlayer, "Reskit " .. tostring(kit.label or kitId) .. " : " .. tostring(n) .. "/" .. tostring(#ids))
	return n > 0
end

function LbgArtisanHubScreenPlay:dispenseItemId(pPlayer, itemKey)
	if (not self:isModeratorPlus(pPlayer)) then
		self:msg(pPlayer, "Acces refuse (compte Mod+ admin_level >= " .. tostring(LBG_AH_MIN_ADMIN) .. ").")
		return false
	end
	local row = self:resolveItem(itemKey)
	if (row == nil) then
		self:msg(pPlayer, "Objet inconnu : " .. tostring(itemKey) .. " — lbg_artisan list")
		return false
	end
	return self:giveTemplate(pPlayer, row.template, row.qty or 1, row.label or row.id)
end

function LbgArtisanHubScreenPlay:dispenseKit(pPlayer, kitId)
	if (not self:isModeratorPlus(pPlayer)) then
		self:msg(pPlayer, "Acces refuse (Mod+ requis).")
		return false
	end
	local doc = self:loadCatalog()
	local kits = doc.kits
	if (kits == nil) then
		self:msg(pPlayer, "Aucun kit configure.")
		return false
	end
	local kit = nil
	for i = 1, #kits do
		if (tostring(kits[i].id) == tostring(kitId)) then
			kit = kits[i]
			break
		end
	end
	if (kit == nil) then
		self:msg(pPlayer, "Kit inconnu : " .. tostring(kitId))
		return false
	end
	local ids = kit.item_ids
	if (ids == nil or #ids == 0) then
		self:msg(pPlayer, "Kit vide.")
		return false
	end
	local n = 0
	for i = 1, #ids do
		if (self:dispenseItemId(pPlayer, ids[i])) then
			n = n + 1
		end
	end
	self:msg(pPlayer, "Kit " .. tostring(kit.label or kitId) .. " : " .. tostring(n) .. "/" .. tostring(#ids))
	return n > 0
end

function LbgArtisanHubScreenPlay:handlePendingDispense(pPlayer, message)
	if (pPlayer == nil) then
		return
	end
	local msg = tostring(message or "")
	if (string.sub(msg, 1, 4) == "kit:") then
		self:dispenseKit(pPlayer, string.sub(msg, 5))
		return
	end
	if (string.sub(msg, 1, 4) == "res:") then
		local body = string.sub(msg, 5)
		local rid, units = string.match(body, "^([^:]+):?(%d*)$")
		if (rid ~= nil and units ~= nil and units ~= "") then
			self:dispenseResourceId(pPlayer, rid, units)
		else
			self:dispenseResourceId(pPlayer, body, nil)
		end
		return
	end
	if (string.sub(msg, 1, 7) == "reskit:") then
		self:dispenseResourceKit(pPlayer, string.sub(msg, 8))
		return
	end
	self:dispenseItemId(pPlayer, msg)
end

function LbgArtisanHubScreenPlay:pollDispenseQueue()
	local path = "ia_bridge/artisan_dispense.queue"
	local f = io.open(path, "r")
	if (f ~= nil) then
		local lines = {}
		for line in f:lines() do
			if (line ~= nil and line ~= "") then
				table.insert(lines, line)
			end
		end
		f:close()
		if (#lines > 0) then
			local wf = io.open(path, "w")
			if (wf ~= nil) then
				wf:close()
			end
			for _, line in ipairs(lines) do
				local oid, name, payload = string.match(line, "^([^|]+)|([^|]+)|(.*)$")
				local pPlayer = nil
				if (name ~= nil and name ~= "") then
					pPlayer = getPlayerByName(name)
				end
				if (pPlayer == nil and oid ~= nil) then
					pPlayer = getSceneObject(tonumber(oid))
				end
				if (pPlayer ~= nil) then
					pcall(function()
						self:handlePendingDispense(pPlayer, payload)
					end)
				end
			end
		end
	end
	createEvent(2000, "LbgArtisanHubScreenPlay", "pollDispenseQueue", nil, "")
end

function LbgArtisanHubScreenPlay:auditDispense(pPlayer, template, qty)
	local name = ""
	pcall(function()
		name = CreatureObject(pPlayer):getFirstName()
	end)
	local line = string.format(
		'{"ts":%d,"player":"%s","template":"%s","qty":%d}',
		os.time(),
		name,
		tostring(template),
		tonumber(qty) or 1
	)
	local f = io.open(LBG_AH_AUDIT_FILE, "a")
	if (f ~= nil) then
		f:write(line)
		f:write("\n")
		f:close()
	end
end

function LbgArtisanHubScreenPlay:msg(pPlayer, text)
	pcall(function()
		CreatureObject(pPlayer):sendSystemMessage("[Artisan] " .. tostring(text))
	end)
end

function LbgArtisanHubScreenPlay:loadAccountAdminCache()
	local cache = { by_account_id = {}, by_firstname = {} }
	local f = io.open(LBG_AH_ACCOUNT_FILE, "r")
	if (f == nil) then
		return cache
	end
	local body = f:read("*a")
	f:close()
	if (body == nil or body == "") then
		return cache
	end
	for ln in string.gmatch(body, "[^\r\n]+") do
		local accId, lvl = string.match(ln, "^account:(%d+)=(%d+)$")
		if (accId ~= nil) then
			cache.by_account_id[accId] = tonumber(lvl) or 0
		end
		local fname, flvl = string.match(ln, "^firstname:([^=]+)=(%d+)$")
		if (fname ~= nil) then
			cache.by_firstname[string.lower(fname)] = tonumber(flvl) or 0
		end
	end
	return cache
end

function LbgArtisanHubScreenPlay:getAccountAdminCache()
	if (self._accountAdminCache == nil) then
		self._accountAdminCache = self:loadAccountAdminCache()
	end
	return self._accountAdminCache
end

function LbgArtisanHubScreenPlay:getPlayerAdminLevel(pPlayer)
	local ok, lvl = pcall(function()
		local pGhost = CreatureObject(pPlayer):getPlayerObject()
		if (pGhost == nil) then
			return 0
		end
		if (PlayerObject(pGhost):hasGodMode()) then
			return 99
		end
		return PlayerObject(pGhost):getAdminLevel()
	end)
	if (not ok) then
		return 0
	end
	return tonumber(lvl) or 0
end

function LbgArtisanHubScreenPlay:getAccountAdminLevel(pPlayer)
	local ok, lvl = pcall(function()
		local pGhost = CreatureObject(pPlayer):getPlayerObject()
		if (pGhost == nil) then
			return 0
		end
		local accId = PlayerObject(pGhost):getAccountID()
		local cache = self:getAccountAdminCache()
		local fromAcc = cache.by_account_id[tostring(accId)]
		if (fromAcc ~= nil) then
			return fromAcc
		end
		local fn = string.lower(CreatureObject(pPlayer):getFirstName())
		return cache.by_firstname[fn] or 0
	end)
	if (not ok) then
		return 0
	end
	return tonumber(lvl) or 0
end

function LbgArtisanHubScreenPlay:getEffectiveAdmin(pPlayer)
	local doc = self:loadCatalog()
	local minLvl = tonumber(doc.min_admin_level) or LBG_AH_MIN_ADMIN
	local pLvl = self:getPlayerAdminLevel(pPlayer)
	local aLvl = self:getAccountAdminLevel(pPlayer)
	if (pLvl >= minLvl) then
		return pLvl
	end
	if (aLvl >= minLvl and pLvl == 0) then
		return aLvl
	end
	if (pLvl > 0 and aLvl > 0) then
		return math.min(aLvl, pLvl)
	end
	return math.max(pLvl, aLvl)
end

function LbgArtisanHubScreenPlay:isModeratorPlus(pPlayer)
	local doc = self:loadCatalog()
	local minLvl = tonumber(doc.min_admin_level) or LBG_AH_MIN_ADMIN
	return self:getEffectiveAdmin(pPlayer) >= minLvl
end
