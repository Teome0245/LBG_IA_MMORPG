-- LBG World Editor v1 — PNJ + POI (Dev+ admin_level >= 3)
-- Plan : docs/world_editor_plan.md
-- Commandes in-game : chat Spatial « lbg_we … » ou slash « /lbgwe … » (C++)
local LBG_WE_ZONE = "tatooine"
local LBG_WE_MIN_ADMIN = 3
local LBG_WE_CMD_PREFIX = "lbg_we"
local LBG_WE_SLASH_CMD = "lbgwe"
local LBG_WE_SESSION_FILE = "ia_bridge/world_editor_session.json"
local LBG_WE_EXPORT_QUEUE = "ia_bridge/world_editor_export.queue"
local LBG_WE_AUDIT_FILE = "ia_bridge/world_editor_audit.jsonl"
local LBG_WE_POI_RUNTIME = "ia_bridge/world_poi/tatooine.json"
local LBG_WE_POI_REPO = "/opt/LBG_IA_MMO/content/core3/world_poi/tatooine.json"
local LBG_WE_POI_SCRAPALTAI_RUNTIME = "ia_bridge/world_poi/scrapaltai.json"
local LBG_WE_POI_SCRAPALTAI_REPO = "/opt/LBG_IA_MMO/content/core3/world_poi/scrapaltai.json"
local LBG_WE_POI_DEFAULT = "poi:lost_heaven_starport"
-- Lost Heaven hub (ADR 0009, recon Teome 2026-06-01)
local LBG_WE_LOST_HEAVEN_X = 4749
local LBG_WE_LOST_HEAVEN_Y = -737
local LBG_WE_LOST_HEAVEN_Z = 12
local LBG_WE_TERRAIN_LAY = "terrain/poi_large.lay"
local LBG_WE_BOWL_LAY = "terrain/poi_bowl.lay"
local LBG_WE_TERRAIN_MOD_STATE = "ia_bridge/lbg_we_terrain_mod_ids.txt"
local LBG_WE_BOWL_MOD_STATE = "ia_bridge/lbg_we_bowl_mod_ids.txt"
local LBG_WE_THEATER_STATE = "ia_bridge/lbg_we_theater_oids.txt"
local LBG_WE_STARPORT_TEMPLATE = "object/building/tatooine/shuttleport_tatooine.iff"
local LBG_WE_STARPORT_POI = "poi:lost_heaven_starport"
local LBG_WE_ACCOUNT_ADMIN_FILE = "ia_bridge/lbg_account_admin.json"
-- Comptes Dev+ à ré-attacher si déjà connectés au boot (évite relog obligatoire)
local LBG_WE_DEV_WATCH = { }

LbgWorldEditorScreenPlay = ScreenPlay:new {
	numberOfActs = 1,
	screenplayName = "LbgWorldEditorScreenPlay",
}

registerScreenPlay("LbgWorldEditorScreenPlay", true)

function LbgWorldEditorScreenPlay:start()
	if (not isZoneEnabled(LBG_WE_ZONE)) then
		createEvent(5000, "LbgWorldEditorScreenPlay", "start", nil, "")
		return
	end
	printf("LbgWorldEditor: actif zone=%s (Dev+ admin>=%d)\n", LBG_WE_ZONE, LBG_WE_MIN_ADMIN)
	createEvent(2000, "LbgWorldEditorScreenPlay", "pollCmdQueue", nil, "")
	createEvent(2000, "LbgWorldEditorScreenPlay", "pollTerrainApply", nil, "")
	createEvent(5000, "LbgWorldEditorScreenPlay", "pollAttachObservers", nil, "")
	createEvent(15000, "LbgWorldEditorScreenPlay", "replaySavedPlateauOnBoot", nil, "")
end

function LbgWorldEditorScreenPlay:replaySavedPlateauOnBoot()
	if (LbgTerrainLib == nil) then
		return
	end
	if (LbgTerrainLib.sanitizeBloatedIdFiles()) then
		printf("LbgWorldEditor: replay boot ignore — IDs purgés, restart Core3 requis\n")
		return
	end
	local cfg = LbgTerrainLib.loadPlateauConfig()
	if (cfg == nil) then
		return
	end
	local live, expected = LbgTerrainLib.hubPlateauLive(cfg.theaterIdFile, cfg.halfCells)
	if (live >= expected - 2) then
		printf("LbgWorldEditor: plateau deja actif (%d/%d theaters)\n", live, expected)
		return
	end
	local r, err = LbgTerrainLib.replaySavedPlateau(true)
	if (r == nil) then
		printf("LbgWorldEditor: replay plateau ignore — %s\n", tostring(err))
		return
	end
	printf("LbgWorldEditor: replay plateau @ %.0f,%.0f theaters=%d flatten=%d\n",
		r.cx, r.cy, r.theater_count, r.flatten_count)
end

function LbgWorldEditorScreenPlay:pollAttachObservers()
	for _, name in ipairs(LBG_WE_DEV_WATCH) do
		local pPlayer = getPlayerByName(name)
		if (pPlayer ~= nil and self:isDevPlus(pPlayer)) then
			self:ensureSpatialObserver(pPlayer)
		end
	end
	createEvent(30000, "LbgWorldEditorScreenPlay", "pollAttachObservers", nil, "")
end

function LbgWorldEditorScreenPlay:pollCmdQueue()
	local path = "ia_bridge/world_editor_cmd.queue"
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
				local oid, name, cmd = string.match(line, "^([^|]+)|([^|]+)|(.*)$")
				if (cmd ~= nil and cmd ~= "") then
					local pPlayer = self:resolvePlayerForQueue(oid, name)
					if (pPlayer == nil) then
						printf("LbgWorldEditor: pollCmdQueue skip (joueur absent) oid=%s name=%s cmd=%s\n",
							tostring(oid), tostring(name), tostring(cmd))
					elseif (not self:isDevPlus(pPlayer)) then
						local eff = self:getEffectiveAdmin(pPlayer)
						printf("LbgWorldEditor: pollCmdQueue skip (pas Dev+) name=%s player=%d account=%d eff=%d cmd=%s\n",
							self:getActorName(pPlayer), self:getPlayerAdminLevel(pPlayer),
							self:getAccountAdminLevel(pPlayer), eff, tostring(cmd))
					else
						local ok, err = pcall(function()
							self:handleCommand(pPlayer, cmd)
						end)
						if (not ok) then
							printf("LbgWorldEditor: pollCmdQueue error: %s\n", tostring(err))
						else
							printf("LbgWorldEditor: pollCmdQueue ok name=%s cmd=%s\n",
								self:getActorName(pPlayer), tostring(cmd))
						end
					end
				end
			end
		end
	end
	createEvent(500, "LbgWorldEditorScreenPlay", "pollCmdQueue", nil, "")
end

function LbgWorldEditorScreenPlay:pollTerrainApply()
	if (LbgTerrainLib ~= nil and LbgTerrainLib.processHeadlessTerrainApply ~= nil) then
		pcall(function()
			LbgTerrainLib.processHeadlessTerrainApply()
		end)
	end
	createEvent(2000, "LbgWorldEditorScreenPlay", "pollTerrainApply", nil, "")
end

function LbgWorldEditorScreenPlay:onPlayerLoggedIn(pPlayer)
	if (pPlayer == nil) then
		return
	end
	-- Ghost parfois indisponible au premier tick login : retries
	self:ensureSpatialObserverDelayed(pPlayer, 0)
end

function LbgWorldEditorScreenPlay:ensureSpatialObserverDelayed(pPlayer, attempt)
	if (pPlayer == nil) then
		return
	end
	local n = tonumber(attempt) or 0
	if (self:isDevPlus(pPlayer)) then
		self:ensureSpatialObserver(pPlayer)
		if (n == 0) then
			self:msg(pPlayer, "World Editor: onglet Spatial → lbg_we session on (sans /)")
			printf("LbgWorldEditor: hooks actifs pour %s\n", self:getActorName(pPlayer))
		end
		return
	end
	if (n < 8) then
		createEvent(3000, "LbgWorldEditorScreenPlay", "ensureSpatialObserverDelayed", pPlayer, tostring(n + 1))
	elseif (n == 8) then
		printf("LbgWorldEditor: pas Dev+ pour %s (player=%d account=%d) — cache %s ?\n",
			self:getActorName(pPlayer), self:getPlayerAdminLevel(pPlayer),
			self:getAccountAdminLevel(pPlayer), LBG_WE_ACCOUNT_ADMIN_FILE)
	end
end

-- Appelé par la commande slash C++ /lbgwe (LbgWeCommand.h)
function LbgWorldEditorScreenPlay:handleSlashCommand(pPlayer, line)
	if (pPlayer == nil) then
		return
	end
	local ok, err = pcall(function()
		if (not self:isDevPlus(pPlayer)) then
			self:msg(pPlayer, "Accès refusé (Dev+ admin >= " .. tostring(LBG_WE_MIN_ADMIN) .. ")")
			return
		end
		self:handleCommand(pPlayer, line or "")
	end)
	if (not ok) then
		printf("LbgWorldEditor: handleSlashCommand error: %s\n", tostring(err))
		self:msg(pPlayer, "Erreur World Editor (voir log serveur)")
	end
end

function LbgWorldEditorScreenPlay:normalizeChatLine(raw)
	local msg = tostring(raw or "")
	msg = string.gsub(msg, "^%s+", "")
	msg = string.gsub(msg, "%s+$", "")
	msg = string.gsub(msg, "^%.+", "")
	msg = string.gsub(msg, "^%?+", "")
	msg = string.gsub(msg, "[%.%?]+$", "")
	msg = string.lower(msg)
	if (string.sub(msg, 1, 1) == "/") then
		msg = string.sub(msg, 2)
		msg = string.gsub(msg, "^%s+", "")
	end
	if (string.sub(msg, 1, #LBG_WE_SLASH_CMD) == LBG_WE_SLASH_CMD) then
		msg = string.sub(msg, #LBG_WE_SLASH_CMD + 1)
		msg = string.gsub(msg, "^%s+", "")
		return msg
	end
	if (string.sub(msg, 1, #LBG_WE_CMD_PREFIX) == LBG_WE_CMD_PREFIX) then
		msg = string.sub(msg, #LBG_WE_CMD_PREFIX + 1)
		msg = string.gsub(msg, "^%s+", "")
		return msg
	end
	return nil
end

function LbgWorldEditorScreenPlay:attachChatObserver(pPlayer, eventType, methodName)
	if (pPlayer == nil) then
		return
	end
	pcall(function()
		if (not hasObserver(eventType, "LbgWorldEditorScreenPlay", methodName, pPlayer)) then
			createObserver(eventType, "LbgWorldEditorScreenPlay", methodName, pPlayer, 1)
		end
	end)
end

function LbgWorldEditorScreenPlay:ensureSpatialObserver(pPlayer)
	if (pPlayer == nil) then
		return
	end
	-- CHAT = notifyObservers dans ChatManager::handleMessage (fiable pour le spatial joueur)
	self:attachChatObserver(pPlayer, CHAT, "onSpatialChat")
	-- SPATIALCHATSENT = filet de secours (async)
	self:attachChatObserver(pPlayer, SPATIALCHATSENT, "onSpatialChat")
end

function LbgWorldEditorScreenPlay:onSpatialChat(pPlayer, pChatMessage, arg2)
	if (pPlayer == nil or pChatMessage == nil) then
		return 0
	end
	if (not self:isDevPlus(pPlayer)) then
		return 0
	end
	local raw = getChatMessage(pChatMessage)
	if (raw == nil or raw == "") then
		return 0
	end
	local rest = self:normalizeChatLine(raw)
	if (rest == nil) then
		return 0
	end
	local ok, err = pcall(function()
		self:handleCommand(pPlayer, rest)
	end)
	if (not ok) then
		printf("LbgWorldEditor: onSpatialChat error: %s\n", tostring(err))
	end
	return 0
end

function LbgWorldEditorScreenPlay:resolvePlayerForQueue(oid, name)
	if (name ~= nil and name ~= "") then
		local p = getPlayerByName(name)
		if (p ~= nil) then
			return p
		end
	end
	if (oid ~= nil and oid ~= "") then
		return getSceneObject(tonumber(oid))
	end
	return nil
end

function LbgWorldEditorScreenPlay:loadAccountAdminCache()
	local cache = { by_account_id = {}, by_firstname = {} }
	local f = io.open(LBG_WE_ACCOUNT_ADMIN_FILE, "r")
	if (f == nil) then
		return cache
	end
	local body = f:read("*a")
	f:close()
	if (body == nil or body == "") then
		return cache
	end
	for line in string.gmatch(body, "[^\r\n]+") do
		local accId, lvl = string.match(line, "^account:(%d+)=(%d+)$")
		if (accId ~= nil) then
			cache.by_account_id[accId] = tonumber(lvl) or 0
		end
		local fname, flvl = string.match(line, "^firstname:([^=]+)=(%d+)$")
		if (fname ~= nil) then
			cache.by_firstname[string.lower(fname)] = tonumber(flvl) or 0
		end
	end
	return cache
end

function LbgWorldEditorScreenPlay:getAccountAdminCache()
	if (self._accountAdminCache == nil) then
		self._accountAdminCache = self:loadAccountAdminCache()
	end
	return self._accountAdminCache
end

function LbgWorldEditorScreenPlay:getPlayerAdminLevel(pPlayer)
	if (pPlayer == nil) then
		return 0
	end
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

function LbgWorldEditorScreenPlay:getAccountAdminLevel(pPlayer)
	if (pPlayer == nil) then
		return 0
	end
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

-- ADR : min(compte, perso) sauf perso à 0 avec compte Dev+ (Teome gameplay normal)
function LbgWorldEditorScreenPlay:getEffectiveAdmin(pPlayer)
	local pLvl = self:getPlayerAdminLevel(pPlayer)
	local aLvl = self:getAccountAdminLevel(pPlayer)
	if (pLvl >= LBG_WE_MIN_ADMIN) then
		return pLvl
	end
	if (aLvl >= LBG_WE_MIN_ADMIN and pLvl == 0) then
		return aLvl
	end
	if (pLvl > 0 and aLvl > 0) then
		return math.min(aLvl, pLvl)
	end
	return math.max(pLvl, aLvl)
end

function LbgWorldEditorScreenPlay:isDevPlus(pPlayer)
	if (pPlayer == nil) then
		return false
	end
	return self:getEffectiveAdmin(pPlayer) >= LBG_WE_MIN_ADMIN
end

function LbgWorldEditorScreenPlay:msg(pPlayer, text)
	if (pPlayer ~= nil and text ~= nil) then
		CreatureObject(pPlayer):sendSystemMessage("[WorldEditor] " .. tostring(text))
	end
end

function LbgWorldEditorScreenPlay:audit(actor, action, detail)
	local line = string.format(
		"%s|%s|%s|%s",
		os.date("%Y-%m-%dT%H:%M:%S"),
		tostring(actor or ""),
		tostring(action or ""),
		tostring(detail or "")
	)
	local f = io.open(LBG_WE_AUDIT_FILE, "a")
	if (f ~= nil) then
		f:write(line .. "\n")
		f:close()
	end
end

function LbgWorldEditorScreenPlay:getActorName(pPlayer)
	if (pPlayer == nil) then
		return ""
	end
	return CreatureObject(pPlayer):getFirstName()
end

function LbgWorldEditorScreenPlay:getPlayerDump(pPlayer)
	local scene = SceneObject(pPlayer)
	local x = scene:getPositionX()
	local z = scene:getPositionZ()
	local y = scene:getPositionY()
	local heading = CreatureObject(pPlayer):getDirectionAngle()
	local cell = 0
	local parentId = scene:getParentID()
	if (parentId ~= nil and parentId ~= 0) then
		cell = parentId
	end
	return {
		x = x,
		y = y,
		z = z,
		cell = cell,
		heading = heading,
		zone = scene:getZoneName() or LBG_WE_ZONE,
	}
end

function LbgWorldEditorScreenPlay:loadSession()
	local f = io.open(LBG_WE_SESSION_FILE, "r")
	if (f == nil) then
		return { active = false, npc_slots = {}, poi = {} }
	end
	local body = f:read("*a")
	f:close()
	if (body == nil or body == "") then
		return { active = false, npc_slots = {}, poi = {} }
	end
	-- Format minimal ligne par ligne : active=1 actor=Foo
	local sess = { active = false, actor = "", npc_slots = {}, poi = {}, last_dump = nil }
	for line in string.gmatch(body, "[^\r\n]+") do
		local k, v = string.match(line, "^([^=]+)=(.*)$")
		if (k == "active") then
			sess.active = (v == "1" or v == "true")
		elseif (k == "actor") then
			sess.actor = v
		elseif (k == "last_x") then
			sess.last_dump = sess.last_dump or {}
			sess.last_dump.x = tonumber(v)
		elseif (k == "last_y") then
			sess.last_dump = sess.last_dump or {}
			sess.last_dump.y = tonumber(v)
		elseif (k == "last_z") then
			sess.last_dump = sess.last_dump or {}
			sess.last_dump.z = tonumber(v)
		elseif (k == "last_cell") then
			sess.last_dump = sess.last_dump or {}
			sess.last_dump.cell = tonumber(v)
		elseif (k == "last_heading") then
			sess.last_dump = sess.last_dump or {}
			sess.last_dump.heading = tonumber(v)
		elseif (k == "terrain_cx") then
			sess.terrain = sess.terrain or {}
			sess.terrain.cx = tonumber(v)
		elseif (k == "terrain_cy") then
			sess.terrain = sess.terrain or {}
			sess.terrain.cy = tonumber(v)
		elseif (k == "terrain_cz") then
			sess.terrain = sess.terrain or {}
			sess.terrain.cz = tonumber(v)
		elseif (k == "terrain_step") then
			sess.terrain = sess.terrain or {}
			sess.terrain.step = tonumber(v)
		elseif (k == "terrain_half") then
			sess.terrain = sess.terrain or {}
			sess.terrain.half = tonumber(v)
		elseif (string.sub(k or "", 1, 5) == "wpoi.") then
			local poiId = string.sub(k, 6)
			local parts = {}
			for part in string.gmatch(v, "[^,]+") do
				table.insert(parts, part)
			end
			if (#parts >= 5) then
				sess.poi[poiId] = {
					template = parts[1] or "",
					x = tonumber(parts[2]) or 0,
					y = tonumber(parts[3]) or 0,
					z = tonumber(parts[4]) or 0,
					heading = tonumber(parts[5]) or 0,
					object_id = tonumber(parts[6]) or 0,
					root_cell_id = tonumber(parts[7]) or 0,
				}
			end
		elseif (string.sub(k or "", 1, 4) == "npc:") then
			-- npc:pilot_id=x,y,z,cell,heading,mobile,roster_id
			local pid = string.sub(k, 5)
			local parts = {}
			for part in string.gmatch(v, "[^,]+") do
				table.insert(parts, part)
			end
			if (#parts >= 5) then
				sess.npc_slots[pid] = {
					x = tonumber(parts[1]) or 0,
					y = tonumber(parts[2]) or 0,
					z = tonumber(parts[3]) or 0,
					cell = tonumber(parts[4]) or 0,
					heading = tonumber(parts[5]) or 0,
					mobile = parts[6] or "",
					roster_id = parts[7] or "",
				}
			end
		end
	end
	return sess
end

function LbgWorldEditorScreenPlay:normalizePoiId(poiId)
	if (poiId == nil or poiId == "") then
		return LBG_WE_POI_DEFAULT
	end
	if (string.sub(poiId, 1, 4) ~= "poi:") then
		return "poi:" .. poiId
	end
	return poiId
end

function LbgWorldEditorScreenPlay:saveSession(sess)
	if (sess == nil) then
		return
	end
	local lines = {}
	table.insert(lines, "active=" .. (sess.active and "1" or "0"))
	table.insert(lines, "actor=" .. tostring(sess.actor or ""))
	if (sess.last_dump ~= nil) then
		local d = sess.last_dump
		table.insert(lines, "last_x=" .. tostring(d.x or 0))
		table.insert(lines, "last_y=" .. tostring(d.y or 0))
		table.insert(lines, "last_z=" .. tostring(d.z or 0))
		table.insert(lines, "last_cell=" .. tostring(d.cell or 0))
		table.insert(lines, "last_heading=" .. tostring(d.heading or 0))
	end
	if (sess.terrain ~= nil) then
		local t = sess.terrain
		if (t.cx ~= nil) then table.insert(lines, "terrain_cx=" .. tostring(t.cx)) end
		if (t.cy ~= nil) then table.insert(lines, "terrain_cy=" .. tostring(t.cy)) end
		if (t.cz ~= nil) then table.insert(lines, "terrain_cz=" .. tostring(t.cz)) end
		if (t.step ~= nil) then table.insert(lines, "terrain_step=" .. tostring(t.step)) end
		if (t.half ~= nil) then table.insert(lines, "terrain_half=" .. tostring(t.half)) end
	end
	for pid, slot in pairs(sess.npc_slots or {}) do
		local v = string.format(
			"%s,%s,%s,%s,%s,%s,%s",
			tostring(slot.x or 0),
			tostring(slot.y or 0),
			tostring(slot.z or 0),
			tostring(slot.cell or 0),
			tostring(slot.heading or 0),
			tostring(slot.mobile or ""),
			tostring(slot.roster_id or "")
		)
		table.insert(lines, "npc:" .. pid .. "=" .. v)
	end
	for poiId, p in pairs(sess.poi or {}) do
		local v = string.format(
			"%s,%s,%s,%s,%s,%s,%s",
			tostring(p.template or ""),
			tostring(p.x or 0),
			tostring(p.y or 0),
			tostring(p.z or 0),
			tostring(p.heading or 0),
			tostring(p.object_id or 0),
			tostring(p.root_cell_id or 0)
		)
		table.insert(lines, "wpoi." .. poiId .. "=" .. v)
	end
	local f = io.open(LBG_WE_SESSION_FILE, "w")
	if (f ~= nil) then
		f:write(table.concat(lines, "\n") .. "\n")
		f:close()
	end
end

function LbgWorldEditorScreenPlay:requireSession(pPlayer, sess)
	if (sess ~= nil and sess.active == true) then
		return true
	end
	self:msg(pPlayer, "Session inactive. Utilise lbg_we session on (Spatial) ou /lbgwe session on")
	return false
end

function LbgWorldEditorScreenPlay:splitWords(s)
	local out = {}
	for w in string.gmatch(s or "", "%S+") do
		table.insert(out, w)
	end
	return out
end

function LbgWorldEditorScreenPlay:handleCommand(pPlayer, line)
	local words = self:splitWords(line)
	local cmd = words[1] or ""
	local actor = self:getActorName(pPlayer)
	local sess = self:loadSession()

	if (cmd == "session") then
		local mode = words[2] or ""
		if (mode == "on") then
			sess.active = true
			sess.actor = actor
			self:saveSession(sess)
			self:msg(pPlayer, "Session ON (" .. actor .. ")")
			self:audit(actor, "session_on", "")
		elseif (mode == "off") then
			sess.active = false
			self:saveSession(sess)
			self:msg(pPlayer, "Session OFF")
			self:audit(actor, "session_off", "")
		else
			self:msg(pPlayer, "Usage: /lbg_we session on|off")
		end
		return
	end

	if (cmd == "hub") then
		self:cmdHub(pPlayer, words, sess, actor)
		return
	end

	if (cmd == "terrain") then
		self:cmdTerrain(pPlayer, words, sess, actor)
		return
	end

	if (cmd == "dump") then
		local sub = words[2] or ""
		local d = self:getPlayerDump(pPlayer)
		sess.last_dump = d
		self:saveSession(sess)
		if (sub == "json") then
			self:msg(pPlayer, string.format(
				'{"x":%.2f,"y":%.2f,"z":%.2f,"cell":%s,"heading":%.1f,"zone":"%s"}',
				d.x, d.y, d.z, tostring(d.cell), d.heading, tostring(d.zone or LBG_WE_ZONE)
			))
		else
			self:msg(pPlayer, string.format(
				"dump x=%.2f y=%.2f z=%.2f cell=%s heading=%.1f zone=%s",
				d.x, d.y, d.z, tostring(d.cell), d.heading, d.zone
			))
		end
		self:audit(actor, "dump", string.format("%.2f,%.2f,%.2f,cell=%s", d.x, d.y, d.z, tostring(d.cell)))
		return
	end

	if (cmd == "status") then
		local n = 0
		for _, _ in pairs(sess.npc_slots or {}) do
			n = n + 1
		end
		self:msg(pPlayer, string.format("session=%s slots=%d actor=%s", tostring(sess.active), n, tostring(sess.actor)))
		return
	end

	if (not self:requireSession(pPlayer, sess)) then
		return
	end

	if (cmd == "npc") then
		self:cmdNpc(pPlayer, words, sess, actor)
	elseif (cmd == "poi") then
		self:cmdPoi(pPlayer, words, sess, actor)
	elseif (cmd == "export") then
		self:cmdExport(pPlayer, sess, actor)
	else
		self:msg(pPlayer, "Commandes: hub … | terrain anchor|scan|plateau … | dump [json] | export")
		self:msg(pPlayer, "Lost Heaven: lbg_we hub goto puis lbg_we poi preset starport")
		self:msg(pPlayer, "Syntaxe Spatial: lbg_we session on (onglet Spatial, sans /)")
	end
end

function LbgWorldEditorScreenPlay:cmdHub(pPlayer, words, sess, actor)
	local sub = words[2] or ""
	if (sub == "goto" or sub == "ground") then
		local z = LBG_WE_LOST_HEAVEN_Z
		if (LbgTerrainLib ~= nil and LbgTerrainLib.floorAt ~= nil) then
			z = LbgTerrainLib.floorAt(LBG_WE_ZONE, LBG_WE_LOST_HEAVEN_X, LBG_WE_LOST_HEAVEN_Y, LBG_WE_LOST_HEAVEN_Z)
		end
		CreatureObject(pPlayer):teleport(LBG_WE_LOST_HEAVEN_X, z, LBG_WE_LOST_HEAVEN_Y, 0)
		sess.terrain = sess.terrain or {}
		sess.terrain.cx = LBG_WE_LOST_HEAVEN_X
		sess.terrain.cy = LBG_WE_LOST_HEAVEN_Y
		sess.terrain.cz = z
		self:saveSession(sess)
		self:msg(pPlayer, string.format(
			"Place bazar (centre plateau) x=%.0f y=%.0f z=%.1f",
			LBG_WE_LOST_HEAVEN_X, LBG_WE_LOST_HEAVEN_Y, z
		))
		self:audit(actor, sub == "ground" and "hub_ground" or "hub_goto", "")
		return
	end
	if (sub == "anchor") then
		sess.last_dump = {
			x = LBG_WE_LOST_HEAVEN_X,
			y = LBG_WE_LOST_HEAVEN_Y,
			z = LBG_WE_LOST_HEAVEN_Z,
			cell = 0,
			heading = 90,
			zone = LBG_WE_ZONE,
		}
		self:saveSession(sess)
		self:msg(pPlayer, "last_dump = ancre hub (utilise avant poi preset starport)")
		self:audit(actor, "hub_anchor", "")
		return
	end
	if (sub == "build") then
		if (LbgLostHeavenScreenPlay == nil or LbgLostHeavenScreenPlay.forceRebuild == nil) then
			self:msg(pPlayer, "LbgLostHeavenScreenPlay absent — redeploy Lua + restart core3")
			return
		end
		local ok = LbgLostHeavenScreenPlay:forceRebuild(pPlayer)
		if (ok) then
			self:msg(pPlayer, "Lost Heaven rebuild v9 (terrain-first, Z local)")
			self:audit(actor, "hub_build", "ok")
		else
			self:msg(pPlayer, "Rebuild echoue — etre sur tatooine, voir log serveur")
			self:audit(actor, "hub_build", "fail")
		end
		return
	end
	if (sub == "terrain") then
		if (LbgLostHeavenScreenPlay == nil or LbgLostHeavenScreenPlay.buildTerrainOnly == nil) then
			self:msg(pPlayer, "LbgLostHeavenScreenPlay absent")
			return
		end
		LbgLostHeavenScreenPlay:buildTerrainOnly(pPlayer)
		self:audit(actor, "hub_terrain", "ok")
		return
	end
	if (sub == "clean") then
		if (LbgLostHeavenScreenPlay == nil or LbgLostHeavenScreenPlay.resetHubState == nil) then
			self:msg(pPlayer, "LbgLostHeavenScreenPlay absent")
			return
		end
		LbgLostHeavenScreenPlay:resetHubState()
		self:msg(pPlayer, "Doublons / POI hub detruits — puis lbg_we hub build")
		self:audit(actor, "hub_clean", "ok")
		return
	end
	if (sub == "freeze" or sub == "autobuild" and (words[3] or "") == "off") then
		if (LbgLostHeavenScreenPlay == nil or LbgLostHeavenScreenPlay.freezeAutobuild == nil) then
			self:msg(pPlayer, "LbgLostHeavenScreenPlay absent")
			return
		end
		LbgLostHeavenScreenPlay:freezeAutobuild(pPlayer)
		self:audit(actor, "hub_freeze", "ok")
		return
	end
	if (sub == "unfreeze" or sub == "autobuild" and (words[3] or "") == "on") then
		if (LbgLostHeavenScreenPlay == nil or LbgLostHeavenScreenPlay.unfreezeAutobuild == nil) then
			self:msg(pPlayer, "LbgLostHeavenScreenPlay absent")
			return
		end
		LbgLostHeavenScreenPlay:unfreezeAutobuild(pPlayer)
		self:audit(actor, "hub_unfreeze", "ok")
		return
	end
	self:msg(pPlayer, "Usage: lbg_we hub goto | ground | anchor | terrain | clean | build | freeze | unfreeze")
end

function LbgWorldEditorScreenPlay:terrainParams(sess, words, startIdx)
	local step = LbgTerrainLib and LbgTerrainLib.DEFAULT_STEP_M or 48
	local half = LbgTerrainLib and LbgTerrainLib.DEFAULT_HALF_CELLS or 6
	if (sess ~= nil and sess.terrain ~= nil) then
		step = sess.terrain.step or step
		half = sess.terrain.half or half
	end
	if (words[startIdx] ~= nil and tonumber(words[startIdx]) ~= nil) then
		step = tonumber(words[startIdx])
	end
	if (words[startIdx + 1] ~= nil and tonumber(words[startIdx + 1]) ~= nil) then
		half = tonumber(words[startIdx + 1])
	end
	return step, half
end

function LbgWorldEditorScreenPlay:terrainCenter(sess, pPlayer, useHere)
	local d = self:getPlayerDump(pPlayer)
	if (useHere or sess.terrain == nil or sess.terrain.cx == nil) then
		return d.x, d.y, d.z
	end
	return sess.terrain.cx, sess.terrain.cy, sess.terrain.cz or d.z
end

function LbgWorldEditorScreenPlay:cmdTerrain(pPlayer, words, sess, actor)
	if (LbgTerrainLib == nil) then
		self:msg(pPlayer, "LbgTerrainLib absent — redeploy Lua + restart core3")
		return
	end
	local sub = words[2] or ""
	local d = self:getPlayerDump(pPlayer)

	if (sub == "anchor" or sub == "center") then
		sess.terrain = sess.terrain or {}
		sess.terrain.cx = math.floor(d.x + 0.5)
		sess.terrain.cy = math.floor(d.y + 0.5)
		sess.terrain.cz = d.z
		self:saveSession(sess)
		self:msg(pPlayer, string.format(
			"terrain centre @ %.0f,%.0f z=%.1f — puis scan puis plateau",
			sess.terrain.cx, sess.terrain.cy, sess.terrain.cz
		))
		self:audit(actor, "terrain_anchor", string.format("%.0f,%.0f", d.x, d.y))
		return
	end

	if (sub == "status") then
		local cfg = LbgTerrainLib.loadPlateauConfig()
		local t = sess.terrain or {}
		local cx = (cfg ~= nil and cfg.cx) or t.cx or LBG_WE_LOST_HEAVEN_X
		local cy = (cfg ~= nil and cfg.cy) or t.cy or LBG_WE_LOST_HEAVEN_Y
		local step, half = self:terrainParams(sess, words, 3)
		local nMod = #LbgTerrainLib.readIdFile(LBG_WE_TERRAIN_MOD_STATE)
		local nBowl = #LbgTerrainLib.readIdFile(LBG_WE_BOWL_MOD_STATE)
		local nTh = #LbgTerrainLib.readIdFile(LBG_WE_THEATER_STATE)
		local liveTh = LbgTerrainLib.countLiveTheaters(LBG_WE_THEATER_STATE)
		local layOk = LbgTerrainLib.layFileExists(LBG_WE_TERRAIN_LAY)
		local bowlLayOk = LbgTerrainLib.layFileExists(LBG_WE_BOWL_LAY)
		self:msg(pPlayer, string.format(
			"terrain centre=%.0f,%.0f step=%dm half=%d span~%dm mods=%d bowl=%d theaters=%d live=%d lay=%s bowl_lay=%s",
			cx, cy, step, half, step * half * 2, nMod, nBowl, nTh, liveTh,
			layOk and "OK" or "ABSENT", bowlLayOk and "OK" or "ABSENT"
		))
		if (liveTh < nTh) then
			self:msg(pPlayer, "theaters fichier > live — restart core3 ou lbg_we terrain replay")
		end
		return
	end

	if (sub == "replay") then
		local r, err = LbgTerrainLib.replaySavedPlateau(true)
		if (r == nil) then
			self:msg(pPlayer, err or "replay echec")
			return
		end
		self:msg(pPlayer, string.format(
			"REPLAY plateau @ %.0f,%.0f theaters=%d flatten=%d bowl=%s siteZ=%.1f",
			r.cx, r.cy, r.theater_count, r.flatten_count,
			tostring(r.bowl_count or 0), r.siteZ
		))
		if (r.flatten_error ~= nil) then
			self:msg(pPlayer, r.flatten_error)
		end
		if (r.bowl_error ~= nil) then
			self:msg(pPlayer, r.bowl_error)
		end
		self:audit(actor, "terrain_replay", string.format("%.0f,%.0f", r.cx, r.cy))
		return
	end

	if (sub == "height") then
		local h = LbgTerrainLib.heightAt(LBG_WE_ZONE, d.x, d.y) or d.z
		self:msg(pPlayer, string.format("height x=%.0f y=%.0f z=%.2f (pieds z=%.2f)", d.x, d.y, h, d.z))
		return
	end

	if (sub == "scan") then
		local cx, cy = self:terrainCenter(sess, pPlayer, false)
		local step = tonumber(words[3]) or 20
		local half = tonumber(words[4]) or 5
		local s = LbgTerrainLib.scan(LBG_WE_ZONE, cx, cy, step, half)
		self:msg(pPlayer, string.format(
			"scan @ %.0f,%.0f pas=%dm : min=%.2f max=%.2f delta=%.2f m (%d pts)",
			cx, cy, step, s.min, s.max, s.delta, s.count
		))
		if (s.delta > 3) then
			self:msg(pPlayer, "delta > 3m — plateau recommande avant batiments")
		end
		self:audit(actor, "terrain_scan", string.format("%.0f,%.0f,d=%.1f", cx, cy, s.delta))
		return
	end

	if (sub == "flatten") then
		if (words[3] == "grid") then
			local cx, cy = self:terrainCenter(sess, pPlayer, words[4] == "here")
			local step, half = self:terrainParams(sess, words, 5)
			sess.terrain = sess.terrain or {}
			sess.terrain.step = step
			sess.terrain.half = half
			self:saveSession(sess)
			local n, err = LbgTerrainLib.applyServerFlatten(
				LBG_WE_ZONE, cx, cy, step, half, LBG_WE_TERRAIN_LAY, LBG_WE_TERRAIN_MOD_STATE
			)
			if (err ~= nil) then
				self:msg(pPlayer, err)
				return
			end
			self:msg(pPlayer, string.format(
				"flatten serveur : %d cellules @ %.0f,%.0f pas=%dm half=%d — relog pour voir le sol",
				n, cx, cy, step, half
			))
			self:audit(actor, "terrain_flatten_grid", string.format("%.0f,%.0f,n=%d", cx, cy, n))
			return
		end
		local modId = addTerrainFlatten(LBG_WE_ZONE, d.x, d.y, LBG_WE_TERRAIN_LAY, 0)
		if (LbgTerrainLib.modIdOk(modId)) then
			LbgTerrainLib.appendIdFile(LBG_WE_TERRAIN_MOD_STATE, modId)
			self:msg(pPlayer, string.format("flatten 1 cellule @ %.0f,%.0f modId=%s", d.x, d.y, tostring(modId)))
		else
			self:msg(pPlayer, "flatten echec")
		end
		return
	end

	if (sub == "theater") then
		local cx, cy = self:terrainCenter(sess, pPlayer, words[3] == "here")
		local step, half = self:terrainParams(sess, words, words[3] == "here" and 4 or 3)
		local siteZ = LbgTerrainLib.computeSiteMaxZ(LBG_WE_ZONE, cx, cy, step, half)
		local n = LbgTerrainLib.applyTheaters(LBG_WE_ZONE, cx, cy, siteZ, step, half, LBG_WE_THEATER_STATE)
		self:msg(pPlayer, string.format(
			"theater client : %d @ %.0f,%.0f siteZ=%.1f pas=%dm — deja visible sans relog",
			n, cx, cy, siteZ, step
		))
		self:audit(actor, "terrain_theater", string.format("%.0f,%.0f", cx, cy))
		return
	end

	if (sub == "plateau") then
		local useHere = (words[3] == "here")
		local cx, cy = self:terrainCenter(sess, pPlayer, useHere)
		local step, half = self:terrainParams(sess, words, useHere and 4 or 3)
		sess.terrain = sess.terrain or {}
		sess.terrain.cx = math.floor(cx + 0.5)
		sess.terrain.cy = math.floor(cy + 0.5)
		sess.terrain.step = step
		sess.terrain.half = half
		self:saveSession(sess)
		local r = LbgTerrainLib.applyPlateau({
			zone = LBG_WE_ZONE,
			cx = cx,
			cy = cy,
			step = step,
			halfCells = half,
			lay = LBG_WE_TERRAIN_LAY,
			modIdFile = LBG_WE_TERRAIN_MOD_STATE,
			theaterIdFile = LBG_WE_THEATER_STATE,
			refZ = d.z,
			playerX = d.x,
			playerY = d.y,
			clearFirst = true,
		})
		if (r.flatten_error ~= nil) then
			self:msg(pPlayer, r.flatten_error)
		end
		local extra = ""
		if (r.flatten_count == 0 and r.theater_count > 0) then
			extra = " | theater OK (sol visible). Rebuild Core3 pour flatten serveur + relog."
		end
		self:msg(pPlayer, string.format(
			"PLATEAU @ %.0f,%.0f siteZ=%.1f span=%dm | flatten=%d theater=%d%s",
			cx, cy, r.siteZ, r.span_m, r.flatten_count, r.theater_count, extra
		))
		self:audit(actor, "terrain_plateau", string.format("%.0f,%.0f,z=%.1f", cx, cy, r.siteZ))
		return
	end

	if (sub == "bowl") then
		local useHere = (words[3] == "here")
		local cx, cy = self:terrainCenter(sess, pPlayer, useHere)
		local radius = tonumber(useHere and words[4] or words[3]) or LbgTerrainLib.DEFAULT_BOWL_RADIUS_M
		local targetZ = tonumber(useHere and words[5] or words[4]) or 0
		if (useHere and words[4] == nil) then
			radius = LbgTerrainLib.DEFAULT_BOWL_RADIUS_M
		end
		if (math.abs(radius - LbgTerrainLib.DEFAULT_BOWL_RADIUS_M) > 1) then
			self:msg(pPlayer, string.format(
				"WARN: poi_bowl.lay genere pour R=%dm — regen si autre rayon",
				LbgTerrainLib.DEFAULT_BOWL_RADIUS_M
			))
		end
		sess.terrain = sess.terrain or {}
		sess.terrain.cx = math.floor(cx + 0.5)
		sess.terrain.cy = math.floor(cy + 0.5)
		self:saveSession(sess)
		local bowlCount, bowlErr = LbgTerrainLib.applyBowl(
			LBG_WE_ZONE, cx, cy, radius, targetZ, LBG_WE_BOWL_LAY, LBG_WE_BOWL_MOD_STATE, true
		)
		LbgTerrainLib.saveBowlConfig({
			zone = LBG_WE_ZONE,
			cx = cx,
			cy = cy,
			radiusM = radius,
			targetZ = targetZ,
			lay = LBG_WE_BOWL_LAY,
			modIdFile = LBG_WE_BOWL_MOD_STATE,
		})
		if (bowlErr ~= nil) then
			self:msg(pPlayer, bowlErr)
		end
		self:msg(pPlayer, string.format(
			"CUVETTE @ %.0f,%.0f R=%dm Z=%.1f | bowl_mod=%d — relog pour voir la fosse serveur",
			cx, cy, radius, targetZ, bowlCount
		))
		self:audit(actor, "terrain_bowl", string.format("%.0f,%.0f,R=%.0f,z=%.1f", cx, cy, radius, targetZ))
		return
	end

	if (sub == "base") then
		local useHere = (words[3] == "here")
		local cx, cy
		if (useHere) then
			cx, cy = d.x, d.y
		else
			cx = LBG_WE_LOST_HEAVEN_X
			cy = LBG_WE_LOST_HEAVEN_Y
		end
		local step, half = self:terrainParams(sess, words, useHere and 4 or 3)
		local bowlRadius = tonumber(words[useHere and 6 or 5]) or LbgTerrainLib.DEFAULT_BOWL_RADIUS_M
		local bowlZ = tonumber(words[useHere and 7 or 6]) or 0
		sess.terrain = sess.terrain or {}
		sess.terrain.cx = math.floor(cx + 0.5)
		sess.terrain.cy = math.floor(cy + 0.5)
		sess.terrain.step = step
		sess.terrain.half = half
		self:saveSession(sess)
		local r = LbgTerrainLib.applyBaseSite({
			zone = LBG_WE_ZONE,
			cx = cx,
			cy = cy,
			step = step,
			halfCells = half,
			lay = LBG_WE_TERRAIN_LAY,
			modIdFile = LBG_WE_TERRAIN_MOD_STATE,
			theaterIdFile = LBG_WE_THEATER_STATE,
			refZ = d.z,
			playerX = d.x,
			playerY = d.y,
			bowlRadius = bowlRadius,
			bowlZ = bowlZ,
			bowlLay = LBG_WE_BOWL_LAY,
			bowlModIdFile = LBG_WE_BOWL_MOD_STATE,
			clearFirst = true,
		})
		if (r.flatten_error ~= nil) then
			self:msg(pPlayer, r.flatten_error)
		end
		if (r.bowl_error ~= nil) then
			self:msg(pPlayer, r.bowl_error)
		end
		self:msg(pPlayer, string.format(
			"BASE @ %.0f,%.0f siteZ=%.1f span=%dm | flatten=%d theater=%d bowl=%d (R=%dm Z=%.1f) — relog si fosse absente",
			cx, cy, r.siteZ, r.span_m, r.flatten_count, r.theater_count,
			r.bowl_count or 0, bowlRadius, bowlZ
		))
		self:audit(actor, "terrain_base", string.format("%.0f,%.0f", cx, cy))
		return
	end

	if (sub == "clear") then
		local mode = words[3] or "we"
		local nMod = LbgTerrainLib.clearTerrainMods(LBG_WE_ZONE, LBG_WE_TERRAIN_MOD_STATE)
		local nBowl = LbgTerrainLib.clearTerrainMods(LBG_WE_ZONE, LBG_WE_BOWL_MOD_STATE)
		local nTh = LbgTerrainLib.clearTheaters(LBG_WE_THEATER_STATE)
		if (mode == "all" and LbgLostHeavenScreenPlay ~= nil) then
			if (LbgLostHeavenScreenPlay.destroyOldTerrainMods ~= nil) then
				LbgLostHeavenScreenPlay:destroyOldTerrainMods()
			end
			if (LbgLostHeavenScreenPlay.destroyOldTheaters ~= nil) then
				LbgLostHeavenScreenPlay:destroyOldTheaters()
			end
			writeData("lbg_lost_heaven_theater_v1", 0)
			self:msg(pPlayer, "terrain clear all (WE + Lost Heaven)")
		else
			self:msg(pPlayer, string.format(
				"terrain clear : %d mods + %d bowl + %d theaters WE",
				nMod, nBowl, nTh
			))
		end
		self:audit(actor, "terrain_clear", mode)
		return
	end

	self:msg(pPlayer, "terrain: anchor | scan | plateau | bowl [R [Z]] | base [pas half [R [Z]]] | replay | status | clear [all]")
end

function LbgWorldEditorScreenPlay:resolvePilotCfg(pilotId)
	if (pilotId == nil or pilotId == "") then
		return nil
	end
	if (IA_BRIDGE_PILOTS ~= nil and IA_BRIDGE_PILOTS[pilotId] ~= nil) then
		return IA_BRIDGE_PILOTS[pilotId]
	end
	if (IaBridgeScreenPlay ~= nil and IaBridgeScreenPlay.getPilotCfg ~= nil) then
		local cfg = IaBridgeScreenPlay:getPilotCfg(pilotId)
		if (cfg ~= nil) then
			return cfg
		end
	end
	return self:resolvePilotCfgFromCatalogJson(pilotId)
end

-- Secours si ia_bridge n'a pas encore rempli IA_BRIDGE_PILOTS (lecture directe du JSON deploye)
function LbgWorldEditorScreenPlay:resolvePilotCfgFromCatalogJson(pilotId)
	local paths = {
		"ia_bridge/core3_npc_catalog.json",
		"core3_npc_catalog.json",
		"/opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json",
	}
	local needle = '"pilot_id": "' .. pilotId .. '"'
	for _, path in ipairs(paths) do
		local f = io.open(path, "r")
		if (f ~= nil) then
			local body = f:read("*a")
			f:close()
			local pos = body:find(needle, 1, true)
			if (pos ~= nil) then
				local slice = body:sub(pos, pos + 900)
				local mobile = slice:match('"mobile_template"%s*:%s*"([^"]+)"')
				local display = slice:match('"display_name"%s*:%s*"([^"]+)"')
				local lbgId = slice:match('"lbg_npc_id"%s*:%s*"([^"]+)"')
				local roster = slice:match('"roster_id"%s*:%s*"(roster:[^"]+)"')
				if (mobile == nil or mobile == "") then
					mobile = slice:match('"mobile"%s*:%s*"([^"]+)"')
				end
				if (mobile ~= nil and mobile ~= "") then
					return {
						lbg_npc_id = lbgId or "",
						display_name = display or pilotId,
						mobile = mobile,
						roster = roster,
					}
				end
			end
		end
	end
	return nil
end

function LbgWorldEditorScreenPlay:cmdNpc(pPlayer, words, sess, actor)
	local sub = words[2] or ""
	if (sub == "place") then
		local pilotId = words[3]
		if (pilotId == nil or pilotId == "") then
			self:msg(pPlayer, "Usage: /lbg_we npc place <pilot_id>")
			return
		end
		local d = sess.last_dump or self:getPlayerDump(pPlayer)
		local cfg = self:resolvePilotCfg(pilotId)
		if (cfg == nil) then
			self:msg(pPlayer, "Pilot inconnu: " .. pilotId .. " (catalogue / ia_bridge)")
			self:msg(pPlayer, "Verifie core3_npc_catalog.json deploye ; pas de commoner de secours.")
			return
		end
		local mobile = cfg.mobile
		if (mobile == nil or mobile == "") then
			mobile = words[4]
		end
		if (mobile == nil or mobile == "") then
			self:msg(pPlayer, "mobile_template vide pour " .. pilotId)
			return
		end
		cfg.mobile = mobile
		local roster = cfg.roster or (words[5] or "")
		sess.npc_slots[pilotId] = {
			x = d.x,
			y = d.y,
			z = d.z,
			cell = d.cell,
			heading = d.heading,
			mobile = mobile,
			roster_id = roster,
		}
		self:saveSession(sess)
		cfg.x = d.x
		cfg.y = d.y
		cfg.z = d.z
		cfg.heading = d.heading
		cfg.spawn_cell = d.cell
		if (IaBridgeScreenPlay ~= nil) then
			local ib = IaBridgeScreenPlay
			if (ib.despawnPilot ~= nil) then
				ib:despawnPilot(pilotId)
			end
			if (ib.spawnPilotAt ~= nil) then
				ib:spawnPilotAt(pilotId, cfg, d.x, d.z, d.y, d.cell)
			end
		else
			_G.__IA_BRIDGE_SPAWNING_PILOT = pilotId
			spawnMobile(LBG_WE_ZONE, mobile, 0, d.x, d.z, d.y, d.heading, d.cell)
			_G.__IA_BRIDGE_SPAWNING_PILOT = nil
		end
		self:msg(pPlayer, string.format(
			"NPC place %s mobile=%s nom=%s cell=%s",
			pilotId, tostring(mobile), tostring(cfg.display_name or "?"), tostring(d.cell)
		))
		self:audit(actor, "npc_place", pilotId .. "@" .. tostring(d.cell))
	elseif (sub == "remove") then
		local pilotId = words[3]
		if (pilotId == nil) then
			self:msg(pPlayer, "Usage: /lbg_we npc remove <pilot_id>")
			return
		end
		sess.npc_slots[pilotId] = nil
		self:saveSession(sess)
		if (IaBridgeScreenPlay ~= nil and IaBridgeScreenPlay.despawnPilot ~= nil) then
			IaBridgeScreenPlay:despawnPilot(pilotId)
		end
		self:msg(pPlayer, "NPC remove " .. pilotId)
		self:audit(actor, "npc_remove", pilotId)
	else
		self:msg(pPlayer, "Usage: /lbg_we npc place|remove <pilot_id>")
	end
end

function LbgWorldEditorScreenPlay:cmdPoi(pPlayer, words, sess, actor)
	local sub = words[2] or ""
	if (sub == "preset") then
		local preset = words[3] or ""
		if (preset == "starport") then
			words = { "poi", "place", LBG_WE_STARPORT_POI, LBG_WE_STARPORT_TEMPLATE }
			sub = "place"
		else
			self:msg(pPlayer, "Usage: lbg_we poi preset starport (shuttleport_tatooine)")
			return
		end
	end
	local poiId = self:normalizePoiId(words[3])
	if (sub == "place") then
		local template = words[4]
		if (template == nil or template == "") then
			self:msg(pPlayer, "Usage: lbg_we poi place <poi_id> <structure_template>")
			self:msg(pPlayer, "Ou: lbg_we poi preset starport")
			return
		end
		local d = sess.last_dump or self:getPlayerDump(pPlayer)
		local pBuilding = spawnBuilding(pPlayer, template, d.x, d.y, 0)
		if (pBuilding == nil) then
			self:msg(pPlayer, "Echec spawnBuilding template=" .. template)
			self:audit(actor, "poi_place_fail", template)
			return
		end
		local oid = SceneObject(pBuilding):getObjectID()
		sess.poi = sess.poi or {}
		sess.poi[poiId] = {
			template = template,
			x = d.x,
			y = d.y,
			z = d.z,
			heading = d.heading,
			object_id = oid,
			root_cell_id = d.cell,
		}
		self:saveSession(sess)
		self:msg(pPlayer, string.format("POI %s pose oid=%s (export pour persister)", poiId, tostring(oid)))
		self:audit(actor, "poi_place", poiId .. " oid=" .. tostring(oid))
	elseif (sub == "remove") then
		self:msg(pPlayer, "poi remove: despawn manuel GM pour l instant ; slot session efface au export")
		if (sess.poi ~= nil) then
			sess.poi[poiId] = nil
		end
		self:saveSession(sess)
		self:audit(actor, "poi_remove", poiId)
	else
		self:msg(pPlayer, "Usage: /lbg_we poi place|remove <poi_id> [template]")
	end
end

function LbgWorldEditorScreenPlay:writeExportQueue(actor)
	local f = io.open(LBG_WE_EXPORT_QUEUE, "a")
	if (f ~= nil) then
		f:write(os.time() .. "|" .. tostring(actor) .. "\n")
		f:close()
	end
end

function LbgWorldEditorScreenPlay:writePoiExportJson(path, sess, actor)
	if (path == nil or path == "") then
		return
	end
	local outDir = "ia_bridge/world_poi"
	os.execute("mkdir -p " .. outDir .. " 2>/dev/null")
	local poiIds = {}
	for pid, _ in pairs(sess.poi or {}) do
		table.insert(poiIds, pid)
	end
	table.sort(poiIds)
	local lines = {}
	table.insert(lines, "{")
	table.insert(lines, '  "schema_version": 1,')
	table.insert(lines, '  "zone_id": "tatooine",')
	table.insert(lines, '  "display_zone": "Scrapaltai",')
	table.insert(lines, '  "hub_location_id": "loc:lost_heaven_hub",')
	table.insert(lines, '  "exported_at": "' .. os.date("!%Y-%m-%dT%H:%M:%SZ") .. '",')
	table.insert(lines, '  "exported_by": "' .. tostring(actor) .. '",')
	table.insert(lines, '  "pois": [')
	for i, poiId in ipairs(poiIds) do
		local p = sess.poi[poiId]
		if (i > 1) then
			table.insert(lines, ",")
		end
		table.insert(lines, "    {")
		table.insert(lines, '      "poi_id": "' .. poiId .. '",')
		table.insert(lines, '      "structure_template": "' .. tostring(p.template or "") .. '",')
		table.insert(lines, '      "world": { "x": ' .. tostring(p.x) .. ', "y": ' .. tostring(p.y) .. ', "z": ' .. tostring(p.z or 6) .. ', "heading": ' .. tostring(p.heading or 0) .. " },")
		table.insert(lines, '      "root_cell_id": ' .. tostring(p.root_cell_id or 0) .. ",")
		table.insert(lines, '      "object_id": ' .. tostring(p.object_id or 0))
		table.insert(lines, "    }")
	end
	table.insert(lines, "  ],")
	table.insert(lines, '  "npc_slots": [')
	local first = true
	for pid, slot in pairs(sess.npc_slots or {}) do
		if (not first) then
			table.insert(lines, ",")
		end
		first = false
		table.insert(lines, "    {")
		table.insert(lines, '      "pilot_id": "' .. pid .. '",')
		table.insert(lines, '      "roster_id": "' .. tostring(slot.roster_id or "") .. '",')
		table.insert(lines, '      "mobile_template": "' .. tostring(slot.mobile or "") .. '",')
		table.insert(lines, '      "service_post": { "x": ' .. tostring(slot.x) .. ', "y": ' .. tostring(slot.y) .. ', "z": ' .. tostring(slot.z) .. ', "heading": ' .. tostring(slot.heading) .. ', "cell": ' .. tostring(slot.cell) .. " }")
		table.insert(lines, "    }")
	end
	table.insert(lines, "  ]")
	table.insert(lines, "}")
	local body = table.concat(lines, "\n") .. "\n"
	local f = io.open(path, "w")
	if (f ~= nil) then
		f:write(body)
		f:close()
	end
end

function LbgWorldEditorScreenPlay:cmdExport(pPlayer, sess, actor)
	-- Snapshot session → JSON ; agent merge vers repo
	self:writePoiExportJson(LBG_WE_POI_SCRAPALTAI_RUNTIME, sess, actor)
	self:writePoiExportJson(LBG_WE_POI_RUNTIME, sess, actor)
	self:writePoiExportJson(LBG_WE_POI_SCRAPALTAI_REPO, sess, actor)
	self:writePoiExportJson(LBG_WE_POI_REPO, sess, actor)
	self:writeExportQueue(actor)
	pcall(function()
		os.execute("bash /opt/LBG_IA_MMO/infra/scripts/lbg_world_export_agent.sh >/tmp/lbg_world_export_agent.log 2>&1 &")
	end)
	self:msg(pPlayer, "Export Scrapaltai → " .. LBG_WE_POI_SCRAPALTAI_RUNTIME .. " (agent Git)")
	self:audit(actor, "export", LBG_WE_POI_SCRAPALTAI_RUNTIME)
end
