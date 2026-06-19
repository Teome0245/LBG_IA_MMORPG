-- Pont IA — Serveur Prime (core3-clean) : planète Tatooine uniquement.
-- Phase A : say / switch_zone / move_to / animate / perform / approach_player. Phase B : snapshot joueur.
-- Phase C : PNJ pilotes + npc_say (spatialChat) + ia_bridge/npc_snapshots.json
-- Aligner avec content/core3/core3_npc_pilots.json
local IA_BRIDGE_ZONE = "tatooine"
local IA_BRIDGE_BOT = "Lia"
local IA_BRIDGE_AI_PLAYERS = { "Lia", "Nix", "Mira" }
-- Inventaire joueurs IA : le forage MVP empile des fruits → blocage déplacement si plein.
local IA_BRIDGE_INV_SOFT_MAX = 50
local IA_BRIDGE_INV_HARD_MAX = 58
local IA_BRIDGE_FORAGE_KEEP_EACH = 2
-- Relais chat (joueurs en ligne, pas d'exception perso hardcodee)
local IA_BRIDGE_CHAT_RELAY = { }
local IA_BRIDGE_CHAT_RANGE_M = 64
local IA_BRIDGE_APPROACH_RANGE_M = 12
-- Mouvement joueurs IA : teleport | walk (serveur) | client (core3client DataTransform).
local IA_BRIDGE_MOVEMENT_MODE_FILE = "ia_bridge/movement_mode"
local IA_BRIDGE_BOT_MOVE_FILE = "ia_bridge/bot_move.jsonl"
local IA_BRIDGE_MOVEMENT_MODE_DEFAULT = "teleport"
local IA_BRIDGE_WALK_STEP_M = 5
local IA_BRIDGE_WALK_STEP_MS = 1400
-- Vanilla tatooine_mos_eisley.lua : 1082877 = salle cantina (bar, PNJ, z ~ -0.9)
-- 1105851 = scene theatre (dump Teome 2026-06-01). 1105853 = mezzanine (theater_manager)
local IA_BRIDGE_CANTINA_CELL = 1082877
local IA_BRIDGE_CANTINA_BAR_CELL = 1082877
-- Centre entrainement Mos Eisley (instructeurs artisan, etc.)
local IA_BRIDGE_TRAINING_CELL = 1189639
local IA_BRIDGE_THEATER_CELL = 1105851
local IA_BRIDGE_CANTINA_BAR_X = 7.26
local IA_BRIDGE_CANTINA_BAR_Z = -0.89
-- Derriere le bar profond (2.8) : conversation bloquee par le comptoir ; ~1.15 = colles au bord client
local IA_BRIDGE_CANTINA_BAR_Y = 1.15
local IA_BRIDGE_CANTINA_BAR_HEADING = 30.2
-- Lia = joueur (pas PNJ comptoir) : cote client du comptoir, face au barman (y=1.15 cote serveur)
local IA_BRIDGE_CANTINA_LIA_GUEST_X = 7.26
local IA_BRIDGE_CANTINA_LIA_GUEST_Y = -0.22
local IA_BRIDGE_CANTINA_LIA_GUEST_Z = 1.02
local IA_BRIDGE_CANTINA_LIA_GUEST_HEADING = 210.0
-- Lost Heaven / Scrapaltai (ADR 0009) — ancre confirmée IG 2026-06-01 (Teome /way 4809 -802)
-- Option A (2026-06-28) : redirect login ME → LH **désactivé** jusqu'au hub terrain déployé (lbg_lost_heaven_screenplay).
-- Réactiver : passer IA_BRIDGE_LOST_HEAVEN_ENABLED à true après rebuild hub v9.
local IA_BRIDGE_LOST_HEAVEN_ENABLED = false
local IA_BRIDGE_LOST_HEAVEN_X = 4809
local IA_BRIDGE_LOST_HEAVEN_Y = -802
local IA_BRIDGE_LOST_HEAVEN_Z = 9
local IA_BRIDGE_ME_SPAWN_X = 3496
local IA_BRIDGE_ME_SPAWN_Y = -4784
local IA_BRIDGE_ME_REDIRECT_RADIUS_M = 1000
local IA_BRIDGE_LOST_HEAVEN_ARRIVED_RADIUS_M = 120
local IA_BRIDGE_CANTINA_BAR_STAFF_Y = 2.8
local IA_BRIDGE_CANTINA_LIA_NEAR_BAR_M = 1.5
local IA_BRIDGE_THEATER_X = 0.34
local IA_BRIDGE_THEATER_Z = 2.13
local IA_BRIDGE_THEATER_Y = 51.19
local IA_BRIDGE_THEATER_HEADING = 173.9
local IA_BRIDGE_LIA_PRESENCE_FILE = "ia_bridge/lia_presence.json"
-- Rotation des styles de danse (perform dance / dance:style).
local IA_BRIDGE_DANCE_ROTATION = {
	"basic", "basic2", "formal", "formal2", "lyrical", "lyrical2",
	"popular", "popular2", "rhythmic", "exotic", "exotic2",
}
local IA_BRIDGE_DANCE_COMPACT = { "basic", "basic2", "formal", "formal2", "lyrical", "lyrical2" }
local IA_BRIDGE_DANCE_FLOURISH_INTERVAL_MS = 3200
local IA_BRIDGE_DANCE_FLOURISH_MAX_ROUNDS = 12
-- Incrémenter pour forcer re-application mesh + scale sur PNJ déjà spawnés (sans rebuild).
local IA_BRIDGE_BODY_APPLY_REV = 2
local IA_BRIDGE_BODY_HEIGHT_DEFER_MS = 600

-- Marqueurs visibles PNJ (cohabitation test) — voir aussi ia_spawn_tag.lua ([No IA] monde).
-- PNJ pilotes LBG : suffixe par défaut ; entrées explicites [IA] dans le catalogue conservées.
local IA_BRIDGE_PILOT_TAG_MODE = "suffix" -- "off" | "prefix" | "suffix" | "both"
local IA_BRIDGE_PILOT_TAG_PREFIX = "[IA] "
local IA_BRIDGE_PILOT_TAG_SUFFIX = " (PNJ IA)"
local IA_BRIDGE_PENDING_FILE = "ia_bridge/pending.jsonl"
local IA_BRIDGE_PLAYER_SNAPSHOT_FILE = "ia_bridge/player_snapshot.json"
local IA_BRIDGE_PLAYER_SNAPSHOTS_FILE = "ia_bridge/player_snapshots.json"
local IA_BRIDGE_EVENTS_FILE = "ia_bridge/events.jsonl"
local IA_BRIDGE_QUEST_STATE_FILE = "ia_bridge/quest_state.jsonl"

-- Catalogue data-driven (déployé par infra/scripts/deploy_core3_ia_bridge_vm.sh)
-- On supporte plusieurs emplacements pour rester robuste entre dev/VM.
local IA_BRIDGE_NPC_CATALOG_PATHS = {
	-- Priorite bin/ (cwd MMOCoreORB/bin) — io.open Core3 peut refuser /opt hors arbre serveur
	"ia_bridge/core3_npc_catalog.json",
	"core3_npc_catalog.json",
	"/opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json",
}
local IA_BRIDGE_CATALOG_BOOT_LOG = "ia_bridge/catalog_boot.log"
local IA_BRIDGE_CONTENT_BASE = "/opt/LBG_IA_MMO/content/core3/"
local IA_BRIDGE_CONTENT_FILES = {
	quests = { "core3_quest_templates.json", "ia_bridge/core3_quest_templates.json" },
	economy = { "core3_economy.json", "ia_bridge/core3_economy.json" },
	factions = { "core3_factions.json", "ia_bridge/core3_factions.json" },
	planets = { "core3_planet_rules.json", "ia_bridge/core3_planet_rules.json" },
	npc_sim = { "core3_npc_simulation.json", "ia_bridge/core3_npc_simulation.json" },
	pilots = { "core3_npc_pilots.json", "ia_bridge/core3_npc_pilots.json" },
	pilot_bodies = { "core3_npc_pilot_bodies.json", "ia_bridge/core3_npc_pilot_bodies.json" },
	species_size = { "core3_species_size_matrix.json", "ia_bridge/core3_species_size_matrix.json" },
	species_slot = { "core3_species_slot_map.json", "ia_bridge/core3_species_slot_map.json" },
}
IA_BRIDGE_QUEST_TEMPLATES = nil
IA_BRIDGE_ECONOMY = nil
IA_BRIDGE_FACTIONS = nil
IA_BRIDGE_PLANET_RULES = nil
IA_BRIDGE_NPC_SIM = nil
local IA_BRIDGE_PASSIVE_STATE_FILE = "ia_bridge/npc_passive_state.json"
local IA_BRIDGE_TICK_COUNT = 0

-- JSON minimal (pas de dépendance dkjson/cjson dans Core3 Lua).
-- Supporte: object/array/string/number/true/false/null.
local function ia_json_decode(str)
	if (str == nil) then
		return nil, "nil input"
	end
	local i = 1
	local n = string.len(str)

	local function skip_ws()
		while i <= n do
			local c = string.sub(str, i, i)
			if (c == " " or c == "\t" or c == "\r" or c == "\n") then
				i = i + 1
			else
				break
			end
		end
	end

	local function parse_error(msg)
		return nil, (msg or "json parse error") .. " @ " .. tostring(i)
	end

	local function parse_string()
		-- assume current is '"'
		i = i + 1
		local out = {}
		local k = 1
		while i <= n do
			local c = string.sub(str, i, i)
			if (c == '"') then
				i = i + 1
				return table.concat(out), nil
			end
			if (c == "\\") then
				local esc = string.sub(str, i + 1, i + 1)
				if (esc == '"' or esc == "\\" or esc == "/") then
					out[k] = esc
					k = k + 1
					i = i + 2
				elseif (esc == "b") then
					out[k] = "\b"
					k = k + 1
					i = i + 2
				elseif (esc == "f") then
					out[k] = "\f"
					k = k + 1
					i = i + 2
				elseif (esc == "n") then
					out[k] = "\n"
					k = k + 1
					i = i + 2
				elseif (esc == "r") then
					out[k] = "\r"
					k = k + 1
					i = i + 2
				elseif (esc == "t") then
					out[k] = "\t"
					k = k + 1
					i = i + 2
				elseif (esc == "u") then
					-- On ne tente pas de décoder UTF-16; on conserve une version ASCII sûre.
					-- uXXXX -> '?'
					out[k] = "?"
					k = k + 1
					i = i + 6
				else
					return parse_error("invalid escape")
				end
			else
				out[k] = c
				k = k + 1
				i = i + 1
			end
		end
		return parse_error("unterminated string")
	end

	local function parse_number()
		local start = i
		local c = string.sub(str, i, i)
		if (c == "-") then
			i = i + 1
		end
		while i <= n do
			c = string.sub(str, i, i)
			if (c >= "0" and c <= "9") then
				i = i + 1
			else
				break
			end
		end
		if (string.sub(str, i, i) == ".") then
			i = i + 1
			while i <= n do
				c = string.sub(str, i, i)
				if (c >= "0" and c <= "9") then
					i = i + 1
				else
					break
				end
			end
		end
		c = string.sub(str, i, i)
		if (c == "e" or c == "E") then
			i = i + 1
			c = string.sub(str, i, i)
			if (c == "+" or c == "-") then
				i = i + 1
			end
			while i <= n do
				c = string.sub(str, i, i)
				if (c >= "0" and c <= "9") then
					i = i + 1
				else
					break
				end
			end
		end
		local raw = string.sub(str, start, i - 1)
		local val = tonumber(raw)
		if (val == nil) then
			return parse_error("invalid number")
		end
		return val, nil
	end

	local parse_value

	local function parse_array()
		-- assume current is '['
		i = i + 1
		skip_ws()
		local arr = {}
		local idx = 1
		if (string.sub(str, i, i) == "]") then
			i = i + 1
			return arr, nil
		end
		while i <= n do
			local v, err = parse_value()
			if (err ~= nil) then
				return nil, err
			end
			arr[idx] = v
			idx = idx + 1
			skip_ws()
			local c = string.sub(str, i, i)
			if (c == ",") then
				i = i + 1
				skip_ws()
			elseif (c == "]") then
				i = i + 1
				return arr, nil
			else
				return parse_error("expected ',' or ']'")
			end
		end
		return parse_error("unterminated array")
	end

	local function parse_object()
		-- assume current is '{'
		i = i + 1
		skip_ws()
		local obj = {}
		if (string.sub(str, i, i) == "}") then
			i = i + 1
			return obj, nil
		end
		while i <= n do
			if (string.sub(str, i, i) ~= '"') then
				return parse_error("expected string key")
			end
			local key, kerr = parse_string()
			if (kerr ~= nil) then
				return nil, kerr
			end
			skip_ws()
			if (string.sub(str, i, i) ~= ":") then
				return parse_error("expected ':'")
			end
			i = i + 1
			skip_ws()
			local v, verr = parse_value()
			if (verr ~= nil) then
				return nil, verr
			end
			obj[key] = v
			skip_ws()
			local c = string.sub(str, i, i)
			if (c == ",") then
				i = i + 1
				skip_ws()
			elseif (c == "}") then
				i = i + 1
				return obj, nil
			else
				return parse_error("expected ',' or '}'")
			end
		end
		return parse_error("unterminated object")
	end

	parse_value = function()
		skip_ws()
		if (i > n) then
			return parse_error("unexpected end")
		end
		local c = string.sub(str, i, i)
		if (c == '"') then
			return parse_string()
		end
		if (c == "{") then
			return parse_object()
		end
		if (c == "[") then
			return parse_array()
		end
		if ((c >= "0" and c <= "9") or c == "-") then
			return parse_number()
		end
		-- literals
		if (string.sub(str, i, i + 3) == "true") then
			i = i + 4
			return true, nil
		end
		if (string.sub(str, i, i + 4) == "false") then
			i = i + 5
			return false, nil
		end
		if (string.sub(str, i, i + 3) == "null") then
			i = i + 4
			return nil, nil
		end
		return parse_error("unexpected token")
	end

	local val, err = parse_value()
	if (err ~= nil) then
		return nil, err
	end
	return val, nil
end

local function ia_read_file_first_existing(paths)
	for j = 1, #paths do
		local p = paths[j]
		local f = io.open(p, "r")
		if (f ~= nil) then
			local body = f:read("*a")
			f:close()
			if (body ~= nil and body ~= "") then
				return body, p
			end
		end
	end
	return nil, ""
end

local function ia_content_paths_for(key)
	local names = IA_BRIDGE_CONTENT_FILES[key]
	if (names == nil) then
		return {}
	end
	local paths = {}
	for i = 1, #names do
		paths[i] = IA_BRIDGE_CONTENT_BASE .. names[i]
		paths[#paths + 1] = names[i]
	end
	return paths
end

local function ia_load_content_json(key)
	local paths = ia_content_paths_for(key)
	local raw, chosen = ia_read_file_first_existing(paths)
	if (raw == nil) then
		return nil, ""
	end
	local doc, err = ia_json_decode(raw)
	if (doc == nil) then
		printf("IaBridge: JSON %s invalide (%s) path=%s\n", tostring(key), tostring(err), tostring(chosen))
		return nil, chosen
	end
	return doc, chosen
end

local function ia_load_all_world_content()
	local q, qp = ia_load_content_json("quests")
	if (q ~= nil and q.templates ~= nil) then
		IA_BRIDGE_QUEST_TEMPLATES = q.templates
		printf("IaBridge: quetes chargees (%s) n=%d\n", tostring(qp), #q.templates)
	end
	local e, ep = ia_load_content_json("economy")
	if (e ~= nil) then
		IA_BRIDGE_ECONOMY = e
		printf("IaBridge: economie chargee (%s)\n", tostring(ep))
	end
	local f, fp = ia_load_content_json("factions")
	if (f ~= nil) then
		IA_BRIDGE_FACTIONS = f
		printf("IaBridge: factions chargees (%s)\n", tostring(fp))
	end
	local p, pp = ia_load_content_json("planets")
	if (p ~= nil) then
		IA_BRIDGE_PLANET_RULES = p
		printf("IaBridge: planetes chargees (%s)\n", tostring(pp))
	end
	local s, sp = ia_load_content_json("npc_sim")
	if (s ~= nil) then
		IA_BRIDGE_NPC_SIM = s
		printf("IaBridge: simulation PNJ chargee (%s)\n", tostring(sp))
	end
end
-- Gestes métier Lia (perform) — aligné content/core3/lia_perform_catalog.json
local IA_BRIDGE_LIA_PERFORM = {
	dance = {
		anims = { "social_dance_medium", "social_spin", "bounce" },
		delay_ms = 2800,
		system = "[Lia] Danse pour les voyageurs.",
	},
	dance_floor = {
		anims = { "wave_on_dance_floor", "social_dance_medium", "celebrate" },
		delay_ms = 2600,
	},
	greet = {
		anims = { "wave_hail", "greet", "nod" },
		delay_ms = 2200,
		system = "[Lia] Salut les voyageurs.",
	},
	bow = { anims = { "bow", "curtsy" }, delay_ms = 2400 },
	cheer = { anims = { "applause_polite", "celebrate", "clap" }, delay_ms = 2200 },
	think = { anims = { "pound_fist_palm", "scratch_head", "inspect" }, delay_ms = 2400 },
	search = {
		anims = { "crouch", "pickup", "inspect" },
		delay_ms = 2500,
		system = "[Lia] Fouille les environs…",
	},
	forage = {
		anims = { "survey", "inspect", "crouch" },
		delay_ms = 2500,
		system = "[Lia] Analyse le terrain.",
	},
	meditate = { anims = { "sit", "sit_ground", "meditate" }, delay_ms = 3000 },
	conduct = {
		anims = { "point", "point_forward", "wave" },
		delay_ms = 2200,
		system = "[Lia] Coordonne la scène.",
	},
}
-- Chemin relatif au cwd du serveur (MMOCoreORB/bin) ; copie miroir via sidecar env si besoin
local IA_BRIDGE_NPC_SNAPSHOT_FILE = "ia_bridge/npc_snapshots.json"
-- Format file : action|player|zone|x|y|z|message  (player = prénom IG ou pilot_id)

-- C.4b — temps jeu : 24h reel = 4j IG ; 1j IG = 6h reel ; phases 2h travail / repos / loisir
local IA_BRIDGE_ROSTER_ENTERTAINER = "roster:mos_entertainer_trainer"
local IA_BRIDGE_ROSTER_QUEST_GIVER = "roster:mos_eisley_quest_giver"
local IA_BRIDGE_ROSTER_POLICIES = {}
local IA_BRIDGE_ROSTER_PRESENCE_PRIORITY = {
	off = 0,
	rest_home = 1,
	leisure = 2,
	cantina = 3,
	post = 4,
}
local IA_BRIDGE_NPC_SAY_COOLDOWN_SEC = 45
local IA_BRIDGE_NPC_SAY_MAX_LEN = 180
local IA_BRIDGE_GAME_TIME = {
	real_hours_per_game_day = 6,
	phase_hours_real = { work = 2, rest = 2, leisure = 2 },
}
local IA_BRIDGE_LIFECYCLE_PHASES = { "work", "rest", "leisure" }
local IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS = {}

local function ia_world_coord_looks_outdoor(x, y)
	return math.abs(tonumber(x) or 0) > 200 or math.abs(tonumber(y) or 0) > 200
end

local function ia_infer_patrol_cell(px, py, explicitCell, defaultCell)
	if (explicitCell ~= nil) then
		return tonumber(explicitCell) or 0
	end
	if (ia_world_coord_looks_outdoor(px, py)) then
		return 0
	end
	return tonumber(defaultCell) or 0
end

local function ia_apply_outdoor_fallback_fields(cfg, anchor)
	if (cfg == nil or anchor == nil) then
		return
	end
	cfg.outdoor_fb_x = tonumber(anchor.x) or 0
	cfg.outdoor_fb_y = tonumber(anchor.y) or 0
	cfg.outdoor_fb_z = tonumber(anchor.z) or 0
	cfg.outdoor_fb_heading = tonumber(anchor.heading) or 0
end

local function ia_apply_interior_outdoor_anchors(doc)
	IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS = {}
	if (doc == nil or doc.interior_outdoor_anchors == nil) then
		return
	end
	local byCell = doc.interior_outdoor_anchors.by_cell
	if (byCell == nil) then
		byCell = doc.interior_outdoor_anchors
	end
	if (byCell == nil) then
		return
	end
	for cellKey, anchor in pairs(byCell) do
		if (anchor ~= nil and anchor.x ~= nil) then
			IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS[tostring(cellKey)] = {
				building_id = anchor.building_id or "",
				label = anchor.label or "",
				x = tonumber(anchor.x) or 0,
				y = tonumber(anchor.y) or 0,
				z = tonumber(anchor.z) or 0,
				heading = tonumber(anchor.heading) or 0,
			}
		end
	end
end

local function ia_lookup_outdoor_anchor(cellId)
	if (cellId == nil or tonumber(cellId) == 0) then
		return nil
	end
	return IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS[tostring(cellId)]
end

local function ia_attach_outdoor_fallback_to_cfg(cfg, binding, roster)
	if (cfg == nil) then
		return
	end
	if (binding ~= nil and binding.outdoor_fallback ~= nil) then
		ia_apply_outdoor_fallback_fields(cfg, binding.outdoor_fallback)
		return
	end
	if (roster ~= nil and roster.outdoor_fallback ~= nil and cfg.outdoor_fb_x == nil) then
		ia_apply_outdoor_fallback_fields(cfg, roster.outdoor_fallback)
	end
	if (cfg.outdoor_fb_x ~= nil) then
		return
	end
	local cells = {}
	local function consider(cell)
		local c = tonumber(cell)
		if (c ~= nil and c ~= 0) then
			cells[tostring(c)] = true
		end
	end
	consider(cfg.spawn_cell)
	consider(cfg.home_cell)
	consider(cfg.cantina_cell)
	for cellKey, _ in pairs(cells) do
		local anchor = IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS[cellKey]
		if (anchor ~= nil) then
			ia_apply_outdoor_fallback_fields(cfg, anchor)
			return
		end
	end
end

local function ia_ensure_outdoor_roam_patrol(cfg)
	if (cfg == nil or cfg.roam_patrol == nil or cfg.outdoor_fb_x == nil) then
		return
	end
	for _, pt in ipairs(cfg.roam_patrol) do
		if ((pt[4] or 0) == 0) then
			return
		end
	end
	local x = cfg.outdoor_fb_x
	local z = cfg.outdoor_fb_z
	local y = cfg.outdoor_fb_y
	cfg.roam_patrol = {
		{ x, z, y, 0 },
		{ x + 4, z, y, 0 },
		{ x - 3, z, y + 4, 0 },
		{ x - 3, z, y - 4, 0 },
	}
end

-- Chargement data-driven (catalogue PNJ + rosters + game_time) ; fallback sur valeurs hardcodées.
local function ia_catalog_boot_log(msg)
	printf("IaBridge: %s\n", tostring(msg))
	local f = io.open(IA_BRIDGE_CATALOG_BOOT_LOG, "a")
	if (f ~= nil) then
		f:write(os.date("%Y-%m-%d %H:%M:%S ") .. tostring(msg) .. "\n")
		f:close()
	end
end

local function ia_load_npc_catalog()
	local raw, chosen = ia_read_file_first_existing(IA_BRIDGE_NPC_CATALOG_PATHS)
	if (raw == nil) then
		ia_catalog_boot_log("catalogue introuvable (fallback hardcoded)")
		return nil, ""
	end
	local doc, err = ia_json_decode(raw)
	if (doc == nil) then
		ia_catalog_boot_log("catalogue JSON invalide: " .. tostring(err) .. " path=" .. tostring(chosen))
		return nil, chosen
	end
	return doc, chosen
end

local function ia_vec3_from(obj)
	if (obj == nil) then
		return 0, 0, 0
	end
	return tonumber(obj.x) or 0, tonumber(obj.z) or 0, tonumber(obj.y) or 0
end

local function ia_apply_game_time_from_catalog(doc)
	if (doc == nil or doc.game_time == nil) then
		return
	end
	local gt = doc.game_time
	if (gt.real_hours_per_game_day ~= nil) then
		IA_BRIDGE_GAME_TIME.real_hours_per_game_day = tonumber(gt.real_hours_per_game_day) or IA_BRIDGE_GAME_TIME.real_hours_per_game_day
	end
	if (gt.phase_hours_real ~= nil) then
		IA_BRIDGE_GAME_TIME.phase_hours_real.work = tonumber(gt.phase_hours_real.work) or IA_BRIDGE_GAME_TIME.phase_hours_real.work
		IA_BRIDGE_GAME_TIME.phase_hours_real.rest = tonumber(gt.phase_hours_real.rest) or IA_BRIDGE_GAME_TIME.phase_hours_real.rest
		IA_BRIDGE_GAME_TIME.phase_hours_real.leisure = tonumber(gt.phase_hours_real.leisure) or IA_BRIDGE_GAME_TIME.phase_hours_real.leisure
	end
end

local function ia_build_pilots_from_catalog(doc)
	if (doc == nil) then
		return false, 0
	end
	ia_apply_interior_outdoor_anchors(doc)
	local pilots = {}
	local rosterPolicies = {}
	-- entries -> PNJ simples
	if (doc.entries ~= nil) then
		for _, e in ipairs(doc.entries) do
			if (e ~= nil and e.pilot_id ~= nil and e.binding ~= nil) then
				local b = e.binding
				local spawn = b.spawn or (b.binding and b.binding.spawn) or b.post
				if (spawn == nil and b.mode ~= "roster") then
					spawn = b.spawn
				end
				if (spawn ~= nil) then
					local cell = tonumber(spawn.cell) or 0
					pilots[e.pilot_id] = {
						lbg_npc_id = e.lbg_npc_id or "",
						display_name = e.display_name or e.pilot_id,
						mobile = (b.mobile_template or ""),
						x = tonumber(spawn.x) or 0,
						y = tonumber(spawn.y) or 0,
						z = tonumber(spawn.z) or 0,
						heading = tonumber(spawn.heading) or 0,
						home_cell = cell,
						spawn_cell = cell,
						follow_lia = (b.follow_lia and b.follow_lia.enabled) == true,
						roam_mode = (b.follow_lia and b.follow_lia.mode) or b.roam_mode,
						roam_contain_m = (b.follow_lia and b.follow_lia.roam_contain_m) or b.roam_contain_m,
						roam_patrol = b.roam_patrol,
					}
					if (pilots[e.pilot_id].roam_mode == "walk_patrol" and pilots[e.pilot_id].roam_patrol == nil) then
						pilots[e.pilot_id].roam_mode = "linger"
					end
					ia_attach_outdoor_fallback_to_cfg(pilots[e.pilot_id], b, nil)
					ia_ensure_outdoor_roam_patrol(pilots[e.pilot_id])
				end
			end
		end
	end

	-- rosters -> pilotes pilotés par lifecycle
	if (doc.rosters ~= nil) then
		for _, r in ipairs(doc.rosters) do
			if (r ~= nil and r.slots ~= nil and r.roster_id ~= nil and r.status ~= "draft") then
				if (r.service_policy ~= nil and r.service_policy ~= "") then
					rosterPolicies[r.roster_id] = r.service_policy
				end
				for _, s in ipairs(r.slots) do
					if (s ~= nil and s.pilot_id ~= nil and s.binding ~= nil) then
						local b = s.binding
						local post = b.post or r.service_post
						if (post ~= nil) then
							local postCell = tonumber(post.cell)
							if (postCell == nil and r.service_post ~= nil) then
								postCell = tonumber(r.service_post.cell)
							end
							local cfg = {
								lbg_npc_id = s.lbg_npc_id or "",
								display_name = s.display_name or s.pilot_id,
								mobile = (b.mobile_template or ""),
								x = tonumber(post.x) or 0,
								y = tonumber(post.y) or 0,
								z = tonumber(post.z) or 0,
								heading = tonumber(post.heading) or 0,
								spawn_cell = postCell or 0,
								follow_lia = false,
								roster = r.roster_id,
								shift_offset = tonumber(s.shift_offset) or 0,
							}
							if (b.combat_policy ~= nil and b.combat_policy ~= "") then
								cfg.combat_policy = b.combat_policy
							end
							local po = b.post_offset_toward_customer
							if (po ~= nil) then
								if (po.dx ~= nil) then
									cfg.post_offset_dx = tonumber(po.dx)
								end
								if (po.dy ~= nil) then
									cfg.post_offset_dy = tonumber(po.dy)
								end
								if (po.dz ~= nil) then
									cfg.post_offset_dz = tonumber(po.dz)
								end
							end
							-- cantina presence
							if (b.cantina ~= nil) then
								cfg.cantina_x = tonumber(b.cantina.x) or nil
								cfg.cantina_y = tonumber(b.cantina.y) or nil
								cfg.cantina_z = tonumber(b.cantina.z) or nil
								cfg.cantina_cell = tonumber(b.cantina.cell) or nil
								cfg.cantina_heading = tonumber(b.cantina.heading) or nil
							end
							-- home pour repos (rest_home, PNJ en ligne) et loisir
							if (b.home ~= nil) then
								cfg.home_x = tonumber(b.home.x) or nil
								cfg.home_y = tonumber(b.home.y) or nil
								cfg.home_z = tonumber(b.home.z) or nil
								cfg.home_cell = tonumber(b.home.cell) or nil
							end
							-- leisure patrol
							if (b.leisure_patrol ~= nil) then
								cfg.roam_mode = "walk_patrol"
								cfg.roam_contain_m = tonumber(b.leisure_contain_m) or 12
								cfg.roam_patrol = {}
								local patrolCell = cfg.home_cell or cfg.spawn_cell or 0
								for _, pt in ipairs(b.leisure_patrol) do
									local px = tonumber(pt.x) or 0
									local py = tonumber(pt.y) or 0
									local pz = tonumber(pt.z) or 0
									local pc = ia_infer_patrol_cell(px, py, pt.cell, patrolCell)
									table.insert(cfg.roam_patrol, { px, pz, py, pc })
								end
							end
							if (r.roster_id ~= nil and string.find(r.roster_id, "mos_pilot_", 1, true) ~= nil) then
								cfg.outdoor_world = true
								cfg.roam_contain_m = tonumber(b.leisure_contain_m) or 8
							end
							ia_attach_outdoor_fallback_to_cfg(cfg, b, r)
							ia_ensure_outdoor_roam_patrol(cfg)
							pilots[s.pilot_id] = cfg
						end
					end
				end
			end
		end
	end

	-- Appliquer si au moins 1 pilote trouvé.
	local count = 0
	for _, _ in pairs(pilots) do
		count = count + 1
	end
	if (count <= 0) then
		return false, 0
	end
	IA_BRIDGE_PILOTS = pilots
	local ps = _G.IA_BRIDGE_PERSIST
	if (ps == nil) then
		ps = { pilotMobs = {}, catalogPilots = nil, rosterPolicies = nil }
		_G.IA_BRIDGE_PERSIST = ps
	end
	ps.catalogPilots = pilots
	ps.rosterPolicies = rosterPolicies
	IA_BRIDGE_ROSTER_POLICIES = rosterPolicies
	writeData("ia_bridge_catalog_ready", 1)
	local anchorCount = 0
	for _ in pairs(IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS) do
		anchorCount = anchorCount + 1
	end
	if (anchorCount > 0) then
		ia_catalog_boot_log("interior outdoor anchors=" .. tostring(anchorCount))
	end
	return true, count
end

-- Pilotes supplementaires (sublots interieurs) depuis core3_npc_pilots.json
local function ia_merge_pilots_from_pilots_json()
	local doc, chosen = ia_load_content_json("pilots")
	if (doc == nil or doc.pilots == nil) then
		return 0
	end
	local added = 0
	for _, e in ipairs(doc.pilots) do
		if (e ~= nil and e.pilot_id ~= nil and e.spawn ~= nil and IA_BRIDGE_PILOTS[e.pilot_id] == nil) then
			local s = e.spawn
			local cell = tonumber(s.cell) or 0
			local cfg = {
				lbg_npc_id = e.lbg_npc_id or "",
				display_name = e.display_name or e.pilot_id,
				mobile = e.mobile_template or "commoner",
				x = tonumber(s.x) or 0,
				y = tonumber(s.y) or 0,
				z = tonumber(s.z) or 0,
				heading = tonumber(s.heading) or 0,
				home_cell = cell,
				spawn_cell = cell,
				follow_lia = false,
				roam_mode = (cell ~= 0) and "linger" or "linger",
				roam_contain_m = (cell ~= 0) and 8 or 14,
			}
			if (e.body ~= nil) then
				cfg.lbg_race_id = e.body.lbg_race_id
				cfg.lbg_race_display = e.body.lbg_race_display
				cfg.species_key = e.body.species_key
				cfg.gender = e.body.gender
				cfg.height_m = tonumber(e.body.height_m)
			end
			if (e.combat_policy ~= nil) then
				cfg.combat_policy = e.combat_policy
			end
			ia_attach_outdoor_fallback_to_cfg(cfg, e, nil)
			ia_ensure_outdoor_roam_patrol(cfg)
			IA_BRIDGE_PILOTS[e.pilot_id] = cfg
			added = added + 1
		end
	end
	if (added > 0) then
		printf("IaBridge: pilotes JSON merges (%s) +%d\n", tostring(chosen), added)
	end
	return added
end

IA_BRIDGE_SPECIES_HEIGHT = {}
IA_BRIDGE_LBG_SLOT_HEIGHT = {}

local function ia_load_species_slot_heights()
	local doc, chosen = ia_load_content_json("species_slot")
	if (doc == nil or doc.slots == nil) then
		return 0
	end
	local count = 0
	for _, slot in ipairs(doc.slots) do
		if (slot ~= nil and slot.species_key ~= nil and slot.target_height_m ~= nil) then
			local t = slot.target_height_m
			IA_BRIDGE_LBG_SLOT_HEIGHT[tostring(slot.species_key)] = {
				min_m = tonumber(t[1]) or tonumber(t.min) or nil,
				max_m = tonumber(t[2]) or tonumber(t.max) or nil,
				race_id = slot.race_id,
			}
			count = count + 1
		end
	end
	if (count > 0) then
		printf("IaBridge: slots tailles LBG charges (%s) n=%d\n", tostring(chosen), count)
	end
	return count
end

local function ia_load_species_height_table()
	local doc, chosen = ia_load_content_json("species_size")
	if (doc == nil or doc.swg_height_active == nil) then
		printf("IaBridge: matrice tailles introuvable (fallback vide)\n")
		return 0
	end
	local count = 0
	for _, row in ipairs(doc.swg_height_active) do
		if (row ~= nil and row.species_key ~= nil and row.gender ~= nil) then
			local key = tostring(row.species_key) .. ":" .. tostring(row.gender)
			IA_BRIDGE_SPECIES_HEIGHT[key] = {
				base_m = tonumber(row.base_m) or 1.65,
				scale_min = tonumber(row.scale_min) or 0.89,
				scale_max = tonumber(row.scale_max) or 1.08,
			}
			count = count + 1
		end
	end
	printf("IaBridge: matrice tailles chargee (%s) rows=%d\n", tostring(chosen), count)
	return count
end

local function ia_merge_pilot_bodies()
	local doc, chosen = ia_load_content_json("pilot_bodies")
	if (doc == nil) then
		return 0
	end
	local defaults = doc.defaults or {}
	local merged = 0
	local function applyBody(pilotId, body)
		if (pilotId == nil or body == nil or IA_BRIDGE_PILOTS[pilotId] == nil) then
			return
		end
		local cfg = IA_BRIDGE_PILOTS[pilotId]
		cfg.lbg_race_id = body.lbg_race_id or defaults.lbg_race_id or cfg.lbg_race_id
		cfg.lbg_race_display = body.lbg_race_display or defaults.lbg_race_display or cfg.lbg_race_display
		cfg.species_key = body.species_key or defaults.species_key or cfg.species_key
		cfg.gender = body.gender or defaults.gender or cfg.gender
		cfg.height_m = tonumber(body.height_m) or tonumber(defaults.height_m) or cfg.height_m
		merged = merged + 1
	end
	if (doc.pilots ~= nil) then
		for pilotId, body in pairs(doc.pilots) do
			applyBody(pilotId, body)
		end
	end
	if (merged > 0) then
		printf("IaBridge: corps PNJ merges (%s) +%d\n", tostring(chosen), merged)
	end
	return merged
end

local IA_BRIDGE_PILOTS_FALLBACK = {
	["npc:core3_scribe"] = {
		lbg_npc_id = "npc:scribe",
		display_name = "[IA] Archiviste",
		mobile = "commoner_old",
		x = 3498,
		y = -4788,
		z = 5,
		heading = 90,
		follow_lia = false,
		roam_mode = "linger",
		roam_contain_m = 8,
	},
	["npc:core3_guard"] = {
		lbg_npc_id = "npc:guard",
		display_name = "[IA] Garde",
		mobile = "mos_espa_police_officer",
		x = 3568,
		y = -4818,
		z = 5,
		heading = 180,
		follow_lia = false,
		roam_mode = "linger",
		roam_contain_m = 8,
	},
	-- C.3 — remplacement PNJ simple (poste fixe Mos Eisley, pas de suivi Lia)
	["npc:core3_kisreudi"] = {
		lbg_npc_id = "npc:scientist_mos",
		display_name = "Kisreudi Teste",
		mobile = "scientist",
		x = 3551,
		y = -4725,
		z = 5,
		heading = 270,
		follow_lia = false,
	},
	-- C.4 — roster instructeur entertainer (exactly_one au poste + show cantina)
	["npc:core3_bige_coto"] = {
		lbg_npc_id = "npc:entertainer_trainer_mos",
		display_name = "Bige Coto",
		mobile = "trainer_entertainer",
		x = 3477.89,
		y = -4791.6,
		z = 5,
		heading = 215,
		follow_lia = false,
		roster = IA_BRIDGE_ROSTER_ENTERTAINER,
		shift_offset = 0,
		cantina_x = IA_BRIDGE_THEATER_X,
		cantina_z = IA_BRIDGE_THEATER_Z,
		cantina_y = IA_BRIDGE_THEATER_Y,
		cantina_cell = IA_BRIDGE_THEATER_CELL,
		cantina_heading = IA_BRIDGE_THEATER_HEADING,
		home_x = IA_BRIDGE_THEATER_X,
		home_z = IA_BRIDGE_THEATER_Z,
		home_y = IA_BRIDGE_THEATER_Y,
		home_cell = IA_BRIDGE_THEATER_CELL,
	},
	["npc:core3_lyra_velo"] = {
		lbg_npc_id = "npc:entertainer_trainer_relief",
		display_name = "Lyra Velo",
		mobile = "trainer_entertainer",
		x = 3477.89,
		y = -4791.6,
		z = 5,
		heading = 215,
		follow_lia = false,
		roster = IA_BRIDGE_ROSTER_ENTERTAINER,
		shift_offset = 1,
		cantina_x = IA_BRIDGE_THEATER_X,
		cantina_z = IA_BRIDGE_THEATER_Z,
		cantina_y = IA_BRIDGE_THEATER_Y,
		cantina_cell = IA_BRIDGE_THEATER_CELL,
		cantina_heading = IA_BRIDGE_THEATER_HEADING,
		home_x = IA_BRIDGE_THEATER_X,
		home_z = IA_BRIDGE_THEATER_Z,
		home_y = IA_BRIDGE_THEATER_Y,
		home_cell = IA_BRIDGE_THEATER_CELL,
		roam_mode = "linger",
		roam_contain_m = 18,
	},
	["npc:core3_talen_ress"] = {
		lbg_npc_id = "npc:entertainer_trainer_relief2",
		display_name = "Talen Ress",
		mobile = "trainer_entertainer",
		x = 3477.89,
		y = -4791.6,
		z = 5,
		heading = 215,
		follow_lia = false,
		roster = IA_BRIDGE_ROSTER_ENTERTAINER,
		shift_offset = 2,
		cantina_x = IA_BRIDGE_THEATER_X,
		cantina_z = IA_BRIDGE_THEATER_Z,
		cantina_y = IA_BRIDGE_THEATER_Y,
		cantina_cell = IA_BRIDGE_THEATER_CELL,
		cantina_heading = IA_BRIDGE_THEATER_HEADING,
		home_x = IA_BRIDGE_THEATER_X,
		home_z = IA_BRIDGE_THEATER_Z,
		home_y = IA_BRIDGE_THEATER_Y,
		home_cell = IA_BRIDGE_THEATER_CELL,
		roam_mode = "linger",
		roam_contain_m = 18,
	},
	-- C.5 — triplon donneur de quete (poste informant Mos Eisley)
	["npc:core3_vex_sorn"] = {
		lbg_npc_id = "npc:quest_giver_mos",
		display_name = "Vex Sorn",
		mobile = "informant_npc_lvl_1",
		x = 3488,
		y = -4782,
		z = 5,
		heading = 135,
		follow_lia = false,
		roster = IA_BRIDGE_ROSTER_QUEST_GIVER,
		shift_offset = 0,
		home_x = 3495,
		home_z = 5,
		home_y = -4790,
		roam_mode = "walk_patrol",
		roam_contain_m = 20,
		roam_patrol = {
			{ 3488, 5, -4782 },
			{ 3480, 5, -4775 },
			{ 3495, 5, -4790 },
		},
	},
	["npc:core3_nira_kell"] = {
		lbg_npc_id = "npc:quest_giver_mos_relief",
		display_name = "Nira Kell",
		mobile = "informant_npc_lvl_1",
		x = 3488,
		y = -4782,
		z = 5,
		heading = 135,
		follow_lia = false,
		roster = IA_BRIDGE_ROSTER_QUEST_GIVER,
		shift_offset = 1,
		home_x = 3475,
		home_z = 5,
		home_y = -4810,
		roam_mode = "walk_patrol",
		roam_contain_m = 18,
		roam_patrol = {
			{ 3475, 5, -4810 },
			{ 3482, 5, -4795 },
			{ 3468, 5, -4802 },
		},
	},
	["npc:core3_daan_oth"] = {
		lbg_npc_id = "npc:quest_giver_mos_relief2",
		display_name = "Daan Oth",
		mobile = "informant_npc_lvl_1",
		x = 3488,
		y = -4782,
		z = 5,
		heading = 135,
		follow_lia = false,
		roster = IA_BRIDGE_ROSTER_QUEST_GIVER,
		shift_offset = 2,
		home_x = 3500,
		home_z = 5,
		home_y = -4805,
		roam_mode = "walk_patrol",
		roam_contain_m = 18,
		roam_patrol = {
			{ 3500, 5, -4805 },
			{ 3490, 5, -4795 },
			{ 3505, 5, -4788 },
		},
	},
}

local function ia_table_has_entries(tbl)
	return tbl ~= nil and next(tbl) ~= nil
end

if (_G.IA_BRIDGE_PERSIST == nil) then
	_G.IA_BRIDGE_PERSIST = { pilotMobs = {}, catalogPilots = nil, rosterPolicies = nil }
end

if (ia_table_has_entries(_G.IA_BRIDGE_PERSIST.catalogPilots)) then
	IA_BRIDGE_PILOTS = _G.IA_BRIDGE_PERSIST.catalogPilots
elseif (IA_BRIDGE_PILOTS == nil) then
	IA_BRIDGE_PILOTS = {}
end

if (_G.IA_BRIDGE_PERSIST.rosterPolicies ~= nil) then
	IA_BRIDGE_ROSTER_POLICIES = _G.IA_BRIDGE_PERSIST.rosterPolicies
end

IaBridgeScreenPlay = ScreenPlay:new {
	numberOfActs = 1,
	screenplayName = "IaBridgeScreenPlay",
	tickMs = 2000,
	rosterPresence = {},
	questSeq = 0,
}

registerScreenPlay("IaBridgeScreenPlay", true)

if (_G.IA_BRIDGE_PERSIST.pilotsBootDone == true) then
	IaBridgeScreenPlay.pilotsBootDone = true
end

function IaBridgeScreenPlay:persistStore()
	if (_G.IA_BRIDGE_PERSIST == nil) then
		_G.IA_BRIDGE_PERSIST = { pilotMobs = {}, catalogPilots = nil, rosterPolicies = nil }
	end
	if (_G.IA_BRIDGE_PERSIST.pilotMobs == nil) then
		_G.IA_BRIDGE_PERSIST.pilotMobs = {}
	end
	return _G.IA_BRIDGE_PERSIST
end

function IaBridgeScreenPlay:syncGlobalsFromPersist()
	local ps = self:persistStore()
	if (ia_table_has_entries(ps.catalogPilots)) then
		IA_BRIDGE_PILOTS = ps.catalogPilots
	elseif (ia_table_has_entries(IA_BRIDGE_PILOTS)) then
		ps.catalogPilots = IA_BRIDGE_PILOTS
	end
	if (ps.rosterPolicies ~= nil) then
		IA_BRIDGE_ROSTER_POLICIES = ps.rosterPolicies
	end
end

function IaBridgeScreenPlay:hasProductionCatalog()
	local ps = self:persistStore()
	if (ia_table_has_entries(ps.catalogPilots)) then
		return true
	end
	if (ia_table_has_entries(IA_BRIDGE_PILOTS)) then
		return true
	end
	return false
end

function IaBridgeScreenPlay:shouldRehydrateCatalog()
	if (self:hasProductionCatalog()) then
		return false
	end
	local last = readData("ia_bridge_catalog_rehydrate_ts") or 0
	return (os.time() - last) >= 30
end

function IaBridgeScreenPlay:ensureCatalogReady()
	self:syncGlobalsFromPersist()
	if (self:hasProductionCatalog()) then
		return true
	end
	if (not self:shouldRehydrateCatalog()) then
		return false
	end
	writeData("ia_bridge_catalog_rehydrate_ts", os.time())
	local doc, chosen = ia_load_npc_catalog()
	if (doc == nil) then
		ia_catalog_boot_log("catalogue rehydrate FAILED introuvable")
		return false
	end
	ia_apply_game_time_from_catalog(doc)
	local ok, pilotCount = ia_build_pilots_from_catalog(doc)
	if (not ok) then
		IA_BRIDGE_PILOTS = IA_BRIDGE_PILOTS_FALLBACK
		self:syncGlobalsFromPersist()
		ia_catalog_boot_log("catalogue rehydrate fallback hardcoded")
		return ia_table_has_entries(IA_BRIDGE_PILOTS)
	end
	ia_merge_pilots_from_pilots_json()
	ia_merge_pilot_bodies()
	self:syncGlobalsFromPersist()
	writeData("ia_bridge_catalog_ready", 1)
	ia_catalog_boot_log("catalogue rehydrate OK path=" .. tostring(chosen) .. " pilots=" .. tostring(pilotCount))
	return true
end

function IaBridgeScreenPlay:rehydratePilotMobCache()
	for pilotId, _ in pairs(self:catalogPilotTable()) do
		self:resolvePilotMob(pilotId)
	end
	for pilotId, _ in pairs(self:pilotMobTable()) do
		self:resolvePilotMob(pilotId)
	end
end

function IaBridgeScreenPlay:pilotMobTable()
	return self:persistStore().pilotMobs
end

function IaBridgeScreenPlay:catalogPilotTable()
	local ps = self:persistStore()
	if (ia_table_has_entries(ps.catalogPilots)) then
		return ps.catalogPilots
	end
	if (ia_table_has_entries(IA_BRIDGE_PILOTS)) then
		if (ps.catalogPilots == nil) then
			ps.catalogPilots = IA_BRIDGE_PILOTS
		end
		return IA_BRIDGE_PILOTS
	end
	return IA_BRIDGE_PILOTS_FALLBACK
end

function IaBridgeScreenPlay:countTableKeys(tbl)
	local n = 0
	if (tbl ~= nil) then
		for _ in pairs(tbl) do
			n = n + 1
		end
	end
	return n
end

function IaBridgeScreenPlay:countResolvedPilots()
	local n = 0
	for pilotId, _ in pairs(self:catalogPilotTable()) do
		if (self:resolvePilotMob(pilotId) ~= nil) then
			n = n + 1
		end
	end
	return n
end

function IaBridgeScreenPlay:getPilotCfg(pilotId)
	if (pilotId == nil) then
		return nil
	end
	local cat = self:catalogPilotTable()
	if (cat ~= nil and cat[pilotId] ~= nil) then
		return cat[pilotId]
	end
	return IA_BRIDGE_PILOTS_FALLBACK[pilotId]
end

function IaBridgeScreenPlay:configurePersistentGameTime()
	local gt = self:getGameTimeConfig()
	local daySec = (gt.real_hours_per_game_day or 6) * 3600
	local workSec = (gt.phase_hours_real.work or 2) * 3600
	local restSec = (gt.phase_hours_real.rest or 2) * 3600
	local leisureSec = (gt.phase_hours_real.leisure or 2) * 3600
	if (iaConfigureGameTime ~= nil) then
		local ok, err = pcall(function()
			iaConfigureGameTime(daySec, workSec, restSec, leisureSec)
		end)
		if (ok) then
			printf("IaBridge: GameTime persistant configure (jour=%ds)\n", daySec)
		else
			printf("IaBridge: iaConfigureGameTime erreur : %s\n", tostring(err))
		end
	end
end

function IaBridgeScreenPlay:start()
	ia_load_all_world_content()
	-- Chargement du catalogue PNJ (data-driven). Si échec, on reste sur les tables hardcodées.
	local doc, chosen = ia_load_npc_catalog()
	if (doc ~= nil) then
		ia_apply_game_time_from_catalog(doc)
		local ok, pilotCount = ia_build_pilots_from_catalog(doc)
		if (ok) then
			ia_catalog_boot_log("catalogue OK path=" .. tostring(chosen) .. " pilots=" .. tostring(pilotCount))
			printf("IaBridge: catalogue PNJ chargé (%s) pilots=%d\n", tostring(chosen), tonumber(pilotCount) or 0)
		else
			ia_catalog_boot_log("catalogue sans entree exploitable path=" .. tostring(chosen))
			printf("IaBridge: catalogue PNJ chargé (%s) mais aucune entrée exploitable (fallback hardcoded)\n", tostring(chosen))
			IA_BRIDGE_PILOTS = IA_BRIDGE_PILOTS_FALLBACK
		end
	end
	ia_merge_pilots_from_pilots_json()
	ia_load_species_height_table()
	ia_load_species_slot_heights()
	ia_merge_pilot_bodies()
	self:syncGlobalsFromPersist()
	self:configurePersistentGameTime()
	-- Toujours lancer le tick (pending.jsonl) même si Tatooine n'est pas encore deployee au boot.
	self:scheduleTick()
	if (not isZoneEnabled(IA_BRIDGE_ZONE)) then
		printf("IaBridge: zone %s pas encore active — boot pilotes reporte.\n", IA_BRIDGE_ZONE)
		createEvent(5000, "IaBridgeScreenPlay", "deferredBoot", nil, "")
		return
	end
	self:deferredBoot()
end

function IaBridgeScreenPlay:deferredBoot()
	if (not isZoneEnabled(IA_BRIDGE_ZONE)) then
		createEvent(5000, "IaBridgeScreenPlay", "deferredBoot", nil, "")
		return
	end
	local ok, err = pcall(function()
		self:bootPilotsOnce()
	end)
	if (not ok) then
		printf("IaBridge: ensurePilots erreur : %s\n", tostring(err))
	end
end

function IaBridgeScreenPlay:scheduleTick()
	createEvent(self.tickMs, "IaBridgeScreenPlay", "tick", nil, "")
end

function IaBridgeScreenPlay:resolvePlayer(playerName)
	if (playerName == nil or playerName == "") then
		return nil
	end
	local pPlayer = getPlayerByName(playerName)
	if (pPlayer ~= nil) then
		return pPlayer
	end
	local first = string.match(playerName, "^(%S+)")
	if (first ~= nil and first ~= playerName) then
		return getPlayerByName(first)
	end
	return nil
end

function IaBridgeScreenPlay:dist2d(x1, y1, x2, y2)
	local dx = x1 - x2
	local dy = y1 - y2
	return math.sqrt(dx * dx + dy * dy)
end

function IaBridgeScreenPlay:getGameTimeConfig()
	return IA_BRIDGE_GAME_TIME
end

-- Phase personnelle : work | rest | leisure (decalee par shift_offset 0..2 triplon)
function IaBridgeScreenPlay:getLifecyclePhase(shiftOffset)
	local gt = self:getGameTimeConfig()
	local daySec = (gt.real_hours_per_game_day or 6) * 3600
	local workSec = (gt.phase_hours_real.work or 2) * 3600
	local restSec = (gt.phase_hours_real.rest or 2) * 3600
	local leisureSec = (gt.phase_hours_real.leisure or 2) * 3600
	local inDay = 0
	if (iaGetGameTime ~= nil) then
		local ok, v = pcall(function()
			return iaGetGameTime()
		end)
		if (ok and v ~= nil and v.inDay ~= nil) then
			inDay = tonumber(v.inDay) or 0
			if (v.daySec ~= nil) then
				daySec = tonumber(v.daySec) or daySec
			end
		else
			inDay = os.time() % daySec
		end
	else
		inDay = os.time() % daySec
	end
	local offset = shiftOffset or 0
	if (inDay < workSec) then
		local idx = (0 + offset) % 3
		if (idx == 0) then return "work" elseif (idx == 1) then return "rest" else return "leisure" end
	elseif (inDay < workSec + restSec) then
		local idx = (1 + offset) % 3
		if (idx == 0) then return "work" elseif (idx == 1) then return "rest" else return "leisure" end
	else
		local idx = (2 + offset) % 3
		if (idx == 0) then return "work" elseif (idx == 1) then return "rest" else return "leisure" end
	end
end

function IaBridgeScreenPlay:getRosterDesiredPresence(pilotId, cfg)
	if (cfg.roster == nil) then
		return nil
	end
	local life = self:getLifecyclePhase(cfg.shift_offset or 0)
	if (life == "rest") then
		-- Centre entrainement : cour exterieure (patrol catalogue), pas cellule interieure videe.
		if (cfg.roster ~= nil and string.find(cfg.roster, "mos_trainer_") ~= nil) then
			if (cfg.roam_patrol ~= nil) then
				return "leisure"
			end
			return "rest_home"
		end
		if (cfg.home_x ~= nil and cfg.home_y ~= nil) then
			return "rest_home"
		end
		return "off"
	end
	if (life == "work") then
		return "post"
	end
	if (life == "leisure") then
		if (cfg.roster ~= nil and string.find(cfg.roster, "mos_trainer_") ~= nil) then
			if (cfg.roam_patrol ~= nil) then
				return "leisure"
			end
			return "rest_home"
		end
		if (self:isBartenderPilot(cfg)) then
			return "rest_home"
		end
		if (cfg.cantina_cell ~= nil and cfg.cantina_x ~= nil) then
			return "cantina"
		end
		if (cfg.roam_patrol ~= nil or cfg.roam_mode == "linger" or cfg.roam_mode == "walk_patrol") then
			return "leisure"
		end
		return "off"
	end
	return "off"
end

function IaBridgeScreenPlay:isTrainerPilot(cfg)
	if (cfg == nil or cfg.mobile == nil) then
		return false
	end
	return string.find(cfg.mobile, "trainer") ~= nil
end

function IaBridgeScreenPlay:isCantinaBarmanPilot(cfg)
	if (cfg == nil) then
		return false
	end
	local r = tostring(cfg.roster or "")
	return string.find(r, "cantina_barman", 1, true) ~= nil
end

function IaBridgeScreenPlay:isArtisanTrainerPilot(cfg)
	if (cfg == nil) then
		return false
	end
	return tostring(cfg.roster or "") == "roster:mos_trainer_artisan"
end

function IaBridgeScreenPlay:isOutdoorWorldRosterPilot(cfg)
	if (cfg == nil) then
		return false
	end
	if (cfg.outdoor_world == true) then
		return true
	end
	local r = tostring(cfg.roster or "")
	return string.find(r, "mos_pilot_", 1, true) ~= nil
end

function IaBridgeScreenPlay:isBartenderPilot(cfg)
	if (self:isCantinaBarmanPilot(cfg)) then
		return true
	end
	if (cfg == nil or cfg.mobile == nil) then
		return false
	end
	return cfg.mobile == "bartender"
end

-- Poste catalogue + decalage optionnel (rapprocher du comptoir cote client)
function IaBridgeScreenPlay:resolvePostCoords(cfg)
	local x = tonumber(cfg.x) or 0
	local y = tonumber(cfg.y) or 0
	local z = tonumber(cfg.z) or 0
	if (cfg.post_offset_dx ~= nil) then
		x = x + tonumber(cfg.post_offset_dx)
	end
	if (cfg.post_offset_dy ~= nil) then
		y = y + tonumber(cfg.post_offset_dy)
	end
	if (cfg.post_offset_dz ~= nil) then
		z = z + tonumber(cfg.post_offset_dz)
	end
	return x, z, y
end

function IaBridgeScreenPlay:setRosterServiceEnabled(pMob, enabled)
	if (pMob == nil) then
		return
	end
	pcall(function()
		if (enabled) then
			CreatureObject(pMob):setOptionBit(CONVERSABLE)
		else
			CreatureObject(pMob):clearOptionBit(CONVERSABLE)
		end
	end)
end

function IaBridgeScreenPlay:syncRosterServiceForPresence(cfg, pMob, want)
	if (pMob == nil or cfg == nil) then
		return
	end
	if (self:isTrainerPilot(cfg)) then
		self:setRosterServiceEnabled(pMob, want == "post")
	elseif (self:isBartenderPilot(cfg)) then
		-- Dialogue via spatial IA ; actif au comptoir (interieur ou fallback exterieur).
		self:setRosterServiceEnabled(pMob, want == "post")
	elseif (want == "rest_home") then
		self:setRosterServiceEnabled(pMob, false)
	else
		self:setRosterServiceEnabled(pMob, true)
	end
end

function IaBridgeScreenPlay:rosterServicePolicy(rosterId)
	if (rosterId == nil or IA_BRIDGE_ROSTER_POLICIES == nil) then
		return nil
	end
	return IA_BRIDGE_ROSTER_POLICIES[rosterId]
end

function IaBridgeScreenPlay:getRosterWinnerPilot(rosterId)
	local bestPid, bestPri = nil, -1
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.roster == rosterId) then
			local want = self:getRosterDesiredPresence(pilotId, cfg)
			local pri = IA_BRIDGE_ROSTER_PRESENCE_PRIORITY[want or "off"] or 0
			if (pri > bestPri) then
				bestPri = pri
				bestPid = pilotId
			elseif (pri == bestPri and pri > 0 and bestPid ~= nil) then
				local curOff = IA_BRIDGE_PILOTS[bestPid].shift_offset or 99
				local newOff = cfg.shift_offset or 99
				if (newOff < curOff) then
					bestPid = pilotId
				end
			end
		end
	end
	if (bestPri <= 0) then
		return nil
	end
	return bestPid
end

function IaBridgeScreenPlay:pilotAllowedByRosterPolicy(pilotId, cfg)
	if (cfg == nil or cfg.roster == nil) then
		return true
	end
	if (self:rosterServicePolicy(cfg.roster) ~= "exactly_one") then
		return true
	end
	local want = self:getRosterDesiredPresence(pilotId, cfg)
	if (self:isBartenderPilot(cfg)) then
		if (want ~= "post" and want ~= "rest_home" and want ~= "cantina") then
			return false
		end
	end
	return pilotId == self:getRosterWinnerPilot(cfg.roster)
end

function IaBridgeScreenPlay:pilotShouldExist(pilotId, cfg)
	if (cfg.roster ~= nil) then
		local want = self:getRosterDesiredPresence(pilotId, cfg)
		if (want == nil or want == "off") then
			return false
		end
		return self:pilotAllowedByRosterPolicy(pilotId, cfg)
	end
	return true
end

function IaBridgeScreenPlay:despawnRosterExcept(rosterId, keepPilotId)
	if (rosterId == nil) then
		return
	end
	for pilotId, cfg in pairs(self:catalogPilotTable()) do
		if (cfg.roster == rosterId and pilotId ~= keepPilotId) then
			if (self:resolvePilotMob(pilotId) ~= nil) then
				self:despawnPilot(pilotId)
			end
			IaBridgeScreenPlay.rosterPresence[pilotId] = "off"
		end
	end
end

function IaBridgeScreenPlay:enforceRosterExactlyOnePolicies()
	if (IA_BRIDGE_ROSTER_POLICIES == nil) then
		return
	end
	for rosterId, policy in pairs(IA_BRIDGE_ROSTER_POLICIES) do
		if (policy == "exactly_one") then
			if (rosterId == "roster:mos_eisley_cantina_barman" or rosterId == "roster:mos_trainer_artisan") then
				-- Lifecycle dedie (ensureCantinaBarmanOnDuty / ensureArtisanTrainerOnDuty).
			else
			local winner = self:getRosterWinnerPilot(rosterId)
			for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
				if (cfg.roster == rosterId) then
					local keep = (pilotId == winner) and self:pilotAllowedByRosterPolicy(pilotId, cfg)
					if (not keep) then
						local pMob = self:resolvePilotMob(pilotId)
						if (pMob ~= nil) then
							self:despawnPilot(pilotId)
						end
						IaBridgeScreenPlay.rosterPresence[pilotId] = "off"
					end
				end
			end
			end
		end
	end
end

function IaBridgeScreenPlay:liaAnchor()
	local pPlayer = self:resolvePlayer(IA_BRIDGE_BOT)
	if (pPlayer == nil) then
		return nil
	end
	local scene = SceneObject(pPlayer)
	return scene:getPositionX(), scene:getPositionZ(), scene:getPositionY(), scene:getParentID()
end

function IaBridgeScreenPlay:pilotOidKey(pilotId)
	return "ia_bridge_pilot_oid:" .. pilotId
end

function IaBridgeScreenPlay:isMobAlive(pMob)
	if (pMob == nil) then
		return false
	end
	local ok, oid = pcall(function()
		return SceneObject(pMob):getObjectID()
	end)
	if (not ok or oid == nil or oid == 0) then
		return false
	end
	local ok2, scene = pcall(function()
		return getSceneObject(oid)
	end)
	return ok2 and scene ~= nil
end

function IaBridgeScreenPlay:resolvePilotMob(pilotId)
	local tbl = self:pilotMobTable()
	local cached = tbl[pilotId]
	if (cached ~= nil) then
		if (self:isMobAlive(cached)) then
			return cached
		end
		local grace = readData("ia_bridge_pilot_grace:" .. pilotId) or 0
		local tick = self:persistStore().tickCount or 0
		if (grace > 0 and (tick - grace) < 60) then
			return cached
		end
	end
	local oid = readData(self:pilotOidKey(pilotId))
	if (oid ~= nil and oid ~= 0) then
		local pMob = getSceneObject(oid)
		if (self:isMobAlive(pMob)) then
			tbl[pilotId] = pMob
			return pMob
		end
	end
	tbl[pilotId] = nil
	return nil
end

function IaBridgeScreenPlay:purgeStalePilotRef(pilotId)
	local tbl = self:pilotMobTable()
	local cached = tbl[pilotId]
	if (cached ~= nil and not self:isMobAlive(cached)) then
		self:despawnPilot(pilotId)
		return
	end
	local oid = readData(self:pilotOidKey(pilotId))
	if (oid ~= nil and oid ~= 0) then
		local pMob = getSceneObject(oid)
		if (not self:isMobAlive(pMob)) then
			tbl[pilotId] = nil
			deleteData(self:pilotOidKey(pilotId))
		end
	end
end

function IaBridgeScreenPlay:registerPilotMob(pilotId, pMob)
	local tbl = self:pilotMobTable()
	tbl[pilotId] = pMob
	local oid = SceneObject(pMob):getObjectID()
	writeData(self:pilotOidKey(pilotId), oid)
	writeData("ia_bridge_pilot_grace:" .. pilotId, self:persistStore().tickCount or 0)
	self:rememberPilotOid(pilotId, oid)
end

function IaBridgeScreenPlay:pilotOidHistory()
	local ps = self:persistStore()
	if (ps.pilotOidHistory == nil) then
		ps.pilotOidHistory = {}
	end
	return ps.pilotOidHistory
end

function IaBridgeScreenPlay:rememberPilotOid(pilotId, oid)
	if (pilotId == nil or oid == nil or oid == 0) then
		return
	end
	local hist = self:pilotOidHistory()
	hist[pilotId] = hist[pilotId] or {}
	for _, existing in ipairs(hist[pilotId]) do
		if (existing == oid) then
			return
		end
	end
	table.insert(hist[pilotId], oid)
end

function IaBridgeScreenPlay:destroyExtraPilotMobs(pilotId, keepOid)
	local hist = self:pilotOidHistory()
	local list = hist[pilotId]
	if (list == nil) then
		return
	end
	local keepNum = tonumber(keepOid) or keepOid
	local kept = false
	for i = #list, 1, -1 do
		local oid = list[i]
		local oidNum = tonumber(oid) or oid
		local pMob = getSceneObject(oid)
		if (pMob ~= nil and self:isMobAlive(pMob)) then
			if (keepNum ~= nil and oidNum == keepNum and not kept) then
				kept = true
			else
				self:clearPilotMobMarks(pMob)
				pcall(function()
					SceneObject(pMob):destroyObjectFromWorld(true)
				end)
				table.remove(list, i)
			end
		else
			table.remove(list, i)
		end
	end
	if (keepNum ~= nil) then
		hist[pilotId] = { keepNum }
	end
end

function IaBridgeScreenPlay:stripIaNameMarkers(name)
	if (name == nil or name == "") then
		return ""
	end
	local n = name
	if (IA_BRIDGE_PILOT_TAG_PREFIX ~= "" and string.sub(n, 1, #IA_BRIDGE_PILOT_TAG_PREFIX) == IA_BRIDGE_PILOT_TAG_PREFIX) then
		n = string.sub(n, #IA_BRIDGE_PILOT_TAG_PREFIX + 1)
	end
	if (IA_BRIDGE_PILOT_TAG_SUFFIX ~= "" and #n >= #IA_BRIDGE_PILOT_TAG_SUFFIX) then
		if (string.sub(n, -#IA_BRIDGE_PILOT_TAG_SUFFIX) == IA_BRIDGE_PILOT_TAG_SUFFIX) then
			n = string.sub(n, 1, -#IA_BRIDGE_PILOT_TAG_SUFFIX - 1)
		end
	end
	return n
end

function IaBridgeScreenPlay:resolvePilotBody(cfg)
	if (cfg == nil) then
		return nil
	end
	if (cfg.species_key == nil or cfg.gender == nil) then
		return nil
	end
	return {
		lbg_race_id = cfg.lbg_race_id,
		lbg_race_display = cfg.lbg_race_display,
		species_key = cfg.species_key,
		gender = cfg.gender,
		height_m = tonumber(cfg.height_m),
	}
end

function IaBridgeScreenPlay:speciesAppearanceIff(speciesKey, gender)
	if (speciesKey == nil or gender == nil) then
		return nil
	end
	return "object/mobile/shared_" .. tostring(speciesKey) .. "_" .. tostring(gender) .. ".iff"
end

function IaBridgeScreenPlay:heightToScale(speciesKey, gender, heightM)
	if (speciesKey == nil or gender == nil or heightM == nil) then
		return nil
	end
	local row = IA_BRIDGE_SPECIES_HEIGHT[tostring(speciesKey) .. ":" .. tostring(gender)]
	if (row == nil) then
		return nil
	end
	local base = row.base_m
	if (base == nil or base <= 0) then
		return nil
	end
	local scale = heightM / base
	if (row.scale_min ~= nil and scale < row.scale_min) then
		scale = row.scale_min
	end
	if (row.scale_max ~= nil and scale > row.scale_max) then
		scale = row.scale_max
	end
	return scale
end

function IaBridgeScreenPlay:pilotBodyApplyTag(cfg)
	local body = self:resolvePilotBody(cfg)
	if (body == nil or body.height_m == nil) then
		return nil
	end
	local scale = self:heightToScale(body.species_key, body.gender, body.height_m)
	if (scale == nil) then
		return nil
	end
	return string.format(
		"v%d:%s:%s:%.3f",
		IA_BRIDGE_BODY_APPLY_REV,
		tostring(body.species_key),
		tostring(body.gender),
		scale
	)
end

function IaBridgeScreenPlay:applyPilotHeightOnly(pMob, cfg)
	if (pMob == nil or cfg == nil) then
		return false
	end
	local body = self:resolvePilotBody(cfg)
	if (body == nil or body.height_m == nil) then
		return false
	end
	local scale = self:heightToScale(body.species_key, body.gender, body.height_m)
	if (scale == nil) then
		return false
	end
	if (iaApplyPilotHeight == nil) then
		if (IaBridgeScreenPlay.warnedPilotHeight ~= true) then
			IaBridgeScreenPlay.warnedPilotHeight = true
			printf("IaBridge: iaApplyPilotHeight absent — rebuild core3 requis pour tailles\n")
		end
		return false
	end
	pcall(function()
		iaApplyPilotHeight(pMob, scale)
	end)
	return true
end

function IaBridgeScreenPlay:deferredPilotHeightStep(pMob, payload)
	if (pMob == nil or not self:isMobAlive(pMob)) then
		return
	end
	local pilotId = payload
	local pass = "1"
	if (payload ~= nil and string.find(payload, "|", 1, true) ~= nil) then
		pilotId, pass = string.match(payload, "^(.-)|(.+)$")
	end
	local cfg = IA_BRIDGE_PILOTS[pilotId]
	if (cfg == nil) then
		return
	end
	self:applyPilotHeightOnly(pMob, cfg)
	if (pass == "1") then
		createEvent(
			IA_BRIDGE_BODY_HEIGHT_DEFER_MS,
			"IaBridgeScreenPlay",
			"deferredPilotHeightStep",
			pMob,
			tostring(pilotId) .. "|2"
		)
	end
end

-- Evite que les pilotes IA (surtout templates police) attaquent les rebelles vanilla GCW.
-- combat_policy: "peaceful" (defaut) | "peaceful_static" | "vanilla" (comportement template)
function IaBridgeScreenPlay:isPilotPoliceTemplate(cfg)
	local m = string.lower(tostring((cfg ~= nil and cfg.mobile) or ""))
	return (string.find(m, "police", 1, true) ~= nil)
		or (string.find(m, "crackdown", 1, true) ~= nil)
end

function IaBridgeScreenPlay:resolvePilotCombatPolicy(cfg)
	if (cfg == nil) then
		return "peaceful"
	end
	if (cfg.combat_policy ~= nil and cfg.combat_policy ~= "") then
		return cfg.combat_policy
	end
	if (self:isPilotPoliceTemplate(cfg)) then
		return "peaceful_static"
	end
	if (self:isBartenderPilot(cfg)) then
		return "peaceful_static"
	end
	return "peaceful"
end

function IaBridgeScreenPlay:applyPilotCombatPolicy(pilotId, pMob, cfg)
	if (pMob == nil or cfg == nil) then
		return
	end
	local policy = self:resolvePilotCombatPolicy(cfg)
	if (policy == "vanilla") then
		return
	end
	pcall(function()
		CreatureObject(pMob):setFaction(FACTIONNEUTRAL)
		CreatureObject(pMob):setFactionStatus(COVERT)
		AiAgent(pMob):addObjectFlag(AI_NOAIAGGRO)
	end)
	if (policy == "peaceful_static") then
		pcall(function()
			AiAgent(pMob):addObjectFlag(AI_STATIC)
		end)
	end
end

function IaBridgeScreenPlay:applyPilotBody(pMob, cfg, pilotId)
	if (pMob == nil or cfg == nil) then
		return false
	end
	-- Proxy commoner outdoor : setAppearance casse le mob.
	if (self:isCantinaBarmanPilot(cfg)) then
		return false
	end
	local body = self:resolvePilotBody(cfg)
	if (body == nil or body.height_m == nil) then
		return false
	end
	local iff = self:speciesAppearanceIff(body.species_key, body.gender)
	if (iff ~= nil) then
		pcall(function()
			CreatureObject(pMob):setAppearance(iff)
		end)
	end
	self:applyPilotHeightOnly(pMob, cfg)
	if (pilotId ~= nil and pilotId ~= "") then
		createEvent(
			IA_BRIDGE_BODY_HEIGHT_DEFER_MS,
			"IaBridgeScreenPlay",
			"deferredPilotHeightStep",
			pMob,
			tostring(pilotId) .. "|1"
		)
	end
	local tag = self:pilotBodyApplyTag(cfg)
	if (tag ~= nil) then
		writeStringData("ia_bridge_pilot_body:" .. SceneObject(pMob):getObjectID(), tag)
	end
	return true
end

function IaBridgeScreenPlay:clearPilotBodyMark(pMob)
	if (pMob == nil) then
		return
	end
	deleteStringData("ia_bridge_pilot_body:" .. SceneObject(pMob):getObjectID())
end

function IaBridgeScreenPlay:refreshPilotBody(pilotId)
	local cfg = IA_BRIDGE_PILOTS[pilotId]
	if (cfg == nil) then
		return false
	end
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob == nil) then
		return false
	end
	self:clearPilotBodyMark(pMob)
	self:applyPilotBody(pMob, cfg, pilotId)
	CreatureObject(pMob):setCustomObjectName(self:formatPilotDisplayName(cfg))
	return true
end

function IaBridgeScreenPlay:refreshAllPilotBodies()
	local n = 0
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.species_key ~= nil and self:refreshPilotBody(pilotId)) then
			n = n + 1
		end
	end
	printf("IaBridge: refreshAllPilotBodies n=%d rev=%d\n", n, IA_BRIDGE_BODY_APPLY_REV)
	return n
end

function IaBridgeScreenPlay:ensurePilotBodiesApplied()
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.species_key ~= nil and cfg.gender ~= nil and not self:isCantinaBarmanPilot(cfg)) then
			local pMob = self:resolvePilotMob(pilotId)
			if (pMob ~= nil) then
				local oid = SceneObject(pMob):getObjectID()
				local wantTag = self:pilotBodyApplyTag(cfg)
				local applied = readStringData("ia_bridge_pilot_body:" .. oid)
				if (wantTag ~= nil and applied ~= wantTag) then
					self:applyPilotBody(pMob, cfg, pilotId)
					CreatureObject(pMob):setCustomObjectName(self:formatPilotDisplayName(cfg))
				end
				self:applyPilotCombatPolicy(pilotId, pMob, cfg)
			end
		end
	end
end

function IaBridgeScreenPlay:formatPilotDisplayName(cfg)
	local base = self:stripIaNameMarkers(cfg.display_name or "PNJ")
	local raceLabel = cfg.lbg_race_display
	if (raceLabel == nil or raceLabel == "") then
		raceLabel = nil
	elseif (string.find(base, raceLabel, 1, true) == nil) then
		base = base .. " · " .. raceLabel
	end
	if (cfg.hide_ia_tag == true or IA_BRIDGE_PILOT_TAG_MODE == "off") then
		return base
	end
	local out = base
	local mode = IA_BRIDGE_PILOT_TAG_MODE
	if (mode == "prefix" or mode == "both") then
		out = IA_BRIDGE_PILOT_TAG_PREFIX .. out
	end
	if (mode == "suffix" or mode == "both") then
		if (IA_BRIDGE_PILOT_TAG_SUFFIX ~= "" and string.sub(out, -#IA_BRIDGE_PILOT_TAG_SUFFIX) ~= IA_BRIDGE_PILOT_TAG_SUFFIX) then
			out = out .. IA_BRIDGE_PILOT_TAG_SUFFIX
		end
	end
	return out
end

function IaBridgeScreenPlay:markPilotMob(pilotId, pMob, cfg)
	local oid = SceneObject(pMob):getObjectID()
	writeStringData("ia_bridge_pilot_id:" .. oid, pilotId)
	if (cfg.lbg_npc_id ~= nil and cfg.lbg_npc_id ~= "") then
		writeStringData("ia_bridge_lbg_npc:" .. oid, cfg.lbg_npc_id)
	end
end

function IaBridgeScreenPlay:clearPilotMobMarks(pMob)
	if (pMob == nil) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	deleteStringData("ia_bridge_pilot_id:" .. oid)
	deleteStringData("ia_bridge_lbg_npc:" .. oid)
	deleteStringData("ia_bridge_pilot_body:" .. oid)
end

function IaBridgeScreenPlay:resolvePilotIdFromMob(pMob)
	if (pMob == nil) then
		return nil
	end
	local pid = readStringData("ia_bridge_pilot_id:" .. SceneObject(pMob):getObjectID())
	if (pid == nil or pid == "") then
		return nil
	end
	return pid
end

function IaBridgeScreenPlay:barmanEffectiveMobile(cfg, cell)
	if ((cell or 0) ~= 0) then
		return "bartender"
	end
	if (self:isCantinaBarmanPilot(cfg)) then
		return "patron"
	end
	return cfg.mobile or "bartender"
end

function IaBridgeScreenPlay:pilotMobNearPost(pMob, cfg, radiusM)
	if (pMob == nil or cfg == nil) then
		return false
	end
	radiusM = tonumber(radiusM) or 4.0
	local px, pz, py = self:resolvePostCoords(cfg)
	local scene = SceneObject(pMob)
	if (scene == nil) then
		return false
	end
	local sx = scene:getPositionX()
	local sy = scene:getPositionY()
	local sz = scene:getPositionZ()
	if (self:dist2d(sx, sy, px, py) < radiusM) then
		return true
	end
	if (self:dist2d(sx, sz, px, pz) < radiusM) then
		return true
	end
	if (self:dist2d(sx, sy, px, pz) < radiusM) then
		return true
	end
	return false
end

function IaBridgeScreenPlay:pilotMobInServiceCell(pMob, cfg)
	if (pMob == nil or cfg == nil) then
		return false
	end
	local postCell = tonumber(cfg.spawn_cell) or 0
	local parent = self:sceneParentId(pMob)
	if (postCell == 0) then
		return parent == 0
	end
	if (parent == postCell) then
		return true
	end
	-- spawnMobile interieur : parent souvent 0 ou building id (pas cell id)
	if (not self:pilotMobNearPost(pMob, cfg, 4.0)) then
		return false
	end
	local px, pz, py = self:resolvePostCoords(cfg)
	pcall(function()
		CreatureObject(pMob):teleport(px, pz, py, postCell)
	end)
	return true
end

function IaBridgeScreenPlay:releasePilotMobUnlessAtCell(pilotId, cell, cfg)
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob == nil) then
		return nil
	end
	local useCfg = cfg
	if (useCfg == nil) then
		useCfg = self:getPilotCfg(pilotId)
	end
	if (useCfg ~= nil and self:pilotMobNearPost(pMob, useCfg, 6.0) and not self:isPilotOnOutdoorPost(pilotId)) then
		return pMob
	end
	if (useCfg ~= nil and self:pilotMobInServiceCell(pMob, useCfg) and not self:isPilotOnOutdoorPost(pilotId)) then
		return pMob
	end
	local wantCell = tonumber(cell) or 0
	if (wantCell == 0 and self:sceneParentId(pMob) == 0 and not self:isPilotOnOutdoorPost(pilotId)) then
		return pMob
	end
	self:despawnPilot(pilotId)
	return nil
end

function IaBridgeScreenPlay:spawnPilotAt(pilotId, cfg, x, z, y, cell)
	cell = tonumber(cell) or 0
	if (cell ~= 0 and not self:isInteriorCellLoadable(cell)) then
		return nil
	end
	local pMob = self:releasePilotMobUnlessAtCell(pilotId, cell, cfg)
	if (pMob ~= nil) then
		return pMob
	end
	if (cfg ~= nil and (cfg.post_offset_dx ~= nil or cfg.post_offset_dy ~= nil or cfg.post_offset_dz ~= nil)) then
		x, z, y = self:resolvePostCoords(cfg)
	end
	_G.__IA_BRIDGE_SPAWNING_PILOT = pilotId
	local template = cfg.mobile
	local commonerProxy = false
	if (self:isCantinaBarmanPilot(cfg)) then
		template = self:barmanEffectiveMobile(cfg, cell)
		commonerProxy = (template == "commoner")
	end
	local pMob = spawnMobile(
		IA_BRIDGE_ZONE,
		template,
		0,
		x,
		z,
		y,
		cfg.heading or 0,
		cell or 0
	)
	if (pMob ~= nil) then
		self:markPilotMob(pilotId, pMob, cfg)
		if (commonerProxy) then
			ia_catalog_boot_log("barman outdoor post " .. pilotId)
		end
		if (not commonerProxy) then
			self:applyPilotBody(pMob, cfg, pilotId)
		end
		if (not self:isCantinaBarmanPilot(cfg)) then
			self:applyPilotCombatPolicy(pilotId, pMob, cfg)
		else
			pcall(function()
				CreatureObject(pMob):setFaction(FACTIONNEUTRAL)
				AiAgent(pMob):addObjectFlag(AI_STATIC)
				AiAgent(pMob):addObjectFlag(AI_NOAIAGGRO)
			end)
		end
		local displayName = self:formatPilotDisplayName(cfg)
		pcall(function()
			CreatureObject(pMob):setCustomObjectName(displayName)
		end)
		self:registerPilotMob(pilotId, pMob)
		if (cell ~= 0) then
			pcall(function()
				CreatureObject(pMob):teleport(x, z, y, cell)
			end)
		end
		if (cfg.roster == nil and self:resolvePilotCombatPolicy(cfg) ~= "peaceful_static") then
			self:enableRoamBehavior(pilotId, pMob, cfg)
		end
		printf("IaBridge: pilote spawn %s (%s) @ %.1f %.1f %.1f cell=%s tpl=%s\n",
			pilotId, cfg.display_name, x, y, z, tostring(cell or 0), tostring(template))
	else
		printf("IaBridge: echec spawn pilote %s template=%s @ %.1f %.1f %.1f cell=%s\n",
			pilotId, tostring(template), x, y, z, tostring(cell or 0))
		ia_catalog_boot_log(string.format(
			"echec spawn %s template=%s @ %.1f,%.1f,%.1f cell=%s",
			pilotId, tostring(template), x, y, z, tostring(cell or 0)
		))
	end
	_G.__IA_BRIDGE_SPAWNING_PILOT = nil
	return pMob
end

function IaBridgeScreenPlay:ensurePilots()
	local ax, az, ay, acell = self:liaAnchor()
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.roster ~= nil) then
			-- gere par tickRosterLifecycle
		elseif (self:resolvePilotMob(pilotId) ~= nil) then
			-- deja en vie
		elseif (self:pilotShouldExist(pilotId, cfg)) then
			local cell = tonumber(cfg.spawn_cell) or 0
			if (cell ~= 0 and not self:isInteriorCellLoadable(cell)) then
				-- Evite spawn en murs (cell theatre/mezzanine non chargee)
			else
			local x, z, y = cfg.x, cfg.z, cfg.y
			if (cfg.follow_lia == true and ax ~= nil) then
				x = ax + (cfg.off_x or 0)
				z = az
				y = ay + (cfg.off_y or 0)
				cell = acell
			end
			x, z, y, cell = self:resolveStableWorldCoords(cfg, x, z, y, cell, pilotId)
			self:spawnPilotAt(pilotId, cfg, x, z, y, cell)
			end
		end
	end
end

function IaBridgeScreenPlay:despawnPilot(pilotId)
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob ~= nil) then
		local oid = SceneObject(pMob):getObjectID()
		deleteData("ia_bridge_roam_pilot:" .. oid)
		deleteData("ia_bridge_walk_idx:" .. oid)
		self:clearPilotMobMarks(pMob)
		pcall(function()
			SceneObject(pMob):destroyObjectFromWorld(true)
		end)
	end
	self:pilotMobTable()[pilotId] = nil
	deleteData("ia_bridge_pilot_grace:" .. pilotId)
	deleteData(self:pilotOidKey(pilotId))
	if (pilotId == "npc:core3_barman_jax") then
		self:persistStore().cantinaBarmanSpawnDone = false
	end
end

function IaBridgeScreenPlay:clearPilotBehaviors(pMob)
	if (pMob == nil) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	deleteData("ia_bridge_dance_on:" .. oid)
	deleteData("ia_bridge_roam_pilot:" .. oid)
	pcall(function()
		AiAgent(pMob):addObjectFlag(AI_STATIC)
	end)
end

function IaBridgeScreenPlay:rosterCantinaCell(cfg)
	if (cfg ~= nil and cfg.cantina_cell ~= nil and tonumber(cfg.cantina_cell) ~= 0) then
		return tonumber(cfg.cantina_cell)
	end
	return IA_BRIDGE_CANTINA_CELL
end

function IaBridgeScreenPlay:teleportRosterToCantina(pilotId, cfg, pMob)
	if (pMob == nil or cfg == nil) then
		return
	end
	local cell = self:rosterCantinaCell(cfg)
	local cx = cfg.cantina_x or 0
	local cz = cfg.cantina_z or 0
	local cy = cfg.cantina_y or 0
	cx, cz, cy, cell = self:resolveStableWorldCoords(cfg, cx, cz, cy, cell, pilotId)
	local parent = SceneObject(pMob):getParentID() or 0
	if (parent == cell and cell ~= 0) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	local debounceKey = "ia_bridge_cantina_tp:" .. oid
	local now = os.time()
	local last = readData(debounceKey) or 0
	if (now - last < 2) then
		return
	end
	writeData(debounceKey, now)
	self:clearPilotBehaviors(pMob)
	CreatureObject(pMob):teleport(cx, cz, cy, cell)
	local logKey = "ia_bridge_cantina_log:" .. oid
	local lastLog = readData(logKey) or 0
	if (now - lastLog >= 60) then
		writeData(logKey, now)
		printf(
			"IaBridge: %s -> cantina cell %s (etait %s)\n",
			tostring(pilotId),
			tostring(cell),
			tostring(parent)
		)
	end
end

function IaBridgeScreenPlay:outdoorPostKey(pilotId)
	return "ia_bridge_outdoor_post:" .. pilotId
end

function IaBridgeScreenPlay:isPilotOnOutdoorPost(pilotId)
	return readData(self:outdoorPostKey(pilotId)) == 1
end

function IaBridgeScreenPlay:setPilotOutdoorPost(pilotId, enabled)
	if (enabled) then
		writeData(self:outdoorPostKey(pilotId), 1)
	else
		deleteData(self:outdoorPostKey(pilotId))
	end
end

function IaBridgeScreenPlay:isInteriorCellLoadable(cellId)
	if (cellId == nil or cellId == 0) then
		return true
	end
	local pCell = getSceneObject(cellId)
	if (pCell == nil) then
		return false
	end
	return self:resolveBuildingFromCell(cellId) ~= nil
end

function IaBridgeScreenPlay:lookupOutdoorAnchor(cellId)
	if (cellId == nil or tonumber(cellId) == 0) then
		return nil
	end
	return IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS[tostring(cellId)]
end

function IaBridgeScreenPlay:resolveOutdoorPostFallback(cfg, interiorCell)
	if (cfg == nil) then
		return nil
	end
	if (cfg.outdoor_fb_x ~= nil) then
		return cfg.outdoor_fb_x, cfg.outdoor_fb_z, cfg.outdoor_fb_y
	end
	local cells = {}
	if (interiorCell ~= nil and tonumber(interiorCell) ~= 0) then
		cells[tostring(interiorCell)] = true
	end
	if (cfg.spawn_cell ~= nil and tonumber(cfg.spawn_cell) ~= 0) then
		cells[tostring(cfg.spawn_cell)] = true
	end
	if (cfg.home_cell ~= nil and tonumber(cfg.home_cell) ~= 0) then
		cells[tostring(cfg.home_cell)] = true
	end
	if (cfg.cantina_cell ~= nil and tonumber(cfg.cantina_cell) ~= 0) then
		cells[tostring(cfg.cantina_cell)] = true
	end
	for cellKey, _ in pairs(cells) do
		local anchor = IA_BRIDGE_INTERIOR_OUTDOOR_ANCHORS[cellKey]
		if (anchor ~= nil) then
			return anchor.x, anchor.z, anchor.y
		end
	end
	local ox, oz, oy = self:getOutdoorPatrolAnchorCoords(cfg)
	if (ox ~= nil) then
		return ox, oz, oy
	end
	return nil
end

function IaBridgeScreenPlay:resolveStableWorldCoords(cfg, x, z, y, cell, pilotId)
	cell = tonumber(cell) or 0
	if (cell == 0) then
		return x, z, y, 0
	end
	if (pilotId ~= nil and self:isPilotOnOutdoorPost(pilotId)) then
		local ox, oz, oy = self:resolveOutdoorPostFallback(cfg, cell)
		if (ox ~= nil) then
			return ox, oz, oy, 0
		end
	end
	if (not self:isInteriorCellLoadable(cell)) then
		local ox, oz, oy = self:resolveOutdoorPostFallback(cfg, cell)
		if (ox ~= nil) then
			if (pilotId ~= nil) then
				self:setPilotOutdoorPost(pilotId, true)
			end
			return ox, oz, oy, 0
		end
	end
	return x, z, y, cell
end

function IaBridgeScreenPlay:shouldUseOutdoorPost(pilotId, cfg, presence, cell)
	if (cell == 0) then
		return false
	end
	if (self:isPilotOnOutdoorPost(pilotId)) then
		return true
	end
	if (self:isCantinaBarmanPilot(cfg)) then
		if (not self:isInteriorCellLoadable(cell)) then
			return self:resolveOutdoorPostFallback(cfg, cell) ~= nil
		end
		return false
	end
	-- Cycle de vie autonome : fallback exterieur si la cellule interieure n'est pas chargee
	-- (pas de condition sur la presence d'un joueur).
	if (not self:isInteriorCellLoadable(cell)) then
		return self:resolveOutdoorPostFallback(cfg) ~= nil
	end
	return false
end

function IaBridgeScreenPlay:resolveBuildingFromCell(cellId)
	if (cellId == nil or cellId == 0) then
		return nil
	end
	local pCell = getSceneObject(cellId)
	if (pCell == nil) then
		return nil
	end
	local buildingId = SceneObject(pCell):getParentID() or 0
	if (buildingId == 0) then
		return nil
	end
	return getSceneObject(buildingId)
end

function IaBridgeScreenPlay:spawnPilotInBuilding(pilotId, cfg, cell)
	cell = tonumber(cell) or 0
	if (cell == 0 or not self:isInteriorCellLoadable(cell)) then
		return nil
	end
	local pBuilding = self:resolveBuildingFromCell(cell)
	if (pBuilding == nil) then
		return nil
	end
	local pMob = self:releasePilotMobUnlessAtCell(pilotId, cell, cfg)
	if (pMob ~= nil) then
		return pMob
	end
	local x, z, y = self:resolvePostCoords(cfg)
	local pMob = nil
	_G.__IA_BRIDGE_SPAWNING_PILOT = pilotId
	pcall(function()
		pMob = BuildingObject(pBuilding):spawnChildCreature(
			cfg.mobile,
			x,
			z,
			y,
			cell,
			cfg.heading or 0,
			true
		)
	end)
	if (pMob ~= nil) then
		ia_catalog_boot_log("building spawn " .. pilotId .. " cell=" .. tostring(cell))
		self:markPilotMob(pilotId, pMob, cfg)
		self:applyPilotBody(pMob, cfg, pilotId)
		self:applyPilotCombatPolicy(pilotId, pMob, cfg)
		CreatureObject(pMob):setCustomObjectName(self:formatPilotDisplayName(cfg))
		self:registerPilotMob(pilotId, pMob)
		pcall(function()
			CreatureObject(pMob):teleport(x, z, y, cell)
		end)
	end
	_G.__IA_BRIDGE_SPAWNING_PILOT = nil
	return pMob
end

function IaBridgeScreenPlay:handleSkillForget(pPlayer, message)
	if (pPlayer == nil) then
		return
	end
	local prof = self:trim(message or "")
	local name = self:eventActorName(pPlayer)
	pcall(function()
		CreatureObject(pPlayer):sendSystemMessage(
			"[IA] Oubli progressif du metier " .. prof .. " (stub — API skill_forget a brancher cote Core3)."
		)
	end)
	self:appendSocialEvent("core3.skill_forget", name, prof, "", 0, 0, 0, prof)
	ia_catalog_boot_log("skill_forget " .. name .. " prof=" .. prof)
end

function IaBridgeScreenPlay:spawnRosterPilotAt(pilotId, cfg, presence)
	if (self:isOutdoorWorldRosterPilot(cfg) and presence == "cantina") then
		presence = "post"
	end
	local x, z, y, cell, heading
	if (presence == "cantina") then
		x = cfg.cantina_x
		z = cfg.cantina_z
		y = cfg.cantina_y
		cell = self:rosterCantinaCell(cfg)
		heading = cfg.cantina_heading or 0
	else
		local lx, lz, ly = self:getPilotLeisureCoords(cfg)
		if ((presence == "leisure" or presence == "rest_home") and cfg.home_x ~= nil) then
			x, z, y = lx, lz, ly
			cell = self:getPilotHomeCell(cfg)
		else
			x, z, y = self:resolvePostCoords(cfg)
		end
		cell = cell or tonumber(cfg.spawn_cell) or 0
		heading = cfg.heading or 0
	end
	x, z, y, cell = self:resolveStableWorldCoords(cfg, x, z, y, cell, pilotId)
	if (presence == "post" and cell ~= 0 and self:isInteriorCellLoadable(cell) and (self:isBartenderPilot(cfg) or self:isTrainerPilot(cfg))) then
		local pMob = self:spawnPilotInBuilding(pilotId, cfg, cell)
		if (pMob ~= nil) then
			self:clearPilotBehaviors(pMob)
			pcall(function()
				AiAgent(pMob):addObjectFlag(AI_STATIC)
			end)
			self:syncRosterServiceForPresence(cfg, pMob, presence)
			return pMob
		end
	end
	local pMob = self:spawnPilotAt(pilotId, cfg, x, z, y, cell)
	if (pMob == nil and cell ~= 0) then
		local ox, oz, oy = self:resolveOutdoorPostFallback(cfg, cell)
		if (ox ~= nil) then
			pMob = self:spawnPilotAt(pilotId, cfg, ox, oz, oy, 0)
			if (pMob ~= nil) then
				cell = 0
				ia_catalog_boot_log("outdoor fallback " .. pilotId)
			end
		end
	end
	if (pMob == nil) then
		return nil
	end
	if (cell == 0 and presence == "post" and self:resolveOutdoorPostFallback(cfg) ~= nil) then
		self:setPilotOutdoorPost(pilotId, true)
	end
	self:clearPilotBehaviors(pMob)
	if (presence == "cantina") then
		self:startCantinaShow(pMob)
	elseif (presence == "rest_home") then
		if (self:isBartenderPilot(cfg)) then
			pcall(function()
				AiAgent(pMob):addObjectFlag(AI_STATIC)
			end)
		else
			self:enableRoamLinger(pMob, cfg)
		end
	elseif (presence == "leisure") then
		self:enableRoamBehavior(pilotId, pMob, cfg)
	elseif (presence == "post") then
		pcall(function()
			AiAgent(pMob):addObjectFlag(AI_STATIC)
		end)
	end
	self:syncRosterServiceForPresence(cfg, pMob, presence)
	return pMob
end

function IaBridgeScreenPlay:applyRosterPresence(pilotId, cfg, pMob, want)
	if (pMob == nil) then
		return
	end
	local ms = SceneObject(pMob)
	local parent = ms:getParentID()
	if (want == "post") then
		self:clearPilotBehaviors(pMob)
		local postCell = tonumber(cfg.spawn_cell) or 0
		local px, pz, py = self:resolvePostCoords(cfg)
		px, pz, py, postCell = self:resolveStableWorldCoords(cfg, px, pz, py, postCell, pilotId)
		local mx = ms:getPositionX()
		local my = ms:getPositionY()
		if (parent ~= postCell or self:dist2d(mx, my, px, py) > 1.0) then
			pcall(function()
				CreatureObject(pMob):teleport(px, pz, py, postCell)
			end)
		end
		pcall(function()
			AiAgent(pMob):addObjectFlag(AI_STATIC)
		end)
	elseif (want == "cantina") then
		self:teleportRosterToCantina(pilotId, cfg, pMob)
		self:startCantinaShow(pMob)
	elseif (want == "rest_home") then
		local lx, lz, ly = self:getPilotLeisureCoords(cfg)
		local homeCell = self:getPilotHomeCell(cfg)
		lx, lz, ly, homeCell = self:resolveStableWorldCoords(cfg, lx, lz, ly, homeCell, pilotId)
		self:clearPilotBehaviors(pMob)
		if (parent ~= homeCell or self:dist2d(ms:getPositionX(), ms:getPositionY(), lx, ly) > 1.5) then
			CreatureObject(pMob):teleport(lx, lz, ly, homeCell)
		end
		if (self:isBartenderPilot(cfg) or homeCell == 0) then
			pcall(function()
				AiAgent(pMob):addObjectFlag(AI_STATIC)
			end)
		else
			self:enableRoamLinger(pMob, cfg)
		end
	elseif (want == "leisure") then
		local lx, lz, ly = self:getPilotLeisureCoords(cfg)
		local homeCell = self:getPilotHomeCell(cfg)
		lx, lz, ly, homeCell = self:resolveStableWorldCoords(cfg, lx, lz, ly, homeCell, pilotId)
		self:clearPilotBehaviors(pMob)
		if (parent ~= homeCell or self:dist2d(ms:getPositionX(), ms:getPositionY(), lx, ly) > 1.5) then
			CreatureObject(pMob):teleport(lx, lz, ly, homeCell)
		end
		self:enableRoamBehavior(pilotId, pMob, cfg)
	end
	self:syncRosterServiceForPresence(cfg, pMob, want)
end

function IaBridgeScreenPlay:tickRosterLifecycle()
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.roster == nil) then
			-- rien
		elseif (self:isCantinaBarmanPilot(cfg)) then
			-- Comptoir cantina : lifecycle dedie (ensureCantinaBarmanOnDuty).
		elseif (self:isArtisanTrainerPilot(cfg)) then
			-- Centre entrainement artisan : lifecycle dedie (ensureArtisanTrainerOnDuty).
		else
		self:purgeStalePilotRef(pilotId)
		local want = self:getRosterDesiredPresence(pilotId, cfg)
		local life = self:getLifecyclePhase(cfg.shift_offset or 0)
		local pMob = self:resolvePilotMob(pilotId)
		if (pMob ~= nil and self:isOutdoorWorldRosterPilot(cfg)) then
			self:repatriateOutdoorPilotIfInterior(pilotId, cfg, pMob)
			pMob = self:resolvePilotMob(pilotId)
		end
		if (pMob ~= nil and not self:isMobAlive(pMob)) then
			if (want == "post" and (tonumber(cfg.spawn_cell) or 0) ~= 0) then
				self:setPilotOutdoorPost(pilotId, true)
			end
			self:despawnPilot(pilotId)
			pMob = nil
		end
		if (not self:pilotShouldExist(pilotId, cfg)) then
			if (pMob ~= nil) then
				self:despawnPilot(pilotId)
			end
			IaBridgeScreenPlay.rosterPresence[pilotId] = "off"
		elseif (want == nil or want == "off") then
			if (pMob ~= nil) then
				self:despawnPilot(pilotId)
			end
			if (IaBridgeScreenPlay.rosterPresence[pilotId] ~= "off") then
				printf("IaBridge: roster %s phase %s -> off\n", pilotId, life)
				IaBridgeScreenPlay.rosterPresence[pilotId] = "off"
			end
		elseif (pMob == nil) then
			if (want == "post" and self:shouldUseOutdoorPost(pilotId, cfg, want, tonumber(cfg.spawn_cell) or 0)) then
				self:setPilotOutdoorPost(pilotId, true)
			end
			self:spawnRosterPilotAt(pilotId, cfg, want)
			if (IaBridgeScreenPlay.rosterPresence[pilotId] ~= want) then
				printf("IaBridge: roster %s phase %s -> %s (spawn)\n", pilotId, life, want)
				IaBridgeScreenPlay.rosterPresence[pilotId] = want
			end
		else
			if (not (self:isCantinaBarmanPilot(cfg) and want == "post")) then
				self:applyRosterPresence(pilotId, cfg, pMob, want)
			else
				self:syncRosterServiceForPresence(cfg, pMob, want)
			end
			IaBridgeScreenPlay.rosterPresence[pilotId] = want
		end
		end
	end
	self:enforceRosterExactlyOnePolicies()
end

-- linger : static + animations (evite AI_PATROLLING outdoor = traversee des murs)
function IaBridgeScreenPlay:enableRoamLinger(pMob, cfg)
	if (pMob == nil) then
		return
	end
	if (cfg ~= nil and cfg.home_x ~= nil and cfg.home_y ~= nil) then
		local hx, hz, hy = self:getPilotLeisureCoords(cfg)
		local homeCell = self:getPilotHomeCell(cfg)
		hx, hz, hy, homeCell = self:resolveStableWorldCoords(cfg, hx, hz, hy, homeCell, nil)
		pcall(function()
			CreatureObject(pMob):teleport(hx, hz, hy, homeCell)
		end)
	end
	pcall(function()
		AiAgent(pMob):addObjectFlag(AI_STATIC)
	end)
	createEvent(6 * 1000, "IaBridgeScreenPlay", "lingerAnimStep", pMob, "")
end

function IaBridgeScreenPlay:lingerAnimStep(pMob)
	if (pMob == nil or not self:isMobAlive(pMob)) then
		return
	end
	local anims = {"nod", "look_left", "look_right", "stretch", "greet", "point_forward"}
	local idx = getRandomNumber(#anims)
	pcall(function()
		CreatureObject(pMob):doAnimation(anims[idx])
	end)
	local waitSec = getRandomNumber(18, 40)
	createEvent(waitSec * 1000, "IaBridgeScreenPlay", "lingerAnimStep", pMob, "")
end

function IaBridgeScreenPlay:enableRoamBehavior(pilotId, pMob, cfg)
	if (pMob == nil) then
		return
	end
	local mode = cfg.roam_mode or "linger"
	if (mode == "walk_patrol" and cfg.roam_patrol ~= nil) then
		self:enableRoamWalkPatrol(pilotId, pMob, cfg)
	elseif (mode == "patrol" and cfg.roam_patrol ~= nil) then
		self:enableRoamPatrol(pilotId, pMob, cfg)
	else
		self:enableRoamLinger(pMob, cfg)
	end
end

-- walk_patrol : setNextPosition + executeBehavior (navmesh), sans AI_PATROLLING outdoor
function IaBridgeScreenPlay:enableRoamWalkPatrol(pilotId, pMob, cfg)
	if (cfg.roam_patrol == nil or pMob == nil) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	writeStringData("ia_bridge_roam_pilot:" .. oid, pilotId)
	writeData("ia_bridge_walk_idx:" .. oid, 1)
	pcall(function()
		AiAgent(pMob):removeObjectFlag(AI_STATIC)
	end)
	createObserver(DESTINATIONREACHED, "IaBridgeScreenPlay", "reachedWalkPatrolPoint", pMob)
	self:assignRoamWalkPoint(pMob, cfg, false)
end

function IaBridgeScreenPlay:assignRoamWalkPoint(pMob, cfg, advance)
	if (pMob == nil or cfg.roam_patrol == nil) then
		return
	end
	local pts = cfg.roam_patrol
	local oid = SceneObject(pMob):getObjectID()
	local idx = readData("ia_bridge_walk_idx:" .. oid)
	if (idx == nil or idx < 1) then
		idx = 1
	end
	if (advance) then
		idx = (idx % #pts) + 1
		writeData("ia_bridge_walk_idx:" .. oid, idx)
	end
	local pt = pts[idx]
	pcall(function()
		AiAgent(pMob):removeObjectFlag(AI_STATIC)
		AiAgent(pMob):stopWaiting()
		AiAgent(pMob):setWait(0)
		local pc = pt[4] or self:getPilotHomeCell(cfg) or 0
		if (self:isOutdoorWorldRosterPilot(cfg) or self:getPilotHomeCell(cfg) == 0) then
			pc = 0
		end
		AiAgent(pMob):setNextPosition(pt[1], pt[2], pt[3], pc)
		local hx, hz, hy = self:getPilotLeisureCoords(cfg)
		local hc = self:getPilotHomeCell(cfg) or 0
		AiAgent(pMob):setHomeLocation(hx, hz, hy, hc)
		AiAgent(pMob):executeBehavior()
	end)
end

function IaBridgeScreenPlay:reachedWalkPatrolPoint(pMob)
	if (pMob == nil) then
		return 1
	end
	local oid = SceneObject(pMob):getObjectID()
	local pilotId = readStringData("ia_bridge_roam_pilot:" .. oid)
	local cfg = IA_BRIDGE_PILOTS[pilotId]
	if (cfg == nil or cfg.roam_patrol == nil or cfg.roam_mode ~= "walk_patrol") then
		return 1
	end
	local waitSec = getRandomNumber(8, 22)
	createEvent(waitSec * 1000, "IaBridgeScreenPlay", "walkPatrolResume", pMob, "")
	createEvent(3 * 1000, "IaBridgeScreenPlay", "roamPatrolAnim", pMob, "")
	return 0
end

function IaBridgeScreenPlay:walkPatrolResume(pMob)
	if (pMob == nil) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	local pilotId = readStringData("ia_bridge_roam_pilot:" .. oid)
	local cfg = IA_BRIDGE_PILOTS[pilotId]
	if (cfg ~= nil) then
		self:assignRoamWalkPoint(pMob, cfg, true)
	end
end

function IaBridgeScreenPlay:enableRoamPatrol(pilotId, pMob, cfg)
	if (cfg.roam_patrol == nil or pMob == nil) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	writeStringData("ia_bridge_roam_pilot:" .. oid, pilotId)
	pcall(function()
		AiAgent(pMob):removeObjectFlag(AI_STATIC)
		AiAgent(pMob):setMovementState(AI_PATROLLING)
	end)
	self:assignRoamPatrolPoint(pMob, cfg)
	createObserver(DESTINATIONREACHED, "IaBridgeScreenPlay", "reachedRoamPoint", pMob)
end

function IaBridgeScreenPlay:assignRoamPatrolPoint(pMob, cfg)
	if (pMob == nil or cfg.roam_patrol == nil) then
		return
	end
	if (AiAgent(pMob):getPatrolPointsSize() > 0) then
		return
	end
	local pts = cfg.roam_patrol
	local idx = getRandomNumber(#pts)
	local pt = pts[idx]
	AiAgent(pMob):setNextPosition(pt[1], pt[2], pt[3], 0)
end

function IaBridgeScreenPlay:reachedRoamPoint(pMob)
	if (pMob == nil) then
		return 1
	end
	local oid = SceneObject(pMob):getObjectID()
	local pilotId = readStringData("ia_bridge_roam_pilot:" .. oid)
	local cfg = IA_BRIDGE_PILOTS[pilotId]
	if (cfg == nil or cfg.roam_patrol == nil) then
		return 1
	end
	local waitSec = getRandomNumber(12, 35)
	createEvent(waitSec * 1000, "IaBridgeScreenPlay", "roamPatrolResume", pMob, "")
	createEvent(4 * 1000, "IaBridgeScreenPlay", "roamPatrolAnim", pMob, "")
	return 0
end

function IaBridgeScreenPlay:roamPatrolResume(pMob)
	if (pMob == nil) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	local pilotId = readStringData("ia_bridge_roam_pilot:" .. oid)
	local cfg = IA_BRIDGE_PILOTS[pilotId]
	if (cfg ~= nil) then
		self:assignRoamPatrolPoint(pMob, cfg)
	end
end

function IaBridgeScreenPlay:roamPatrolAnim(pMob)
	if (pMob == nil) then
		return
	end
	local anims = {"nod", "wave_hail", "stretch", "greet", "applause_polite"}
	local idx = getRandomNumber(#anims)
	pcall(function()
		CreatureObject(pMob):doAnimation(anims[idx])
	end)
end

function IaBridgeScreenPlay:startCantinaShow(pMob)
	if (pMob == nil) then
		return
	end
	local oid = SceneObject(pMob):getObjectID()
	if (readData("ia_bridge_dance_on:" .. oid) == 1) then
		return
	end
	writeData("ia_bridge_dance_on:" .. oid, 1)
	pcall(function()
		AiAgent(pMob):addObjectFlag(AI_STATIC)
	end)
	self:cantinaDanceStep(pMob)
end

function IaBridgeScreenPlay:cantinaDanceStep(pMob)
	if (pMob == nil or not self:isMobAlive(pMob)) then
		return
	end
	local pilotId = self:resolvePilotIdFromMob(pMob)
	if (pilotId ~= nil and IA_BRIDGE_PILOTS[pilotId] ~= nil) then
		local cfg = IA_BRIDGE_PILOTS[pilotId]
		if (cfg.cantina_x ~= nil) then
			local parent = SceneObject(pMob):getParentID() or 0
			local cell = self:rosterCantinaCell(cfg)
			if (parent ~= cell) then
				self:teleportRosterToCantina(pilotId, cfg, pMob)
			end
		end
	end
	local anims = {"social_dance_medium", "social_spin", "bounce", "wave_on_dance_floor", "celebrate"}
	local idx = getRandomNumber(#anims)
	pcall(function()
		CreatureObject(pMob):doAnimation(anims[idx])
	end)
	createEvent(9 * 1000, "IaBridgeScreenPlay", "cantinaDanceStep", pMob, "")
end

-- Rapproche les pilotes de Lia s'ils s'éloignent (Mos Eisley = foule, dérive des mobiles).
function IaBridgeScreenPlay:replenishMissingPilots()
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.roster ~= nil) then
			-- tickRosterLifecycle
		elseif (self:pilotShouldExist(pilotId, cfg) and self:resolvePilotMob(pilotId) == nil) then
			self:ensurePilots()
			return
		end
	end
end

function IaBridgeScreenPlay:getOutdoorPatrolAnchorCoords(cfg)
	if (cfg == nil) then
		return nil
	end
	if (cfg.outdoor_fb_x ~= nil) then
		return cfg.outdoor_fb_x, cfg.outdoor_fb_z, cfg.outdoor_fb_y
	end
	if (cfg.roam_patrol == nil or #cfg.roam_patrol < 1) then
		return nil
	end
	for _, pt in ipairs(cfg.roam_patrol) do
		if ((pt[4] or 0) == 0 and self:coordLooksOutdoor(pt[1], pt[3])) then
			return pt[1], pt[2], pt[3]
		end
	end
	local pt = cfg.roam_patrol[1]
	if (pt == nil) then
		return nil
	end
	return pt[1], pt[2], pt[3]
end

function IaBridgeScreenPlay:coordLooksOutdoor(x, y)
	return math.abs(tonumber(x) or 0) > 200 or math.abs(tonumber(y) or 0) > 200
end

function IaBridgeScreenPlay:getPilotHomeCell(cfg)
	if (cfg == nil) then
		return 0
	end
	if (cfg.outdoor_fb_x ~= nil and tonumber(cfg.home_cell or 0) ~= 0) then
		if (cfg.roster ~= nil and (
			string.find(cfg.roster, "mos_trainer_", 1, true) ~= nil
			or string.find(cfg.roster, "entertainer_trainer", 1, true) ~= nil
		)) then
			return 0
		end
	end
	if (cfg.roster ~= nil and string.find(cfg.roster, "mos_trainer_", 1, true) ~= nil and cfg.roam_patrol ~= nil) then
		return 0
	end
	if (cfg.home_cell ~= nil) then
		return tonumber(cfg.home_cell) or 0
	end
	if (cfg.spawn_cell ~= nil) then
		return tonumber(cfg.spawn_cell) or 0
	end
	return 0
end

-- Poste de service partagé (ex. instructeur entertainer).
function IaBridgeScreenPlay:getPilotPostCoords(cfg)
	if (cfg == nil) then
		return 0, 0, 0
	end
	return cfg.x or 0, cfg.z or 0, cfg.y or 0
end

-- Position « chez soi » en loisir / patrouille (évite superposition roster).
function IaBridgeScreenPlay:getPilotLeisureCoords(cfg)
	if (cfg == nil) then
		return 0, 0, 0
	end
	if (cfg.roster ~= nil and string.find(cfg.roster, "mos_trainer_", 1, true) ~= nil) then
		local ox, oz, oy = self:getOutdoorPatrolAnchorCoords(cfg)
		if (ox ~= nil) then
			return ox, oz, oy
		end
	end
	if (cfg.home_x ~= nil and cfg.home_y ~= nil) then
		if (not self:coordLooksOutdoor(cfg.home_x, cfg.home_y) and cfg.outdoor_fb_x ~= nil) then
			return cfg.outdoor_fb_x, cfg.outdoor_fb_z, cfg.outdoor_fb_y
		end
		return cfg.home_x, cfg.home_z or cfg.z or 0, cfg.home_y
	end
	return self:getPilotPostCoords(cfg)
end

function IaBridgeScreenPlay:resetPilotToHome(pilotId)
	local cfg = self:getPilotCfg(pilotId)
	if (cfg == nil) then
		return false
	end
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob == nil) then
		return false
	end
	local cell = self:getPilotHomeCell(cfg)
	local tx, tz, ty = cfg.x, cfg.z, cfg.y
	if (cfg.roster ~= nil) then
		local want = self:getRosterDesiredPresence(pilotId, cfg)
		if (self:isOutdoorWorldRosterPilot(cfg)) then
			if (want == "leisure" or want == "rest_home") then
				tx, tz, ty = self:getPilotLeisureCoords(cfg)
			else
				tx, tz, ty = self:resolvePostCoords(cfg)
			end
			cell = 0
		elseif (want == "leisure" or want == "rest_home") then
			tx, tz, ty = self:getPilotLeisureCoords(cfg)
			cell = self:getPilotHomeCell(cfg)
		elseif (want == "cantina" and cfg.cantina_x ~= nil) then
			tx, tz, ty = cfg.cantina_x, cfg.cantina_z, cfg.cantina_y
			cell = self:rosterCantinaCell(cfg)
		end
	end
	tx, tz, ty, cell = self:resolveStableWorldCoords(cfg, tx, tz, ty, cell, pilotId)
	self:clearPilotBehaviors(pMob)
	CreatureObject(pMob):teleport(tx, tz, ty, cell)
	if (cfg.roster ~= nil) then
		local want = self:getRosterDesiredPresence(pilotId, cfg)
		if (want ~= nil and want ~= "off") then
			self:applyRosterPresence(pilotId, cfg, pMob, want)
		end
	elseif (cfg.roam_mode ~= nil) then
		self:enableRoamBehavior(pilotId, pMob, cfg)
	end
	printf("IaBridge: reset_pilot %s -> cell %s (%.1f %.1f)\n", pilotId, tostring(cell), tx, ty)
	return true
end

function IaBridgeScreenPlay:repatriateOutdoorPilotIfInterior(pilotId, cfg, pMob)
	if (pMob == nil or cfg == nil) then
		return false
	end
	local homeCell = self:getPilotHomeCell(cfg)
	if (homeCell ~= 0 and not self:isOutdoorWorldRosterPilot(cfg)) then
		return false
	end
	local parent = SceneObject(pMob):getParentID() or 0
	if (parent == 0) then
		return false
	end
	self:resetPilotToHome(pilotId)
	return true
end

-- Rappel vers le poste d'origine (interieur ou exterieur).
function IaBridgeScreenPlay:containPilotNearHome(pilotId, cfg)
	if (cfg ~= nil and cfg.roster ~= nil) then
		return
	end
	if (cfg ~= nil and (cfg.roam_mode or "linger") == "linger") then
		local pMob = self:resolvePilotMob(pilotId)
		if (pMob ~= nil and self:getPilotHomeCell(cfg) == 0) then
			local parent = SceneObject(pMob):getParentID() or 0
			if (parent ~= 0) then
				self:repatriateOutdoorPilotIfInterior(pilotId, cfg, pMob)
			else
				local hx, hz, hy = cfg.x, cfg.z, cfg.y
				local scene = SceneObject(pMob)
				if (scene ~= nil and self:dist2d(scene:getPositionX(), scene:getPositionY(), hx, hy) > 2.0) then
					pcall(function()
						CreatureObject(pMob):teleport(hx, hz, hy, 0)
					end)
				end
			end
		end
		return
	end
	local radius = cfg.roam_contain_m
	if (radius == nil or radius <= 0) then
		return
	end
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob == nil) then
		return
	end
	local homeCell = self:getPilotHomeCell(cfg)
	local ms = SceneObject(pMob)
	local parent = ms:getParentID() or 0
	if (homeCell == 0 and parent ~= 0) then
		self:repatriateOutdoorPilotIfInterior(pilotId, cfg, pMob)
		return
	end
	if (homeCell ~= 0 and parent ~= homeCell) then
		self:resetPilotToHome(pilotId)
		return
	end
	if (parent ~= homeCell) then
		return
	end
	local hx, hy
	if (cfg.home_x ~= nil and cfg.home_y ~= nil) then
		hx, hy = cfg.home_x, cfg.home_y
	else
		hx, hy = cfg.x, cfg.y
	end
	local mx = ms:getPositionX()
	local my = ms:getPositionY()
	if (self:dist2d(mx, my, hx, hy) > radius) then
		CreatureObject(pMob):teleport(hx, cfg.z or cfg.home_z or 5, hy, homeCell)
	end
end

function IaBridgeScreenPlay:repatriateDriftedPilots()
	if (os.time() % 20 > 3) then
		return
	end
	for pilotId, cfg in pairs(self:catalogPilotTable()) do
		local pMob = self:resolvePilotMob(pilotId)
		if (pMob ~= nil) then
			local parent = SceneObject(pMob):getParentID() or 0
			if (parent ~= 0 and (self:getPilotHomeCell(cfg) == 0 or self:isOutdoorWorldRosterPilot(cfg))) then
				self:resetPilotToHome(pilotId)
			end
		end
	end
end

function IaBridgeScreenPlay:syncPilotsNearLia()
	local pPlayer = self:resolvePlayer(IA_BRIDGE_BOT)
	if (pPlayer == nil) then
		return
	end
	self:replenishMissingPilots()
	local ax, az, ay, acell = self:liaAnchor()
	if (ax == nil) then
		return
	end
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.follow_lia == true) then
			local pMob = self:resolvePilotMob(pilotId)
			if (pMob ~= nil) then
				local ms = SceneObject(pMob)
				local mx = ms:getPositionX()
				local my = ms:getPositionY()
				local leash = cfg.leash_m or 6
				if (self:dist2d(mx, my, ax, ay) > leash) then
					local tx = ax + (cfg.off_x or 0)
					local ty = ay + (cfg.off_y or 0)
					CreatureObject(pMob):teleport(tx, az, ty, acell or 0)
				end
			end
		elseif (cfg.roam_contain_m ~= nil) then
			self:containPilotNearHome(pilotId, cfg)
		end
	end
	if (IaBridgeScreenPlay.notifiedLia ~= true) then
		IaBridgeScreenPlay.notifiedLia = true
		CreatureObject(pPlayer):sendSystemMessage(
			"[IA] Cycle temps jeu actif : triplon entertainer (travail/repos/loisir, 6h reel = 1j IG)."
		)
	end
end

-- Appel unique au boot screenplay (pas a chaque tick).
function IaBridgeScreenPlay:bootPilotsOnce()
	if (IaBridgeScreenPlay.pilotsBootDone == true) then
		return
	end
	IaBridgeScreenPlay.pilotsBootDone = true
	self:persistStore().pilotsBootDone = true
	self:purgeCantinaBarmanBootOnce()
	self:ensurePilots()
	local online = 0
	for pilotId, cfg in pairs(self:catalogPilotTable()) do
		if (self:resolvePilotMob(pilotId) ~= nil) then
			online = online + 1
		end
		if (cfg.roster ~= nil and (string.find(cfg.roster, "mos_trainer_") ~= nil or string.find(cfg.roster, "cantina_barman", 1, true) ~= nil)) then
			local want = self:getRosterDesiredPresence(pilotId, cfg)
			local life = self:getLifecyclePhase(cfg.shift_offset or 0)
			ia_catalog_boot_log(string.format(
				"boot %s roster=%s phase=%s want=%s mob=%s",
				pilotId, cfg.roster, life, tostring(want), tostring(self:resolvePilotMob(pilotId) ~= nil)
			))
		end
	end
	ia_catalog_boot_log("boot pilotes en ligne=" .. tostring(online) .. " mobRefs=" .. tostring(self:countTableKeys(self:pilotMobTable())))
	createEvent(4000, "IaBridgeScreenPlay", "bootRefreshPilotBodies", nil, "")
end

function IaBridgeScreenPlay:bootRefreshPilotBodies()
	self:refreshAllPilotBodies()
end

-- species_id SWG (TemplateSpecies) -> cle matrice tailles
local IA_BRIDGE_SPECIES_ID_TO_KEY = {
	[0] = "human",
	[1] = "rodian",
	[2] = "trandoshan",
	[3] = "moncal",
	[4] = "wookiee",
	[5] = "bothan",
	[6] = "twilek",
	[7] = "zabrak",
	[0x21] = "ithorian",
	[0x31] = "sullustan",
	[33] = "ithorian",
	[49] = "sullustan",
}

function IaBridgeScreenPlay:resolvePlayerSpeciesKey(pCreature)
	if (pCreature == nil) then
		return nil, nil
	end
	local speciesId = nil
	local gender = nil
	pcall(function()
		speciesId = CreatureObject(pCreature):getSpecies()
		gender = CreatureObject(pCreature):getGender()
	end)
	if (speciesId == nil) then
		return nil, nil
	end
	local key = IA_BRIDGE_SPECIES_ID_TO_KEY[speciesId]
	local g = "male"
	if (gender ~= nil and (gender == 1 or gender == "female")) then
		g = "female"
	end
	return key, g
end

-- Sans rebuild : iaApplyPilotHeight (deja dans core3-clean) accepte joueurs et PNJ.
function IaBridgeScreenPlay:setPlayerHeightMeters(playerName, heightM)
	local pPlayer = self:resolvePlayer(playerName)
	if (pPlayer == nil) then
		return false, "joueur introuvable"
	end
	local h = tonumber(heightM)
	if (h == nil or h <= 0) then
		return false, "height_m invalide"
	end
	local speciesKey, gender = self:resolvePlayerSpeciesKey(pPlayer)
	if (speciesKey == nil) then
		return false, "espece joueur inconnue"
	end
	local scale = self:heightToScale(speciesKey, gender, h)
	if (scale == nil or iaApplyPilotHeight == nil) then
		return false, "scale ou iaApplyPilotHeight indisponible"
	end
	pcall(function()
		iaApplyPilotHeight(pPlayer, scale)
	end)
	printf("IaBridge: set_player_height %s %.2fm (%s %s scale=%.3f)\n", playerName, h, speciesKey, gender, scale)
	return true, scale
end

function IaBridgeScreenPlay:setPlayerHeightScale(playerName, scaleVal)
	local pPlayer = self:resolvePlayer(playerName)
	if (pPlayer == nil) then
		return false, "joueur introuvable"
	end
	local scale = tonumber(scaleVal)
	if (scale == nil or scale <= 0) then
		return false, "scale invalide"
	end
	if (iaApplyPilotHeight == nil) then
		return false, "iaApplyPilotHeight absent"
	end
	pcall(function()
		iaApplyPilotHeight(pPlayer, scale)
	end)
	printf("IaBridge: set_player_height %s scale=%.3f\n", playerName, scale)
	return true, scale
end

function IaBridgeScreenPlay:setPlayerLbgBody(playerName, speciesKey, gender, heightM)
	local pPlayer = self:resolvePlayer(playerName)
	if (pPlayer == nil) then
		return false, "joueur introuvable"
	end
	local h = tonumber(heightM)
	if (h == nil or h <= 0) then
		return false, "height_m invalide"
	end
	local iff = self:speciesAppearanceIff(speciesKey, gender)
	if (iff ~= nil) then
		pcall(function()
			CreatureObject(pPlayer):setAppearance(iff)
		end)
	end
	local scale = self:heightToScale(speciesKey, gender, h)
	if (scale == nil or iaApplyPilotHeight == nil) then
		return false, "scale ou iaApplyPilotHeight indisponible"
	end
	pcall(function()
		iaApplyPilotHeight(pPlayer, scale)
	end)
	printf("IaBridge: set_player_lbg_body %s %s %s %.2fm (scale=%.3f)\n", playerName, speciesKey, gender, h, scale)
	return true, scale
end

function IaBridgeScreenPlay:enforceLbgPlayerHeightOnLogin(pPlayer)
	if (pPlayer == nil or iaApplyPilotHeight == nil) then
		return
	end
	local speciesKey, gender = self:resolvePlayerSpeciesKey(pPlayer)
	if (speciesKey == nil) then
		return
	end
	local slot = IA_BRIDGE_LBG_SLOT_HEIGHT[speciesKey]
	if (slot == nil or slot.max_m == nil or slot.max_m > 1.05) then
		return
	end
	local oid = SceneObject(pPlayer):getObjectID()
	if (readData("lbg_height_fix_v1:" .. oid) == 1) then
		return
	end
	local name = CreatureObject(pPlayer):getFirstName()
	local targetH = slot.min_m or slot.max_m
	if (targetH == nil) then
		return
	end
	local ok = self:setPlayerHeightMeters(name, targetH)
	if (ok) then
		writeData("lbg_height_fix_v1:" .. oid, 1)
		CreatureObject(pPlayer):sendSystemMessage(
			"[LBG] Taille ajustee (" .. tostring(math.floor(targetH * 100)) .. " cm) — curseur creation vanilla depasse."
		)
	end
end

function IaBridgeScreenPlay:maybeRedirectPlayerToLostHeaven(pPlayer)
	if (not IA_BRIDGE_LOST_HEAVEN_ENABLED or pPlayer == nil) then
		return
	end
	if (self:isAiBridgePlayer(pPlayer)) then
		return
	end
	local scene = SceneObject(pPlayer)
	if (scene:getZoneName() ~= IA_BRIDGE_ZONE) then
		return
	end
	local oid = scene:getObjectID()
	local flagKey = "lbg_spawn_lost_heaven_v1:" .. oid
	if (readData(flagKey) == 1) then
		return
	end
	local parent = scene:getParentID() or 0
	if (parent > 0) then
		return
	end
	local px = scene:getPositionX()
	local py = scene:getPositionY()
	local dxMe = px - IA_BRIDGE_ME_SPAWN_X
	local dyMe = py - IA_BRIDGE_ME_SPAWN_Y
	local dMe = math.sqrt(dxMe * dxMe + dyMe * dyMe)
	local dxLh = px - IA_BRIDGE_LOST_HEAVEN_X
	local dyLh = py - IA_BRIDGE_LOST_HEAVEN_Y
	local dLh = math.sqrt(dxLh * dxLh + dyLh * dyLh)
	if (dLh < IA_BRIDGE_LOST_HEAVEN_ARRIVED_RADIUS_M) then
		writeData(flagKey, 1)
		return
	end
	if (dMe > IA_BRIDGE_ME_REDIRECT_RADIUS_M) then
		return
	end
	CreatureObject(pPlayer):teleport(
		IA_BRIDGE_LOST_HEAVEN_X,
		IA_BRIDGE_LOST_HEAVEN_Z,
		IA_BRIDGE_LOST_HEAVEN_Y,
		0
	)
	writeData(flagKey, 1)
	CreatureObject(pPlayer):sendSystemMessage(
		"[LBG] Bienvenue sur Scrapaltai — vous êtes redirigé vers Lost Heaven (nouveau hub)."
	)
end

function IaBridgeScreenPlay:onPlayerLoggedIn(pPlayer)
	self:enforceLbgPlayerHeightOnLogin(pPlayer)
	self:maybeRedirectPlayerToLostHeaven(pPlayer)
end

function IaBridgeScreenPlay:isPlayerConnected(pCreature)
	if (pCreature == nil) then
		return false
	end
	local online = false
	local ok = pcall(function()
		local pGhost = CreatureObject(pCreature):getPlayerObject()
		if (pGhost == nil) then
			return
		end
		online = PlayerObject(pGhost):isOnline()
	end)
	return ok and online
end

-- Snapshot JSON : bots headless + client réel en zone (isOnline parfois faux en intérieur).
function IaBridgeScreenPlay:canSnapshotPlayer(pPlayer)
	if (pPlayer == nil) then
		return false
	end
	if (self:isAiBridgePlayer(pPlayer)) then
		return true
	end
	if (self:isPlayerConnected(pPlayer)) then
		return true
	end
	return self:sceneParentId(pPlayer) > 0
end

function IaBridgeScreenPlay:isAiBridgePlayer(pCreature)
	if (pCreature == nil) then
		return false
	end
	local name = self:eventActorName(pCreature)
	for i = 1, #IA_BRIDGE_AI_PLAYERS do
		if (name == IA_BRIDGE_AI_PLAYERS[i]) then
			return true
		end
	end
	return false
end

-- Bots headless (Lia/Nix) : isOnline() peut etre faux alors que le perso est en zone.
function IaBridgeScreenPlay:canRunPlayerGesture(pPlayer)
	if (pPlayer == nil) then
		return false
	end
	if (self:isAiBridgePlayer(pPlayer)) then
		return true
	end
	return self:isPlayerConnected(pPlayer)
end

function IaBridgeScreenPlay:publishSnapshot()
	local pPlayer = self:resolvePlayer(IA_BRIDGE_BOT)
	-- Pour les bots headless (Lia/Nix), PlayerObject:isOnline() peut rester faux.
	-- Dès qu'on résout le player en zone, on publie le snapshot "online".
	if (pPlayer == nil) then
		self:writePlayerSnapshotOffline()
		return
	end
	if (not self:isAiBridgePlayer(pPlayer) and not self:isPlayerConnected(pPlayer)) then
		self:writePlayerSnapshotOffline()
		return
	end
	local ok = pcall(function()
		writeIaBridgePlayerSnapshot(IA_BRIDGE_BOT)
	end)
	if (not ok) then
		return
	end
end

function IaBridgeScreenPlay:writePlayerSnapshotOffline()
	local ts = os.time()
	local body = string.format('{"online":false,"player":"%s","ts":%d}', self:jsonEscape(IA_BRIDGE_BOT), ts)
	local f = io.open(IA_BRIDGE_PLAYER_SNAPSHOT_FILE, "w")
	if (f ~= nil) then
		f:write(body)
		f:close()
	end
end

function IaBridgeScreenPlay:publishAiPlayerSnapshots()
	local ts = os.time()
	local chunks = {}
	local n = 0
	local names = {}
	local seen = {}
	local function addSnapshotName(nm)
		local s = tostring(nm or "")
		if (s == "" or seen[s]) then
			return
		end
		seen[s] = true
		table.insert(names, s)
	end
	for i = 1, #IA_BRIDGE_AI_PLAYERS do
		addSnapshotName(IA_BRIDGE_AI_PLAYERS[i])
	end
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		addSnapshotName(IA_BRIDGE_CHAT_RELAY[i])
	end
	for i = 1, #names do
		local name = names[i]
		local pPlayer = self:resolvePlayer(name)
		if (pPlayer ~= nil and self:canSnapshotPlayer(pPlayer)) then
			local x, y, z = 0, 0, 0
			local firstname = name
			local surname = ""
			local hp, actionHam, mind = 0, 0, 0
			local invCount, invNear, invFull = 0, false, false
			local parentId = 0
			pcall(function()
				local scene = SceneObject(pPlayer)
				x = scene:getPositionX()
				y = scene:getPositionY()
				z = scene:getPositionZ()
				parentId = scene:getParentID() or 0
				firstname = CreatureObject(pPlayer):getFirstName()
				surname = CreatureObject(pPlayer):getLastName()
				hp = CreatureObject(pPlayer):getHAM(0)
				actionHam = CreatureObject(pPlayer):getHAM(3)
				mind = CreatureObject(pPlayer):getHAM(6)
			end)
			invCount, invNear, invFull = self:inventorySnapshotFields(pPlayer)
			if (invNear) then
				self:pruneAiPlayerInventory(pPlayer, { notify = false })
				invCount, invNear, invFull = self:inventorySnapshotFields(pPlayer)
			end
			n = n + 1
			chunks[n] = string.format(
				'"%s":{"online":true,"player":"%s","firstname":"%s","surname":"%s","zone":"%s","x":%.2f,"y":%.2f,"z":%.2f,"parent_id":%d,"in_interior":%s,"hp":%d,"action":%d,"mind":%d,"inventory_count":%d,"inventory_near_full":%s,"inventory_full":%s,"ts":%d}',
				self:jsonEscape(name),
				self:jsonEscape(firstname),
				self:jsonEscape(firstname),
				self:jsonEscape(surname),
				self:jsonEscape(IA_BRIDGE_ZONE),
				x,
				y,
				z,
				parentId,
				(parentId ~= nil and parentId > 0) and "true" or "false",
				hp,
				actionHam,
				mind,
				invCount,
				invNear and "true" or "false",
				invFull and "true" or "false",
				ts
			)
		else
			n = n + 1
			chunks[n] = string.format(
				'"%s":{"online":false,"player":"%s","zone":"%s","ts":%d}',
				self:jsonEscape(name),
				self:jsonEscape(name),
				self:jsonEscape(IA_BRIDGE_ZONE),
				ts
			)
		end
	end
	local body = '{"ts":' .. tostring(ts) .. ',"players":{' .. table.concat(chunks, ",") .. "}}"
	local f = io.open(IA_BRIDGE_PLAYER_SNAPSHOTS_FILE, "w")
	if (f ~= nil) then
		f:write(body)
		f:close()
	end
end

function IaBridgeScreenPlay:jsonEscape(val)
	val = tostring(val or "")
	val = string.gsub(val, "\\", "\\\\")
	val = string.gsub(val, '"', '\\"')
	val = string.gsub(val, "\n", "\\n")
	val = string.gsub(val, "\r", "")
	return val
end

function IaBridgeScreenPlay:eventActorName(pPlayer)
	if (pPlayer == nil) then
		return ""
	end
	local name = ""
	pcall(function()
		name = CreatureObject(pPlayer):getFirstName()
	end)
	return tostring(name or "")
end

function IaBridgeScreenPlay:inferAiMessageTarget(actor, message)
	local msg = tostring(message or "")
	local lowered = string.lower(msg)
	for i = 1, #IA_BRIDGE_AI_PLAYERS do
		local name = IA_BRIDGE_AI_PLAYERS[i]
		if (string.lower(tostring(name)) ~= string.lower(tostring(actor or ""))) then
			local prefix1 = string.lower(tostring(name)) .. ","
			local prefix2 = string.lower(tostring(name)) .. ":"
			if (string.sub(lowered, 1, string.len(prefix1)) == prefix1 or string.sub(lowered, 1, string.len(prefix2)) == prefix2) then
				return name
			end
		end
	end
	return ""
end

function IaBridgeScreenPlay:appendSocialEvent(eventType, actor, target, message, x, y, z, sourceLine)
	local ts = os.time()
	if (IaBridgeScreenPlay.eventSeq == nil) then
		IaBridgeScreenPlay.eventSeq = 0
	end
	IaBridgeScreenPlay.eventSeq = IaBridgeScreenPlay.eventSeq + 1
	local eventId = tostring(ts) .. "-" .. tostring(IaBridgeScreenPlay.eventSeq)
	local body = string.format(
		'{"version":1,"event_id":"%s","ts":%d,"type":"%s","actor":"%s","target":"%s","message":"%s","zone":"%s","x":%.2f,"y":%.2f,"z":%.2f,"source_line":"%s"}',
		self:jsonEscape(eventId),
		ts,
		self:jsonEscape(eventType),
		self:jsonEscape(actor),
		self:jsonEscape(target),
		self:jsonEscape(message),
		self:jsonEscape(IA_BRIDGE_ZONE),
		tonumber(x) or 0,
		tonumber(y) or 0,
		tonumber(z) or 0,
		self:jsonEscape(sourceLine)
	)
	local f = io.open(IA_BRIDGE_EVENTS_FILE, "a")
	if (f ~= nil) then
		f:write(body .. "\n")
		f:close()
	else
		printf("IaBridge: impossible d'ecrire %s\n", IA_BRIDGE_EVENTS_FILE)
	end
	if (iaPublishWorldEvent ~= nil) then
		pcall(function()
			iaPublishWorldEvent(eventType, body)
		end)
	end
end

function IaBridgeScreenPlay:appendNpcSnapshotChunk(chunks, n, pilotId, cfg, pMob, ts)
	if (pMob == nil or cfg == nil) then
		return n
	end
	local x, y, z = cfg.x or 0, cfg.y or 0, cfg.z or 0
	local name = cfg.display_name or pilotId
	local okPos, posErr = pcall(function()
		local scene = SceneObject(pMob)
		x = scene:getPositionX()
		z = scene:getPositionZ()
		y = scene:getPositionY()
		local custom = SceneObject(pMob):getDisplayedName()
		if (custom ~= nil and tostring(custom) ~= "") then
			name = tostring(custom)
		end
	end)
	if (not okPos) then
		printf("IaBridge: position pilote %s : %s\n", pilotId, tostring(posErr))
	end
	n = n + 1
	chunks[n] = string.format(
		'"%s":{"online":true,"pilot_id":"%s","lbg_npc_id":"%s","zone":"%s","x":%.2f,"y":%.2f,"z":%.2f,"name":"%s","ts":%d}',
		self:jsonEscape(pilotId),
		self:jsonEscape(pilotId),
		self:jsonEscape(cfg.lbg_npc_id or ""),
		self:jsonEscape(IA_BRIDGE_ZONE),
		x,
		y,
		z,
		self:jsonEscape(name),
		ts
	)
	return n
end

function IaBridgeScreenPlay:publishNpcSnapshots()
	local ts = os.time()
	local chunks = {}
	local n = 0
	local seen = {}
	local function publishOne(pilotId)
		if (seen[pilotId] == true) then
			return
		end
		local cfg = self:getPilotCfg(pilotId)
		local pMob = self:resolvePilotMob(pilotId)
		if (cfg ~= nil and pMob ~= nil) then
			seen[pilotId] = true
			n = self:appendNpcSnapshotChunk(chunks, n, pilotId, cfg, pMob, ts)
		end
	end
	local function publishAllFrom(tbl)
		if (tbl == nil) then
			return
		end
		for pilotId, _ in pairs(tbl) do
			publishOne(pilotId)
		end
	end
	publishAllFrom(self:catalogPilotTable())
	if (self:hasProductionCatalog()) then
		publishAllFrom(IA_BRIDGE_PILOTS)
	end
	publishAllFrom(self:pilotMobTable())
	local body = "{" .. table.concat(chunks, ",") .. "}"
	if (n == 0) then
		body = "{}"
	end
	local f = io.open(IA_BRIDGE_NPC_SNAPSHOT_FILE, "w")
	if (f ~= nil) then
		f:write(body)
		f:close()
	elseif (n > 0) then
		printf("IaBridge: impossible d'ecrire %s (io.open) n=%d\n", IA_BRIDGE_NPC_SNAPSHOT_FILE, n)
	end
end

function IaBridgeScreenPlay:splitLine(line, expected)
	local parts = {}
	local start = 1
	local idx = 1

	while idx < expected do
		local sep = string.find(line, "|", start, true)
		if sep == nil then
			return nil
		end
		parts[idx] = string.sub(line, start, sep - 1)
		start = sep + 1
		idx = idx + 1
	end

	parts[expected] = string.sub(line, start)
	return parts
end

-- Quêtes v1 (MVP Prime) : persistance append-only + état minimal.
-- Objectif Lot0: 3 quêtes types jouables sans dépendre du journal SWG.
function IaBridgeScreenPlay:appendQuestState(eventType, playerName, questId, payload)
	local ts = os.time()
	IaBridgeScreenPlay.questSeq = (IaBridgeScreenPlay.questSeq or 0) + 1
	local id = tostring(ts) .. "-" .. tostring(IaBridgeScreenPlay.questSeq)
	local body = string.format(
		'{"version":1,"id":"%s","ts":%d,"type":"%s","player":"%s","quest_id":"%s","payload":"%s"}',
		self:jsonEscape(id),
		ts,
		self:jsonEscape(eventType),
		self:jsonEscape(playerName or ""),
		self:jsonEscape(questId or ""),
		self:jsonEscape(payload or "")
	)
	local f = io.open(IA_BRIDGE_QUEST_STATE_FILE, "a")
	if (f ~= nil) then
		f:write(body .. "\n")
		f:close()
	else
		printf("IaBridge: impossible d'ecrire %s\n", IA_BRIDGE_QUEST_STATE_FILE)
	end
end

function IaBridgeScreenPlay:questTemplates()
	if (IA_BRIDGE_QUEST_TEMPLATES ~= nil and #IA_BRIDGE_QUEST_TEMPLATES > 0) then
		return IA_BRIDGE_QUEST_TEMPLATES
	end
	return {
		{
			id = "quest:mos_delivery_water",
			title = "Livraison d'eau",
			brief = "Apporte une ration (fruit forage) au donneur de quete.",
			reward_item = "object/tangible/food/foraged/foraged_fruit_s2.iff",
		},
		{
			id = "quest:mos_repair_generator",
			title = "Reparation rapide",
			brief = "Va sur place, confirme la zone, puis reviens.",
			reward_item = "object/tangible/food/foraged/foraged_fruit_s3.iff",
		},
		{
			id = "quest:mos_investigate_noise",
			title = "Enquete de quartier",
			brief = "Parle au garde puis reviens faire ton rapport.",
			reward_item = "object/tangible/food/foraged/foraged_fruit_s1.iff",
		},
	}
end

function IaBridgeScreenPlay:pickQuestTemplate()
	local q = self:questTemplates()
	return q[getRandomNumber(#q)]
end

function IaBridgeScreenPlay:offerQuestToPlayer(pNpc, npcName, targetName, questId)
	if (targetName == nil or targetName == "") then
		return false
	end
	local pTarget = getPlayerByName(targetName)
	if (pTarget == nil) then
		return false
	end
	local template = nil
	if (questId ~= nil and questId ~= "") then
		for _, t in ipairs(self:questTemplates()) do
			if (t.id == questId) then
				template = t
				break
			end
		end
	end
	if (template == nil) then
		template = self:pickQuestTemplate()
	end
	local brief = template.brief or "Mission locale."
	pcall(function()
		if (pNpc ~= nil) then
			spatialChat(pNpc, targetName .. ", " .. brief .. " (tape: quest_accept:" .. template.id .. ")")
		end
	end)
	pcall(function()
		CreatureObject(pTarget):sendSystemMessage("[Quete] Offre: " .. template.title .. " — " .. template.id)
	end)
	self:appendQuestState("offer", targetName, template.id, "npc=" .. tostring(npcName or ""))
	return true
end

function IaBridgeScreenPlay:acceptQuest(pPlayer, questId)
	if (pPlayer == nil or questId == nil or questId == "") then
		return
	end
	local name = self:eventActorName(pPlayer)
	self:appendQuestState("accept", name, questId, "")
	pcall(function()
		CreatureObject(pPlayer):sendSystemMessage("[Quete] Acceptee: " .. questId .. " (tape: quest_turnin:" .. questId .. ")")
	end)
	self:appendSocialEvent("core3.quest_accept", name, "", questId, 0, 0, 0, questId)
end

function IaBridgeScreenPlay:factionRepKey(playerName, factionId)
	return "ia_bridge:rep:" .. tostring(playerName) .. ":" .. tostring(factionId)
end

function IaBridgeScreenPlay:getFactionRep(playerName, factionId)
	local key = self:factionRepKey(playerName, factionId)
	local raw = getQuestStatus(key)
	if (raw == nil or raw == "") then
		return 0
	end
	return tonumber(raw) or 0
end

function IaBridgeScreenPlay:addFactionRep(playerName, factionId, delta)
	if (playerName == nil or factionId == nil or delta == nil) then
		return
	end
	local cur = self:getFactionRep(playerName, factionId)
	local nxt = cur + delta
	setQuestStatus(self:factionRepKey(playerName, factionId), tostring(nxt))
	self:appendSocialEvent("core3.faction_rep", playerName, factionId, tostring(nxt), 0, 0, 0, "+" .. tostring(delta))
end

function IaBridgeScreenPlay:findShopByPilot(pilotId)
	if (IA_BRIDGE_ECONOMY == nil or IA_BRIDGE_ECONOMY.shops == nil) then
		return nil
	end
	for _, shop in ipairs(IA_BRIDGE_ECONOMY.shops) do
		if (shop.pilot_id == pilotId) then
			return shop
		end
	end
	return nil
end

function IaBridgeScreenPlay:handleVendorBuy(pPlayer, pilotId, itemIndex)
	if (pPlayer == nil) then
		return
	end
	local shop = self:findShopByPilot(pilotId)
	if (shop == nil or shop.items == nil) then
		CreatureObject(pPlayer):sendSystemMessage("[Commerce] Marchand inconnu.")
		return
	end
	local idx = (tonumber(itemIndex) or 0) + 1
	local item = shop.items[idx]
	if (item == nil) then
		CreatureObject(pPlayer):sendSystemMessage("[Commerce] Article invalide.")
		return
	end
	local tpl = item.template
	pcall(function()
		local pInv = CreatureObject(pPlayer):getSlottedObject("inventory")
		if (pInv ~= nil and tpl ~= nil) then
			local pItem = giveItem(pInv, tpl, -1, true)
			if (pItem ~= nil) then
				CreatureObject(pPlayer):sendSystemMessage("[Commerce] Achat OK — " .. tostring(shop.display_name or pilotId))
				self:appendSocialEvent("core3.economy_buy", self:eventActorName(pPlayer), pilotId, tpl, 0, 0, 0, tostring(item.price or 0))
			end
		end
	end)
end

function IaBridgeScreenPlay:handleCraftCombine(pPlayer, recipeId)
	if (pPlayer == nil or IA_BRIDGE_ECONOMY == nil or IA_BRIDGE_ECONOMY.craft_chains == nil) then
		return
	end
	for _, chain in ipairs(IA_BRIDGE_ECONOMY.craft_chains) do
		if (chain.id == recipeId) then
			local pInv = CreatureObject(pPlayer):getSlottedObject("inventory")
			if (pInv == nil) then
				return
			end
			local ok = true
			for _, inTpl in ipairs(chain.inputs or {}) do
				-- MVP : on donne la sortie si le joueur a au moins un input (pas de consommation stricte)
				ok = ok and (inTpl ~= nil)
			end
			if (ok and chain.output ~= nil) then
				giveItem(pInv, chain.output, -1, true)
				CreatureObject(pPlayer):sendSystemMessage("[Craft] Combine : " .. tostring(recipeId))
				self:appendSocialEvent("core3.craft_combine", self:eventActorName(pPlayer), recipeId, chain.output, 0, 0, 0, "")
			end
			return
		end
	end
	CreatureObject(pPlayer):sendSystemMessage("[Craft] Recette inconnue.")
end

function IaBridgeScreenPlay:resolveCantinaEnterCoords(pPlayer)
	local cell = IA_BRIDGE_CANTINA_CELL
	local x, z, y = IA_BRIDGE_CANTINA_BAR_X, IA_BRIDGE_CANTINA_BAR_Z, IA_BRIDGE_CANTINA_BAR_Y
	if (pPlayer ~= nil and self:eventActorName(pPlayer) == IA_BRIDGE_BOT) then
		x = IA_BRIDGE_CANTINA_LIA_GUEST_X
		z = IA_BRIDGE_CANTINA_LIA_GUEST_Z
		y = IA_BRIDGE_CANTINA_LIA_GUEST_Y
	end
	return cell, x, z, y
end

function IaBridgeScreenPlay:liaAtCantinaBarPost(pLia)
	if (pLia == nil) then
		return false
	end
	if (self:sceneParentId(pLia) ~= IA_BRIDGE_CANTINA_CELL) then
		return false
	end
	local scene = SceneObject(pLia)
	if (scene == nil) then
		return false
	end
	local dist = self:dist2d(
		scene:getPositionX(),
		scene:getPositionY(),
		IA_BRIDGE_CANTINA_BAR_X,
		IA_BRIDGE_CANTINA_BAR_Y
	)
	return dist < IA_BRIDGE_CANTINA_LIA_NEAR_BAR_M
end

function IaBridgeScreenPlay:liaAtCantinaGuestPost(pLia)
	if (pLia == nil) then
		return false
	end
	if (self:sceneParentId(pLia) ~= IA_BRIDGE_CANTINA_CELL) then
		return false
	end
	local scene = SceneObject(pLia)
	if (scene == nil) then
		return false
	end
	local dist = self:dist2d(
		scene:getPositionX(),
		scene:getPositionY(),
		IA_BRIDGE_CANTINA_LIA_GUEST_X,
		IA_BRIDGE_CANTINA_LIA_GUEST_Y
	)
	return dist < IA_BRIDGE_CANTINA_LIA_NEAR_BAR_M
end

function IaBridgeScreenPlay:liaBehindCantinaBar(pLia)
	if (pLia == nil) then
		return false
	end
	if (self:sceneParentId(pLia) ~= IA_BRIDGE_CANTINA_CELL) then
		return false
	end
	local scene = SceneObject(pLia)
	if (scene == nil) then
		return false
	end
	-- Cote serveur / derriere le comptoir (barman y ~ 1.15, staff y ~ 2.8)
	return scene:getPositionY() > 0.75
end

function IaBridgeScreenPlay:teleportLiaToCantinaGuestPost(pLia)
	if (pLia == nil) then
		return
	end
	pcall(function()
		CreatureObject(pLia):teleport(
			IA_BRIDGE_CANTINA_LIA_GUEST_X,
			IA_BRIDGE_CANTINA_LIA_GUEST_Z,
			IA_BRIDGE_CANTINA_LIA_GUEST_Y,
			IA_BRIDGE_CANTINA_CELL
		)
	end)
	pcall(function()
		CreatureObject(pLia):setDirection(IA_BRIDGE_CANTINA_LIA_GUEST_HEADING)
	end)
end

function IaBridgeScreenPlay:handleHousingEnter(pPlayer, payload)
	if (pPlayer == nil) then
		return
	end
	local cell, x, z, y
	if (payload == "training" or payload == "trainer" or payload == "artisan") then
		-- Centre entrainement Mos Eisley (cell 1189639) — garde le roster artisan charge.
		cell = IA_BRIDGE_TRAINING_CELL
		x = -14.276340484619
		z = 1.133056640625
		y = -8.6046371459961
	elseif (payload == "cantina" or payload == nil or payload == "") then
		cell, x, z, y = self:resolveCantinaEnterCoords(pPlayer)
	else
		cell, x, z, y = self:resolveCantinaEnterCoords(pPlayer)
	end
	CreatureObject(pPlayer):teleport(x, z, y, cell)
	if (self:eventActorName(pPlayer) == IA_BRIDGE_BOT and cell == IA_BRIDGE_CANTINA_CELL) then
		pcall(function()
			CreatureObject(pPlayer):setDirection(IA_BRIDGE_CANTINA_LIA_GUEST_HEADING)
		end)
	end
	local name = self:eventActorName(pPlayer)
	local tag = payload or "cantina_test"
	if (payload == "training" or payload == "trainer" or payload == "artisan") then
		setQuestStatus("ia_bridge:housing:" .. name, "training_center")
		CreatureObject(pPlayer):sendSystemMessage("[Housing] Entree centre entrainement Mos Eisley.")
	else
		setQuestStatus("ia_bridge:housing:" .. name, "cantina_test")
		CreatureObject(pPlayer):sendSystemMessage("[Housing] Entree lot test (cantina Mos Eisley).")
	end
	-- Mode client : arreter la marche outdoor sinon DataTransform ecrase le teleport serveur.
	if (self:isAiBridgePlayer(pPlayer)) then
		self:cancelPlayerWalk(pPlayer)
		self:appendBotMove("stop|" .. name)
		self:appendBotMove(string.format("sync_pos|%s|%.2f|%.2f|%.2f", name, x, y, z))
	end
	self:appendSocialEvent("core3.housing_enter", name, "", payload or "", x, y, z, "")
	createEvent(1200, "IaBridgeScreenPlay", "maintainInteriorRosterPosts", nil, "")
end

function IaBridgeScreenPlay:tickPassiveNpcSimulation()
	if (IA_BRIDGE_NPC_SIM == nil or IA_BRIDGE_NPC_SIM.passive_rules == nil) then
		return
	end
	local rules = IA_BRIDGE_NPC_SIM.passive_rules
	local pop = (IA_BRIDGE_NPC_SIM.levels and IA_BRIDGE_NPC_SIM.levels.passive and IA_BRIDGE_NPC_SIM.levels.passive.population_virtual) or 200
	local births = math.floor(pop * (rules.birth_rate_per_tick or 0))
	local deaths = math.floor(pop * (rules.death_rate_per_tick or 0))
	local ts = os.time()
	local body = string.format(
		'{"ts":%d,"virtual_pop":%d,"births":%d,"deaths":%d,"zone":"%s"}',
		ts,
		pop,
		births,
		deaths,
		self:jsonEscape(IA_BRIDGE_ZONE)
	)
	local f = io.open(IA_BRIDGE_PASSIVE_STATE_FILE, "w")
	if (f ~= nil) then
		f:write(body)
		f:close()
	end
	if (iaPublishWorldEvent ~= nil) then
		pcall(function()
			iaPublishWorldEvent("npc.passive_tick", body)
		end)
	end
end

function IaBridgeScreenPlay:tickPlanetMoonEffects()
	if (IA_BRIDGE_PLANET_RULES == nil or IA_BRIDGE_PLANET_RULES.planets == nil) then
		return
	end
	for _, planet in ipairs(IA_BRIDGE_PLANET_RULES.planets) do
		if (planet.zone == IA_BRIDGE_ZONE and planet.moons ~= nil and #planet.moons > 0) then
			local moon = planet.moons[1]
			local cycle = tonumber(moon.cycle_hours_real) or 12
			local phase = os.time() % (cycle * 3600)
			if (phase < 300) then
				-- annonce courte au boot de phase lunaire (~5 min)
				local pLia = self:resolvePlayer(IA_BRIDGE_BOT)
				if (pLia ~= nil and self:isPlayerConnected(pLia)) then
					pcall(function()
						CreatureObject(pLia):sendSystemMessage("[Monde] Effet lunaire actif : " .. tostring(moon.id))
					end)
				end
			end
			break
		end
	end
end

function IaBridgeScreenPlay:turninQuest(pPlayer, questId)
	if (pPlayer == nil or questId == nil or questId == "") then
		return
	end
	local name = self:eventActorName(pPlayer)
	self:appendQuestState("turnin", name, questId, "")
	local rewardTpl = nil
	local template = nil
	for _, t in ipairs(self:questTemplates()) do
		if (t.id == questId) then
			rewardTpl = t.reward_item
			template = t
			break
		end
	end
	if (template ~= nil and template.faction_rep ~= nil) then
		for fid, delta in pairs(template.faction_rep) do
			local factionId = "faction:" .. tostring(fid)
			self:addFactionRep(name, factionId, tonumber(delta) or 0)
		end
	end
	if (rewardTpl ~= nil) then
		pcall(function()
			local pInv = CreatureObject(pPlayer):getSlottedObject("inventory")
			if (pInv ~= nil) then
				local pItem = giveItem(pInv, rewardTpl, -1, true)
				if (pItem ~= nil) then
					CreatureObject(pPlayer):sendSystemMessage("[Quete] Recompense ajoutee a l inventaire.")
				end
			end
		end)
	end
	pcall(function()
		CreatureObject(pPlayer):sendSystemMessage("[Quete] Terminee: " .. questId)
	end)
	self:appendSocialEvent("core3.quest_turnin", name, "", questId, 0, 0, 0, questId)
end

function IaBridgeScreenPlay:getMovementMode()
	local now = os.time()
	if (self._movementModeCache ~= nil and self._movementModeCacheTs ~= nil and (now - self._movementModeCacheTs) < 30) then
		return self._movementModeCache
	end
	local mode = IA_BRIDGE_MOVEMENT_MODE_DEFAULT
	local f = io.open(IA_BRIDGE_MOVEMENT_MODE_FILE, "r")
	if (f ~= nil) then
		local line = f:read("*l")
		f:close()
		if (line ~= nil) then
			line = string.lower(string.gsub(line, "%s+", ""))
			if (line == "walk" or line == "teleport" or line == "client") then
				mode = line
			end
		end
	end
	self._movementModeCache = mode
	self._movementModeCacheTs = now
	return mode
end

function IaBridgeScreenPlay:appendBotMove(line)
	if (line == nil or line == "") then
		return
	end
	local f = io.open(IA_BRIDGE_BOT_MOVE_FILE, "a")
	if (f ~= nil) then
		f:write(line .. "\n")
		f:close()
	end
end

function IaBridgeScreenPlay:queueClientMove(pPlayer, tx, ty, tz, stopM)
	if (pPlayer == nil) then
		return false
	end
	local name = self:eventActorName(pPlayer)
	local z = tz
	if (z == nil) then
		z = 0
	end
	local radius = stopM or 2
	self:appendBotMove(string.format("move_to|%s|%.2f|%.2f|%.2f|%.2f", name, tx, ty, z, radius))
	printf("IaBridge: client move %s -> %.1f %.1f (r=%.1f)\n", name, tx, ty, radius)
	return true
end

function IaBridgeScreenPlay:playerWalkKey(oid, suffix)
	return "ia_bridge_pwalk_" .. suffix .. ":" .. tostring(oid)
end

function IaBridgeScreenPlay:cancelPlayerWalk(pPlayer)
	if (pPlayer == nil) then
		return
	end
	local oid = SceneObject(pPlayer):getObjectID()
	deleteStringData(self:playerWalkKey(oid, "dst"))
	deleteData(self:playerWalkKey(oid, "active"))
end

function IaBridgeScreenPlay:isPlayerWalkActive(pPlayer)
	if (pPlayer == nil) then
		return false
	end
	local oid = SceneObject(pPlayer):getObjectID()
	local active = readData(self:playerWalkKey(oid, "active"))
	return active ~= nil and active == 1
end

function IaBridgeScreenPlay:sceneParentId(pObj)
	if (pObj == nil) then
		return 0
	end
	local parentId = 0
	pcall(function()
		parentId = SceneObject(pObj):getParentID() or 0
	end)
	return parentId
end

function IaBridgeScreenPlay:moveAiPlayerToward(pPlayer, tx, ty, tz, withinM)
	if (pPlayer == nil) then
		return false
	end
	withinM = withinM or IA_BRIDGE_APPROACH_RANGE_M
	local scene = SceneObject(pPlayer)
	local sx, sy = scene:getPositionX(), scene:getPositionY()
	local dist = self:dist2d(sx, sy, tx, ty)
	if (dist <= withinM) then
		self:cancelPlayerWalk(pPlayer)
		return true
	end
	if (self:isAiBridgePlayer(pPlayer) and self:getMovementMode() == "client") then
		return self:queueClientMove(pPlayer, tx, ty, tz, withinM)
	end
	if (not self:isAiBridgePlayer(pPlayer) or self:getMovementMode() ~= "walk") then
		local curZ = scene:getPositionZ()
		local useZ = tz
		if (useZ == nil or useZ == 0) then
			useZ = curZ
		end
		scene:teleport(tx, useZ, ty, scene:getParentID() or 0)
		return true
	end
	local step = dist - withinM
	local nx = sx + (tx - sx) * (step / dist)
	local ny = sy + (ty - sy) * (step / dist)
	self:cancelPlayerWalk(pPlayer)
	local oid = scene:getObjectID()
	writeData(self:playerWalkKey(oid, "active"), 1)
	local stopM = withinM
	if (stopM > 2.5) then
		stopM = 2
	end
	writeStringData(
		self:playerWalkKey(oid, "dst"),
		string.format("%.3f,%.3f,%.3f,%.3f", nx, ny, tz or scene:getPositionZ(), stopM)
	)
	self:playerWalkStep(pPlayer)
	return true
end

function IaBridgeScreenPlay:playerWalkStep(pPlayer)
	if (pPlayer == nil) then
		return
	end
	local oid = SceneObject(pPlayer):getObjectID()
	local active = readData(self:playerWalkKey(oid, "active"))
	if (active == nil or active ~= 1) then
		return
	end
	local packed = readStringData(self:playerWalkKey(oid, "dst"))
	if (packed == nil or packed == "") then
		self:cancelPlayerWalk(pPlayer)
		return
	end
	local tx, ty, tz, withinM = string.match(packed, "^([^,]+),([^,]+),([^,]+),([^,]+)$")
	tx = tonumber(tx)
	ty = tonumber(ty)
	tz = tonumber(tz)
	withinM = tonumber(withinM) or IA_BRIDGE_APPROACH_RANGE_M
	if (tx == nil or ty == nil) then
		self:cancelPlayerWalk(pPlayer)
		return
	end
	local scene = SceneObject(pPlayer)
	local sx, sy = scene:getPositionX(), scene:getPositionY()
	local dist = self:dist2d(sx, sy, tx, ty)
	if (dist <= withinM) then
		self:cancelPlayerWalk(pPlayer)
		return
	end
	local step = math.min(IA_BRIDGE_WALK_STEP_M, dist - withinM)
	if (step < 0.2) then
		self:cancelPlayerWalk(pPlayer)
		return
	end
	local nx = sx + (tx - sx) * (step / dist)
	local ny = sy + (ty - sy) * (step / dist)
	local useZ = scene:getPositionZ()
	if (tz ~= nil and tz ~= 0) then
		useZ = tz
	end
	scene:teleport(nx, useZ, ny, scene:getParentID() or 0)
	createEvent(IA_BRIDGE_WALK_STEP_MS, "IaBridgeScreenPlay", "playerWalkStep", pPlayer, "")
end

function IaBridgeScreenPlay:approachCoords(pPlayer, x, y, z)
	if (pPlayer == nil) then
		return
	end
	local scene = SceneObject(pPlayer)
	local cell = scene:getParentID() or 0
	if (self:isAiBridgePlayer(pPlayer) and self:getMovementMode() == "client") then
		self:queueClientMove(pPlayer, x, y, z, 3)
		return
	end
	if (cell ~= 0 and self:isAiBridgePlayer(pPlayer) and self:getMovementMode() == "walk") then
		-- move_to interieur : pas de teleport longue distance
		self:moveAiPlayerToward(pPlayer, x, y, z, 2)
		return
	end
	local curZ = scene:getPositionZ()
	local tz = z
	if (tz == nil or tz == 0) then
		tz = curZ
	end
	if (self:isAiBridgePlayer(pPlayer) and self:getMovementMode() == "walk") then
		self:moveAiPlayerToward(pPlayer, x, y, tz, 3)
		return
	end
	scene:teleport(x, tz, y, cell)
end

function IaBridgeScreenPlay:approachPlayer(pPlayer, targetFirstname, withinM)
	if (pPlayer == nil or targetFirstname == nil or targetFirstname == "") then
		return false
	end
	local pTarget = getPlayerByName(targetFirstname)
	if (pTarget == nil) then
		return false
	end
	local scene = SceneObject(pPlayer)
	local ts = SceneObject(pTarget)
	local myCell = self:sceneParentId(pPlayer)
	local targetCell = self:sceneParentId(pTarget)
	if (myCell ~= targetCell) then
		if (self:isAiBridgePlayer(pPlayer)) then
			printf(
				"IaBridge: %s ne peut pas rejoindre %s (cellules differentes %s vs %s) — housing_enter cantina si besoin\n",
				self:eventActorName(pPlayer),
				targetFirstname,
				tostring(myCell),
				tostring(targetCell)
			)
			return false
		end
	end
	local sx, sy = scene:getPositionX(), scene:getPositionY()
	local tx, ty = ts:getPositionX(), ts:getPositionY()
	local dist = self:dist2d(sx, sy, tx, ty)
	withinM = withinM or IA_BRIDGE_APPROACH_RANGE_M
	if (dist <= withinM) then
		self:cancelPlayerWalk(pPlayer)
		return true
	end
	local step = dist - withinM
	local nx = sx + (tx - sx) * (step / dist)
	local ny = sy + (ty - sy) * (step / dist)
	if (self:isAiBridgePlayer(pPlayer) and self:getMovementMode() == "client") then
		self:queueClientMove(pPlayer, nx, ny, scene:getPositionZ(), 2)
		printf(
			"IaBridge: %s client vers %s (%.1fm, pas ~%.1fm)\n",
			self:eventActorName(pPlayer),
			targetFirstname,
			dist,
			withinM
		)
		return true
	end
	if (self:isAiBridgePlayer(pPlayer) and self:getMovementMode() == "walk") then
		self:moveAiPlayerToward(pPlayer, nx, ny, scene:getPositionZ(), 2)
		printf(
			"IaBridge: %s marche vers %s (%.1fm, pas ~%.1fm)\n",
			self:eventActorName(pPlayer),
			targetFirstname,
			dist,
			withinM
		)
		return true
	end
	scene:teleport(nx, scene:getPositionZ(), ny, scene:getParentID() or 0)
	printf("IaBridge: %s approche %s (%.1fm -> ~%.1fm)\n", self:eventActorName(pPlayer), targetFirstname, dist, withinM)
	return true
end

function IaBridgeScreenPlay:relaySayToNearby(pSpeaker, message)
	if (message == nil or message == "") then
		return
	end
	local sx, sy = SceneObject(pSpeaker):getPositionX(), SceneObject(pSpeaker):getPositionY()
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		local name = IA_BRIDGE_CHAT_RELAY[i]
		local pOther = getPlayerByName(name)
		if (pOther ~= nil and pOther ~= pSpeaker) then
			local tx, ty = SceneObject(pOther):getPositionX(), SceneObject(pOther):getPositionY()
			if (self:dist2d(sx, sy, tx, ty) <= IA_BRIDGE_CHAT_RANGE_M) then
				CreatureObject(pOther):sendSystemMessage("[Lia] " .. message)
			end
		end
	end
end

function IaBridgeScreenPlay:performPlayAnim(pPlayer, animName)
	if (pPlayer == nil or animName == nil or animName == "") then
		return
	end
	pcall(function()
		CreatureObject(pPlayer):doAnimation(animName)
	end)
end

-- Essaye de déclencher une commande type /startdance, /flourish via action controller.
-- Retourne true si l'appel n'a pas levé d'erreur (pas forcément "succès gameplay").
function IaBridgeScreenPlay:tryObjectControllerAction(pPlayer, cmdName, args)
	if (pPlayer == nil or cmdName == nil or cmdName == "") then
		return false
	end
	local ok = false
	pcall(function()
		local crc = getHashCode(cmdName)
		-- Certains serveurs acceptent args="" ; on force string.
		CreatureObject(pPlayer):executeObjectControllerAction(crc, 0, tostring(args or ""))
		ok = true
	end)
	return ok
end

-- Enqueue une commande serveur (QueueCommand) sans passer par l'ObjectController client.
function IaBridgeScreenPlay:tryEnqueueCommand(pPlayer, cmdName, args)
	if (pPlayer == nil or cmdName == nil or cmdName == "") then
		return false
	end
	local ok = false
	pcall(function()
		local crc = getHashCode(cmdName)
		CreatureObject(pPlayer):enqueueCommand(crc, 0, 0, tostring(args or ""))
		ok = true
	end)
	return ok
end

function IaBridgeScreenPlay:tryStartDanceBasic(pPlayer)
	return self:tryStartDanceSmart(pPlayer)
end

function IaBridgeScreenPlay:checkDanceStartedEvent(pPlayer, arg)
	if (pPlayer == nil) then
		return
	end
	local danceName = "basic"
	local attempt = 0
	if (arg ~= nil and arg ~= "") then
		local n, a = string.match(tostring(arg), "^([^|]*)|(%d+)$")
		if (n ~= nil) then
			danceName = n
			attempt = tonumber(a) or 0
		else
			danceName = tostring(arg)
		end
	end
	local dancing = false
	pcall(function()
		dancing = CreatureObject(pPlayer):isDancing()
	end)
	if (dancing) then
		printf("IaBridge: startdance ok (%s) attempt=%d\n", danceName, attempt)
		self:onDanceStarted(pPlayer, danceName)
		return
	end
	-- Bots IA : enchaîner /startdance (QueueCommand) puis iaStartDance avant tout doAnimation.
	if (self:isAiBridgePlayer(pPlayer) and attempt < 3) then
		if (attempt == 0) then
			self:tryEnqueueCommand(pPlayer, "startdance", danceName)
		elseif (attempt == 1) then
			self:tryEnqueueCommand(pPlayer, "startdance", "basic")
		elseif (attempt == 2 and type(iaStartDance) == "function") then
			pcall(function()
				iaStartDance(pPlayer, danceName)
			end)
		end
		createEvent(900, "IaBridgeScreenPlay", "checkDanceStartedEvent", pPlayer, danceName .. "|" .. tostring(attempt + 1))
		return
	end
	printf("IaBridge: startdance FAIL (%s) attempt=%d -> fallback doAnimation\n", danceName, attempt)
	self:performAnimChainStep(pPlayer, "dance", 1)
end

function IaBridgeScreenPlay:onDanceStarted(pPlayer, danceName)
	if (pPlayer == nil) then
		return
	end
	local label = tostring(danceName or "basic")
	pcall(function()
		spatialChat(pPlayer, "*danse " .. label .. "*")
	end)
	if (CreatureObject(pPlayer):isDancing()) then
		self:scheduleDanceFlourishes(pPlayer, 0)
		self:notifyRelayLiaVisible(pPlayer)
	end
end

-- Aide les joueurs déjà connectés à rafraîchir Lia sans /logout (message + spatial).
function IaBridgeScreenPlay:notifyRelayLiaVisible(pLia)
	if (pLia == nil) then
		return
	end
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		local pRelay = getPlayerByName(IA_BRIDGE_CHAT_RELAY[i])
		if (pRelay ~= nil) then
			local relayCell = self:sceneParentId(pRelay)
			local liaCell = self:sceneParentId(pLia)
			if (relayCell ~= 0 and relayCell == liaCell) then
				pcall(function()
					CreatureObject(pRelay):sendSystemMessage(
						"[Lia] Je danse en cantina — si je suis invisible, eloignez-vous puis revenez."
					)
				end)
				pcall(function()
					spatialChat(pLia, "Content de vous retrouver, " .. IA_BRIDGE_CHAT_RELAY[i] .. ".")
				end)
				return
			end
		end
	end
end

function IaBridgeScreenPlay:tryFlourish(pPlayer, flourishId)
	-- /flourish <1..8>
	local n = tonumber(flourishId) or 1
	if (n < 1) then n = 1 end
	if (n > 8) then n = 8 end
	if (not CreatureObject(pPlayer):isDancing()) then
		return false
	end
	-- Priorité : QueueCommand serveur
	if (self:tryEnqueueCommand(pPlayer, "flourish", tostring(n))) then
		return true
	end
	-- Fallback : action controller
	if (self:tryObjectControllerAction(pPlayer, "flourish", tostring(n))) then
		return true
	end
	-- Fallback : un flourish basique visuel.
	self:performPlayAnim(pPlayer, "celebrate")
	return false
end

function IaBridgeScreenPlay:isTightSpace(pPlayer)
	if (pPlayer == nil) then
		return true
	end
	-- Heuristique: intérieur / cellule (cantina, bâtiment) => espace réduit.
	local parent = 0
	pcall(function()
		parent = SceneObject(pPlayer):getParentID() or 0
	end)
	if (parent ~= 0) then
		return true
	end
	-- Heuristique: si proche d'un joueur relay (foule), privilégier une danse compacte.
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		local pOther = getPlayerByName(IA_BRIDGE_CHAT_RELAY[i])
		if (pOther ~= nil) then
			local sx, sy = SceneObject(pPlayer):getPositionX(), SceneObject(pPlayer):getPositionY()
			local tx, ty = SceneObject(pOther):getPositionX(), SceneObject(pOther):getPositionY()
			if (self:dist2d(sx, sy, tx, ty) <= 10) then
				return true
			end
		end
	end
	return false
end

function IaBridgeScreenPlay:canStartDance(pPlayer, danceName)
	if (pPlayer == nil or danceName == nil or danceName == "") then
		return false
	end
	local pGhost = CreatureObject(pPlayer):getPlayerObject()
	if (pGhost == nil) then
		-- Bots headless: parfois pas de ghost exploitable, on tente quand même.
		return true
	end
	local ok = false
	pcall(function()
		ok = PlayerObject(pGhost):hasAbility("startDance+" .. tostring(danceName))
	end)
	return ok
end

function IaBridgeScreenPlay:parseDanceStyleHint(text)
	local raw = string.lower(self:trim(text or ""))
	if (raw == "" or raw == "dance" or raw == "dance_floor") then
		return nil
	end
	local style = string.match(raw, "^dance:?%s*(.+)$")
	if (style == nil or style == "") then
		return nil
	end
	style = string.gsub(style, "^%s*(.-)%s*$", "%1")
	local aliases = {
		["classique"] = "formal",
		["classique2"] = "formal2",
		["lente"] = "lyrical",
		["lent"] = "lyrical",
		["pop"] = "popular",
		["exo"] = "exotic",
		["theatre"] = "theatrical",
		["theatral"] = "theatrical",
		["break"] = "breakdance",
	}
	return aliases[style] or style
end

function IaBridgeScreenPlay:awardEntertainerDanceSkills(pPlayer)
	if (awardSkill == nil or pPlayer == nil) then
		return
	end
	pcall(function()
		awardSkill(pPlayer, "social_entertainer_novice")
		awardSkill(pPlayer, "social_entertainer_dance_01")
		awardSkill(pPlayer, "social_entertainer_dance_02")
		awardSkill(pPlayer, "social_entertainer_dance_03")
		awardSkill(pPlayer, "social_entertainer_dance_04")
	end)
end

function IaBridgeScreenPlay:pickDanceName(pPlayer, requestedStyle)
	if (requestedStyle ~= nil and requestedStyle ~= "") then
		if (self:canStartDance(pPlayer, requestedStyle)) then
			return requestedStyle
		end
	end
	local tight = self:isTightSpace(pPlayer)
	local pool = IA_BRIDGE_DANCE_ROTATION
	if (tight) then
		pool = IA_BRIDGE_DANCE_COMPACT
	end
	IA_BRIDGE_LAST_DANCE_IDX = (IA_BRIDGE_LAST_DANCE_IDX or 0) + 1
	local start = (IA_BRIDGE_LAST_DANCE_IDX % #pool) + 1
	for i = 0, #pool - 1 do
		local name = pool[((start + i - 1) % #pool) + 1]
		if (self:canStartDance(pPlayer, name)) then
			return name
		end
	end
	for j = 1, #IA_BRIDGE_DANCE_COMPACT do
		if (self:canStartDance(pPlayer, IA_BRIDGE_DANCE_COMPACT[j])) then
			return IA_BRIDGE_DANCE_COMPACT[j]
		end
	end
	return "basic"
end

function IaBridgeScreenPlay:tryStartDanceSmart(pPlayer, requestedStyle)
	local name = self:pickDanceName(pPlayer, requestedStyle)
	if (name == nil or name == "") then
		name = "basic"
	end
	self:awardEntertainerDanceSkills(pPlayer)
	local issued = false
	-- Priorité : vraie commande serveur /startdance (visible pour les autres joueurs).
	issued = self:tryEnqueueCommand(pPlayer, "startdance", name)
	if (not issued) then
		issued = self:tryObjectControllerAction(pPlayer, "startdance", name)
	end
	if (not issued) then
		issued = self:tryEnqueueCommand(pPlayer, "startdance", "basic")
	end
	if (not issued and type(iaStartDance) == "function") then
		pcall(function()
			iaStartDance(pPlayer, name)
		end)
		issued = true
	end
	createEvent(900, "IaBridgeScreenPlay", "checkDanceStartedEvent", pPlayer, name .. "|0")
	return issued
end

function IaBridgeScreenPlay:scheduleDanceFlourishes(pPlayer, round)
	if (pPlayer == nil) then
		return
	end
	round = tonumber(round) or 0
	if (round >= IA_BRIDGE_DANCE_FLOURISH_MAX_ROUNDS) then
		return
	end
	local flourishId = getRandomNumber(1, 8)
	createEvent(
		IA_BRIDGE_DANCE_FLOURISH_INTERVAL_MS,
		"IaBridgeScreenPlay",
		"danceFlourishEvent",
		pPlayer,
		tostring(flourishId) .. "|" .. tostring(round)
	)
end

function IaBridgeScreenPlay:danceFlourishEvent(pPlayer, arg)
	if (pPlayer == nil) then
		return
	end
	local flourishId, roundStr = string.match(tostring(arg or ""), "^(%d+)|(%d+)$")
	local n = tonumber(flourishId) or 1
	local round = tonumber(roundStr) or 0
	if (not CreatureObject(pPlayer):isDancing()) then
		return
	end
	if (not self:tryFlourish(pPlayer, n) and type(iaFlourish) == "function") then
		pcall(function()
			iaFlourish(pPlayer, n)
		end)
	end
	self:scheduleDanceFlourishes(pPlayer, round + 1)
end

function IaBridgeScreenPlay:performAnimChainStep(pPlayer, performId, step)
	if (pPlayer == nil or self:canRunPlayerGesture(pPlayer) ~= true) then
		return
	end
	local cfg = IA_BRIDGE_LIA_PERFORM[performId]
	if (cfg == nil or cfg.anims == nil) then
		return
	end
	local anims = cfg.anims
	if (step > #anims) then
		return
	end
	self:performPlayAnim(pPlayer, anims[step])
	if (step < #anims) then
		local delay = cfg.delay_ms or 2500
		createEvent(delay, "IaBridgeScreenPlay", "performAnimChainEvent", pPlayer, performId .. "|" .. tostring(step + 1))
	end
end

function IaBridgeScreenPlay:performAnimChainEvent(pPlayer, arg)
	if (pPlayer == nil or arg == nil) then
		return
	end
	local performId, stepStr = string.match(arg, "^([^|]+)|(.+)$")
	if (performId == nil) then
		return
	end
	self:performAnimChainStep(pPlayer, performId, tonumber(stepStr) or 1)
end

function IaBridgeScreenPlay:isForageLootTemplate(tpl)
	if (tpl == nil or tpl == "") then
		return false
	end
	return string.find(tostring(tpl), "food/foraged/", 1, true) ~= nil
end

function IaBridgeScreenPlay:isProtectedInventoryTemplate(tpl)
	if (tpl == nil or tpl == "") then
		return true
	end
	if (self:isForageLootTemplate(tpl)) then
		return false
	end
	local protected = {
		"/weapon/",
		"/wearables/",
		"/armor/",
		"/datapad/",
		"/instrument/",
		"/container/",
		"/ticket/",
		"/credit_chip",
	}
	for i = 1, #protected do
		if (string.find(tpl, protected[i], 1, true) ~= nil) then
			return true
		end
	end
	return false
end

function IaBridgeScreenPlay:getInventoryItemCount(pPlayer)
	local count = 0
	pcall(function()
		local pInv = CreatureObject(pPlayer):getSlottedObject("inventory")
		if (pInv ~= nil) then
			count = SceneObject(pInv):getContainerObjectsSize()
		end
	end)
	return count
end

function IaBridgeScreenPlay:destroyInventoryObject(pItem)
	if (pItem == nil) then
		return false
	end
	local ok = pcall(function()
		SceneObject(pItem):destroyObjectFromWorld(true)
	end)
	return ok
end

-- Vide le surplus (fruits de forage en priorité) pour les bots IA.
function IaBridgeScreenPlay:pruneAiPlayerInventory(pPlayer, opts)
	opts = opts or {}
	if (pPlayer == nil or not self:isAiBridgePlayer(pPlayer)) then
		return 0
	end
	local destroyed = 0
	pcall(function()
		local pInv = CreatureObject(pPlayer):getSlottedObject("inventory")
		if (pInv == nil) then
			return
		end
		local size = SceneObject(pInv):getContainerObjectsSize()
		if (size <= 0) then
			return
		end
		local byTpl = {}
		for i = 0, size - 1, 1 do
			local pItem = SceneObject(pInv):getContainerObject(i)
			if (pItem ~= nil) then
				local tpl = SceneObject(pItem):getTemplateObjectPath() or ""
				if (byTpl[tpl] == nil) then
					byTpl[tpl] = {}
				end
				table.insert(byTpl[tpl], pItem)
			end
		end
		local function destroyFromList(list, maxKeep)
			if (list == nil or #list <= maxKeep) then
				return
			end
			for j = #list, maxKeep + 1, -1 do
				if (self:destroyInventoryObject(list[j])) then
					destroyed = destroyed + 1
				end
			end
		end
		for tpl, list in pairs(byTpl) do
			if (self:isForageLootTemplate(tpl)) then
				destroyFromList(list, IA_BRIDGE_FORAGE_KEEP_EACH)
			end
		end
		local remaining = self:getInventoryItemCount(pPlayer)
		while (remaining > IA_BRIDGE_INV_SOFT_MAX) do
			local removedOne = false
			local curSize = SceneObject(pInv):getContainerObjectsSize()
			if (curSize <= 0) then
				break
			end
			for i = curSize - 1, 0, -1 do
				local pItem = SceneObject(pInv):getContainerObject(i)
				if (pItem ~= nil) then
					local tpl = SceneObject(pItem):getTemplateObjectPath() or ""
					if (not self:isProtectedInventoryTemplate(tpl)) then
						if (self:destroyInventoryObject(pItem)) then
							destroyed = destroyed + 1
							removedOne = true
							break
						end
					end
				end
			end
			if (not removedOne) then
				break
			end
			remaining = self:getInventoryItemCount(pPlayer)
		end
	end)
	if (destroyed > 0 and opts.notify ~= false) then
		pcall(function()
			CreatureObject(pPlayer):sendSystemMessage(
				"[IA] Inventaire allégé (" .. tostring(destroyed) .. " objet(s) retirés)."
			)
		end)
	end
	return destroyed
end

function IaBridgeScreenPlay:inventorySnapshotFields(pPlayer)
	local count = self:getInventoryItemCount(pPlayer)
	local nearFull = count >= IA_BRIDGE_INV_SOFT_MAX
	local full = count >= IA_BRIDGE_INV_HARD_MAX
	return count, nearFull, full
end

function IaBridgeScreenPlay:giveForageLoot(pPlayer)
	if (pPlayer == nil) then
		return false
	end
	if (self:isAiBridgePlayer(pPlayer)) then
		local count, nearFull, full = self:inventorySnapshotFields(pPlayer)
		if (nearFull) then
			self:pruneAiPlayerInventory(pPlayer, { notify = true })
			count = self:getInventoryItemCount(pPlayer)
			full = count >= IA_BRIDGE_INV_HARD_MAX
		end
		if (full) then
			pcall(function()
				CreatureObject(pPlayer):sendSystemMessage("[IA] Inventaire plein — fouille sans nouveau butin.")
			end)
			return false
		end
	end
	local lootTemplates = {
		"object/tangible/food/foraged/foraged_fruit_s1.iff",
		"object/tangible/food/foraged/foraged_fruit_s2.iff",
		"object/tangible/food/foraged/foraged_fruit_s3.iff",
	}
	local tpl = lootTemplates[getRandomNumber(#lootTemplates)]
	local given = false
	pcall(function()
		local pInv = CreatureObject(pPlayer):getSlottedObject("inventory")
		if (pInv == nil) then
			return
		end
		local pItem = giveItem(pInv, tpl, -1, true)
		if (pItem ~= nil) then
			given = true
			CreatureObject(pPlayer):sendSystemMessage("[IA] Butin de fouille ajoute a l inventaire.")
		end
	end)
	return given
end

function IaBridgeScreenPlay:handlePlayerPerform(pPlayer, performId)
	if (pPlayer == nil or performId == nil) then
		return
	end
	local id = string.lower(string.gsub(performId, "^%s*(.-)%s*$", "%1"))
	local cfg = IA_BRIDGE_LIA_PERFORM[id]
	if (cfg == nil) then
		self:performPlayAnim(pPlayer, performId)
		printf("IaBridge: perform inconnu %s -> animate brut\n", tostring(performId))
		return
	end
	-- Feedback visible pour les joueurs proches (les bots headless n'affichent pas toujours les systemMessage).
	local actorName = self:eventActorName(pPlayer)
	if (id == "dance" or id == "dance_floor" or string.find(id, "^dance:", 1) == 1) then
		local style = self:parseDanceStyleHint(id)
		self:tryStartDanceSmart(pPlayer, style)
	elseif (id == "forage") then
		pcall(function()
			spatialChat(pPlayer, "*fouille*")
		end)
	end
	if (cfg.system ~= nil and cfg.system ~= "") then
		pcall(function()
			CreatureObject(pPlayer):sendSystemMessage(cfg.system)
		end)
	end
	-- Animations legacy (fallback uniquement) : la danse est gérée par startdance ci-dessus.
	if (id ~= "dance" and id ~= "dance_floor") then
		if (cfg.anims ~= nil and #cfg.anims > 0) then
			self:performAnimChainStep(pPlayer, id, 1)
		end
	end
	if (id == "forage") then
		if (self:isAiBridgePlayer(pPlayer)) then
			self:pruneAiPlayerInventory(pPlayer, { notify = false })
		end
		local given = self:giveForageLoot(pPlayer)
		if (given) then
			pcall(function()
				spatialChat(pPlayer, "Butin ajoute a mon inventaire.")
			end)
		else
			pcall(function()
				spatialChat(pPlayer, "Sac plein, je range un peu.")
			end)
		end
	end
	printf("IaBridge: perform %s -> %s\n", actorName, id)
end

function IaBridgeScreenPlay:trim(val)
	return string.gsub(tostring(val or ""), "^%s*(.-)%s*$", "%1")
end

function IaBridgeScreenPlay:parseInteraction(message)
	local raw = self:trim(message)
	if (raw == "") then
		return "greet", "", ""
	end
	local kind, target, extra = string.match(raw, "^([^:]+):([^:]+):?(.*)$")
	if (kind == nil) then
		return string.lower(raw), "", ""
	end
	return string.lower(self:trim(kind)), self:trim(target), self:trim(extra)
end

function IaBridgeScreenPlay:sendInteractionNotice(pTarget, text)
	if (pTarget == nil or text == nil or text == "") then
		return
	end
	pcall(function()
		CreatureObject(pTarget):sendSystemMessage("[Lia] " .. text)
	end)
end

function IaBridgeScreenPlay:handlePlayerInteract(pPlayer, message)
	if (pPlayer == nil) then
		return
	end
	local actorName = self:eventActorName(pPlayer)
	local kind, targetName, extra = self:parseInteraction(message)
	if (targetName == nil or targetName == "") then
		return
	end
	local pTarget = getPlayerByName(targetName)
	if (pTarget == nil) then
		self:playerSay(pPlayer, "Je cherche " .. targetName .. ", mais je ne le vois pas encore.")
		printf("IaBridge: interact %s -> %s cible absente\n", tostring(kind), tostring(targetName))
		return
	end

	self:approachPlayer(pPlayer, targetName, IA_BRIDGE_APPROACH_RANGE_M)

	if (kind == "greet") then
		self:handlePlayerPerform(pPlayer, "greet")
		self:playerSay(pPlayer, "Bonjour " .. targetName .. ", Lia est prête à interagir.")
		self:sendInteractionNotice(pTarget, "Lia te salue et ouvre le contact.")
	elseif (kind == "offer_trade" or kind == "trade") then
		self:handlePlayerPerform(pPlayer, "conduct")
		self:playerSay(pPlayer, targetName .. ", je peux ouvrir un échange IA quand le module commerce sera branché.")
		self:sendInteractionNotice(pTarget, "Demande d'échange IA (stub sûr, pas de transfert d'objet).")
	elseif (kind == "invite_group" or kind == "group") then
		self:handlePlayerPerform(pPlayer, "greet")
		self:playerSay(pPlayer, targetName .. ", veux-tu me grouper pour explorer ensemble ?")
		self:sendInteractionNotice(pTarget, "Lia souhaite te rejoindre en groupe (stub).")
	elseif (kind == "request_duel" or kind == "duel") then
		self:handlePlayerPerform(pPlayer, "cheer")
		self:playerSay(pPlayer, targetName .. ", duel d'entraînement demandé — sans engagement automatique.")
		self:sendInteractionNotice(pTarget, "Lia propose un duel roleplay (stub, aucun combat lancé).")
	elseif (kind == "examine" or kind == "inspect") then
		self:handlePlayerPerform(pPlayer, "think")
		self:playerSay(pPlayer, "Scan de " .. targetName .. " terminé : présence confirmée près de Lia.")
		self:sendInteractionNotice(pTarget, "Lia t'examine et synchronise son contexte.")
	elseif (kind == "assist" or kind == "help") then
		self:handlePlayerPerform(pPlayer, "conduct")
		local suffix = ""
		if (extra ~= nil and extra ~= "") then
			suffix = " (" .. extra .. ")"
		end
		self:playerSay(pPlayer, targetName .. ", quelle action veux-tu que je coordonne maintenant ?" .. suffix)
		self:sendInteractionNotice(pTarget, "Lia attend ton objectif.")
	elseif (kind == "quest_accept") then
		self:handlePlayerPerform(pPlayer, "greet")
		if (extra == nil or extra == "") then
			self:playerSay(pPlayer, "Indique l id de quete: quest_accept:quest:...")
		else
			self:acceptQuest(pPlayer, extra)
			self:playerSay(pPlayer, "Note. Quete acceptee: " .. extra)
		end
	elseif (kind == "quest_turnin") then
		self:handlePlayerPerform(pPlayer, "conduct")
		if (extra == nil or extra == "") then
			self:playerSay(pPlayer, "Indique l id de quete: quest_turnin:quest:...")
		else
			self:turninQuest(pPlayer, extra)
			self:playerSay(pPlayer, "Rapport recu. Merci.")
		end
	else
		self:handlePlayerPerform(pPlayer, "think")
		self:playerSay(pPlayer, "Interaction " .. tostring(kind) .. " notée pour " .. targetName .. ".")
		self:sendInteractionNotice(pTarget, "Interaction Lia : " .. tostring(kind))
	end

	local sx, sy, sz = 0, 0, 0
	pcall(function()
		sx = SceneObject(pPlayer):getPositionX()
		sy = SceneObject(pPlayer):getPositionY()
		sz = SceneObject(pPlayer):getPositionZ()
	end)
	self:appendSocialEvent("core3.ai_interact", actorName, targetName, tostring(kind), sx, sy, sz, tostring(message or ""))
	printf("IaBridge: interact %s -> %s (%s)\n", actorName, tostring(kind), tostring(targetName))
end

function IaBridgeScreenPlay:playerSay(pPlayer, message)
	if (message == nil or message == "") then
		return
	end
	local actorName = self:eventActorName(pPlayer)
	local sx, sy, sz = 0, 0, 0
	pcall(function()
		sx = SceneObject(pPlayer):getPositionX()
		sy = SceneObject(pPlayer):getPositionY()
		sz = SceneObject(pPlayer):getPositionZ()
	end)
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		self:approachPlayer(pPlayer, IA_BRIDGE_CHAT_RELAY[i], IA_BRIDGE_APPROACH_RANGE_M)
	end
	local okChat, errChat = pcall(function()
		spatialChat(pPlayer, message)
	end)
	if (not okChat) then
		printf("IaBridge: spatialChat %s : %s\n", IA_BRIDGE_BOT, tostring(errChat))
	end
	self:relaySayToNearby(pPlayer, message)
	self:appendSocialEvent("core3.ai_say", actorName, self:inferAiMessageTarget(actorName, message), message, sx, sy, sz, message)
	printf("IaBridge: say %s : %s\n", actorName, message)
end

function IaBridgeScreenPlay:scrambleForLanguage(message, langId)
	if (IA_BRIDGE_FACTIONS == nil or IA_BRIDGE_FACTIONS.languages == nil) then
		return message
	end
	for _, lang in ipairs(IA_BRIDGE_FACTIONS.languages) do
		if (lang.id == langId and lang.scramble == true) then
			local prefix = lang.scramble_prefix or "[?] "
			return prefix .. string.gsub(message or "", "%a", "?")
		end
	end
	return message
end

function IaBridgeScreenPlay:handleNpcPerform(pilotId, performId)
	if (performId == nil or performId == "") then
		return
	end
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob == nil) then
		printf("IaBridge: npc_perform pilote inconnu : %s\n", tostring(pilotId))
		return
	end
	local id = string.lower(string.gsub(performId, "^%s*(.-)%s*$", "%1"))
	if (id == "greet") then
		id = "wave"
	end
	local anims = IA_BRIDGE_LIA_PERFORM[id]
	if (anims ~= nil and anims.anims ~= nil and #anims.anims > 0) then
		id = anims.anims[getRandomNumber(#anims.anims)]
	end
	if (id == "dance" or id == "dance_floor") then
		id = "social_dance_medium"
	end
	pcall(function()
		CreatureObject(pMob):doAnimation(id)
	end)
	if (id == "wipe_brow" or id == "wave") then
		-- geste silencieux au comptoir
	elseif (id == "dance" or id == "dance_floor") then
		pcall(function()
			spatialChat(pMob, "*hum une melodie*")
		end)
	end
	printf("IaBridge: npc_perform %s -> %s\n", tostring(pilotId), tostring(id))
end

function IaBridgeScreenPlay:handleNpcPath(pilotId, x, y, z, message)
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob == nil) then
		return
	end
	local msg = string.lower(string.gsub(message or "", "^%s*(.-)%s*$", "%1"))
	if (msg == "home" or msg == "post") then
		self:resetPilotToHome(pilotId)
		return
	end
	local cfg = IA_BRIDGE_PILOTS[pilotId]
	local cell = 0
	if (cfg ~= nil) then
		cell = self:getPilotHomeCell(cfg)
	end
	if (x ~= 0 or y ~= 0) then
		local tz = z
		if (tz == 0 and cfg ~= nil) then
			tz = cfg.z
		end
		CreatureObject(pMob):teleport(x, tz, y, cell)
		printf("IaBridge: npc_path %s -> %.1f %.1f cell %s\n", pilotId, x, y, tostring(cell))
	end
end

function IaBridgeScreenPlay:handleVendorSell(pPlayer, pilotId, itemIndex)
	if (pPlayer == nil) then
		return
	end
	local shop = self:findShopByPilot(pilotId)
	if (shop == nil) then
		CreatureObject(pPlayer):sendSystemMessage("[Commerce] Marchand inconnu pour revente.")
		return
	end
	local buyback = shop.buyback_templates_v2
	if (buyback == nil or #buyback == 0) then
		buyback = {}
		for _, it in ipairs(shop.items or {}) do
			if (it.template ~= nil) then
				table.insert(buyback, it.template)
			end
		end
	end
	local idx = (tonumber(itemIndex) or 0) + 1
	local wantTpl = buyback[idx]
	if (wantTpl == nil) then
		wantTpl = buyback[1]
	end
	if (wantTpl == nil) then
		CreatureObject(pPlayer):sendSystemMessage("[Commerce] Rachat indisponible ici.")
		return
	end
	local pInv = CreatureObject(pPlayer):getSlottedObject("inventory")
	if (pInv == nil) then
		return
	end
	local sold = false
	pcall(function()
		local contents = SceneObject(pInv):getContainerObjects()
		if (contents == nil) then
			return
		end
		for i = 0, contents:size() - 1 do
			local obj = contents:get(i)
			if (obj ~= nil and SceneObject(obj):getTemplateObjectPath() == wantTpl) then
				SceneObject(obj):destroyObjectFromWorld(true)
				sold = true
				break
			end
		end
	end)
	if (sold) then
		local price = 10
		CreatureObject(pPlayer):sendSystemMessage("[Commerce] Vente OK — " .. tostring(shop.display_name or pilotId) .. " +" .. price .. " cr")
		self:appendSocialEvent("core3.economy_sell", self:eventActorName(pPlayer), pilotId, wantTpl, 0, 0, 0, tostring(price))
	else
		CreatureObject(pPlayer):sendSystemMessage("[Commerce] Objet introuvable pour rachat.")
	end
end

function IaBridgeScreenPlay:handleNpcSay(pilotId, message)
	if (message == nil or message == "") then
		return
	end
	local pMob = self:resolvePilotMob(pilotId)
	if (pMob == nil) then
		printf("IaBridge: pilote inconnu ou non spawn : %s\n", tostring(pilotId))
		return
	end
	IaBridgeScreenPlay.npcSayLast = IaBridgeScreenPlay.npcSayLast or {}
	local now = os.time()
	local last = IaBridgeScreenPlay.npcSayLast[pilotId] or 0
	if ((now - last) < IA_BRIDGE_NPC_SAY_COOLDOWN_SEC) then
		return
	end
	IaBridgeScreenPlay.npcSayLast[pilotId] = now
	local out = message
	if (pilotId == "npc:core3_scribe") then
		out = self:scrambleForLanguage(message, "lang:arcane")
	end
	if (string.len(out) > IA_BRIDGE_NPC_SAY_MAX_LEN) then
		out = string.sub(out, 1, IA_BRIDGE_NPC_SAY_MAX_LEN)
	end
	spatialChat(pMob, out)
end

-- C.5 stub : spatial chat + trace quete (pas de journal SWG vanilla encore)
function IaBridgeScreenPlay:handleNpcOfferQuest(pilotId, message)
	local pMob = self:resolvePilotMob(pilotId)
	local actor = tostring(pilotId or "")
	local target = ""
	local questId = ""
	local raw = self:trim(message)
	-- Formats supportés:
	--   "Teome|quest:mos_delivery_water"
	--   "Teome" (quest aléatoire)
	--   "" (quest aléatoire vers Teome)
	if (raw ~= "") then
		local a, b = string.match(raw, "^([^|]+)|?(.*)$")
		if (a ~= nil and a ~= "") then
			target = self:trim(a)
		end
		if (b ~= nil and b ~= "") then
			questId = self:trim(b)
		end
	end
	self:offerQuestToPlayer(pMob, actor, target, questId)
	printf("IaBridge: offer_quest v1 %s -> %s (%s)\n", tostring(actor), tostring(target), tostring(questId))
end

-- Si un relay (ex. Teome) est en cantina/interieur et Lia dehors → entree cantina (teleport explicite).
function IaBridgeScreenPlay:readLiaPresenceMode()
	local f = io.open(IA_BRIDGE_LIA_PRESENCE_FILE, "r")
	if (f == nil) then
		return ""
	end
	local raw = f:read("*a")
	f:close()
	if (raw == nil or raw == "") then
		return ""
	end
	local mode = string.match(raw, '"mode"%s*:%s*"([^"]+)"')
	return mode or ""
end

-- Lia pilotee par le client SWG humain (fichier ia_bridge/lia_presence.json mode=manual).
function IaBridgeScreenPlay:isLiaManualSession()
	return self:readLiaPresenceMode() == "manual"
end

-- Postes interieurs : spawn permanent chaque tick (independant des joueurs IA).
-- Si interieur indisponible (cellule videe), fallback exterieur pour barman/artisan.
function IaBridgeScreenPlay:ensureExactlyOneRosterOnDuty(rosterId, opts)
	if (IA_BRIDGE_ROSTER_POLICIES == nil) then
		return
	end
	opts = opts or {}
	local forceOutdoor = opts.force_outdoor_post == true
	local logLabel = tostring(opts.log_label or rosterId)
	local winner = opts.winner_pilot_id or self:getRosterWinnerPilot(rosterId)
	if (winner == nil) then
		return
	end
	self:despawnRosterExcept(rosterId, winner)
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.roster == rosterId and not self:pilotAllowedByRosterPolicy(pilotId, cfg)) then
			if (self:resolvePilotMob(pilotId) ~= nil) then
				self:despawnPilot(pilotId)
			end
			IaBridgeScreenPlay.rosterPresence[pilotId] = "off"
		end
	end
	local cfg = self:getPilotCfg(winner)
	if (cfg == nil) then
		return
	end
	local want = self:getRosterDesiredPresence(winner, cfg)
	if (opts.force_post == true) then
		want = "post"
	end
	if (opts.force_outdoor_post ~= true and opts.winner_pilot_id ~= nil) then
		self:setPilotOutdoorPost(winner, false)
	end
	if (want == "off" or want == nil) then
		if (self:resolvePilotMob(winner) ~= nil) then
			self:despawnPilot(winner)
		end
		IaBridgeScreenPlay.rosterPresence[winner] = "off"
		return
	end
	self:purgeStalePilotRef(winner)
	local pMob = self:resolvePilotMob(winner)
	if (pMob ~= nil and self:isMobAlive(pMob) and not self:isPilotOnOutdoorPost(winner)
			and self:pilotMobInServiceCell(pMob, cfg)) then
		self:setPilotOutdoorPost(winner, false)
		self:syncRosterServiceForPresence(cfg, pMob, want)
		IaBridgeScreenPlay.rosterPresence[winner] = want
		return
	end
	pMob = self:resolvePilotMob(winner)
	if (pMob ~= nil and self:isMobAlive(pMob)) then
		if (self:isPilotOnOutdoorPost(winner)) then
			self:despawnPilot(winner)
			pMob = nil
		elseif (self:sceneParentId(pMob) == 0 and tonumber(cfg.spawn_cell or 0) ~= 0 and self:isInteriorCellLoadable(cfg.spawn_cell)) then
			local postCell = tonumber(cfg.spawn_cell) or 0
			local px, pz, py = self:resolvePostCoords(cfg)
			pcall(function()
				CreatureObject(pMob):teleport(px, pz, py, postCell)
			end)
			self:setPilotOutdoorPost(winner, false)
			if (self:pilotMobInServiceCell(pMob, cfg)) then
				self:syncRosterServiceForPresence(cfg, pMob, want)
				IaBridgeScreenPlay.rosterPresence[winner] = want
				return
			end
		elseif (self:sceneParentId(pMob) == 0 and not self:pilotMobNearPost(pMob, cfg, 4.0)) then
			self:despawnPilot(winner)
			pMob = nil
		else
			local postCell = tonumber(cfg.spawn_cell) or 0
			local px, pz, py = self:resolvePostCoords(cfg)
			pcall(function()
				CreatureObject(pMob):teleport(px, pz, py, postCell)
			end)
			self:setPilotOutdoorPost(winner, false)
			self:syncRosterServiceForPresence(cfg, pMob, want)
			IaBridgeScreenPlay.rosterPresence[winner] = want
			return
		end
	end
	if (pMob ~= nil) then
		self:despawnPilot(winner)
	end
	if (forceOutdoor) then
		self:setPilotOutdoorPost(winner, true)
	end
	if (opts.force_post == true and opts.force_outdoor_post ~= true and self:isCantinaBarmanPilot(cfg)) then
		local postCell = tonumber(cfg.spawn_cell) or 0
		if (postCell ~= 0 and self:isInteriorCellLoadable(postCell)) then
			pMob = self:resolvePilotMob(winner)
			if (pMob ~= nil and self:isMobAlive(pMob) and self:pilotMobNearPost(pMob, cfg, 4.0)) then
				self:setPilotOutdoorPost(winner, false)
				self:registerPilotMob(winner, pMob)
				self:syncRosterServiceForPresence(cfg, pMob, want)
				IaBridgeScreenPlay.rosterPresence[winner] = want
				return
			end
			self:setPilotOutdoorPost(winner, false)
			pMob = self:spawnPilotInBuilding(winner, cfg, postCell)
			if (pMob == nil) then
				local px, pz, py = self:resolvePostCoords(cfg)
				pMob = self:spawnPilotAt(winner, cfg, px, pz, py, postCell)
			end
			if (pMob ~= nil) then
				self:clearPilotBehaviors(pMob)
				pcall(function()
					AiAgent(pMob):addObjectFlag(AI_STATIC)
				end)
				self:syncRosterServiceForPresence(cfg, pMob, want)
				ia_catalog_boot_log("ensure on duty " .. logLabel .. " " .. winner .. " want=" .. want .. " (interior)")
				IaBridgeScreenPlay.rosterPresence[winner] = want
				return
			end
		end
	end
	pMob = self:spawnRosterPilotAt(winner, cfg, want)
	if (pMob ~= nil) then
		ia_catalog_boot_log("ensure on duty " .. logLabel .. " " .. winner .. " want=" .. want)
		IaBridgeScreenPlay.rosterPresence[winner] = want
	else
		ia_catalog_boot_log("ensure FAILED " .. logLabel .. " " .. winner .. " want=" .. want)
	end
end

function IaBridgeScreenPlay:purgeCantinaBarmanBootOnce()
	if (_G.IA_BRIDGE_CANTINA_BARMAN_BOOT_PURGED == true) then
		return
	end
	_G.IA_BRIDGE_CANTINA_BARMAN_BOOT_PURGED = true
	self:persistStore().cantinaBarmanSpawnDone = false
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.roster == "roster:mos_eisley_cantina_barman") then
			self:destroyExtraPilotMobs(pilotId, nil)
			if (self:resolvePilotMob(pilotId) ~= nil) then
				self:despawnPilot(pilotId)
			end
			IaBridgeScreenPlay.rosterPresence[pilotId] = "off"
		end
	end
	ia_catalog_boot_log("purge boot cantina barman (refs reset)")
end

function IaBridgeScreenPlay:reattachPilotMobFromHistory(pilotId)
	local hist = self:pilotOidHistory()[pilotId]
	if (hist == nil) then
		return nil
	end
	for _, oid in ipairs(hist) do
		local pMob = getSceneObject(oid)
		if (pMob ~= nil and self:isMobAlive(pMob)) then
			self:registerPilotMob(pilotId, pMob)
			return pMob
		end
	end
	return nil
end

-- Detruit les clones orphelins (meme cellule) : refs perdues mais mob encore IG.
function IaBridgeScreenPlay:purgeCantinaOrphanClones(keepOid)
	local cell = tonumber(IA_BRIDGE_CANTINA_CELL) or 1082877
	if (not self:isInteriorCellLoadable(cell)) then
		return
	end
	local pCell = getSceneObject(cell)
	if (pCell == nil) then
		return
	end
	local keepNum = tonumber(keepOid) or keepOid
	local canonical = keepNum
	pcall(function()
		local contents = SceneObject(pCell):getContainerObjects()
		if (contents == nil) then
			return
		end
		for i = 0, contents:size() - 1 do
			local obj = contents:get(i)
			if (obj == nil) then
				-- rien
			elseif (not SceneObject(obj):isCreatureObject()) then
				-- rien
			elseif (SceneObject(obj):isPlayerCreature()) then
				-- rien
			else
				local oidNum = tonumber(SceneObject(obj):getObjectID()) or SceneObject(obj):getObjectID()
				local pid = readStringData("ia_bridge_pilot_id:" .. tostring(oidNum)) or ""
				local name = SceneObject(obj):getCustomObjectName() or ""
				local isClone = (string.find(pid, "core3_barman", 1, true) ~= nil)
					or (string.find(name, "Jax Moro", 1, true) ~= nil)
				if (isClone) then
					if (canonical ~= nil and oidNum == canonical) then
						-- garder
					elseif (canonical == nil and pid == "npc:core3_barman_jax") then
						canonical = oidNum
					else
						self:clearPilotMobMarks(obj)
						SceneObject(obj):destroyObjectFromWorld(true)
					end
				end
			end
		end
	end)
end

function IaBridgeScreenPlay:ensureCantinaBarmanOnDuty()
	local rosterId = "roster:mos_eisley_cantina_barman"
	local winner = "npc:core3_barman_jax"
	local cfg = self:getPilotCfg(winner)
	if (cfg == nil) then
		return
	end
	local ps = self:persistStore()
	for pilotId, pc in pairs(IA_BRIDGE_PILOTS) do
		if (pc.roster == rosterId and pilotId ~= winner) then
			if (self:resolvePilotMob(pilotId) ~= nil) then
				self:despawnPilot(pilotId)
			end
			self:destroyExtraPilotMobs(pilotId, nil)
			IaBridgeScreenPlay.rosterPresence[pilotId] = "off"
		end
	end
	local postCell = tonumber(cfg.spawn_cell) or 0
	local tick = ps.tickCount or 0
	local pMob = self:resolvePilotMob(winner)
	if (pMob == nil) then
		pMob = self:reattachPilotMobFromHistory(winner)
	end
	if (pMob == nil and ps.cantinaBarmanSpawnDone == true) then
		local oid = readData(self:pilotOidKey(winner))
		if (oid ~= nil and oid ~= 0) then
			pMob = getSceneObject(oid)
			if (pMob ~= nil) then
				self:registerPilotMob(winner, pMob)
			end
		end
		if (pMob == nil) then
			return
		end
	end
	local pMobValid = false
	if (pMob ~= nil) then
		pMobValid = self:isMobAlive(pMob)
		if (not pMobValid) then
			local ok = pcall(function()
				return SceneObject(pMob):getObjectID()
			end)
			pMobValid = ok
		end
	end
	if (pMobValid) then
		self:setPilotOutdoorPost(winner, false)
		if (not self:pilotMobNearPost(pMob, cfg, 6.0) and postCell ~= 0 and self:isInteriorCellLoadable(postCell)) then
			local px, pz, py = self:resolvePostCoords(cfg)
			pcall(function()
				CreatureObject(pMob):teleport(px, pz, py, postCell)
			end)
		end
		self:syncRosterServiceForPresence(cfg, pMob, "post")
		IaBridgeScreenPlay.rosterPresence[winner] = "post"
		local keepOid = tonumber(SceneObject(pMob):getObjectID()) or SceneObject(pMob):getObjectID()
		self:destroyExtraPilotMobs(winner, keepOid)
		if ((ps.tickCount or 0) % 30 == 0) then
			self:purgeCantinaOrphanClones(keepOid)
		end
		return
	end
	if (postCell == 0 or not self:isInteriorCellLoadable(postCell)) then
		return
	end
	if (ps.cantinaBarmanSpawnDone == true) then
		return
	end
	local last = ps.cantinaBarmanLastSpawnTick or 0
	if ((tick - last) < 5) then
		return
	end
	self:setPilotOutdoorPost(winner, false)
	pMob = self:spawnPilotInBuilding(winner, cfg, postCell)
	if (pMob == nil) then
		local px, pz, py = self:resolvePostCoords(cfg)
		pMob = self:spawnPilotAt(winner, cfg, px, pz, py, postCell)
	end
	if (pMob ~= nil) then
		ps.cantinaBarmanLastSpawnTick = tick
		ps.cantinaBarmanSpawnDone = true
		self:clearPilotBehaviors(pMob)
		pcall(function()
			AiAgent(pMob):addObjectFlag(AI_STATIC)
		end)
		self:syncRosterServiceForPresence(cfg, pMob, "post")
		IaBridgeScreenPlay.rosterPresence[winner] = "post"
		ia_catalog_boot_log("ensure on duty barman " .. winner .. " want=post (interior)")
	end
end

function IaBridgeScreenPlay:ensureArtisanTrainerOnDuty()
	self:ensureExactlyOneRosterOnDuty("roster:mos_trainer_artisan", {
		force_outdoor_post = false,
		log_label = "artisan_trainer",
	})
end

function IaBridgeScreenPlay:maintainInteriorRosterPosts()
	for pilotId, cfg in pairs(IA_BRIDGE_PILOTS) do
		if (cfg.roster ~= nil and not self:isCantinaBarmanPilot(cfg) and not self:isArtisanTrainerPilot(cfg)) then
			local cell = tonumber(cfg.spawn_cell) or 0
			if (cell ~= 0) then
				self:purgeStalePilotRef(pilotId)
				if (self:pilotShouldExist(pilotId, cfg)) then
					local pMob = self:resolvePilotMob(pilotId)
					if (pMob == nil) then
						local want = self:getRosterDesiredPresence(pilotId, cfg)
						if (want ~= nil and want ~= "off") then
							self:spawnRosterPilotAt(pilotId, cfg, want)
						end
					end
				end
			end
		end
	end
end

function IaBridgeScreenPlay:maybeSyncRelayCantina()
	if (os.time() % 12 > 2) then
		return
	end
	if (self:isLiaManualSession()) then
		return
	end
	local pLia = self:resolvePlayer(IA_BRIDGE_BOT)
	if (pLia == nil) then
		return
	end
	if (not self:isAiBridgePlayer(pLia) and not self:isPlayerConnected(pLia)) then
		return
	end
	local liaCell = self:sceneParentId(pLia)
	if (liaCell == IA_BRIDGE_CANTINA_CELL) then
		return
	end
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		local relayName = IA_BRIDGE_CHAT_RELAY[i]
		local pRelay = getPlayerByName(relayName)
		if (pRelay == nil) then
			break
		end
		local relayCell = self:sceneParentId(pRelay)
		-- Uniquement si le relay est deja en cantina (pas theatre / autre interieur).
		if (relayCell == IA_BRIDGE_CANTINA_CELL and liaCell ~= IA_BRIDGE_CANTINA_CELL) then
			printf(
				"IaBridge: %s rejoint %s en cantina (cell %s)\n",
				self:eventActorName(pLia),
				relayName,
				tostring(relayCell)
			)
			self:handleHousingEnter(pLia, "sync_relay:" .. relayName)
			createEvent(2500, "IaBridgeScreenPlay", "relayCantinaArrived", pLia, relayName)
			return
		end
	end
end

function IaBridgeScreenPlay:relayCantinaArrived(pLia, relayName)
	if (pLia == nil) then
		return
	end
	self:notifyRelayLiaVisible(pLia)
end

-- Ajuste la position de Lia si elle est deja en cantina (pas de repatriement force).
function IaBridgeScreenPlay:containLiaInCantina()
	if (self:isLiaManualSession()) then
		return
	end
	local pLia = self:resolvePlayer(IA_BRIDGE_BOT)
	if (pLia == nil) then
		return
	end
	if (not self:isAiBridgePlayer(pLia) and not self:isPlayerConnected(pLia)) then
		return
	end
	local liaCell = self:sceneParentId(pLia)
	if (liaCell == IA_BRIDGE_CANTINA_CELL) then
		if (self:liaBehindCantinaBar(pLia) or not self:liaAtCantinaGuestPost(pLia)) then
			self:teleportLiaToCantinaGuestPost(pLia)
		end
	end
end

function IaBridgeScreenPlay:maybeFollowRelayPlayers()
	if (self:isLiaManualSession()) then
		return
	end
	local pLia = self:resolvePlayer(IA_BRIDGE_BOT)
	if (pLia == nil) then
		return
	end
	if (not self:isAiBridgePlayer(pLia) and not self:isPlayerConnected(pLia)) then
		return
	end
	if (os.time() % 15 > 2) then
		return
	end
	local liaCell = self:sceneParentId(pLia)
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		local relayName = IA_BRIDGE_CHAT_RELAY[i]
		local pRelay = getPlayerByName(relayName)
		if (pRelay == nil) then
			break
		end
		local relayCell = self:sceneParentId(pRelay)
		-- Ne jamais suivre Teome au theatre : cantina uniquement.
		if (relayCell == IA_BRIDGE_THEATER_CELL) then
			if (liaCell ~= IA_BRIDGE_CANTINA_CELL) then
				self:handleHousingEnter(pLia, "block_theater_follow")
			end
			return
		end
		if (relayCell == IA_BRIDGE_CANTINA_CELL and liaCell ~= IA_BRIDGE_CANTINA_CELL) then
			self:handleHousingEnter(pLia, "follow:" .. relayName)
		elseif (relayCell == liaCell and relayCell == IA_BRIDGE_CANTINA_CELL) then
			if (not self:liaBehindCantinaBar(pLia)) then
				self:approachPlayer(pLia, relayName, IA_BRIDGE_APPROACH_RANGE_M + 3)
			end
		end
	end
end

-- Geste ambient si Lia est seule (sans commande pending récente)
function IaBridgeScreenPlay:maybeAmbientGesture()
	local pLia = self:resolvePlayer(IA_BRIDGE_BOT)
	if (pLia == nil or self:isPlayerConnected(pLia) ~= true) then
		return
	end
	if (os.time() % 45 > 3) then
		return
	end
	for i = 1, #IA_BRIDGE_CHAT_RELAY do
		local pOther = getPlayerByName(IA_BRIDGE_CHAT_RELAY[i])
		if (pOther ~= nil) then
			local sx, sy = SceneObject(pLia):getPositionX(), SceneObject(pLia):getPositionY()
			local tx, ty = SceneObject(pOther):getPositionX(), SceneObject(pOther):getPositionY()
			if (self:dist2d(sx, sy, tx, ty) <= IA_BRIDGE_APPROACH_RANGE_M + 2) then
				pcall(function()
					CreatureObject(pLia):doAnimation("wave")
				end)
				return
			end
		end
	end
end

-- Remet une commande en file si le joueur n'est pas encore en ligne (évite perte au poll).
local function enqueueIaBridgePendingLine(line)
	if (line == nil or line == "") then
		return
	end
	local f = io.open(IA_BRIDGE_PENDING_FILE, "a")
	if (f == nil) then
		return
	end
	f:write(line)
	f:write("\n")
	f:close()
end

-- Fallback si le binaire core3-clean n'expose pas encore pollIaBridgeCommand (C++).
local function pollIaBridgeCommandFallback()
	local f = io.open(IA_BRIDGE_PENDING_FILE, "r")
	if (f == nil) then
		return nil
	end
	local lines = {}
	for ln in f:lines() do
		ln = string.gsub(ln, "\r$", "")
		if (ln ~= nil and ln ~= "") then
			table.insert(lines, ln)
		end
	end
	f:close()
	if (#lines == 0) then
		return nil
	end
	local first = lines[1]
	local w = io.open(IA_BRIDGE_PENDING_FILE, "w")
	if (w ~= nil) then
		for i = 2, #lines do
			w:write(lines[i])
			w:write("\n")
		end
		w:close()
	end
	return first
end

local function pollIaBridgeCommandLine()
	if (type(pollIaBridgeCommand) == "function") then
		local ok, line = pcall(pollIaBridgeCommand)
		if (ok and line ~= nil and line ~= "") then
			return line
		end
	end
	return pollIaBridgeCommandFallback()
end

function IaBridgeScreenPlay:tick()
	local ps = self:persistStore()
	ps.tickCount = (ps.tickCount or 0) + 1
	IA_BRIDGE_TICK_COUNT = ps.tickCount
	if (IA_BRIDGE_TICK_COUNT % 60 == 0) then
		ia_catalog_boot_log("tick heartbeat=" .. tostring(IA_BRIDGE_TICK_COUNT))
	end
	-- Priorite aux commandes joueur (pending.jsonl) avant la maintenance PNJ.
	local line = nil
	local okPoll, pollResult = pcall(pollIaBridgeCommandLine)
	if (okPoll) then
		line = pollResult
	end
	if (line == nil or line == "") then
		local okTick, tickErr = pcall(function()
			self:ensureCatalogReady()
			self:containLiaInCantina()
			self:tickRosterLifecycle()
			self:ensureCantinaBarmanOnDuty()
			self:ensureArtisanTrainerOnDuty()
			self:maintainInteriorRosterPosts()
			self:syncPilotsNearLia()
			self:maybeSyncRelayCantina()
			self:maybeFollowRelayPlayers()
			self:repatriateDriftedPilots()
			if (IA_BRIDGE_TICK_COUNT % 30 == 0) then
				self:ensurePilotBodiesApplied()
			end
			self:maybeAmbientGesture()
			self:rehydratePilotMobCache()
			self:publishSnapshot()
			self:publishAiPlayerSnapshots()
			self:publishNpcSnapshots()
			-- Simulation passive (~15 min si tick 2s)
			if (IA_BRIDGE_TICK_COUNT % 450 == 0) then
				self:tickPassiveNpcSimulation()
			end
			if (IA_BRIDGE_TICK_COUNT % 300 == 0) then
				self:tickPlanetMoonEffects()
			end
			if (IA_BRIDGE_TICK_COUNT % 60 == 0) then
				local mobRefs = 0
				for _ in pairs(self:pilotMobTable()) do
					mobRefs = mobRefs + 1
				end
				local ps = self:persistStore()
				local catSize = self:countTableKeys(ps.catalogPilots)
				if (catSize == 0) then
					catSize = self:countTableKeys(IA_BRIDGE_PILOTS)
				end
				local online = 0
				local okCount, countResult = pcall(function()
					return self:countResolvedPilots()
				end)
				if (okCount) then
					online = countResult or 0
				end
				ia_catalog_boot_log(string.format(
					"tick online=%d mobRefs=%d catalog=%d tick=%d",
					online, mobRefs, catSize, IA_BRIDGE_TICK_COUNT
				))
				if (catSize == 0) then
					ia_catalog_boot_log(string.format(
						"catalog EMPTY persistCat=%s globals=%s fallback=%d",
						tostring(ps.catalogPilots ~= nil),
						tostring(ia_table_has_entries(IA_BRIDGE_PILOTS)),
						self:countTableKeys(IA_BRIDGE_PILOTS_FALLBACK)
					))
				end
			end
		end)
		if (not okTick) then
			ia_catalog_boot_log("tick erreur tick=" .. tostring(IA_BRIDGE_TICK_COUNT) .. " : " .. tostring(tickErr))
		end
		self:scheduleTick()
		return
	end

	local parts = self:splitLine(line, 7)
	if (parts == nil) then
		printf("IaBridge: ligne invalide (7 champs attendus) : %s\n", tostring(line))
		self:scheduleTick()
		return
	end

	local action = parts[1]
	local playerName = parts[2]
	local zoneName = parts[3]
	local x = tonumber(parts[4]) or 0
	local y = tonumber(parts[5]) or 0
	local z = tonumber(parts[6]) or 0
	local message = parts[7] or ""
	local homeZone = IA_BRIDGE_ZONE

	if (zoneName ~= nil and zoneName ~= "" and zoneName ~= homeZone) then
		printf("IaBridge: zone refusee %s (attendu %s)\n", tostring(zoneName), homeZone)
		self:scheduleTick()
		return
	end

	if (action == "npc_say") then
		self:handleNpcSay(playerName, message)
		self:scheduleTick()
		return
	end

	if (action == "npc_perform") then
		self:handleNpcPerform(playerName, message)
		self:scheduleTick()
		return
	end

	if (action == "npc_path") then
		self:handleNpcPath(playerName, x, y, z, message)
		self:scheduleTick()
		return
	end

	if (action == "offer_quest") then
		self:handleNpcOfferQuest(playerName, message)
		self:scheduleTick()
		return
	end

	if (action == "vendor_buy") then
		-- Format: vendor_buy|<pilot_id>|tatooine|0|0|0|<buyer>|<itemIndex>
		local buyerName, itemIdx = string.match(message or "", "^([^|]+)|(.+)$")
		if (buyerName == nil) then
			buyerName = message
			itemIdx = "0"
		end
		local pBuyer = self:resolvePlayer(buyerName)
		if (pBuyer ~= nil) then
			self:handleVendorBuy(pBuyer, playerName, itemIdx)
		end
		self:scheduleTick()
		return
	end

	if (action == "vendor_sell") then
		-- Format: vendor_sell|<pilot_id>|tatooine|0|0|0|<seller>|<itemIndex>
		local sellerName, itemIdx = string.match(message or "", "^([^|]+)|(.+)$")
		if (sellerName == nil) then
			sellerName = message
			itemIdx = "0"
		end
		local pSeller = self:resolvePlayer(sellerName)
		if (pSeller ~= nil) then
			self:handleVendorSell(pSeller, playerName, itemIdx)
		end
		self:scheduleTick()
		return
	end

	local pPlayer = self:resolvePlayer(playerName)
	if (pPlayer == nil) then
		printf("IaBridge: joueur hors ligne ou inconnu : %s — commande remise en file\n", tostring(playerName))
		enqueueIaBridgePendingLine(line)
		self:scheduleTick()
		return
	end

	if (playerName == IA_BRIDGE_BOT and self:isLiaManualSession()) then
		if (action == "move_to" or action == "approach_player" or action == "housing_enter" or action == "switch_zone") then
			printf("IaBridge: %s en session manuelle — action %s ignoree\n", IA_BRIDGE_BOT, tostring(action))
			self:scheduleTick()
			return
		end
	end

	if (playerName == IA_BRIDGE_BOT and action == "move_to" and (x ~= 0 or y ~= 0)) then
		-- Refuse move_to outdoor si Lia n est pas deja en cantina (evite derive theatre 1105853).
		local pLia = self:resolvePlayer(IA_BRIDGE_BOT)
		if (pLia ~= nil and self:sceneParentId(pLia) ~= IA_BRIDGE_CANTINA_CELL) then
			self:containLiaInCantina()
			self:scheduleTick()
			return
		end
	end

	if (action == "noop") then
		-- rien
	elseif (action == "say") then
		self:playerSay(pPlayer, message)
	elseif (action == "move_to") then
		if (x ~= 0 or y ~= 0) then
			self:approachCoords(pPlayer, x, y, z)
			printf("IaBridge: move_to %s -> %.1f %.1f %.1f\n", IA_BRIDGE_BOT, x, y, z)
		end
	elseif (action == "animate") then
		if (message ~= nil and message ~= "") then
			pcall(function()
				CreatureObject(pPlayer):doAnimation(message)
			end)
			printf("IaBridge: animate %s : %s\n", IA_BRIDGE_BOT, message)
		end
	elseif (action == "perform") then
		if (message ~= nil and message ~= "") then
			self:handlePlayerPerform(pPlayer, message)
		end
	elseif (action == "interact") then
		self:handlePlayerInteract(pPlayer, message)
	elseif (action == "craft_combine") then
		self:handleCraftCombine(pPlayer, message)
	elseif (action == "skill_forget") then
		self:handleSkillForget(pPlayer, message)
	elseif (action == "housing_enter") then
		self:handleHousingEnter(pPlayer, message)
	elseif (action == "reset_pilot") then
		local pid = message
		if (pid == nil or pid == "") then
			pid = "npc:core3_scribe"
		end
		self:resetPilotToHome(pid)
		self:refreshPilotBody(pid)
	elseif (action == "reapply_pilot_bodies") then
		local pid = message
		if (pid ~= nil and pid ~= "" and pid ~= "all") then
			self:refreshPilotBody(pid)
		else
			self:refreshAllPilotBodies()
		end
	elseif (action == "set_player_height") then
		-- message: "Teome|1.65" (metres) ou "Teome|scale:0.95"
		local target = playerName
		local val = message
		if (message ~= nil and string.find(message, "|", 1, true) ~= nil) then
			target, val = string.match(message, "^(.-)|(.+)$")
		end
		if (target == nil or target == "") then
			target = playerName
		end
		if (val ~= nil and string.sub(val, 1, 6) == "scale:") then
			self:setPlayerHeightScale(target, string.sub(val, 7))
		else
			self:setPlayerHeightMeters(target, val)
		end
	elseif (action == "set_player_lbg_body") then
		-- message: "bothan|male|0.60" — player = prénom IG (parts[2])
		local speciesKey, gender, heightM = string.match(message or "", "^(.-)|(.-)|(.+)$")
		if (speciesKey == nil) then
			speciesKey, gender, heightM = "bothan", "male", "0.60"
		end
		self:setPlayerLbgBody(playerName, speciesKey, gender, heightM)
	elseif (action == "approach_player") then
		local target = message
		if (target == nil or target == "") then
			return
		end
		self:approachPlayer(pPlayer, target, IA_BRIDGE_APPROACH_RANGE_M)
	elseif (action == "switch_zone") then
		local dest = zoneName
		if (dest == nil or dest == "") then
			dest = homeZone
		end
		if (dest == homeZone) then
			CreatureObject(pPlayer):sendSystemMessage("[IA] Transfert vers " .. dest .. "...")
			SceneObject(pPlayer):switchZone(dest, x, y, z, 0)
		else
			printf("IaBridge: switch_zone refuse vers %s\n", tostring(dest))
		end
	else
		printf("IaBridge: action inconnue : %s\n", tostring(action))
	end

	pcall(function()
		self:publishSnapshot()
		self:publishAiPlayerSnapshots()
	end)
	self:scheduleTick()
end
