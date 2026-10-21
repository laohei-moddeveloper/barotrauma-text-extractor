-- Optional CLIENT module. Never executes or rewrites another mod's scripts.
-- Translation stays in the desktop process; this module makes no HTTP requests.
if not CLIENT then return end
local root = tostring(... or ""):gsub("\\", "/"):gsub("/+$", "")
if root == "" then return end
local live = root .. "/Live/"
local active, pending, dirty = false, false, false
local nextPoll, nextSend, serial, nextSettings = 0, 0, 0, 0
local requestId, revision = "", ""
local translations, translatedValues, queued, sent, controls, originals = {}, {}, {}, {}, {}, {}
local queuedCount, controlCount = 0, 0
local queuedBytes, sentCount = 0, 0
local patchSignatures, installed = {}, false
local InstallPatches
local uiLanguage, sourceLanguage, targetLanguage = "zh", "English", "Simplified Chinese"
local button, languageFile
local richString
pcall(function()
    LuaUserData.RegisterType("Barotrauma.RichString")
    richString = LuaUserData.CreateStatic("Barotrauma.RichString")
end)
local warned = {}
local function Warn(key, message)
    if warned[key] then return end
    warned[key] = true
    print("[AbyssTextLive] " .. message)
end
local function Ui(zh, en) if uiLanguage == "en" then return en end return zh end
local function UpdateButton()
    if button then pcall(function()
        button.Text = active and Ui("译潜 · 停止试译", "AbyssText · Stop") or Ui("译潜 · 一键试译", "AbyssText · Translate")
        button.ToolTip = Ui("连接桌面工作台后试译；再次点击恢复。F3：abyss_translate / abyss_stop", "Connect the desktop workbench. Click to translate; click again to restore. F3: abyss_translate / abyss_stop")
    end) end
end
local function ReadSettings()
    if File.Exists(live .. "settings.json") then
        local settings = json.parse(File.Read(live .. "settings.json"))
        uiLanguage = settings.ui_language == "en" and "en" or "zh"
        sourceLanguage = settings.source_language or "English"
        if sourceLanguage == "Auto" then sourceLanguage = tostring(TextManager.DefaultLanguage) end
        targetLanguage = settings.target_language or "Simplified Chinese"
    end
    UpdateButton()
end
local function PacksFor(name)
    if TextManager.AvailableLanguages ~= nil then
        for language in TextManager.AvailableLanguages do
            if tostring(language):lower() == name:lower() then return TextManager.TextPacks[language] end
        end
    end
    return TextManager.TextPacks[name]
end
local function Normalize(path) return tostring(path or ""):gsub("\\", "/"):gsub("/+$", "") end
local function TextValue(value)
    if type(value) == "string" then return value end
    if value == nil then return "" end
    local ok, text = pcall(function() return value.NestedStr.Value end)
    if ok and text ~= nil then return tostring(text) end
    ok, text = pcall(function() return value.SanitizedValue end)
    if ok and text ~= nil then return tostring(text) end
    ok, text = pcall(function() return value.Value end)
    if ok and text ~= nil then return tostring(text) end
    return tostring(value)
end
local function Signature(text)
    local values = {}
    -- Existing engine placeholders and rich-text markers must remain untouched.
    if text:find("[",1,true) or text:find("{",1,true) or text:find("‖",1,true) then return text, values end
    local template = text:gsub("%d+%.?%d*", function(value)
        values[#values+1] = value
        return "[abyss_value_" .. #values .. "]"
    end)
    return template, values
end
local function Translated(text)
    if translations[text] then return translations[text] end
    local template, values = Signature(text)
    local translated = translations[template]
    if not translated then return nil end
    return translated:gsub("%[abyss_value_(%d+)%]",function(index) return values[tonumber(index)] or "" end)
end
local function Observe(text, key)
    if not active or type(text) ~= "string" or #text < 2 or #text > 20000 then return end
    if not (text:match("%a") or text:match("[\128-\255]")) or translatedValues[text] or translations[text] then return end
    if key == nil or key == "" then text = Signature(text) end
    if translatedValues[text] or translations[text] then return end
    local identity = (key or "") .. "\0" .. text
    if sent[identity] or queued[identity] or queuedCount >= 10000 or sentCount >= 20000 or queuedBytes + #text + #(key or "") > 1000000 then return end
    queued[identity] = {text=text, key=key or ""}
    queuedCount = queuedCount + 1
    queuedBytes = queuedBytes + #text + #(key or "")
    dirty = true
end
local function FindLanguageFile()
    for package in ContentPackageManager.EnabledPackages.All do
        if Normalize(package.Dir) == root then
            for file in package.Files do
                if LuaUserData.IsTargetType(file, "Barotrauma.TextFile") and Normalize(file.Path.Value) == live .. "Translations.xml" then
                    return file
                end
            end
        end
    end
end
local function RefreshLanguage(unloadOnly)
    languageFile = languageFile or FindLanguageFile()
    if languageFile == nil then Warn("file", Ui("未找到插件语言资源，请检查 filelist.xml 与插件启用状态。", "Plugin text resource unavailable. Check filelist.xml and enable the companion.")) return end
    languageFile.UnloadFile()
    if not unloadOnly then languageFile.LoadFile() end
    TextManager.IncrementLanguageVersion()
end
local function CollectLanguageKeys()
    local current = {}
    local targetPacks = PacksFor(targetLanguage)
    if targetPacks ~= nil then
        for pack in targetPacks do
            for pair in pack.Texts do
                local key = tostring(pair.Key):lower()
                current[key] = current[key] or {}
                for value in pair.Value do current[key][tostring(value.String)] = true end
            end
        end
    end
    local sourcePacks = PacksFor(sourceLanguage)
    if sourcePacks == nil then Warn("source", Ui("未找到源语言表，继续采集当前界面。", "Source language pack unavailable; collecting displayed text.")) return end
    for pack in sourcePacks do
        -- Texts loads an unloaded English pack via its own public getter.
        for pair in pack.Texts do
            local key = tostring(pair.Key):lower()
            for value in pair.Value do
                local text = tostring(value.String)
                local alternatives = current[key]
                -- A different current-language string is already localized.
                local localized = false
                if alternatives then
                    for existing in pairs(alternatives) do
                        if existing ~= text then localized = true break end
                    end
                end
                if not localized then Observe(text, key) end
            end
        end
    end
end
local function CollectControls(component)
    if not active or component == nil then return end
    local ok, isText = pcall(LuaUserData.IsTargetType, component, "Barotrauma.GUITextBlock")
    if ok and isText then
        if controls[component] == nil and controlCount < 3000 then controls[component] = true; controlCount = controlCount + 1 end
        local read, text = pcall(function() return TextValue(component.Text) end)
        if read then Observe(text) end
    end
end
local function ApplyControls()
    for component in pairs(controls) do
        local ok = pcall(function()
            local current = TextValue(component.Text)
            local old = originals[component]
            if old and current ~= old.display then originals[component] = nil end
            local target = Translated(current)
            -- Dynamic getters retain control over their value; the draw hook can
            -- replace plain strings instead of destroying the getter delegate.
            if target and component.TextGetter == nil then
                local original = component.Text
                if target:find("‖",1,true) then
                    if richString == nil then Warn("rich", Ui("富文本构造接口不可用，保留该控件原文。", "Rich text constructor unavailable; preserving this control.")) return end
                    component.Text = richString.Rich(target)
                else
                    component.Text = target
                end
                originals[component] = {value=original, display=TextValue(component.Text)}
            end
        end)
        if not ok then controls[component] = nil; originals[component] = nil end
    end
end
local function SendRequest()
    if not active or pending or not dirty then return end
    local records = {}
    for identity, record in pairs(queued) do
        records[#records + 1] = record
    end
    if #records == 0 then dirty = false return end
    serial = serial + 1
    requestId = tostring(Timer.GetTime()) .. "." .. tostring(serial)
    File.Write(live .. "requests.json", json.serialize({protocol=1, request_id=requestId, translate=true, source_language=sourceLanguage, target_language=targetLanguage, records=records}))
    for identity in pairs(queued) do sent[identity]=true; sentCount=sentCount+1 end
    queued, queuedCount, queuedBytes, dirty, pending = {}, 0, 0, false, true
    print("[AbyssTextLive] " .. Ui("已请求试译；请保持桌面工作台运行。条数：", "Translation requested. Keep the desktop workbench running. Records: ") .. #records)
end
local function Begin()
    local configured, err = pcall(ReadSettings)
    if not configured then Warn("settings", Ui("无法读取语言设置：", "Cannot read language settings: ") .. tostring(err)) end
    if sourceLanguage == targetLanguage then Warn("same", Ui("源语言与目标语言相同，请在桌面切换。", "Source and target languages match. Change them in the desktop workbench.")) return end
    active, pending = true, false
    if not installed then InstallPatches() end
    UpdateButton()
    local ok, err = pcall(CollectLanguageKeys)
    if not ok then Warn("collect", Ui("语言键采集不可用，继续采集原生界面与字体文字：", "Language-key capture unavailable; continuing with native controls and font strings: ") .. tostring(err)) end
    -- Let one native frame render; no synchronous translation in the draw loop.
    Timer.Wait(function()
        local scanned = 0
        local function Walk(component)
            if scanned >= 3000 then return end
            scanned = scanned + 1
            CollectControls(component)
            if component.Children ~= nil then
                for child in component.Children do Walk(child) end
            end
        end
        pcall(function() Walk(GUI.Canvas) end)
        local sentOk, sendError = pcall(SendRequest)
        if not sentOk then Warn("send", Ui("无法写入翻译请求：", "Cannot write translation request: ") .. tostring(sendError)) end
    end, 800)
end
local function Stop()
    active, pending, dirty = false, false, false
    for component, old in pairs(originals) do
        pcall(function() if TextValue(component.Text) == old.display then component.Text = old.value end end)
    end
    originals, translations, translatedValues, queued, sent, controls = {}, {}, {}, {}, {}, {}
    queuedCount, controlCount = 0, 0
    queuedBytes, sentCount = 0, 0
    for index, signature in ipairs(patchSignatures) do
        pcall(Hook.RemovePatch,"abysstext.draw." .. index,"Barotrauma.ScalableFont","DrawString",signature,Hook.HookMethodType.Before)
    end
    pcall(Hook.RemovePatch,"abysstext.controls","Barotrauma.GUI","AddToUpdateList",{"Barotrauma.GUIComponent"},Hook.HookMethodType.Before)
    installed = false
    UpdateButton()
    local ok, err = pcall(RefreshLanguage, true)
    if not ok then Warn("restore", Ui("语言缓存恢复失败：", "Language-cache restore failed: ") .. tostring(err)) end
    print("[AbyssTextLive] " .. Ui("已停止试译并移除本插件语言资源；原控件文字已尽力恢复，必要时重新打开界面。", "Preview stopped; reopen cached screens if needed."))
end
local function DrawText(_, parameters)
    if not active then return end
    local text = parameters["text"]
    if type(text) ~= "string" then return end
    local translated = Translated(text)
    if translated then parameters["text"] = translated else Observe(text) end
end
InstallPatches = function()
    -- Exact overload signatures checked against public game source. A missing
    -- overload is reported once rather than breaking game startup.
    patchSignatures = {
        {"Microsoft.Xna.Framework.Graphics.SpriteBatch","System.String","Microsoft.Xna.Framework.Vector2","Microsoft.Xna.Framework.Color","Barotrauma.ForceUpperCase","System.Boolean"},
        {"Microsoft.Xna.Framework.Graphics.SpriteBatch","System.String","Microsoft.Xna.Framework.Vector2","Microsoft.Xna.Framework.Color","System.Single","Microsoft.Xna.Framework.Vector2","Microsoft.Xna.Framework.Vector2","Microsoft.Xna.Framework.Graphics.SpriteEffects","System.Single","Barotrauma.Alignment","Barotrauma.ForceUpperCase"}
    }
    for index, signature in ipairs(patchSignatures) do
        local ok, err = pcall(function()
            Hook.Patch("abysstext.draw." .. index, "Barotrauma.ScalableFont", "DrawString", signature, DrawText, Hook.HookMethodType.Before)
        end)
        if not ok then Warn("draw" .. index, Ui("字体采集接口不可用：", "Font capture API unavailable: ") .. tostring(err)) end
    end
    local ok, err = pcall(function()
        Hook.Patch("abysstext.controls", "Barotrauma.GUI", "AddToUpdateList", {"Barotrauma.GUIComponent"},
            function(_, parameters) CollectControls(parameters["component"]) end, Hook.HookMethodType.Before)
    end)
    if not ok then Warn("controls", Ui("控件采集接口不可用：", "Control capture API unavailable: ") .. tostring(err)) end
    installed = true
end
Game.AddCommand("abyss_translate", "译潜：试译源语言 / Translate source text via desktop", Begin)
Game.AddCommand("abyss_stop", "译潜：停止恢复 / Stop and restore", Stop)
Game.AddCommand("abyss_apply", "译潜：刷新语言资源 / Reload companion text pack", function() pcall(RefreshLanguage, false) end)
Timer.Wait(function()
    pcall(ReadSettings)
    pcall(RefreshLanguage, true)
    local ok, err = pcall(function()
        button = GUI.Button(GUI.RectTransform(Vector2(0.14, 0.04), GUI.Canvas, GUI.Anchor.TopRight), "译潜 · 一键试译")
        pcall(function() button.Color = Color(112, 74, 130) end)
        button.OnClicked = function() if active then Stop() else Begin() end return true end
        UpdateButton()
    end)
    if not ok then Warn("button", Ui("按钮创建不可用，请使用 F3 命令 abyss_translate：", "Button unavailable. Use F3 command abyss_translate: ") .. tostring(err)) end
end, 1000)
Hook.Add("think", "abysstext.live", function()
    if button ~= nil then pcall(function() button.AddToGUIUpdateList() end) end
    local now = Timer.GetTime()
    if not active then
        if now >= nextSettings then nextSettings=now+2; pcall(ReadSettings) end
        return
    end
    if now >= nextPoll then
        nextPoll = now + 1
        local ok, err = pcall(function()
            if File.Exists(live .. "response.json") then
                local response = json.parse(File.Read(live .. "response.json"))
                if response.protocol == 1 and response.request_id == requestId then
                    if response.revision ~= revision then
                        revision = response.revision
                        for source, target in pairs(response.translations or {}) do
                            translations[source] = target
                            translatedValues[target] = true
                        end
                        RefreshLanguage(false)
                        ApplyControls()
                    end
                    if response.complete ~= false then pending = false end
                end
            end
        end)
        -- The desktop writes atomically, but a sharing violation can still be transient.
        if not ok then Warn("poll", Ui("桥接刷新暂不可用：", "Bridge refresh temporarily unavailable: ") .. tostring(err)) end
    end
    if not pending and now >= nextSend then
        nextSend = now + 2
        local sentOk, sendError = pcall(SendRequest)
        if not sentOk then Warn("send", Ui("无法写入翻译请求：", "Cannot write translation request: ") .. tostring(sendError)) end
    end
end)
