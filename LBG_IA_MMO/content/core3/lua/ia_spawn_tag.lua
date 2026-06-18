-- Culling monde Prime : supprime tout spawnMobile vanilla (toutes zones).
-- Exceptions : joueurs, pilotes ia_bridge (__IA_BRIDGE_SPAWNING_PILOT / ia_bridge_pilot_id).
-- Repopulation décorative : spawns manuels / screenplay LBG ; préfixe [No IA] réactivable plus tard si besoin.

local IA_WORLD_CULL_ENABLED = true
-- nil = toutes les planètes
local IA_WORLD_CULL_ZONES = nil

-- Tag [No IA] désactivé tant qu'on part de presque zéro (réactiver pour meubler au fil de l'eau).
local IA_WORLD_NO_IA_ENABLED = false
local IA_WORLD_NO_IA_PREFIX = "[No IA] "
local IA_WORLD_NO_IA_ZONES = nil

local IA_WORLD_CULL_LOG_INTERVAL = 200
local IA_WORLD_CULL_COUNT = 0

IaSpawnTag = {}

function IaSpawnTag:zoneInList(zoneName, list)
	if (list == nil) then
		return true
	end
	if (zoneName == nil or zoneName == "") then
		return false
	end
	for i = 1, #list do
		if (list[i] == zoneName) then
			return true
		end
	end
	return false
end

function IaSpawnTag:cullZoneEnabled(zoneName)
	if (not IA_WORLD_CULL_ENABLED) then
		return false
	end
	return self:zoneInList(zoneName, IA_WORLD_CULL_ZONES)
end

function IaSpawnTag:zoneEnabled(zoneName)
	if (not IA_WORLD_NO_IA_ENABLED) then
		return false
	end
	return self:zoneInList(zoneName, IA_WORLD_NO_IA_ZONES)
end

function IaSpawnTag:isBridgePilotSpawn()
	return _G.__IA_BRIDGE_SPAWNING_PILOT ~= nil and _G.__IA_BRIDGE_SPAWNING_PILOT ~= ""
end

function IaSpawnTag:getVisibleName(pMob)
	local scene = SceneObject(pMob)
	local custom = scene:getCustomObjectName()
	if (custom ~= nil and custom ~= "") then
		return custom
	end
	return scene:getDisplayedName()
end

function IaSpawnTag:alreadyNoIa(name)
	if (name == nil or name == "") then
		return false
	end
	return string.sub(name, 1, #IA_WORLD_NO_IA_PREFIX) == IA_WORLD_NO_IA_PREFIX
end

function IaSpawnTag:isPilotMob(pMob)
	if (pMob == nil) then
		return false
	end
	local oid = SceneObject(pMob):getObjectID()
	local pilotId = readStringData("ia_bridge_pilot_id:" .. oid)
	return pilotId ~= nil and pilotId ~= ""
end

function IaSpawnTag:shouldCullWorldMob(pMob, zoneName)
	if (pMob == nil or not self:cullZoneEnabled(zoneName)) then
		return false
	end
	if (self:isBridgePilotSpawn() or self:isPilotMob(pMob)) then
		return false
	end
	local ok, isCreature = pcall(function()
		return SceneObject(pMob):isCreatureObject()
	end)
	if (not ok or not isCreature) then
		return false
	end
	if (SceneObject(pMob):isPlayerCreature()) then
		return false
	end
	return true
end

function IaSpawnTag:cullWorldMob(pMob, zoneName, mobileTemplate)
	if (not self:shouldCullWorldMob(pMob, zoneName)) then
		return false
	end
	pcall(function()
		SceneObject(pMob):destroyObjectFromWorld(true)
	end)
	IA_WORLD_CULL_COUNT = IA_WORLD_CULL_COUNT + 1
	if (IA_WORLD_CULL_COUNT == 1 or (IA_WORLD_CULL_COUNT % IA_WORLD_CULL_LOG_INTERVAL) == 0) then
		printf(
			"IaSpawnTag: cull #%d template=%s zone=%s\n",
			IA_WORLD_CULL_COUNT,
			tostring(mobileTemplate),
			tostring(zoneName)
		)
	end
	return true
end

function IaSpawnTag:shouldTagWorldMob(pMob, zoneName)
	if (pMob == nil or zoneName == nil or zoneName == "") then
		return false
	end
	if (not self:zoneEnabled(zoneName)) then
		return false
	end
	if (self:isBridgePilotSpawn() or self:isPilotMob(pMob)) then
		return false
	end
	local ok, isCreature = pcall(function()
		return SceneObject(pMob):isCreatureObject()
	end)
	if (not ok or not isCreature) then
		return false
	end
	if (SceneObject(pMob):isPlayerCreature()) then
		return false
	end
	local name = self:getVisibleName(pMob)
	if (self:alreadyNoIa(name)) then
		return false
	end
	return true
end

function IaSpawnTag:applyNoIaPrefix(pMob, zoneName)
	if (not self:shouldTagWorldMob(pMob, zoneName)) then
		return false
	end
	local name = self:getVisibleName(pMob)
	CreatureObject(pMob):setCustomObjectName(IA_WORLD_NO_IA_PREFIX .. name)
	writeData("ia_world_no_ia:" .. SceneObject(pMob):getObjectID(), 1)
	return true
end

function IaSpawnTag:processWorldSpawn(pMob, zoneName, mobileTemplate)
	if (pMob == nil) then
		return
	end
	pcall(function()
		if (self:cullWorldMob(pMob, zoneName, mobileTemplate)) then
			return
		end
		self:applyNoIaPrefix(pMob, zoneName)
	end)
end

function IaSpawnTag:isWorldNoIaMob(pMob)
	if (pMob == nil) then
		return false
	end
	return readData("ia_world_no_ia:" .. SceneObject(pMob):getObjectID()) == 1
		or self:alreadyNoIa(self:getVisibleName(pMob))
end

function IaSpawnTag:installSpawnHooks()
	if (_G.__IA_SPAWN_TAG_HOOKED == true) then
		return
	end
	_G.__IA_SPAWN_TAG_HOOKED = true

	local origSpawnMobile = spawnMobile
	local origSpawnEventMobile = spawnEventMobile

	function spawnMobile(zoneName, mobileTemplate, ...)
		local pMob = origSpawnMobile(zoneName, mobileTemplate, ...)
		IaSpawnTag:processWorldSpawn(pMob, zoneName, mobileTemplate)
		return pMob
	end

	function spawnEventMobile(zoneName, mobileTemplate, ...)
		local pMob = origSpawnEventMobile(zoneName, mobileTemplate, ...)
		IaSpawnTag:processWorldSpawn(pMob, zoneName, mobileTemplate)
		return pMob
	end

	printf(
		"IaSpawnTag: cull=%s (zones=%s) tag=%s\n",
		tostring(IA_WORLD_CULL_ENABLED),
		IA_WORLD_CULL_ZONES == nil and "toutes" or table.concat(IA_WORLD_CULL_ZONES, ","),
		tostring(IA_WORLD_NO_IA_ENABLED)
	)
end

IaSpawnTag:installSpawnHooks()
