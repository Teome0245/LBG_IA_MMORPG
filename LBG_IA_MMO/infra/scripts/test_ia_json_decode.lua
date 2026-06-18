-- Test ia_json_decode sur le catalogue PNJ (hors Core3).
dofile(arg[1] or "scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua")

local path = arg[2] or "/opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json"
local f = io.open(path, "r")
if f == nil then
  print("FAIL open", path)
  os.exit(1)
end
local body = f:read("*a")
f:close()

local doc, err = ia_json_decode(body)
if doc == nil then
  print("FAIL decode", err)
  os.exit(2)
end

local n = 0
for _ in pairs(doc.profiles or {}) do n = n + 1 end
print("profiles", n)

local pilots = {}
if doc.entries then
  for _, e in ipairs(doc.entries) do
    if e.pilot_id then pilots[e.pilot_id] = true end
  end
end
if doc.rosters then
  for _, r in ipairs(doc.rosters) do
    if r.slots then
      for _, s in ipairs(r.slots) do
        if s.pilot_id then pilots[s.pilot_id] = true end
      end
    end
  end
end
local c = 0
for _ in pairs(pilots) do c = c + 1 end
print("pilot_ids", c)
print("has brawler", pilots["npc:core3_brawler_trainer_a"] == true)
