-- The harness's script-marks program (#3042's eligibility rule, placed at the worker): every
-- script in the three synced folders that carries attributes or CollectionService tags. Script
-- Sync's files can't carry either, so such a script is one the repository can't describe, and the
-- game's owners' rule is that code never relies on them. It reads only, and takes no input.
local HttpService = game:GetService("HttpService")
local CollectionService = game:GetService("CollectionService")
local FOLDERS = {
	{ "ServerScriptService", "Server" },
	{ "ReplicatedStorage", "Shared" },
	{ "StarterPlayer", "StarterPlayerScripts", "Client" },
}
local marked = {}
for _, path in FOLDERS do
	local node = game:FindService(path[1])
	for i = 2, #path do
		node = node and node:FindFirstChild(path[i])
	end
	if node then
		for _, instance in node:GetDescendants() do
			if instance:IsA("LuaSourceContainer") then
				local attributes = {}
				for key in instance:GetAttributes() do
					table.insert(attributes, key)
				end
				table.sort(attributes)
				local tags = CollectionService:GetTags(instance)
				table.sort(tags)
				if #attributes > 0 or #tags > 0 then
					table.insert(marked, { path = instance:GetFullName(), attributes = attributes, tags = tags })
				end
			end
		end
	end
end
table.sort(marked, function(a, b) return a.path < b.path end)
return HttpService:JSONEncode({ marked = marked })
