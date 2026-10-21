-- Fictional UI fixture; not executed by the extractor.
local warning = "Pressure " .. "warning"
GUI.TextBlock(parent, warning)
GUI.Button(parent, "Activate sonar")
Hook.Add("roundStart", "pressurekit.internal", function() end)
