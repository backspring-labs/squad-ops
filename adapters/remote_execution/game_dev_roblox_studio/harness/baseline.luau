-- The harness's baseline program (SIP-0117 R3.6): the place's non-script state, one line per
-- instance, over a stated property set, for the worker to digest before play and after stop.
-- It reads only. Its input is PAYLOAD, hex-encoded JSON in place of the token below:
--   { snapshot, offset, max_chars, release }
-- The first call of a snapshot walks the place and keeps its sorted lines in _G under that
-- snapshot's id. Each call answers the lines from `offset` until `max_chars` would be passed (at
-- least one), with the total and the next offset. `release` clears the kept lines.
--
-- Covered: every instance under the services below, by its path, class, attributes, tags and the
-- properties PROPERTIES names for the classes it is. Scripts outside the three synced folders
-- carry their whole source. Left out, each for its reason:
--   - the three synced folders' contents: the script read-back covers them whole;
--   - Camera instances: Studio moves the camera whenever the viewport moves;
--   - Terrain's voxels: no property reads them.
local PAYLOAD = "{{PAYLOAD}}"

local HttpService = game:GetService("HttpService")
local CollectionService = game:GetService("CollectionService")

local job = HttpService:JSONDecode((string.gsub(PAYLOAD, "%x%x", function(pair)
	return string.char(tonumber(pair, 16))
end)))

local SERVICES = {
	"Workspace", "Lighting", "ReplicatedFirst", "ReplicatedStorage", "ServerScriptService",
	"ServerStorage", "StarterGui", "StarterPack", "StarterPlayer", "SoundService", "Teams",
	"TextChatService", "MaterialService",
}
local SYNCED = {
	["ServerScriptService/Server"] = true,
	["ReplicatedStorage/Shared"] = true,
	["StarterPlayer/StarterPlayerScripts/Client"] = true,
}
local SCRIPT_CLASSES = { Script = true, LocalScript = true, ModuleScript = true }

-- The stated property set: for an instance that IsA the key, these properties.
local PROPERTIES = {
	BasePart = {
		"CFrame", "Size", "Anchored", "CanCollide", "CanTouch", "CanQuery", "Transparency",
		"Reflectance", "Color", "Material", "MaterialVariant", "CastShadow", "Massless", "Locked",
	},
	MeshPart = { "MeshId", "TextureID" },
	SpecialMesh = { "MeshId", "TextureId", "MeshType", "Scale", "Offset" },
	Decal = { "Texture", "Transparency", "Color3", "Face" },
	Light = { "Enabled", "Brightness", "Color", "Shadows" },
	PointLight = { "Range" },
	SpotLight = { "Range", "Angle", "Face" },
	SurfaceLight = { "Range", "Angle", "Face" },
	Fire = { "Enabled", "Color", "SecondaryColor", "Size", "Heat" },
	ParticleEmitter = { "Enabled", "Rate", "Texture", "Lifetime", "Speed" },
	Smoke = { "Enabled" },
	Sparkles = { "Enabled" },
	Attachment = { "CFrame" },
	WeldConstraint = { "Part0", "Part1", "Enabled" },
	JointInstance = { "Part0", "Part1", "C0", "C1", "Enabled" },
	Constraint = { "Attachment0", "Attachment1", "Enabled" },
	Model = { "PrimaryPart", "WorldPivot" },
	ValueBase = { "Value" },
	GuiObject = { "Position", "Size", "Visible", "ZIndex" },
	GuiBase2d = {},
	TextLabel = { "Text" },
	TextButton = { "Text" },
	ImageLabel = { "Image" },
	ImageButton = { "Image" },
	Sound = { "SoundId", "Volume", "Looped", "PlaybackSpeed" },
	SpawnLocation = { "Enabled", "Neutral" },
	ProximityPrompt = { "Enabled", "ActionText", "MaxActivationDistance" },
	ClickDetector = { "MaxActivationDistance" },
	Lighting = { "ClockTime", "Brightness", "Ambient", "OutdoorAmbient", "FogStart", "FogEnd", "FogColor" },
	Workspace = { "Gravity" },
	LuaSourceContainer = {},
}

-- A value as text, exact enough to see a part moved 0.01 studs anywhere in a place.
local function show(value, pathOf)
	local kind = typeof(value)
	if kind == "number" then
		return string.format("%.9g", value)
	elseif kind == "string" then
		return HttpService:JSONEncode(value)
	elseif kind == "Instance" then
		return "@" .. pathOf(value)
	elseif kind == "CFrame" then
		local parts = { value:GetComponents() }
		for i, n in parts do
			parts[i] = string.format("%.9g", n)
		end
		return "CFrame(" .. table.concat(parts, ",") .. ")"
	elseif kind == "Vector3" then
		return string.format("Vector3(%.9g,%.9g,%.9g)", value.X, value.Y, value.Z)
	elseif kind == "Color3" then
		return string.format("Color3(%.9g,%.9g,%.9g)", value.R, value.G, value.B)
	end
	return kind .. "(" .. tostring(value) .. ")"
end

local function build()
	local names = {}
	-- Per parent, once: each child's order among its same-named siblings, and how many share it.
	local orders = {}
	local function orderOf(parent, instance)
		local order = orders[parent]
		if order == nil then
			order = { nth = {}, count = {} }
			for _, sibling in parent:GetChildren() do
				local n = (order.count[sibling.Name] or 0) + 1
				order.count[sibling.Name] = n
				order.nth[sibling] = n
			end
			orders[parent] = order
		end
		return order.nth[instance] or 0, order.count[instance.Name] or 0
	end
	local function pathOf(instance)
		local known = names[instance]
		if known then
			return known
		end
		if instance == game or instance == nil then
			return ""
		end
		local parent = instance.Parent
		local prefix = if parent == game or parent == nil then "" else pathOf(parent) .. "/"
		local name = instance.Name
		-- Siblings that share a name are told apart by their order among those siblings.
		local nth, same = 0, 0
		if parent then
			nth, same = orderOf(parent, instance)
		end
		local path = prefix .. name .. (if same > 1 then "[" .. nth .. "]" else "")
		names[instance] = path
		return path
	end

	local lines = {}
	local function line(instance, path)
		local fields = { path, instance.ClassName }
		local attributes = {}
		for key, value in instance:GetAttributes() do
			table.insert(attributes, key .. "=" .. show(value, pathOf))
		end
		table.sort(attributes)
		if #attributes > 0 then
			table.insert(fields, "attributes{" .. table.concat(attributes, ";") .. "}")
		end
		local tags = CollectionService:GetTags(instance)
		table.sort(tags)
		if #tags > 0 then
			table.insert(fields, "tags{" .. table.concat(tags, ";") .. "}")
		end
		local props = {}
		for class, list in PROPERTIES do
			if instance:IsA(class) then
				for _, prop in list do
					local ok, value = pcall(function()
						return instance[prop]
					end)
					props[prop] = if ok then show(value, pathOf) else "unreadable"
				end
			end
		end
		if SCRIPT_CLASSES[instance.ClassName] then
			props.Source = HttpService:JSONEncode(instance.Source)
		end
		local keys = {}
		for key in props do
			table.insert(keys, key)
		end
		table.sort(keys)
		for _, key in keys do
			table.insert(fields, key .. "=" .. props[key])
		end
		table.insert(lines, table.concat(fields, "\t"))
	end

	local function walk(instance)
		local path = pathOf(instance)
		if instance:IsA("Camera") then
			return
		end
		line(instance, path)
		if SYNCED[path] then
			return
		end
		for _, child in instance:GetChildren() do
			walk(child)
		end
	end

	for _, name in SERVICES do
		local service = game:FindService(name)
		if service then
			walk(service)
		end
	end
	table.sort(lines)
	return lines
end

local kept = _G.SquadOpsBaseline
if kept == nil or kept.snapshot ~= job.snapshot then
	kept = { snapshot = job.snapshot, lines = build() }
	_G.SquadOpsBaseline = kept
end
local lines = kept.lines
local out, used, index = {}, 0, job.offset + 1
while index <= #lines do
	local size = #lines[index] + 1
	if #out > 0 and used + size > job.max_chars then
		break
	end
	table.insert(out, lines[index])
	used += size
	index += 1
end
local total = #lines
if job.release then
	_G.SquadOpsBaseline = nil
end
return HttpService:JSONEncode({ total = total, next = index - 1, lines = out })
