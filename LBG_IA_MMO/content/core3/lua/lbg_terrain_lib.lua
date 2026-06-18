-- Terraform / plateau — lib partagée (World Editor + Lost Heaven)
-- Serveur : addTerrainFlatten (heightmap) · Client : spawnTheaterObject (flatten visuel)

LbgTerrainLib = {}

LbgTerrainLib.DEFAULT_LAY = "terrain/poi_small.lay"
LbgTerrainLib.DEFAULT_BOWL_LAY = "terrain/poi_bowl.lay"
LbgTerrainLib.DEFAULT_BOWL_RADIUS_M = 450
LbgTerrainLib.DEFAULT_STEP_M = 48
LbgTerrainLib.DEFAULT_HALF_CELLS = 6
LbgTerrainLib.PLATEAU_CONFIG = "ia_bridge/lbg_terrain_plateau.json"
LbgTerrainLib.BOWL_CONFIG = "ia_bridge/lbg_terrain_bowl.json"
LbgTerrainLib.DEFAULT_BOWL_MOD_FILE = "ia_bridge/lbg_we_bowl_mod_ids.txt"
-- Mesh Tatooine Lost Heaven ~12 m (getPlanetHeight peut renvoyer 28–180 m à proximité)
LbgTerrainLib.DEFAULT_GROUND_Z = 12

function LbgTerrainLib.gridOffsets(step, halfCells)
	local offsets = {}
	for ix = -halfCells, halfCells do
		for iy = -halfCells, halfCells do
			table.insert(offsets, { ix * step, iy * step })
		end
	end
	return offsets
end

function LbgTerrainLib.heightAt(zone, x, y)
	if (getPlanetHeight ~= nil) then
		local h = getPlanetHeight(zone, x, y)
		if (h ~= nil and h >= 0 and h < 512) then
			return h
		end
	end
	if (getWorldFloor ~= nil) then
		local z = getWorldFloor(x, y, zone)
		if (z ~= nil and z >= 0 and z < 512) then
			return z
		end
	end
	return nil
end

-- Hauteur sol pour spawn (theaters) : getWorldFloor d'abord — getPlanetHeight peut renvoyer
-- une valeur incohérente (ex. 180 m) alors que le mesh client/serveur est à ~6 m.
function LbgTerrainLib.floorAt(zone, x, y, refZ)
	refZ = refZ or LbgTerrainLib.DEFAULT_GROUND_Z
	local z = LbgTerrainLib.heightAt(zone, x, y)
	if (z == nil) then
		return refZ
	end
	-- getPlanetHeight local peut valoir ~28 m alors que le mesh joueur est ~12 m
	if (z > refZ + 15) then
		return refZ
	end
	return z
end

-- Indice Z pieds joueur (getPositionZ serveur souvent 0–1 après hub goto).
function LbgTerrainLib.resolveRefZ(zone, x, y, playerZ)
	local hint = LbgTerrainLib.DEFAULT_GROUND_Z
	if (playerZ ~= nil and playerZ > 1 and playerZ < 80) then
		hint = playerZ
	end
	return LbgTerrainLib.floorAt(zone, x, y, hint)
end

function LbgTerrainLib.modIdOk(modId)
	return modId ~= nil and tostring(modId) ~= "0" and tostring(modId) ~= "-0"
end

function LbgTerrainLib.scan(zone, cx, cy, step, halfCells)
	step = step or LbgTerrainLib.DEFAULT_STEP_M
	halfCells = halfCells or 3
	local minz, maxz = 99999, -99999
	local n = 0
	for ix = -halfCells, halfCells do
		for iy = -halfCells, halfCells do
			local h = LbgTerrainLib.heightAt(zone, cx + ix * step, cy + iy * step)
			if (h ~= nil) then
				n = n + 1
				if (h < minz) then minz = h end
				if (h > maxz) then maxz = h end
			end
		end
	end
	if (n == 0) then
		return { count = 0, min = 0, max = 0, delta = 0, center = cx, center_y = cy }
	end
	return {
		count = n,
		min = minz,
		max = maxz,
		delta = maxz - minz,
		center = cx,
		center_y = cy,
		step = step,
		half = halfCells,
	}
end

function LbgTerrainLib.computeSiteMaxZ(zone, cx, cy, step, halfCells, refZ)
	refZ = refZ or LbgTerrainLib.DEFAULT_GROUND_Z
	step = step or LbgTerrainLib.DEFAULT_STEP_M
	halfCells = halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS
	local sum, n = 0, 0
	for _, off in ipairs(LbgTerrainLib.gridOffsets(step, halfCells)) do
		local h = LbgTerrainLib.floorAt(zone, cx + off[1], cy + off[2], refZ)
		if (h ~= nil and h > 0.5) then
			sum = sum + h
			n = n + 1
		end
	end
	if (n == 0) then
		return refZ
	end
	return sum / n
end

function LbgTerrainLib.readIdFile(path)
	local ids = {}
	local f = io.open(path, "r")
	if (f == nil) then
		return ids
	end
	for line in f:lines() do
		local id = tonumber(line)
		-- modId uint64 dépasse souvent 2^53 → Lua le stocke en négatif ; != 0 suffit
		if (id ~= nil and id ~= 0) then
			table.insert(ids, id)
		end
	end
	f:close()
	return ids
end

function LbgTerrainLib.appendIdFile(path, id)
	if (id == nil or id == 0) then
		return
	end
	local f = io.open(path, "a")
	if (f ~= nil) then
		f:write(tostring(id) .. "\n")
		f:close()
	end
end

function LbgTerrainLib.countIdFile(path)
	return #LbgTerrainLib.readIdFile(path)
end

LbgTerrainLib.MAX_ID_FILE_LINES = 500

-- Fichiers ID gonflés (replays headless/boot) : purge disque sans retirer le monde →
-- empiler encore des theaters au login freeze le serveur. Retourne true si purge faite
-- (dans ce cas : redémarrer Core3 avant tout replay/apply).
function LbgTerrainLib.sanitizeBloatedIdFiles()
	local purged = false
	local paths = {
		"ia_bridge/lbg_we_terrain_mod_ids.txt",
		"ia_bridge/lbg_we_bowl_mod_ids.txt",
		"ia_bridge/lbg_we_theater_oids.txt",
		"ia_bridge/lost_heaven_theater_oids.txt",
		"ia_bridge/lost_heaven_terrain_mod_ids.txt",
	}
	for _, path in ipairs(paths) do
		local n = LbgTerrainLib.countIdFile(path)
		if (n > LbgTerrainLib.MAX_ID_FILE_LINES) then
			printf("LbgTerrainLib: WARN purge %s (%d lignes, max %d) — restart Core3 requis\n",
				path, n, LbgTerrainLib.MAX_ID_FILE_LINES)
			LbgTerrainLib.clearIdFile(path)
			purged = true
		end
	end
	return purged
end

function LbgTerrainLib.hubPlateauLive(theaterIdFile, halfCells)
	halfCells = halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS
	local expected = (halfCells * 2 + 1) ^ 2
	local live = LbgTerrainLib.countLiveTheaters(theaterIdFile or "ia_bridge/lbg_we_theater_oids.txt")
	return live, expected
end

function LbgTerrainLib.clearIdFile(path)
	local f = io.open(path, "w")
	if (f ~= nil) then
		f:close()
	end
end

function LbgTerrainLib.clearTerrainMods(zone, modIdFile)
	if (removeTerrainFlatten == nil) then
		return 0
	end
	local ids = LbgTerrainLib.readIdFile(modIdFile)
	local n = #ids
	if (n > LbgTerrainLib.MAX_ID_FILE_LINES) then
		printf("LbgTerrainLib: WARN purge flatten %s (%d lignes)\n", modIdFile, n)
		LbgTerrainLib.clearIdFile(modIdFile)
		return n
	end
	for _, id in ipairs(ids) do
		pcall(function() removeTerrainFlatten(zone, id) end)
	end
	LbgTerrainLib.clearIdFile(modIdFile)
	return n
end

function LbgTerrainLib.clearTheaters(theaterIdFile)
	local ids = LbgTerrainLib.readIdFile(theaterIdFile)
	local n = #ids
	-- Fichier corrompu / replays empilés → boucle énorme au login (freeze serveur)
	if (n > LbgTerrainLib.MAX_ID_FILE_LINES) then
		printf("LbgTerrainLib: WARN purge theaters %s (%d lignes, max %d)\n",
			theaterIdFile, n, LbgTerrainLib.MAX_ID_FILE_LINES)
		LbgTerrainLib.clearIdFile(theaterIdFile)
		return n
	end
	for _, oid in ipairs(ids) do
		pcall(function()
			local pObj = getSceneObject(oid)
			if (pObj ~= nil) then
				SceneObject(pObj):destroyObjectFromWorld()
			end
		end)
	end
	LbgTerrainLib.clearIdFile(theaterIdFile)
	return n
end

function LbgTerrainLib.hasServerFlatten()
	return addTerrainFlatten ~= nil and removeTerrainFlatten ~= nil
end

function LbgTerrainLib.layFileExists(layFile)
	layFile = layFile or LbgTerrainLib.DEFAULT_LAY
	local f = io.open(layFile, "r")
	if (f ~= nil) then
		f:close()
		return true
	end
	return false
end

function LbgTerrainLib.countLiveTheaters(theaterIdFile)
	local n = 0
	for _, oid in ipairs(LbgTerrainLib.readIdFile(theaterIdFile)) do
		if (getSceneObject(oid) ~= nil) then
			n = n + 1
		end
	end
	return n
end

function LbgTerrainLib.pruneDeadTheaterIds(theaterIdFile)
	local live = {}
	for _, oid in ipairs(LbgTerrainLib.readIdFile(theaterIdFile)) do
		if (getSceneObject(oid) ~= nil) then
			table.insert(live, oid)
		end
	end
	LbgTerrainLib.clearIdFile(theaterIdFile)
	for _, oid in ipairs(live) do
		LbgTerrainLib.appendIdFile(theaterIdFile, oid)
	end
	return #live
end

function LbgTerrainLib.savePlateauConfig(cfg)
	os.execute("mkdir -p ia_bridge 2>/dev/null")
	local f = io.open(LbgTerrainLib.PLATEAU_CONFIG, "w")
	if (f == nil) then
		return false
	end
	f:write(string.format(
		'{"zone":"%s","cx":%.2f,"cy":%.2f,"step":%d,"halfCells":%d,"lay":"%s","modIdFile":"%s","theaterIdFile":"%s","navmeshName":"%s","navmeshRadius":%d}\n',
		cfg.zone or "tatooine",
		cfg.cx or 0,
		cfg.cy or 0,
		cfg.step or LbgTerrainLib.DEFAULT_STEP_M,
		cfg.halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS,
		cfg.lay or LbgTerrainLib.DEFAULT_LAY,
		cfg.modIdFile or "ia_bridge/lbg_we_terrain_mod_ids.txt",
		cfg.theaterIdFile or "ia_bridge/lbg_we_theater_oids.txt",
		cfg.navmeshName or "",
		cfg.navmeshRadius or 0
	))
	f:close()
	return true
end

function LbgTerrainLib.loadPlateauConfig()
	local f = io.open(LbgTerrainLib.PLATEAU_CONFIG, "r")
	if (f == nil) then
		return nil
	end
	local raw = f:read("*a")
	f:close()
	if (raw == nil or raw == "") then
		return nil
	end
	local zone = string.match(raw, '"zone"%s*:%s*"([^"]+)"')
	local cx = tonumber(string.match(raw, '"cx"%s*:%s*([%-%.%d]+)'))
	local cy = tonumber(string.match(raw, '"cy"%s*:%s*([%-%.%d]+)'))
	local step = tonumber(string.match(raw, '"step"%s*:%s*(%d+)'))
	local halfCells = tonumber(string.match(raw, '"halfCells"%s*:%s*(%d+)'))
	local lay = string.match(raw, '"lay"%s*:%s*"([^"]+)"')
	local modIdFile = string.match(raw, '"modIdFile"%s*:%s*"([^"]+)"')
	local theaterIdFile = string.match(raw, '"theaterIdFile"%s*:%s*"([^"]+)"')
	local navmeshName = string.match(raw, '"navmeshName"%s*:%s*"([^"]*)"')
	local navmeshRadius = tonumber(string.match(raw, '"navmeshRadius"%s*:%s*(%d+)'))
	if (cx == nil or cy == nil) then
		return nil
	end
	return {
		zone = zone or "tatooine",
		cx = cx,
		cy = cy,
		step = step or LbgTerrainLib.DEFAULT_STEP_M,
		halfCells = halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS,
		lay = lay or LbgTerrainLib.DEFAULT_LAY,
		modIdFile = modIdFile or "ia_bridge/lbg_we_terrain_mod_ids.txt",
		theaterIdFile = theaterIdFile or "ia_bridge/lbg_we_theater_oids.txt",
		navmeshName = (navmeshName ~= nil and navmeshName ~= "") and navmeshName or nil,
		navmeshRadius = navmeshRadius or 0,
	}
end

function LbgTerrainLib.replaySavedPlateau(clearFirst)
	local cfg = LbgTerrainLib.loadPlateauConfig()
	if (cfg == nil) then
		return nil, "aucun plateau sauve (lbg_we terrain plateau d'abord)"
	end
	local r = LbgTerrainLib.applyPlateau({
		zone = cfg.zone,
		cx = cfg.cx,
		cy = cfg.cy,
		step = cfg.step,
		halfCells = cfg.halfCells,
		lay = cfg.lay,
		modIdFile = cfg.modIdFile,
		theaterIdFile = cfg.theaterIdFile,
		navmeshName = cfg.navmeshName,
		navmeshRadius = cfg.navmeshRadius,
		clearFirst = clearFirst ~= false,
	})
	local bowlCfg = LbgTerrainLib.loadBowlConfig()
	if (bowlCfg ~= nil and r ~= nil) then
		local bowlCount, bowlErr = LbgTerrainLib.applyBowl(
			bowlCfg.zone,
			bowlCfg.cx,
			bowlCfg.cy,
			bowlCfg.radiusM,
			bowlCfg.targetZ,
			bowlCfg.lay,
			bowlCfg.modIdFile,
			clearFirst ~= false
		)
		r.bowl_count = bowlCount
		r.bowl_error = bowlErr
		r.bowl_radius = bowlCfg.radiusM
		r.bowl_z = bowlCfg.targetZ
	end
	return r
end

function LbgTerrainLib.saveBowlConfig(cfg)
	os.execute("mkdir -p ia_bridge 2>/dev/null")
	local f = io.open(LbgTerrainLib.BOWL_CONFIG, "w")
	if (f == nil) then
		return false
	end
	f:write(string.format(
		'{"zone":"%s","cx":%.2f,"cy":%.2f,"radiusM":%.0f,"targetZ":%.2f,"lay":"%s","modIdFile":"%s"}\n',
		cfg.zone or "tatooine",
		cfg.cx or 0,
		cfg.cy or 0,
		cfg.radiusM or LbgTerrainLib.DEFAULT_BOWL_RADIUS_M,
		cfg.targetZ or 0,
		cfg.lay or LbgTerrainLib.DEFAULT_BOWL_LAY,
		cfg.modIdFile or LbgTerrainLib.DEFAULT_BOWL_MOD_FILE
	))
	f:close()
	return true
end

function LbgTerrainLib.loadBowlConfig()
	local f = io.open(LbgTerrainLib.BOWL_CONFIG, "r")
	if (f == nil) then
		return nil
	end
	local raw = f:read("*a")
	f:close()
	if (raw == nil or raw == "") then
		return nil
	end
	local zone = string.match(raw, '"zone"%s*:%s*"([^"]+)"')
	local cx = tonumber(string.match(raw, '"cx"%s*:%s*([%-%.%d]+)'))
	local cy = tonumber(string.match(raw, '"cy"%s*:%s*([%-%.%d]+)'))
	local radiusM = tonumber(string.match(raw, '"radiusM"%s*:%s*([%-%.%d]+)'))
	local targetZ = tonumber(string.match(raw, '"targetZ"%s*:%s*([%-%.%d]+)'))
	local lay = string.match(raw, '"lay"%s*:%s*"([^"]+)"')
	local modIdFile = string.match(raw, '"modIdFile"%s*:%s*"([^"]+)"')
	if (cx == nil or cy == nil) then
		return nil
	end
	return {
		zone = zone or "tatooine",
		cx = cx,
		cy = cy,
		radiusM = radiusM or LbgTerrainLib.DEFAULT_BOWL_RADIUS_M,
		targetZ = targetZ or 0,
		lay = lay or LbgTerrainLib.DEFAULT_BOWL_LAY,
		modIdFile = modIdFile or LbgTerrainLib.DEFAULT_BOWL_MOD_FILE,
	}
end

function LbgTerrainLib.applyBowl(zone, cx, cy, radiusM, targetZ, layFile, modIdFile, clearFirst)
	if (not LbgTerrainLib.hasServerFlatten()) then
		return 0, "addTerrainFlatten absent — rebuild Core3 C++"
	end
	layFile = layFile or LbgTerrainLib.DEFAULT_BOWL_LAY
	modIdFile = modIdFile or LbgTerrainLib.DEFAULT_BOWL_MOD_FILE
	if (not LbgTerrainLib.layFileExists(layFile)) then
		return 0, layFile .. " absent — bash deploy_terrain_lay_vm.sh"
	end
	if (clearFirst) then
		LbgTerrainLib.clearTerrainMods(zone, modIdFile)
	end
		local modId = addTerrainFlatten(zone, cx, cy, layFile, 0)
	if (LbgTerrainLib.modIdOk(modId)) then
		LbgTerrainLib.appendIdFile(modIdFile, modId)
		return 1, nil
	end
	return 0, "cuvette serveur echec — verifier poi_bowl.lay puis relog"
end

function LbgTerrainLib.applyServerFlatten(zone, cx, cy, step, halfCells, layFile, modIdFile)
	if (not LbgTerrainLib.hasServerFlatten()) then
		return 0, "addTerrainFlatten absent — rebuild Core3 C++ (build_core3_antigravity_vm.sh)"
	end
	layFile = layFile or LbgTerrainLib.DEFAULT_LAY
	if (not LbgTerrainLib.layFileExists(layFile)) then
		return 0, layFile .. " absent sur le serveur — flatten serveur impossible (theater seulement)"
	end
	step = step or LbgTerrainLib.DEFAULT_STEP_M
	halfCells = halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS
	local count = 0
	for _, off in ipairs(LbgTerrainLib.gridOffsets(step, halfCells)) do
		local tx = cx + off[1]
		local ty = cy + off[2]
		local modId = addTerrainFlatten(zone, tx, ty, layFile, 0)
		if (LbgTerrainLib.modIdOk(modId)) then
			LbgTerrainLib.appendIdFile(modIdFile, modId)
			count = count + 1
		end
	end
	return count, nil
end

function LbgTerrainLib.applyTheaters(zone, cx, cy, siteZ, step, halfCells, theaterIdFile, refZ)
	if (spawnTheaterObject == nil) then
		return 0, "spawnTheaterObject absent"
	end
	step = step or LbgTerrainLib.DEFAULT_STEP_M
	halfCells = halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS
	local hintZ = refZ or LbgTerrainLib.DEFAULT_GROUND_Z
	local count = 0
	local sumZ, nZ = 0, 0
	for _, off in ipairs(LbgTerrainLib.gridOffsets(step, halfCells)) do
		local tx = cx + off[1]
		local ty = cy + off[2]
		local tz = LbgTerrainLib.floorAt(zone, tx, ty, hintZ)
		if (tz == nil or tz < 0.5) then
			tz = hintZ
		end
		local pTheater = spawnTheaterObject(zone, tx, tz, ty, true)
		if (pTheater ~= nil) then
			LbgTerrainLib.appendIdFile(theaterIdFile, SceneObject(pTheater):getObjectID())
			count = count + 1
			sumZ = sumZ + tz
			nZ = nZ + 1
		end
	end
	siteZ = (nZ > 0) and (sumZ / nZ) or hintZ
	return count, siteZ
end

-- opts: zone, cx, cy, step, halfCells, lay, modIdFile, theaterIdFile,
--       doFlatten (bool), doTheater (bool), navmeshName, navmeshRadius, clearFirst (bool)
function LbgTerrainLib.applyPlateau(opts)
	opts = opts or {}
	local zone = opts.zone or "tatooine"
	local cx = opts.cx or 0
	local cy = opts.cy or 0
	local step = opts.step or LbgTerrainLib.DEFAULT_STEP_M
	local halfCells = opts.halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS
	local lay = opts.lay or LbgTerrainLib.DEFAULT_LAY
	local modIdFile = opts.modIdFile or "ia_bridge/lbg_we_terrain_mod_ids.txt"
	local theaterIdFile = opts.theaterIdFile or "ia_bridge/lbg_we_theater_oids.txt"
	local doFlatten = opts.doFlatten ~= false
	local doTheater = opts.doTheater ~= false
	local clearFirst = opts.clearFirst ~= false

	os.execute("mkdir -p ia_bridge 2>/dev/null")

	if (LbgTerrainLib.sanitizeBloatedIdFiles()) then
		printf("LbgTerrainLib: applyPlateau annule — IDs gonflés purgés, restart Core3 puis relancer\n")
		return nil
	end

	if (clearFirst) then
		LbgTerrainLib.clearTerrainMods(zone, modIdFile)
		LbgTerrainLib.clearTheaters(theaterIdFile)
	end

	local refZ = LbgTerrainLib.resolveRefZ(
		zone,
		opts.playerX or cx,
		opts.playerY or cy,
		opts.refZ
	)
	local siteZ = LbgTerrainLib.computeSiteMaxZ(zone, cx, cy, step, halfCells, refZ)
	local flatCount, flatErr = 0, nil
	local thCount, thErr = 0, nil

	if (doFlatten and not LbgTerrainLib.hasServerFlatten()) then
		flatErr = "serveur flatten indisponible — theater client seulement (rebuild Core3)"
		doFlatten = false
	end
	if (doFlatten) then
		flatCount, flatErr = LbgTerrainLib.applyServerFlatten(zone, cx, cy, step, halfCells, lay, modIdFile)
	end
	if (doTheater) then
		thCount, thErr = LbgTerrainLib.applyTheaters(zone, cx, cy, siteZ, step, halfCells, theaterIdFile, refZ)
	end

	if (opts.navmeshName ~= nil and createNavMesh ~= nil) then
		pcall(function()
			createNavMesh(zone, cx, cy, opts.navmeshRadius or 280, true, opts.navmeshName)
		end)
	end

	if (opts.saveConfig ~= false) then
		LbgTerrainLib.savePlateauConfig({
			zone = zone,
			cx = cx,
			cy = cy,
			step = step,
			halfCells = halfCells,
			lay = lay,
			modIdFile = modIdFile,
			theaterIdFile = theaterIdFile,
			navmeshName = opts.navmeshName,
			navmeshRadius = opts.navmeshRadius or 0,
		})
	end

	local span = step * halfCells * 2
	return {
		cx = cx,
		cy = cy,
		siteZ = siteZ,
		step = step,
		halfCells = halfCells,
		span_m = span,
		flatten_count = flatCount,
		theater_count = thCount,
		flatten_error = flatErr,
		theater_error = thErr,
	}
end

-- Site complet Lost Heaven : plateau (theaters + grille flatten) puis cuvette large serveur.
function LbgTerrainLib.applyBaseSite(opts)
	opts = opts or {}
	opts.clearFirst = opts.clearFirst ~= false
	opts.saveConfig = opts.saveConfig ~= false
	local r = LbgTerrainLib.applyPlateau(opts)
	if (r == nil) then
		return nil
	end
	local bowlRadius = opts.bowlRadius or LbgTerrainLib.DEFAULT_BOWL_RADIUS_M
	local bowlZ = opts.bowlZ or 0
	local bowlLay = opts.bowlLay or LbgTerrainLib.DEFAULT_BOWL_LAY
	local bowlModFile = opts.bowlModIdFile or LbgTerrainLib.DEFAULT_BOWL_MOD_FILE
	local bowlCount, bowlErr = LbgTerrainLib.applyBowl(
		opts.zone or "tatooine",
		opts.cx or r.cx,
		opts.cy or r.cy,
		bowlRadius,
		bowlZ,
		bowlLay,
		bowlModFile,
		opts.clearFirst
	)
	if (opts.saveConfig) then
		LbgTerrainLib.saveBowlConfig({
			zone = opts.zone or "tatooine",
			cx = opts.cx or r.cx,
			cy = opts.cy or r.cy,
			radiusM = bowlRadius,
			targetZ = bowlZ,
			lay = bowlLay,
			modIdFile = bowlModFile,
		})
	end
	r.bowl_count = bowlCount
	r.bowl_error = bowlErr
	r.bowl_radius = bowlRadius
	r.bowl_z = bowlZ
	return r
end

LbgTerrainLib.TERRAIN_APPLY_FLAG = "ia_bridge/lbg_we_terrain_apply.flag"
LbgTerrainLib.TERRAIN_APPLY_REQ = "ia_bridge/lbg_we_terrain_apply.json"
LbgTerrainLib.TERRAIN_APPLY_RESULT = "ia_bridge/lbg_we_terrain_apply.result.json"
LbgTerrainLib.HUB_X = 4749
LbgTerrainLib.HUB_Y = -737

function LbgTerrainLib.clearAllTerrain(zone)
	zone = zone or "tatooine"
	local nMod = LbgTerrainLib.clearTerrainMods(zone, "ia_bridge/lbg_we_terrain_mod_ids.txt")
	local nBowl = LbgTerrainLib.clearTerrainMods(zone, LbgTerrainLib.DEFAULT_BOWL_MOD_FILE)
	local nLhMod = LbgTerrainLib.clearTerrainMods(zone, "ia_bridge/lost_heaven_terrain_mod_ids.txt")
	local nTh = LbgTerrainLib.clearTheaters("ia_bridge/lbg_we_theater_oids.txt")
	local nLhTh = LbgTerrainLib.clearTheaters("ia_bridge/lost_heaven_theater_oids.txt")
	return nMod + nBowl + nLhMod, nTh + nLhTh
end

function LbgTerrainLib.collectTerrainStatus(opts)
	opts = opts or {}
	local cx = opts.cx or LbgTerrainLib.HUB_X
	local cy = opts.cy or LbgTerrainLib.HUB_Y
	local step = opts.step or LbgTerrainLib.DEFAULT_STEP_M
	local half = opts.halfCells or LbgTerrainLib.DEFAULT_HALF_CELLS
	local modFile = opts.modIdFile or "ia_bridge/lbg_we_terrain_mod_ids.txt"
	local bowlFile = opts.bowlModIdFile or LbgTerrainLib.DEFAULT_BOWL_MOD_FILE
	local thFile = opts.theaterIdFile or "ia_bridge/lbg_we_theater_oids.txt"
	local nMod = #LbgTerrainLib.readIdFile(modFile)
	local nBowl = #LbgTerrainLib.readIdFile(bowlFile)
	local nTh = #LbgTerrainLib.readIdFile(thFile)
	local liveTh = LbgTerrainLib.countLiveTheaters(thFile)
	return {
		centre_x = cx,
		centre_y = cy,
		step = step,
		halfCells = half,
		span_m = step * half * 2,
		mods = nMod,
		bowl = nBowl,
		theaters = nTh,
		live_theaters = liveTh,
		lay = LbgTerrainLib.layFileExists(LbgTerrainLib.DEFAULT_LAY),
		bowl_lay = LbgTerrainLib.layFileExists(LbgTerrainLib.DEFAULT_BOWL_LAY),
	}
end

function LbgTerrainLib.writeTerrainApplyResult(payload)
	os.execute("mkdir -p ia_bridge 2>/dev/null")
	local f = io.open(LbgTerrainLib.TERRAIN_APPLY_RESULT, "w")
	if (f == nil) then
		return false
	end
	local st = payload.status or {}
	f:write(string.format(
		'{"ok":%s,"action":"%s","siteZ":%.2f,"flatten":%d,"theater":%d,"bowl":%d,"centre_x":%.0f,"centre_y":%.0f,"mods":%d,"live_theaters":%d,"error":"%s","ts":"%s"}\n',
		payload.ok and "true" or "false",
		payload.action or "",
		payload.siteZ or 0,
		payload.flatten or 0,
		payload.theater or 0,
		payload.bowl or 0,
		st.centre_x or LbgTerrainLib.HUB_X,
		st.centre_y or LbgTerrainLib.HUB_Y,
		st.mods or 0,
		st.live_theaters or 0,
		payload.error or "",
		os.date("%Y-%m-%dT%H:%M:%S")
	))
	f:close()
	return true
end

function LbgTerrainLib.loadTerrainApplyRequest()
	local f = io.open(LbgTerrainLib.TERRAIN_APPLY_REQ, "r")
	if (f == nil) then
		return nil
	end
	local raw = f:read("*a")
	f:close()
	if (raw == nil or raw == "") then
		return nil
	end
	local action = string.match(raw, '"action"%s*:%s*"([^"]+)"') or "pipeline"
	local cx = tonumber(string.match(raw, '"cx"%s*:%s*([%-%.%d]+)')) or LbgTerrainLib.HUB_X
	local cy = tonumber(string.match(raw, '"cy"%s*:%s*([%-%.%d]+)')) or LbgTerrainLib.HUB_Y
	local step = tonumber(string.match(raw, '"step"%s*:%s*(%d+)')) or 50
	local half = tonumber(string.match(raw, '"halfCells"%s*:%s*(%d+)')) or 9
	local bowlR = tonumber(string.match(raw, '"bowlRadius"%s*:%s*(%d+)')) or LbgTerrainLib.DEFAULT_BOWL_RADIUS_M
	local bowlZ = tonumber(string.match(raw, '"bowlZ"%s*:%s*([%-%.%d]+)')) or 0
	local clearFirst = string.match(raw, '"clearFirst"%s*:%s*false') == nil
	local lay = string.match(raw, '"lay"%s*:%s*"([^"]+)"') or LbgTerrainLib.DEFAULT_LAY
	return {
		action = action,
		cx = cx,
		cy = cy,
		step = step,
		halfCells = half,
		bowlRadius = bowlR,
		bowlZ = bowlZ,
		clearFirst = clearFirst,
		lay = lay,
	}
end

-- Sans joueur connecté : déclenché par ia_bridge/lbg_we_terrain_apply.flag (script SSH).
function LbgTerrainLib.processHeadlessTerrainApply()
	local flag = io.open(LbgTerrainLib.TERRAIN_APPLY_FLAG, "r")
	if (flag == nil) then
		return false
	end
	flag:close()
	os.remove(LbgTerrainLib.TERRAIN_APPLY_FLAG)

	if (LbgTerrainLib.sanitizeBloatedIdFiles()) then
		LbgTerrainLib.writeTerrainApplyResult({
			ok = false,
			action = "sanitize",
			error = "IDs terrain gonflés purgés — redémarrer Core3 puis relancer apply",
		})
		return true
	end

	local req = LbgTerrainLib.loadTerrainApplyRequest()
	if (req == nil) then
		req = {
			action = "pipeline",
			cx = LbgTerrainLib.HUB_X,
			cy = LbgTerrainLib.HUB_Y,
			step = 50,
			halfCells = 9,
			bowlRadius = LbgTerrainLib.DEFAULT_BOWL_RADIUS_M,
			bowlZ = 0,
			clearFirst = true,
		}
	end

	local result = { ok = false, action = req.action, error = "" }
	local okApply, errApply = pcall(function()
		if (req.action == "clear" or req.action == "pipeline" or req.action == "base") then
			LbgTerrainLib.clearAllTerrain("tatooine")
		end
		if (req.action == "base" or req.action == "pipeline") then
			local r = LbgTerrainLib.applyBaseSite({
				zone = "tatooine",
				cx = req.cx,
				cy = req.cy,
				step = req.step,
				halfCells = req.halfCells,
				lay = req.lay,
				refZ = LbgTerrainLib.DEFAULT_GROUND_Z,
				playerX = req.cx,
				playerY = req.cy,
				bowlRadius = req.bowlRadius,
				bowlZ = req.bowlZ,
				clearFirst = req.clearFirst,
			})
			if (r == nil) then
				error("applyBaseSite nil")
			end
			result.ok = true
			result.siteZ = r.siteZ
			result.flatten = r.flatten_count
			result.theater = r.theater_count
			result.bowl = r.bowl_count or 0
			if (r.flatten_error ~= nil) then
				result.error = r.flatten_error
			end
			if (r.bowl_error ~= nil) then
				result.error = (result.error ~= "" and (result.error .. "; ") or "") .. r.bowl_error
			end
			printf("LbgTerrainLib: headless base @ %.0f,%.0f siteZ=%.1f flatten=%d theater=%d bowl=%d\n",
				req.cx, req.cy, r.siteZ, r.flatten_count, r.theater_count, r.bowl_count or 0)
		elseif (req.action == "replay") then
			local r, err = LbgTerrainLib.replaySavedPlateau(req.clearFirst)
			if (r == nil) then
				error(err or "replay echec")
			end
			result.ok = true
			result.siteZ = r.siteZ
			result.flatten = r.flatten_count
			result.theater = r.theater_count
			result.bowl = r.bowl_count or 0
		elseif (req.action == "clear") then
			result.ok = true
		elseif (req.action == "status") then
			result.ok = true
		else
			error("action inconnue: " .. tostring(req.action))
		end
		result.status = LbgTerrainLib.collectTerrainStatus({
			cx = req.cx,
			cy = req.cy,
			step = req.step,
			halfCells = req.halfCells,
		})
	end)

	if (not okApply) then
		result.error = tostring(errApply)
		printf("LbgTerrainLib: headless terrain error — %s\n", result.error)
	end
	LbgTerrainLib.writeTerrainApplyResult(result)
	return true
end
