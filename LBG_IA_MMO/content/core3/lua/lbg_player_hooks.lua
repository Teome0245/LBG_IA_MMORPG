-- Hook login joueur → World Editor (Dev+)
local _lbg_orig_playerLoggedIn = PlayerTriggers.playerLoggedIn

function PlayerTriggers:playerLoggedIn(pPlayer)
	if (_lbg_orig_playerLoggedIn ~= nil) then
		_lbg_orig_playerLoggedIn(self, pPlayer)
	end
	if (LbgWorldEditorScreenPlay ~= nil and LbgWorldEditorScreenPlay.onPlayerLoggedIn ~= nil) then
		pcall(function()
			LbgWorldEditorScreenPlay:onPlayerLoggedIn(pPlayer)
		end)
	end
	if (IaBridgeScreenPlay ~= nil and IaBridgeScreenPlay.onPlayerLoggedIn ~= nil) then
		pcall(function()
			IaBridgeScreenPlay:onPlayerLoggedIn(pPlayer)
		end)
	end
	if (LbgLostHeavenScreenPlay ~= nil and LbgLostHeavenScreenPlay.onPlayerLoggedIn ~= nil) then
		pcall(function()
			LbgLostHeavenScreenPlay:onPlayerLoggedIn(pPlayer)
		end)
	end
end
