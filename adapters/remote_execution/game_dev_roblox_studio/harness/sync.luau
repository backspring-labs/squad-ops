-- The harness's sync program (SIP-0117 D10): writes scripts with their classes, and removes
-- scripts. Its only input is PAYLOAD, hex-encoded JSON put in place of the token below, so nothing
-- it is handed runs as code:
--   { writes = { { path, class, source } }, removes = { path } }
-- A path is an instance path split by "/", starting at a service. Writes come parents first and
-- removes children first; the worker orders them.
local PAYLOAD = "{{PAYLOAD}}"

local HttpService = game:GetService("HttpService")
local SCRIPT_CLASSES = { Script = true, LocalScript = true, ModuleScript = true }

local job = HttpService:JSONDecode((string.gsub(PAYLOAD, "%x%x", function(pair)
	return string.char(tonumber(pair, 16))
end)))

local function split(path)
	local parts = {}
	for part in string.gmatch(path, "[^/]+") do
		table.insert(parts, part)
	end
	return parts
end

-- The instance a path's last part goes in, creating missing folders when asked.
local function parentOf(parts, create)
	local node = game:GetService(parts[1])
	for i = 2, #parts - 1 do
		local nextNode = node:FindFirstChild(parts[i])
		if nextNode == nil then
			if not create then
				return nil
			end
			nextNode = Instance.new("Folder")
			nextNode.Name = parts[i]
			nextNode.Parent = node
		end
		node = nextNode
	end
	return node
end

local written, replaced, removed = 0, 0, 0
for _, write in job.writes do
	if not SCRIPT_CLASSES[write.class] then
		error("sync: " .. tostring(write.class) .. " is not a script class (" .. write.path .. ")")
	end
	local parts = split(write.path)
	local parent = parentOf(parts, true)
	local name = parts[#parts]
	local target = parent:FindFirstChild(name)
	if target ~= nil and target.ClassName ~= write.class then
		-- A script whose class changed is a new instance of the new class, keeping its children.
		local fresh = Instance.new(write.class)
		fresh.Name = name
		for _, child in target:GetChildren() do
			child.Parent = fresh
		end
		target:Destroy()
		target = fresh
		replaced += 1
	elseif target == nil then
		target = Instance.new(write.class)
		target.Name = name
	end
	target.Source = write.source
	target.Parent = parent
	written += 1
end
for _, path in job.removes do
	local parts = split(path)
	local parent = parentOf(parts, false)
	local found = parent and parent:FindFirstChild(parts[#parts])
	if found ~= nil and SCRIPT_CLASSES[found.ClassName] then
		found:Destroy()
		removed += 1
	end
end
return HttpService:JSONEncode({ written = written, replaced = replaced, removed = removed })
