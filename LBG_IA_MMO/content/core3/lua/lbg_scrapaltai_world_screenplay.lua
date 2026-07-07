-- M8 — Monde unique Scrapaltai : purge voyage inter-planètes, login migration complémentaire.
-- Voir content/core3/scrapaltai_world.json

local SW_ZONE = "tatooine"
local SW_BLOCK_TRAVEL = true
local SW_TRAVEL_BLOCKED_MSG = "[LBG] Voyage inter-planètes désactivé — explorez Scrapaltai à pied."

LbgScrapaltaiWorldScreenPlay = ScreenPlay:new {
	numberOfActs = 1,
	screenplayName = "LbgScrapaltaiWorldScreenPlay",
}

registerScreenPlay("LbgScrapaltaiWorldScreenPlay", true)

function LbgScrapaltaiWorldScreenPlay:isOtherPlanetZone(zoneName)
	if (zoneName == nil or zoneName == "" or zoneName == SW_ZONE or zoneName == "tutorial") then
		return false
	end
	return true
end

function LbgScrapaltaiWorldScreenPlay:blockInterplanetTravel(pPlayer)
	if (not SW_BLOCK_TRAVEL or pPlayer == nil) then
		return false
	end
	local scene = SceneObject(pPlayer)
	local zone = scene:getZoneName()
	if (not self:isOtherPlanetZone(zone)) then
		return false
	end
	pcall(function()
		CreatureObject(pPlayer):sendSystemMessage(SW_TRAVEL_BLOCKED_MSG)
	end)
	CreatureObject(pPlayer):teleport(4749, 1, -537, 90)
	return true
end

function LbgScrapaltaiWorldScreenPlay:onPlayerLoggedIn(pPlayer)
	if (pPlayer == nil) then
		return
	end
	self:blockInterplanetTravel(pPlayer)
end

function LbgScrapaltaiWorldScreenPlay:start()
	if (self.started ~= nil and self.started) then
		return
	end
	self.started = true
	printf("LbgScrapaltaiWorld: M8 actif — zone=%s block_travel=%s\n", SW_ZONE, tostring(SW_BLOCK_TRAVEL))
end

createEvent(5000, "LbgScrapaltaiWorldScreenPlay", "start", nil, "")
