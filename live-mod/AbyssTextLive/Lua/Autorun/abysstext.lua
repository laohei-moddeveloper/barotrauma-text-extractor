-- Optional CLIENT module. Never executes or rewrites another mod's scripts.
-- Translation stays in the desktop process; this module makes no HTTP requests.
if not CLIENT then return end
local root = tostring(... or ""):gsub("\\", "/"):gsub("/+$", "")
if root == "" then return end
local live = root .. "/Live/"
local active, pending, dirty = false, false, false
local nextPoll, nextSend, serial, nextSettings = 0, 0, 0, 0
local requestId, revision = "", ""
local sessionId = ""
local languageRevision, hadLanguageKeys = "", false
local applyQueue, applyIndex, responseRaw = {}, 1, ""
local translations, translatedValues, queued, sent, controls, originals = {}, {}, {}, {}, {}, {}
local queuedCount, controlCount = 0, 0
local queuedBytes, sentCount = 0, 0
local patchSignatures, installed = {}, false
local InstallPatches
local preload, preloadSteps = nil, 0
local lastError, translatedCount, nextStatus = "", 0, 0
local captureTime, captureBudget, captureAfter = 0, 100, {}
local uiLanguage, sourceLanguage, targetLanguage = "zh", "English", "Simplified Chinese"
local button, languageFile
local richString
local function Canvas()
    -- LuaCs exposes GUI.Canvas as a constructor; the actual canvas instance is
    -- GUI.GUI.Canvas. Lightweight engine fixtures expose it directly.
    if GUI.GUI ~= nil then return GUI.GUI.Canvas end
    return GUI.Canvas
end
pcall(function()
    LuaUserData.RegisterType("Barotrauma.RichString")
    richString = LuaUserData.CreateStatic("Barotrauma.RichString")
end)
for _, typeName in ipairs({"Barotrauma.TextPack", "Barotrauma.TextPack+Text", "Barotrauma.AfflictionPrefab+Description"}) do
    pcall(LuaUserData.RegisterType,typeName)
end
local warned = {}
local function Warn(key, message)
    if warned[key] then return end
    warned[key] = true
    lastError=message
    print("[AbyssTextLive] " .. message)
    pcall(function() File.Write(live .. "last-error.txt", "[AbyssTextLive] " .. message) end)
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
    if not text:find("%d") then return nil end
    local template, values = Signature(text)
    local translated = translations[template]
    if not translated then return nil end
    return translated:gsub("%[abyss_value_(%d+)%]",function(index) return values[tonumber(index)] or "" end)
end
local function Observe(text, key, priority)
    if not active or type(text) ~= "string" or #text < 2 or #text > 20000 then return end
    if text:find("译潜 · ",1,true)==1 or text:find("AbyssText · ",1,true)==1 then return end
    -- MoonSharp uses .NET strings, not UTF-8 byte strings. Match Han directly.
    if sourceLanguage=="English" and (targetLanguage=="Simplified Chinese" or targetLanguage=="Traditional Chinese") and text:find("[㐀-䶿一-鿿]") then return end
    if not (text:match("%a") or text:match("[\128-\255]")) or translatedValues[text] or translations[text] then return end
    if key == nil or key == "" then text = Signature(text) end
    if translatedValues[text] or translations[text] then return end
    local identity = (key or "") .. "\0" .. text
    priority=priority or (key and key~="" and 3 or 1)
    if queued[identity] then queued[identity].priority=math.min(queued[identity].priority,priority);return end
    if sent[identity]~=nil and (priority~=0 or sent[identity]==0) then return end
    if queuedCount >= 10000 or sentCount >= 20000 or queuedBytes + #text + #(key or "") > 1000000 then return end
    queued[identity] = {text=text, key=key or "",priority=priority}
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
    local function Budget()
        preloadSteps=preloadSteps+1
        if preloadSteps>=32 or queuedCount>=64 then preloadSteps=0;coroutine.yield() end
    end
    local current = {}
    local targetPacks = PacksFor(targetLanguage)
    if targetPacks ~= nil then
        for pack in targetPacks do
            for pair in pack.Texts do
                local key = tostring(pair.Key):lower()
                current[key] = current[key] or {}
                for value in pair.Value do current[key][tostring(value.String)] = true;Budget() end
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
                Budget()
            end
        end
    end
end
local function CollectPrefabs()
    -- Public loaded prefab registries cover inventories, status definitions and
    -- creature definitions before those objects appear on screen.
    for _, registry in ipairs({"ItemPrefab","AfflictionPrefab","CharacterPrefab","MissionPrefab","JobPrefab"}) do
        local static=_G[registry]
        if static==nil then
            pcall(function()
                LuaUserData.RegisterType("Barotrauma."..registry)
                static=LuaUserData.CreateStatic("Barotrauma."..registry)
            end)
        end
        if static ~= nil then
            local ok, err=pcall(function()
                local collection=static.Prefabs
                if collection==nil then return end
                for prefab in collection do
                    local function QueueValue(value,key)
                        local text=TextValue(value)
                        local localized=(targetLanguage=="Simplified Chinese" or targetLanguage=="Traditional Chinese") and text:find("[㐀-䶿一-鿿]")
                        if not localized then Observe(text,key,2) end
                    end
                    for _, field in ipairs({"Name","Description","CauseOfDeathDescription","SelfCauseOfDeathDescription","SuccessMessage","FailureMessage"}) do
                        pcall(function()
                            -- Names already displayed in Chinese need no English->Chinese request.
                            QueueValue(prefab[field])
                        end)
                    end
                    if registry=="AfflictionPrefab" then
                        pcall(function()
                            for description in prefab.Descriptions do QueueValue(description.Text,tostring(description.TextTag)) end
                        end)
                    elseif registry=="MissionPrefab" then
                        pcall(function() for message in prefab.Messages do QueueValue(message) end end)
                    end
                    preloadSteps=preloadSteps+1
                    if preloadSteps>=32 or queuedCount>=64 then preloadSteps=0;coroutine.yield() end
                end
            end)
            if not ok then Warn("prefab"..registry,"Prefab capture unavailable: "..registry..": "..tostring(err)) end
        end
    end
end
local function ReportStatus()
    pcall(function()
        File.Write(live.."status.json",json.serialize({protocol=1,active=active,preloading=preload~=nil,
            queued_records=queuedCount,submitted_records=sentCount,translated_records=translatedCount,
            tracked_controls=controlCount,last_error=lastError}))
    end)
end
local function ResumePreload()
    if preload==nil or pending or queuedCount>=64 then return end
    local ok, err=coroutine.resume(preload)
    if not ok then Warn("preload","Loaded-text capture failed: "..tostring(err));preload=nil
    elseif coroutine.status(preload)=="dead" then preload=nil end
end
local ApplyControl
local function CollectControls(component)
    if not active or component == nil then return end
    if captureBudget<=0 or (captureAfter[component] or 0)>captureTime then return end
    local ok, isText = pcall(LuaUserData.IsTargetType, component, "Barotrauma.GUITextBlock")
    if ok and isText then
        captureBudget=captureBudget-1
        if controls[component]~=nil or controlCount<3000 then captureAfter[component]=captureTime+0.5 end
        if controls[component] == nil and controlCount < 3000 then controls[component] = true; controlCount = controlCount + 1 end
        local read, text = pcall(function() return TextValue(component.Text) end)
        if read then Observe(text) end
        if ApplyControl then ApplyControl(component) end
    end
end
ApplyControl = function(component)
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
local function ApplyControls()
    applyQueue,applyIndex={},1
    for component in pairs(controls) do applyQueue[#applyQueue+1]=component end
end
local function ApplyControlBatch()
    for i=1,32 do
        local component=applyQueue[applyIndex]
        if component==nil then applyQueue={};applyIndex=1;return end
        ApplyControl(component);applyIndex=applyIndex+1
    end
end
local function SendRequest()
    if not active or not dirty then return end
    local records = {}
    local candidates = {}
    for identity, record in pairs(queued) do
        if not pending or record.priority==0 then candidates[#candidates+1]={identity=identity,record=record} end
    end
    table.sort(candidates,function(a,b) return a.record.priority<b.record.priority end)
    for i=1,math.min(8,#candidates) do records[#records+1]=candidates[i].record end
    if #records == 0 then return end
    serial = serial + 1
    requestId = tostring(Timer.GetTime()) .. "." .. tostring(serial)
    File.Write(live .. "requests.json", json.serialize({protocol=1, session_id=sessionId,request_id=requestId, translate=true, source_language=sourceLanguage, target_language=targetLanguage, records=records}))
    for i=1,#records do
        local identity=candidates[i].identity
        if sent[identity]==nil then sentCount=sentCount+1 end
        sent[identity]=records[i].priority
        queuedBytes=queuedBytes-#queued[identity].text-#queued[identity].key
        queued[identity]=nil;queuedCount=queuedCount-1
    end
    dirty,pending=queuedCount>0,true
    print("[AbyssTextLive] " .. Ui("已请求试译；请保持桌面工作台运行。条数：", "Translation requested. Keep the desktop workbench running. Records: ") .. #records)
end
local function Begin()
    if active then return end
    local configured, err = pcall(ReadSettings)
    if not configured then Warn("settings", Ui("无法读取语言设置：", "Cannot read language settings: ") .. tostring(err)) end
    if sourceLanguage == targetLanguage then Warn("same", Ui("源语言与目标语言相同，请在桌面切换。", "Source and target languages match. Change them in the desktop workbench.")) return end
    active, pending = true, false
    responseRaw,revision="",""
    sessionId=tostring(Timer.GetTime())..".session."..tostring(serial+1)
    if not installed then InstallPatches() end
    UpdateButton()
    preload=coroutine.create(function()
        CollectPrefabs()
        local ok, err=pcall(CollectLanguageKeys)
        if not ok then Warn("collect", "Language-key capture unavailable: "..tostring(err)) end
    end)
    ResumePreload()
    -- Let one native frame render; no synchronous translation in the draw loop.
    Timer.Wait(function()
        local scanned = 0
        local function Walk(component)
            if scanned >= 3000 then return end
            scanned = scanned + 1
            CollectControls(component)
            pcall(function() CollectControls(component.GUIComponent) end)
            if component.Children ~= nil then
                for child in component.Children do Walk(child) end
            end
        end
        pcall(function() Walk(Canvas()) end)
        local sentOk, sendError = pcall(SendRequest)
        if not sentOk then Warn("send", Ui("无法写入翻译请求：", "Cannot write translation request: ") .. tostring(sendError)) end
    end, 800)
end
local function Stop()
    active, pending, dirty = false, false, false
    preload=nil
    applyQueue,applyIndex,responseRaw={},1,""
    languageRevision,hadLanguageKeys,revision="",false,""
    for component, old in pairs(originals) do
        pcall(function() if TextValue(component.Text) == old.display then component.Text = old.value end end)
    end
    originals, translations, translatedValues, queued, sent, controls = {}, {}, {}, {}, {}, {}
    captureAfter={}
    queuedCount, controlCount = 0, 0
    translatedCount=0
    queuedBytes, sentCount = 0, 0
    for index, signature in ipairs(patchSignatures) do
        pcall(Hook.RemovePatch,"abysstext.draw." .. index,"Barotrauma.ScalableFont","DrawString",signature,Hook.HookMethodType.Before)
    end
    pcall(Hook.RemovePatch,"abysstext.controls","Barotrauma.GUI","AddToUpdateList",{"Barotrauma.GUIComponent"},Hook.HookMethodType.Before)
    pcall(Hook.RemovePatch,"abysstext.textdraw","Barotrauma.GUITextBlock","Draw",{"Microsoft.Xna.Framework.Graphics.SpriteBatch"},Hook.HookMethodType.Before)
    pcall(Hook.RemovePatch,"abysstext.tooltip","Barotrauma.GUIComponent","DrawToolTip",{"Microsoft.Xna.Framework.Graphics.SpriteBatch","Barotrauma.RichString","Microsoft.Xna.Framework.Rectangle","Barotrauma.Anchor","Barotrauma.Pivot"},Hook.HookMethodType.Before)
    installed = false
    UpdateButton()
    local ok, err = pcall(RefreshLanguage, true)
    if not ok then Warn("restore", Ui("语言缓存恢复失败：", "Language-cache restore failed: ") .. tostring(err)) end
    print("[AbyssTextLive] " .. Ui("已停止试译并移除本插件语言资源；原控件文字已尽力恢复，必要时重新打开界面。", "Preview stopped; reopen cached screens if needed."))
    ReportStatus()
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
    -- Popup/dropdown controls may not live below GUI.Canvas. Observe actual
    -- native text drawing too, and apply dictionary results to newly drawn
    -- controls without waiting for another desktop response.
    local textOk, textErr = pcall(function()
        Hook.Patch("abysstext.textdraw", "Barotrauma.GUITextBlock", "Draw", {"Microsoft.Xna.Framework.Graphics.SpriteBatch"},
            function(instance) CollectControls(instance) end, Hook.HookMethodType.Before)
    end)
    if not textOk then Warn("textdraw", Ui("动态文字控件接口不可用：", "Dynamic text-control API unavailable: ") .. tostring(textErr)) end
    local tooltipOk,tooltipErr=pcall(function()
        Hook.Patch("abysstext.tooltip","Barotrauma.GUIComponent","DrawToolTip",
            {"Microsoft.Xna.Framework.Graphics.SpriteBatch","Barotrauma.RichString","Microsoft.Xna.Framework.Rectangle","Barotrauma.Anchor","Barotrauma.Pivot"},
            function(_,parameters)
                if not active or richString==nil then return end
                local original=TextValue(parameters["toolTip"])
                local function Segment(text)
                    local leading,body,trailing=text:match("^(%s*)(.-)(%s*)$")
                    if body=="" then return text end
                    local translated=Translated(body)
                    if translated then return leading..translated..trailing end
                    Observe(body,nil,0);return text
                end
                local target=original:gsub("[^\r\n]+",function(line)
                    local parts,pos={},1
                    while true do
                        local first,last=line:find("‖.-‖",pos)
                        if not first then parts[#parts+1]=Segment(line:sub(pos));break end
                        parts[#parts+1]=Segment(line:sub(pos,first-1));parts[#parts+1]=line:sub(first,last);pos=last+1
                    end
                    return table.concat(parts)
                end)
                if target~=original then parameters["toolTip"]=richString.Rich(target) end
            end,Hook.HookMethodType.Before)
    end)
    if not tooltipOk then Warn("tooltip","Tooltip capture unavailable: "..tostring(tooltipErr)) end
    installed = true
end
Game.AddCommand("abyss_translate", "译潜：试译源语言 / Translate source text via desktop", Begin)
Game.AddCommand("abyss_stop", "译潜：停止恢复 / Stop and restore", Stop)
Game.AddCommand("abyss_apply", "译潜：刷新语言资源 / Reload companion text pack", function() pcall(RefreshLanguage, false) end)
Timer.Wait(function()
    pcall(ReadSettings)
    pcall(RefreshLanguage, true)
    local ok, err = pcall(function()
        button = GUI.Button(GUI.RectTransform(Vector2(0.14, 0.04), Canvas(), GUI.Anchor.TopRight), "译潜 · 一键试译")
        pcall(function() button.Color = Color(112, 74, 130) end)
        button.OnClicked = function() if active then Stop() else Begin() end return true end
        UpdateButton()
    end)
    if not ok then Warn("button", Ui("按钮创建不可用，请使用 F3 命令 abyss_translate：", "Button unavailable. Use F3 command abyss_translate: ") .. tostring(err)) end
end, 1000)
Hook.Add("think", "abysstext.live", function()
    if button ~= nil then pcall(function() button.AddToGUIUpdateList() end) end
    local now = Timer.GetTime()
    captureTime,captureBudget=now,100
    if now>=nextStatus then nextStatus=now+2;ReportStatus() end
    if not active then
        if now >= nextSettings then nextSettings=now+2; pcall(ReadSettings) end
        return
    end
    ApplyControlBatch()
    if now >= nextPoll then
        nextPoll = now + 1
        local ok, err = pcall(function()
            if File.Exists(live .. "response.json") then
                local raw=File.Read(live .. "response.json")
                if raw==responseRaw then return end
                local response = json.parse(raw)
                if response.protocol == 1 and response.request_id == requestId then
                    responseRaw=raw
                    if response.revision ~= revision then
                        revision = response.revision
                        for source, target in pairs(response.translations or {}) do
                            if translations[source]==nil then translatedCount=translatedCount+1 end
                            translations[source] = target
                            translatedValues[target] = true
                        end
                        if response.language_revision==nil then
                            RefreshLanguage(false) -- Compatibility with older workbenches.
                        elseif response.language_revision~=languageRevision then
                            local hasKeys=(response.keys or 0)>0
                            if hasKeys or hadLanguageKeys then RefreshLanguage(false) end
                            hadLanguageKeys=hasKeys;languageRevision=response.language_revision
                        end
                        ApplyControls()
                        ApplyControlBatch()
                    end
                    if response.complete ~= false then pending = false end
                end
            end
        end)
        -- The desktop writes atomically, but a sharing violation can still be transient.
        if not ok then Warn("poll", Ui("桥接刷新暂不可用：", "Bridge refresh temporarily unavailable: ") .. tostring(err)) end
    end
    if now >= nextSend then
        nextSend = now + 2
        ResumePreload()
        local sentOk, sendError = pcall(SendRequest)
        if not sentOk then Warn("send", Ui("无法写入翻译请求：", "Cannot write translation request: ") .. tostring(sendError)) end
    end
end)
-- Keep the one-click session active across rounds; only explicit Stop restores
-- original text. Re-scan newly loaded definitions without discarding the cache.
Hook.Add("roundStart", "abysstext.round", function()
    if active then
        preload=coroutine.create(function() CollectPrefabs();CollectLanguageKeys() end)
    end
end)
