-- The harness's observe program (SIP-0117 R3.7; #3040): one observation of the roblox-studio/1
-- vocabulary, read in the play session's Server or Client datamodel. It reads only. Its input is
-- PAYLOAD, hex-encoded JSON in place of the token below:
--   { kind, context, path, name?, state? }
-- It answers exactly one of:
--   { value = <number, text or boolean> }
--   { absent = true }                     the path's instance isn't there
--   { unsupported = <why> }               the observation isn't one the harness reads
--   { unreadable = <why> }                it is, and reading it failed
--   { wrong_context = <why> }             it ran somewhere other than the context it names
local PAYLOAD = "{{PAYLOAD}}"

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local job = HttpService:JSONDecode((string.gsub(PAYLOAD, "%x%x", function(pair)
	return string.char(tonumber(pair, 16))
end)))

local function answer(t)
	return HttpService:JSONEncode(t)
end

-- The one player of the session: LocalPlayer on the client, the only player on the server.
local function player()
	if RunService:IsClient() then
		return Players.LocalPlayer, nil
	end
	local all = Players:GetPlayers()
	if #all ~= 1 then
		return nil, #all .. " players are in the session, and @player names one"
	end
	return all[1], nil
end

-- A path's instance, nil when it isn't there, or an error when the path can't name one.
local function resolve(path)
	local parts = string.split(path, ".")
	local node
	local first = parts[1]
	if first == "@player" then
		local found, why = player()
		if found == nil then
			return nil, why
		end
		node = found
	elseif first == "game" then
		node = game
	else
		local ok, service = pcall(function()
			return game:FindService(first)
		end)
		if not ok or service == nil then
			return nil, "a path starts at a service or @player, and " .. first .. " is neither"
		end
		node = service
	end
	for i = 2, #parts do
		node = node:FindFirstChild(parts[i])
		if node == nil then
			return nil, nil
		end
	end
	return node, nil
end

-- A value as the vocabulary reads it: numbers, text and booleans as they are, the rest as text.
local function scalar(value)
	local kind = typeof(value)
	if kind == "number" or kind == "string" or kind == "boolean" then
		return value
	elseif kind == "Instance" then
		local local_player = player()
		local full = value:GetFullName()
		if local_player then
			local prefix = local_player:GetFullName()
			if string.sub(full, 1, #prefix) == prefix then
				full = "@player" .. string.sub(full, #prefix + 1)
			end
		end
		return full
	end
	return tostring(value)
end

local function shown(gui)
	local node = gui
	while node and node ~= game do
		if node:IsA("GuiObject") and not node.Visible then
			return false
		end
		if node:IsA("LayerCollector") then
			return node.Enabled
		end
		node = node.Parent
	end
	return false
end

-- The datamodel it was sent to is the context it was declared for, or it says so.
local running = if RunService:IsClient() then "client" elseif RunService:IsServer() then "server" else "edit"
if running ~= job.context then
	return answer({ wrong_context = "declared for the " .. tostring(job.context) .. ", and it ran on the " .. running })
end

local instance, why = resolve(job.path)
if why then
	return answer({ unreadable = why })
end
if instance == nil then
	return answer({ absent = true })
end

if job.kind == "property" then
	local ok, value = pcall(function()
		return instance[job.name]
	end)
	if not ok then
		return answer({ unsupported = instance.ClassName .. " has no property " .. job.name })
	end
	if value == nil then
		return answer({ absent = true })
	end
	return answer({ value = scalar(value) })
elseif job.kind == "attribute" then
	local value = instance:GetAttribute(job.name)
	if value == nil then
		return answer({ absent = true })
	end
	return answer({ value = scalar(value) })
elseif job.kind == "gui_state" then
	-- A screen (a ScreenGui, any LayerCollector) is visible when it is enabled, which is what
	-- `shown` reads of the screen a GUI object sits in (#3176). It has no text.
	local screen = instance:IsA("LayerCollector")
	if not (screen or instance:IsA("GuiObject")) then
		return answer({ unsupported = job.path .. " is a " .. instance.ClassName .. ", not a GUI object or a screen" })
	end
	if job.state == "visible" then
		return answer({ value = shown(instance) })
	elseif job.state == "text" then
		if screen then
			return answer({ unsupported = job.path .. " is a " .. instance.ClassName .. ", a screen, which has no text" })
		end
		local ok, value = pcall(function()
			return instance.Text
		end)
		if not ok then
			return answer({ unsupported = instance.ClassName .. " has no text" })
		end
		return answer({ value = value })
	end
	return answer({ unsupported = "the gui state " .. job.state .. " isn't one the harness reads (visible, text)" })
elseif job.kind == "value" then
	if not instance:IsA("ValueBase") then
		return answer({ unsupported = job.path .. " is a " .. instance.ClassName .. ", not a ValueBase" })
	end
	if instance.Value == nil then
		return answer({ absent = true })
	end
	return answer({ value = scalar(instance.Value) })
end
return answer({ unsupported = "the harness reads no observation of kind " .. tostring(job.kind) })
