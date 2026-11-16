-- The harness's identity program (SIP-0117 R3.6): what the worker confirms before it writes.
-- It reads only, and takes no input.
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
return HttpService:JSONEncode({
	placeId = game.PlaceId,
	gameId = game.GameId,
	edit = RunService:IsEdit(),
	running = RunService:IsRunning(),
})
