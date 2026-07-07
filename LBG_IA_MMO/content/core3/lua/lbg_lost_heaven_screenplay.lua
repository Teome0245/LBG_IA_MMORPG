-- Lost Heaven (Scrapaltai) — place bazar/banque = centre du plateau
-- Emprise ~64 m → espacement centres 100 m (marge anti-collision)

local LH_ZONE = "tatooine"
local LH_ANCHOR_X = 4749
local LH_ANCHOR_Y = -737
local LH_ANCHOR_Z = 1
local LH_GRID_SPACING = 100
local LH_BUILD_FLAG = "lbg_lost_heaven_city_built_v1"
local LH_BUILD_VERSION_KEY = "lbg_lost_heaven_build_version_v1"
local LH_BUILD_BUSY_FLAG = "lbg_lost_heaven_build_busy_v1"
local LH_BLUE_FROG_FLAG = "lbg_lost_heaven_blue_frog_v1"
local LH_BLUE_FROG_OID_KEY = "lbg_lost_heaven_blue_frog_oid_v1"
local LH_BLUE_FROG_TEMPLATE = "object/tangible/terminal/terminal_character_builder.iff"
local LH_STARPORT_SPAWN_OY = 200
local LH_STARPORT_OID_KEY = "lbg_lost_heaven_starport_oid_v1"
local LH_BANK_OID_KEY = "lbg_lost_heaven_bank_oid_v1"
local LH_MARKET_OID_KEY = "lbg_lost_heaven_market_oid_v1"
local LH_THEATER_FLAG = "lbg_lost_heaven_theater_v1"
local LH_BUILD_VERSION = 9
local LH_BUILD_PHASE_DELAY_MS = 8000
local LH_USE_LOCAL_BUILDING_Z = true
local LH_CIVIC_CENTER_POI = "poi:lost_heaven_market"
local LH_HUB_DEFAULT_HEADING = 90
local LH_ANCHOR_X_KEY = "lbg_lost_heaven_anchor_x_v1"
local LH_ANCHOR_Y_KEY = "lbg_lost_heaven_anchor_y_v1"
local LH_ANCHOR_Z_KEY = "lbg_lost_heaven_anchor_z_v1"
local LH_PLATEAU_Z_KEY = "lbg_lost_heaven_plateau_z_v1"
local LH_SITE_RADIUS_M = 130
local LH_THEATER_STEP_M = 50
local LH_THEATER_HALF_CELLS = 9
local LH_TERRAIN_MOD_STEP_M = 50
local LH_TERRAIN_MOD_HALF_CELLS = 9
local LH_TERRAIN_LAY = "terrain/poi_large.lay"
local LH_STATE_RUNTIME = "ia_bridge/world_poi/scrapaltai.json"
local LH_STATE_REPO = "/opt/LBG_IA_MMO/content/core3/world_poi/scrapaltai.json"
local LH_THEATER_STATE = "ia_bridge/lost_heaven_theater_oids.txt"
local LH_TERRAIN_MOD_STATE = "ia_bridge/lost_heaven_terrain_mod_ids.txt"
local LH_POI_HISTORY = "ia_bridge/lost_heaven_poi_history.txt"
local LH_FORCE_REBUILD_FILE = "ia_bridge/lost_heaven_force_rebuild"
local LH_AUTOBUILD_OFF_FILE = "ia_bridge/lost_heaven_autobuild_off"
local LH_AUTOBUILD_KEY = "lbg_lost_heaven_autobuild_v1"
local LH_NAVMESH_NAME = "lost_heaven_hub"
local LH_MIN_PRESENT_POIS = 6
local LH_PLACEMENT_WATCH = { "Gally", "Teome", "Lia", "Nix", "Mira", "Bot_IA" }

local S = LH_GRID_SPACING
local LH_OUTER = S * 2
-- ox/oy relatifs au centre place bazar (poi:lost_heaven_market @ 0,0)
local LH_BUILD_PLAN = {
	{ poi_id = "poi:lost_heaven_market", template = "object/building/tatooine/guild_commerce_tatooine_style_01.iff", ox = 0, oy = 0 },
	{ poi_id = "poi:lost_heaven_bank", template = "object/building/tatooine/bank_tatooine.iff", ox = -200, oy = 0 },
	{ poi_id = "poi:lost_heaven_cantina", template = "object/building/tatooine/cantina_tatooine.iff", ox = 100, oy = 100 },
	{ poi_id = "poi:lost_heaven_inn", template = "object/building/tatooine/hotel_tatooine_general.iff", ox = -100, oy = 100 },
	{ poi_id = "poi:lost_heaven_starport", template = "object/building/tatooine/shuttleport_tatooine.iff", ox = 0, oy = 200 },
	{ poi_id = "poi:lost_heaven_training_hall", template = "object/building/tatooine/guild_combat_tatooine_style_01.iff", ox = 100, oy = -100 },
	{ poi_id = "poi:lost_heaven_clinic", template = "object/building/tatooine/hospital_tatooine.iff", ox = -100, oy = -100 },
	{ poi_id = "poi:lost_heaven_mission_post", template = "object/building/tatooine/salon_tatooine.iff", ox = 200, oy = -200 },
	{ poi_id = "poi:lost_heaven_town_hall", template = "object/building/tatooine/capitol_tatooine.iff", ox = 0, oy = -200 },
	{ poi_id = "poi:lost_heaven_artisan_hall", template = "object/building/tatooine/housing_tatt_style01_med.iff", ox = 200, oy = 0 },
	{ poi_id = "poi:lost_heaven_housing_npc", template = "object/building/tatooine/housing_tatt_style01_small.iff", ox = -200, oy = 200 },
	{ poi_id = "poi:lost_heaven_gate", template = "object/building/tatooine/filler_building_block_64x32_style_01.iff", ox = 0, oy = -300 },
}

LbgLostHeavenScreenPlay = ScreenPlay:new {
	numberOfActs = 1,
	screenplayName = "LbgLostHeavenScreenPlay",
}

registerScreenPlay("LbgLostHeavenScreenPlay", true)

function LbgLostHeavenScreenPlay:isAutobuildEnabled()
	if (io.open(LH_AUTOBUILD_OFF_FILE, "r") ~= nil) then
		return false
	end
	local v = readData(LH_AUTOBUILD_KEY)
	if (v == nil) then
		return true
	end
	return v ~= 0
end

function LbgLostHeavenScreenPlay:setAutobuildEnabled(enabled)
	writeData(LH_AUTOBUILD_KEY, enabled and 1 or 0)
	if (enabled) then
		pcall(function() os.remove(LH_AUTOBUILD_OFF_FILE) end)
	else
		os.execute("mkdir -p ia_bridge 2>/dev/null")
		local f = io.open(LH_AUTOBUILD_OFF_FILE, "w")
		if (f ~= nil) then
			f:write("1\n")
			f:close()
		end
	end
end

function LbgLostHeavenScreenPlay:sampleFloorZ(x, y)
	local z = getWorldFloor(x, y, LH_ZONE)
	if (z == nil or z < 0) then
		return nil
	end
	return z
end

function LbgLostHeavenScreenPlay:measureSiteRoughness(cx, cy, radius)
	local r = radius or LH_SITE_RADIUS_M
	local corners = {
		{ cx - r, cy - r }, { cx + r, cy - r },
		{ cx - r, cy + r }, { cx + r, cy + r },
		{ cx, cy - r }, { cx, cy + r },
		{ cx - r, cy }, { cx + r, cy },
		{ cx, cy },
	}
	local minz, maxz = 99999, -99999
	local n = 0
	for _, p in ipairs(corners) do
		local z = self:sampleFloorZ(p[1], p[2])
		if (z ~= nil) then
			n = n + 1
			if (z < minz) then minz = z end
			if (z > maxz) then maxz = z end
		end
	end
	if (n < 4) then
		return 99999
	end
	return maxz - minz
end

function LbgLostHeavenScreenPlay:storeHubAnchor(ax, ay, az)
	writeData(LH_ANCHOR_X_KEY, math.floor(ax + 0.5))
	writeData(LH_ANCHOR_Y_KEY, math.floor(ay + 0.5))
	writeData(LH_ANCHOR_Z_KEY, math.floor((az or LH_ANCHOR_Z) * 10 + 0.5))
end

function LbgLostHeavenScreenPlay:readHubAnchor()
	local ax = readData(LH_ANCHOR_X_KEY)
	local ay = readData(LH_ANCHOR_Y_KEY)
	local azRaw = readData(LH_ANCHOR_Z_KEY)
	if (ax ~= nil and ax > 0 and ay ~= nil) then
		local az = LH_ANCHOR_Z
		if (azRaw ~= nil and azRaw > 0) then
			az = azRaw / 10
		end
		return ax, ay, az
	end
	return LH_ANCHOR_X, LH_ANCHOR_Y, LH_ANCHOR_Z
end

function LbgLostHeavenScreenPlay:findHubAnchor()
	-- Ancre fixe : centre plateau = place bazar @ LH_ANCHOR_X/Y (pas de dérive)
	local az = self:sampleFloorZ(LH_ANCHOR_X, LH_ANCHOR_Y) or LH_ANCHOR_Z
	self:storeHubAnchor(LH_ANCHOR_X, LH_ANCHOR_Y, az)
	printf("LbgLostHeaven: centre place bazar @ %d,%d z=%.1f\n", LH_ANCHOR_X, LH_ANCHOR_Y, az)
	return LH_ANCHOR_X, LH_ANCHOR_Y, az
end

function LbgLostHeavenScreenPlay:validateBuildPlanSpacing()
	local minDist = 99999
	local worstA, worstB = "", ""
	for i = 1, #LH_BUILD_PLAN do
		for j = i + 1, #LH_BUILD_PLAN do
			local a, b = LH_BUILD_PLAN[i], LH_BUILD_PLAN[j]
			local dx = a.ox - b.ox
			local dy = a.oy - b.oy
			local d = math.sqrt(dx * dx + dy * dy)
			if (d > 0.1 and d < minDist) then
				minDist = d
				worstA, worstB = a.poi_id, b.poi_id
			end
		end
	end
	if (minDist < LH_GRID_SPACING - 5) then
		printf("LbgLostHeaven: WARN espacement min %.1fm <%dm (%s vs %s)\n",
			minDist, LH_GRID_SPACING, worstA, worstB)
		return false
	end
	return true
end

function LbgLostHeavenScreenPlay:terrainModGridOffsets(step, halfCells)
	local offsets = {}
	for ix = -halfCells, halfCells do
		for iy = -halfCells, halfCells do
			table.insert(offsets, { ix * step, iy * step })
		end
	end
	return offsets
end

function LbgLostHeavenScreenPlay:readTerrainModIds()
	local ids = {}
	local f = io.open(LH_TERRAIN_MOD_STATE, "r")
	if (f == nil) then
		return ids
	end
	for line in f:lines() do
		local id = tonumber(line)
		if (id ~= nil and id > 0) then
			table.insert(ids, id)
		end
	end
	f:close()
	return ids
end

function LbgLostHeavenScreenPlay:appendTerrainModId(id)
	if (id == nil or id == 0) then
		return
	end
	local f = io.open(LH_TERRAIN_MOD_STATE, "a")
	if (f ~= nil) then
		f:write(tostring(id) .. "\n")
		f:close()
	end
end

function LbgLostHeavenScreenPlay:destroyOldTerrainMods()
	if (removeTerrainFlatten == nil) then
		return
	end
	for _, id in ipairs(self:readTerrainModIds()) do
		pcall(function() removeTerrainFlatten(LH_ZONE, id) end)
	end
	local wf = io.open(LH_TERRAIN_MOD_STATE, "w")
	if (wf ~= nil) then
		wf:close()
	end
end

function LbgLostHeavenScreenPlay:applyServerPlateau(ax, ay)
	if (addTerrainFlatten == nil) then
		return 0
	end
	local count = 0
	for _, off in ipairs(self:terrainModGridOffsets(LH_TERRAIN_MOD_STEP_M, LH_TERRAIN_MOD_HALF_CELLS)) do
		local tx = ax + off[1]
		local ty = ay + off[2]
		local modId = addTerrainFlatten(LH_ZONE, tx, ty, LH_TERRAIN_LAY, 0)
		if (modId ~= nil and modId > 0) then
			self:appendTerrainModId(modId)
			count = count + 1
		end
	end
	return count
end

function LbgLostHeavenScreenPlay:computeSiteMaxZ(cx, cy, halfCells, step)
	halfCells = halfCells or LH_THEATER_HALF_CELLS
	step = step or LH_THEATER_STEP_M
	local maxz = -99999
	local n = 0
	for ix = -halfCells, halfCells do
		for iy = -halfCells, halfCells do
			local tx = cx + ix * step
			local ty = cy + iy * step
			local h = nil
			if (getPlanetHeight ~= nil) then
				h = getPlanetHeight(LH_ZONE, tx, ty)
			end
			if (h == nil or h <= -15000) then
				h = self:sampleFloorZ(tx, ty)
			end
			if (h ~= nil and h > -15000) then
				n = n + 1
				if (h > maxz) then
					maxz = h
				end
			end
		end
	end
	if (n == 0) then
		return LH_ANCHOR_Z
	end
	return maxz
end

function LbgLostHeavenScreenPlay:computePlateauZ(ax, ay)
	if (getPlanetHeight ~= nil) then
		local sum, n = 0, 0
		for _, off in ipairs(self:terrainModGridOffsets(40, 3)) do
			local h = getPlanetHeight(LH_ZONE, ax + off[1], ay + off[2])
			if (h ~= nil and h > -15000) then
				sum = sum + h
				n = n + 1
			end
		end
		if (n > 0) then
			return sum / n
		end
	end
	return self:sampleFloorZ(ax, ay) or LH_ANCHOR_Z
end

function LbgLostHeavenScreenPlay:storePlateauZ(z)
	writeData(LH_PLATEAU_Z_KEY, math.floor(z * 10 + 0.5))
end

function LbgLostHeavenScreenPlay:readPlateauZ(fallback)
	local raw = readData(LH_PLATEAU_Z_KEY)
	if (raw ~= nil and raw > 0) then
		return raw / 10
	end
	return fallback or LH_ANCHOR_Z
end

function LbgLostHeavenScreenPlay:normalizeHeading(deg)
	local h = deg % 360
	if (h < 0) then
		h = h + 360
	end
	return math.floor(h + 0.5)
end

-- SWG : heading 0 = +Y, 90 = +X — entrée principale vers le centre du plateau
function LbgLostHeavenScreenPlay:headingTowardCenter(wx, wy, cx, cy, entry)
	local dx = cx - wx
	local dy = cy - wy
	if (math.abs(dx) < 0.5 and math.abs(dy) < 0.5) then
		return self:normalizeHeading((entry and entry.heading) or LH_HUB_DEFAULT_HEADING)
	end
	local h = math.deg(math.atan2(dx, dy))
	h = self:normalizeHeading(h + (entry and entry.heading_offset or 0))
	return h
end

function LbgLostHeavenScreenPlay:computeLocalBuildingZ(wx, wy, fallback)
	if (not LH_USE_LOCAL_BUILDING_Z) then
		return fallback
	end
	local sum, n = 0, 0
	local probes = {
		{ 0, 0 }, { -24, -24 }, { 24, -24 }, { -24, 24 }, { 24, 24 },
		{ 0, -32 }, { 0, 32 }, { -32, 0 }, { 32, 0 },
	}
	for _, off in ipairs(probes) do
		local h = nil
		if (getPlanetHeight ~= nil) then
			h = getPlanetHeight(LH_ZONE, wx + off[1], wy + off[2])
		end
		if (h == nil or h <= -15000) then
			h = self:sampleFloorZ(wx + off[1], wy + off[2])
		end
		if (h ~= nil and h > -15000) then
			sum = sum + h
			n = n + 1
		end
	end
	if (n > 0) then
		return sum / n
	end
	return fallback
end

function LbgLostHeavenScreenPlay:spawnHubBuilding(pOwner, entry, wx, wy, refZ, hubX, hubY)
	local heading = self:headingTowardCenter(wx, wy, hubX, hubY, entry)
	-- v9 : Z local par empreinte (StructureManager) — pas de plateauZ global
	if (spawnBuilding ~= nil) then
		return spawnBuilding(pOwner, entry.template, wx, wy, heading), heading
	end
	if (spawnBuildingOnPlateau ~= nil and refZ ~= nil) then
		local localZ = self:computeLocalBuildingZ(wx, wy, refZ)
		return spawnBuildingOnPlateau(pOwner, entry.template, wx, wy, heading, localZ), heading
	end
	return nil, heading
end

function LbgLostHeavenScreenPlay:theaterGridOffsets()
	local offsets = {}
	for ix = -LH_THEATER_HALF_CELLS, LH_THEATER_HALF_CELLS do
		for iy = -LH_THEATER_HALF_CELLS, LH_THEATER_HALF_CELLS do
			table.insert(offsets, { ix * LH_THEATER_STEP_M, iy * LH_THEATER_STEP_M })
		end
	end
	return offsets
end

function LbgLostHeavenScreenPlay:start()
	if (not isZoneEnabled(LH_ZONE)) then
		createEvent(5000, "LbgLostHeavenScreenPlay", "start", nil, "")
		return
	end
	if (io.open(LH_FORCE_REBUILD_FILE, "r") ~= nil) then
		self:resetHubState()
		os.remove(LH_FORCE_REBUILD_FILE)
		printf("LbgLostHeaven: rebuild force demande\n")
	end
	if (io.open(LH_AUTOBUILD_OFF_FILE, "r") ~= nil) then
		writeData(LH_AUTOBUILD_KEY, 0)
	end
	printf("LbgLostHeaven: actif v%d grille=%dm (%d POI) ancre=%d,%d autobuild=%s\n",
		LH_BUILD_VERSION, LH_GRID_SPACING, #LH_BUILD_PLAN, LH_ANCHOR_X, LH_ANCHOR_Y,
		self:isAutobuildEnabled() and "ON" or "OFF")
	createEvent(20000, "LbgLostHeavenScreenPlay", "replayHubTerrainOnBoot", nil, "")
	createEvent(12000, "LbgLostHeavenScreenPlay", "pollHubEssentials", nil, "")
	self:scheduleBuildPoll()
end

function LbgLostHeavenScreenPlay:pollHubEssentials()
	-- Banque + bazar + blue frog : toujours, même si autobuild OFF
	self:ensureHubEssentials(nil)
	createEvent(45000, "LbgLostHeavenScreenPlay", "pollHubEssentials", nil, "")
end

function LbgLostHeavenScreenPlay:ensureHubEssentialsEvent(pPlayer)
	self:ensureHubEssentials(pPlayer)
end

function LbgLostHeavenScreenPlay:ensureHubEssentials(pPreferred)
	local pOwner = self:resolvePlacementPlayer(pPreferred)
	if (pOwner == nil) then
		return false
	end
	local ax, ay, az = self:readHubAnchor()
	local plateauZ = self:readPlateauZ(az)
	local okMarket = self:ensureBuildingAtKey(pOwner, LH_MARKET_OID_KEY, "poi:lost_heaven_market",
		"object/building/tatooine/guild_commerce_tatooine_style_01.iff", ax, ay, plateauZ, 90, ax, ay)
	local okBank = self:ensureBuildingAtKey(pOwner, LH_BANK_OID_KEY, "poi:lost_heaven_bank",
		"object/building/tatooine/bank_tatooine.iff", ax - 200, ay, plateauZ, 90, ax, ay)
	local okFrog = self:ensureBlueFrog(pOwner, ax, ay, plateauZ)
	return okMarket and okBank and okFrog
end

function LbgLostHeavenScreenPlay:replayHubTerrainOnBoot()
	if (LbgTerrainLib == nil) then
		return
	end
	local ax, ay = self:readHubAnchor()
	self:ensureHubTerrain(ax, ay, nil)
end

function LbgLostHeavenScreenPlay:scheduleBuildPoll()
	createEvent(15000, "LbgLostHeavenScreenPlay", "pollBuildCity", nil, "")
end

function LbgLostHeavenScreenPlay:resetHubState()
	writeData(LH_BUILD_FLAG, 0)
	writeData(LH_BUILD_VERSION_KEY, 0)
	writeData(LH_BUILD_BUSY_FLAG, 0)
	writeData(LH_STARPORT_OID_KEY, 0)
	writeData(LH_THEATER_FLAG, 0)
	writeData(LH_ANCHOR_X_KEY, 0)
	writeData(LH_ANCHOR_Y_KEY, 0)
	writeData(LH_ANCHOR_Z_KEY, 0)
	writeData(LH_PLATEAU_Z_KEY, 0)
	self:destroyAllKnownHubOids()
end

function LbgLostHeavenScreenPlay:pollBuildCity()
	if (not self:isAutobuildEnabled()) then
		createEvent(300000, "LbgLostHeavenScreenPlay", "pollBuildCity", nil, "")
		return
	end
	if (self:cityHealthy()) then
		createEvent(180000, "LbgLostHeavenScreenPlay", "pollBuildCity", nil, "")
		return
	end
	if (readData(LH_BUILD_FLAG) == 1) then
		printf("LbgLostHeaven: hub incomplet ou doublons — reconstruction\n")
		self:resetHubState()
	end
	-- Fallback minimal : si le build complet tarde, on pose au moins banque + bazar + blue frog
	self:ensureHubEssentials(nil)
	self:tryBuildCity(nil)
	createEvent(60000, "LbgLostHeavenScreenPlay", "pollBuildCity", nil, "")
end

function LbgLostHeavenScreenPlay:ensureMinimalCoreBuildings()
	return self:ensureHubEssentials(nil)
end

function LbgLostHeavenScreenPlay:ensureBuildingAtKey(pOwner, oidKey, poiId, template, wx, wy, plateauZ, heading, hubX, hubY)
	if (pOwner == nil) then
		return false
	end
	local oid = readData(oidKey) or 0
	if (oid > 0 and getSceneObject(oid) ~= nil) then
		return true
	end
	local entry = {
		poi_id = poiId,
		template = template,
		heading = heading or LH_HUB_DEFAULT_HEADING,
	}
	local pB, h = self:spawnHubBuilding(pOwner, entry, wx, wy, plateauZ, hubX or wx, hubY or wy)
	if (pB == nil) then
		printf("LbgLostHeaven: echec minimal %s @ %d,%d (spawnBuilding)\n", tostring(poiId), wx, wy)
		return false
	end
	local newOid = SceneObject(pB):getObjectID()
	writeData(oidKey, newOid)
	self:appendHistoryOid(newOid)
	self:finalizeHubBuilding(pB)
	pcall(function()
		SceneObject(pB):setDirection(h or heading or 0)
	end)
	printf("LbgLostHeaven: minimal OK %s oid=%d @ %d,%d\n", tostring(poiId), newOid, wx, wy)
	return true
end

function LbgLostHeavenScreenPlay:readHistoryOids()
	local oids = {}
	local f = io.open(LH_POI_HISTORY, "r")
	if (f == nil) then
		return oids
	end
	for line in f:lines() do
		local oid = tonumber(line)
		if (oid ~= nil and oid > 0) then
			table.insert(oids, oid)
		end
	end
	f:close()
	return oids
end

function LbgLostHeavenScreenPlay:appendHistoryOid(oid)
	if (oid == nil or oid == 0) then
		return
	end
	local f = io.open(LH_POI_HISTORY, "a")
	if (f ~= nil) then
		f:write(tostring(oid) .. "\n")
		f:close()
	end
end

function LbgLostHeavenScreenPlay:clearHistoryOids()
	local f = io.open(LH_POI_HISTORY, "w")
	if (f ~= nil) then
		f:close()
	end
end

function LbgLostHeavenScreenPlay:destroyAllKnownHubOids()
	local seen = {}
	for _, oid in ipairs(self:readAllOidsFromState()) do
		seen[oid] = true
		pcall(function() destroyBuilding(oid) end)
	end
	for _, oid in ipairs(self:readHistoryOids()) do
		if (seen[oid] == nil) then
			pcall(function() destroyBuilding(oid) end)
		end
	end
	self:destroyOldTheaters()
	self:destroyOldTerrainMods()
	self:clearHistoryOids()
end

function LbgLostHeavenScreenPlay:countPresentPois()
	local n = 0
	for _, oid in ipairs(self:readAllOidsFromState()) do
		if (getSceneObject(oid) ~= nil) then
			n = n + 1
		end
	end
	return n
end

function LbgLostHeavenScreenPlay:readStarportOid()
	local oid = readData(LH_STARPORT_OID_KEY)
	if (oid ~= nil and oid > 0) then
		return oid
	end
	return self:readStarportOidFromState()
end

function LbgLostHeavenScreenPlay:cityHealthy()
	if (readData(LH_BUILD_FLAG) ~= 1) then
		return false
	end
	if (readData(LH_BUILD_VERSION_KEY) ~= LH_BUILD_VERSION) then
		return false
	end
	local starport = self:readStarportOid()
	if (starport == nil or starport == 0 or getSceneObject(starport) == nil) then
		return false
	end
	return self:countPresentPois() >= LH_MIN_PRESENT_POIS
end

function LbgLostHeavenScreenPlay:readStarportOidFromState()
	local f = io.open(LH_STATE_RUNTIME, "r")
	if (f == nil) then
		return nil
	end
	local inStarport = false
	for line in f:lines() do
		if (string.find(line, "poi:lost_heaven_starport", 1, true) ~= nil) then
			inStarport = true
		elseif (inStarport and string.find(line, '"object_id"', 1, true) ~= nil) then
			local oidStr = string.match(line, "(%d+)")
			f:close()
			return oidStr and tonumber(oidStr) or nil
		elseif (inStarport and string.find(line, '"poi_id"', 1, true) ~= nil) then
			inStarport = false
		end
	end
	f:close()
	return nil
end

function LbgLostHeavenScreenPlay:readAllOidsFromState()
	local oids = {}
	local f = io.open(LH_STATE_RUNTIME, "r")
	if (f == nil) then
		return oids
	end
	for line in f:lines() do
		local oidStr = string.match(line, '"object_id"%s*:%s*(%d+)')
		if (oidStr ~= nil) then
			local oid = tonumber(oidStr)
			if (oid ~= nil and oid > 0) then
				table.insert(oids, oid)
			end
		end
	end
	f:close()
	return oids
end

function LbgLostHeavenScreenPlay:readTheaterOids()
	local oids = {}
	local f = io.open(LH_THEATER_STATE, "r")
	if (f == nil) then
		return oids
	end
	for line in f:lines() do
		local oid = tonumber(line)
		if (oid ~= nil and oid > 0) then
			table.insert(oids, oid)
		end
	end
	f:close()
	return oids
end

function LbgLostHeavenScreenPlay:destroyOldTheaters()
	for _, oid in ipairs(self:readTheaterOids()) do
		pcall(function()
			local pObj = getSceneObject(oid)
			if (pObj ~= nil) then
				SceneObject(pObj):destroyObjectFromWorld()
			end
		end)
	end
	local wf = io.open(LH_THEATER_STATE, "w")
	if (wf ~= nil) then
		wf:close()
	end
end

function LbgLostHeavenScreenPlay:appendTheaterOid(oid)
	local f = io.open(LH_THEATER_STATE, "a")
	if (f ~= nil) then
		f:write(tostring(oid) .. "\n")
		f:close()
	end
end

function LbgLostHeavenScreenPlay:ensureHubTerrain(ax, ay, az)
	ax = ax or LH_ANCHOR_X
	ay = ay or LH_ANCHOR_Y
	if (LbgTerrainLib ~= nil and LbgTerrainLib.sanitizeBloatedIdFiles()) then
		printf("LbgLostHeaven: ensureHubTerrain ignore — IDs purgés, restart Core3 requis\n")
		return false
	end
	local weLive, weExpected = 0, (LH_THEATER_HALF_CELLS * 2 + 1) ^ 2
	if (LbgTerrainLib ~= nil) then
		weLive, weExpected = LbgTerrainLib.hubPlateauLive("ia_bridge/lbg_we_theater_oids.txt", LH_THEATER_HALF_CELLS)
	end
	if (weLive >= weExpected - 2) then
		writeData(LH_THEATER_FLAG, 1)
		return true
	end
	local expectedTheaters = weExpected
	local liveTheaters = LbgTerrainLib.countLiveTheaters(LH_THEATER_STATE)
	if (liveTheaters >= expectedTheaters - 2) then
		writeData(LH_THEATER_FLAG, 1)
		return true
	end
	if (LbgTerrainLib == nil) then
		printf("LbgLostHeaven: LbgTerrainLib absent\n")
		return false
	end
	local cfg = LbgTerrainLib.loadPlateauConfig()
	if (cfg ~= nil and math.abs(cfg.cx - ax) < 2 and math.abs(cfg.cy - ay) < 2) then
		if (weLive >= weExpected - 2) then
			writeData(LH_THEATER_FLAG, 1)
			return true
		end
		local r, err = LbgTerrainLib.replaySavedPlateau(true)
		if (r ~= nil and (r.theater_count > 0 or r.flatten_count > 0)) then
			writeData(LH_THEATER_FLAG, 1)
			printf("LbgLostHeaven: replay plateau %d theaters + %d flatten @ %d,%d\n",
				r.theater_count, r.flatten_count, ax, ay)
			return true
		end
		if (err ~= nil) then
			printf("LbgLostHeaven: replay plateau echec — %s\n", err)
		end
	end
	local r = LbgTerrainLib.applyPlateau({
		zone = LH_ZONE,
		cx = ax,
		cy = ay,
		step = LH_TERRAIN_MOD_STEP_M,
		halfCells = LH_TERRAIN_MOD_HALF_CELLS,
		lay = LH_TERRAIN_LAY,
		modIdFile = LH_TERRAIN_MOD_STATE,
		theaterIdFile = LH_THEATER_STATE,
		navmeshName = LH_NAVMESH_NAME,
		navmeshRadius = 280,
		clearFirst = true,
	})
	writeData(LH_THEATER_FLAG, 1)
	printf("LbgLostHeaven: plateau %d theaters + %d flatten pas=%dm siteZ=%.1f span=%dm @ %d,%d\n",
		r.theater_count, r.flatten_count, r.step, r.siteZ, r.span_m, ax, ay)
	if (r.flatten_error ~= nil) then
		printf("LbgLostHeaven: flatten serveur — %s\n", r.flatten_error)
	end
	return r.theater_count > 0 or r.flatten_count > 0
end

function LbgLostHeavenScreenPlay:safeTeleportToHub(pPlayer)
	if (pPlayer == nil) then
		return
	end
	local ax, ay, az = self:readHubAnchor()
	local tx = ax
	local ty = ay + LH_STARPORT_SPAWN_OY
	local z = self:readPlateauZ(az)
	if (getPlanetHeight ~= nil) then
		local hz = getPlanetHeight(LH_ZONE, tx, ty)
		if (hz ~= nil and hz > -15000) then
			z = hz
		end
	end
	CreatureObject(pPlayer):teleport(tx, z + 0.15, ty, LH_HUB_DEFAULT_HEADING)
end

function LbgLostHeavenScreenPlay:ensureBlueFrog(pOwner, ax, ay, plateauZ)
	if (readData(LH_BLUE_FROG_FLAG) == 1) then
		local oid = readData(LH_BLUE_FROG_OID_KEY)
		if (oid ~= nil and oid > 0 and getSceneObject(oid) ~= nil) then
			return true
		end
	end
	if (pOwner == nil) then
		return false
	end
	local wx = ax + 50
	local wy = ay - 50
	local z = plateauZ or LH_ANCHOR_Z
	pcall(function()
		if (getPlanetHeight ~= nil) then
			local hz = getPlanetHeight(LH_ZONE, wx, wy)
			if (hz ~= nil and hz > -15000) then
				z = hz
			end
		end
	end)
	local pTerm = spawnSceneObject(LH_ZONE, LH_BLUE_FROG_TEMPLATE, wx, z + 0.1, wy, 0, 1, 0, 0, 0)
	if (pTerm == nil) then
		printf("LbgLostHeaven: echec blue frog @ %d,%d\n", wx, wy)
		return false
	end
	local oid = SceneObject(pTerm):getObjectID()
	writeData(LH_BLUE_FROG_OID_KEY, oid)
	writeData(LH_BLUE_FROG_FLAG, 1)
	self:appendHistoryOid(oid)
	printf("LbgLostHeaven: blue frog oid=%d @ %d,%d z=%.1f\n", oid, wx, wy, z)
	return true
end

function LbgLostHeavenScreenPlay:finalizeHubBuilding(pBuilding)
	if (pBuilding == nil) then
		return
	end
	pcall(function()
		BuildingObject(pBuilding):setOwnerID(0)
		BuildingObject(pBuilding):revokeAllPermissions()
	end)
end

function LbgLostHeavenScreenPlay:resolvePlacementPlayer(pPreferred)
	if (pPreferred ~= nil) then
		local ok, zone = pcall(function()
			return SceneObject(pPreferred):getZoneName()
		end)
		if (ok and zone == LH_ZONE) then
			return pPreferred
		end
	end
	for _, name in ipairs(LH_PLACEMENT_WATCH) do
		local p = getPlayerByName(name)
		if (p ~= nil and SceneObject(p):getZoneName() == LH_ZONE) then
			return p
		end
	end
	return nil
end

function LbgLostHeavenScreenPlay:onPlayerLoggedIn(pPlayer)
	if (pPlayer == nil or SceneObject(pPlayer):getZoneName() ~= LH_ZONE) then
		return
	end
	createEvent(2000, "LbgLostHeavenScreenPlay", "ensureHubEssentialsEvent", pPlayer, "")
	if (not self:isAutobuildEnabled()) then
		return
	end
	if (self:cityHealthy()) then
		return
	end
	createEvent(3000, "LbgLostHeavenScreenPlay", "tryBuildCityEvent", pPlayer, "")
end

function LbgLostHeavenScreenPlay:tryBuildCityEvent(pPlayer)
	self:tryBuildCity(pPlayer, false)
end

function LbgLostHeavenScreenPlay:forceRebuild(pPlayer)
	if (readData(LH_BUILD_BUSY_FLAG) == 1) then
		if (pPlayer ~= nil) then
			CreatureObject(pPlayer):sendSystemMessage("[LBG] Rebuild deja en cours.")
		end
		return false
	end
	writeData(LH_BUILD_BUSY_FLAG, 1)
	self:resetHubState()
	self:tryBuildCity(pPlayer, true)
	return true
end

function LbgLostHeavenScreenPlay:freezeAutobuild(pPlayer)
	self:setAutobuildEnabled(false)
	if (pPlayer ~= nil) then
		CreatureObject(pPlayer):sendSystemMessage(
			"[LBG] Lost Heaven autobuild OFF — plus de repop auto (login/poll). hub build reste manuel."
		)
	end
	return true
end

function LbgLostHeavenScreenPlay:unfreezeAutobuild(pPlayer)
	self:setAutobuildEnabled(true)
	if (pPlayer ~= nil) then
		CreatureObject(pPlayer):sendSystemMessage("[LBG] Lost Heaven autobuild ON — repop auto reactive.")
	end
	return true
end

function LbgLostHeavenScreenPlay:tryBuildCity(pPreferred, allowManual)
	if (not allowManual and not self:isAutobuildEnabled()) then
		return false
	end
	local pOwner = self:resolvePlacementPlayer(pPreferred)
	if (pOwner == nil) then
		return false
	end
	if (self:cityHealthy()) then
		return true
	end

	self:destroyAllKnownHubOids()
	self:validateBuildPlanSpacing()
	local ax, ay, az = self:findHubAnchor()
	self:ensureHubTerrain(ax, ay, az)
	createEvent(LH_BUILD_PHASE_DELAY_MS, "LbgLostHeavenScreenPlay", "tryBuildCityPhase2", pOwner,
		tostring(ax) .. "," .. tostring(ay) .. "," .. tostring(az))
	return true
end

function LbgLostHeavenScreenPlay:buildTerrainOnly(pPlayer)
	local pOwner = self:resolvePlacementPlayer(pPlayer)
	if (pOwner == nil) then
		return false
	end
	local ax, ay, az = self:findHubAnchor()
	self:ensureHubTerrain(ax, ay, az)
	local siteZ = self:computeSiteMaxZ(ax, ay)
	if (pPlayer ~= nil) then
		CreatureObject(pPlayer):sendSystemMessage(string.format(
			"[LBG] Plateau terrain v%d @ %d,%d siteZ=%.1f — verifie le sol puis hub build",
			LH_BUILD_VERSION, ax, ay, siteZ
		))
	end
	return true
end

function LbgLostHeavenScreenPlay:tryBuildCityPhase2(pOwner, coordStr)
	if (pOwner == nil or coordStr == nil) then
		writeData(LH_BUILD_BUSY_FLAG, 0)
		return false
	end
	local ax, ay, az = string.match(coordStr, "([^,]+),([^,]+),([^,]+)")
	ax = tonumber(ax)
	ay = tonumber(ay)
	az = tonumber(az)
	if (ax == nil or ay == nil) then
		return false
	end

	local plateauZ = self:computeSiteMaxZ(ax, ay)
	self:storePlateauZ(plateauZ)
	printf("LbgLostHeaven: siteZ=%.2f (max relief) @ %d,%d — spawn Z local par batiment\n", plateauZ, ax, ay)

	local placed = {}
	local failed = 0
	local starportOid = 0
	for _, entry in ipairs(LH_BUILD_PLAN) do
		local wx = ax + entry.ox
		local wy = ay + entry.oy
		local pBuilding, heading = self:spawnHubBuilding(pOwner, entry, wx, wy, plateauZ, ax, ay)
		if (pBuilding == nil) then
			failed = failed + 1
			printf("LbgLostHeaven: echec %s @ %d,%d\n", entry.poi_id, wx, wy)
		else
			self:finalizeHubBuilding(pBuilding)
			local oid = SceneObject(pBuilding):getObjectID()
			self:appendHistoryOid(oid)
			if (entry.poi_id == "poi:lost_heaven_starport") then
				starportOid = oid
			end
			local bz = plateauZ
			pcall(function()
				bz = SceneObject(pBuilding):getPositionZ()
			end)
			local expectedZ = self:computeLocalBuildingZ(wx, wy, plateauZ)
			table.insert(placed, {
				poi_id = entry.poi_id,
				template = entry.template,
				x = wx,
				y = wy,
				z = bz,
				heading = heading or 0,
				object_id = oid,
				root_cell_id = 0,
			})
			printf("LbgLostHeaven: OK %s @ %d,%d z=%.1f (ref %.1f)\n", entry.poi_id, wx, wy, bz, expectedZ)
		end
	end

	if (#placed == 0) then
		writeData(LH_BUILD_BUSY_FLAG, 0)
		return false
	end

	self:writeScrapaltaiState(placed, CreatureObject(pOwner):getFirstName(), ax, ay, plateauZ)
	writeData(LH_BUILD_FLAG, 1)
	writeData(LH_BUILD_VERSION_KEY, LH_BUILD_VERSION)
	if (starportOid > 0) then
		writeData(LH_STARPORT_OID_KEY, starportOid)
	end
	self:ensureBlueFrog(pOwner, ax, ay, plateauZ)

	local msg = string.format(
		"[LBG] Lost Heaven v%d : %d batiments (Z local), plateau siteZ=%.1f @ %d,%d.",
		LH_BUILD_VERSION, #placed, plateauZ, ax, ay
	)
	if (failed > 0) then
		msg = msg .. " " .. tostring(failed) .. " echec(s)."
	end
	CreatureObject(pOwner):sendSystemMessage(msg)
	self:safeTeleportToHub(pOwner)
	writeData(LH_BUILD_BUSY_FLAG, 0)
	return true
end

function LbgLostHeavenScreenPlay:jsonEscape(s)
	if (s == nil) then
		return ""
	end
	return (tostring(s):gsub("\\", "\\\\"):gsub('"', '\\"'))
end

function LbgLostHeavenScreenPlay:writeScrapaltaiState(placed, actor, ax, ay, az)
	os.execute("mkdir -p ia_bridge/world_poi 2>/dev/null")
	ax = ax or LH_ANCHOR_X
	ay = ay or LH_ANCHOR_Y
	az = az or LH_ANCHOR_Z
	local lines = {}
	table.insert(lines, "{")
	table.insert(lines, '  "schema_version": 1,')
	table.insert(lines, '  "zone_id": "tatooine",')
	table.insert(lines, '  "display_zone": "Scrapaltai",')
	table.insert(lines, '  "hub_location_id": "loc:lost_heaven_hub",')
	table.insert(lines, '  "build_version": ' .. tostring(LH_BUILD_VERSION) .. ',')
	table.insert(lines, '  "grid_spacing_m": ' .. tostring(LH_GRID_SPACING) .. ',')
	table.insert(lines, '  "civic_center_poi": "' .. LH_CIVIC_CENTER_POI .. '",')
	table.insert(lines, '  "hub_anchor": { "x": ' .. tostring(ax) .. ', "y": ' .. tostring(ay)
		.. ', "z": ' .. tostring(az) .. ', "ref_x": ' .. tostring(LH_ANCHOR_X)
		.. ', "ref_y": ' .. tostring(LH_ANCHOR_Y) .. " },")
	table.insert(lines, '  "terrain_flatten": { "theater_step_m": ' .. tostring(LH_THEATER_STEP_M)
		.. ', "theater_grid": ' .. tostring(LH_THEATER_HALF_CELLS * 2 + 1)
		.. ', "terrain_mod_step_m": ' .. tostring(LH_TERRAIN_MOD_STEP_M)
		.. ', "terrain_mod_grid": ' .. tostring(LH_TERRAIN_MOD_HALF_CELLS * 2 + 1)
		.. ', "lay_file": "' .. self:jsonEscape(LH_TERRAIN_LAY) .. '"'
		.. ', "plateau_z_forced": true, "site_radius_m": ' .. tostring(LH_SITE_RADIUS_M) .. " },")
	table.insert(lines, '  "deployed_via": "lbg_lost_heaven_screenplay",')
	table.insert(lines, '  "exported_at": "' .. os.date("!%Y-%m-%dT%H:%M:%SZ") .. '",')
	table.insert(lines, '  "exported_by": "' .. self:jsonEscape(actor or "script") .. '",')
	table.insert(lines, '  "pois": [')
	for i, p in ipairs(placed) do
		if (i > 1) then
			table.insert(lines, ",")
		end
		table.insert(lines, "    {")
		table.insert(lines, '      "poi_id": "' .. self:jsonEscape(p.poi_id) .. '",')
		table.insert(lines, '      "structure_template": "' .. self:jsonEscape(p.template) .. '",')
		table.insert(lines, '      "world": { "x": ' .. tostring(p.x) .. ', "y": ' .. tostring(p.y)
			.. ', "z": ' .. tostring(p.z) .. ', "heading": ' .. tostring(p.heading) .. " },")
		table.insert(lines, '      "root_cell_id": ' .. tostring(p.root_cell_id or 0) .. ",")
		table.insert(lines, '      "object_id": ' .. tostring(p.object_id or 0))
		table.insert(lines, "    }")
	end
	table.insert(lines, "  ],")
	table.insert(lines, '  "npc_slots": []')
	table.insert(lines, "}")
	local body = table.concat(lines, "\n") .. "\n"
	for _, path in ipairs({ LH_STATE_RUNTIME, LH_STATE_REPO }) do
		local f = io.open(path, "w")
		if (f ~= nil) then
			f:write(body)
			f:close()
		end
	end
end
