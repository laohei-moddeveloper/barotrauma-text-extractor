-- Optional CLIENT module. Never executes or rewrites another mod's scripts.
-- Translation stays in the desktop process; this module makes no HTTP requests.
if not CLIENT then return end
local root = tostring(... or ""):gsub("\\", "/"):gsub("/+$", "")
if root == "" then return end
local live = root .. "/Live/"
local active, pending, dirty = false, false, false
local nextPoll, nextSend, serial, nextSettings = 0, 0, 0, 0
local requestId, revision = "", ""
local nextRequestNotice=0
local sessionId = ""
local accepted, generation = false, 0
local appliedSequence, nextPreload, lastQueueVisits = 0, 0, 0
local controlScan = nil
local nextControlScan,lastScanNodes,renderCallbacks=0,0,0
local compatibilityCapture=false
local dictionaryEpoch=0
local controlSlots,freeSlots,controlCursor={}, {}, 1
local lastControlVisits=0
local patternBudget,patternChars=64,8192
local pendingLanguage,nextLanguageRefresh,languagePendingAt,languageQuietAt=false,0,0,0
local languageReloads=0
local observeBudget=64
local targetUses={}
local ignoredCache
local function NewBuckets()
    local result={}
    for priority=0,3 do result[priority]={items={},head=1,tail=0} end
    return result
end
local buckets=NewBuckets()
local function Enqueue(identity,priority)
    local bucket=buckets[priority];bucket.tail=bucket.tail+1;bucket.items[bucket.tail]=identity
end
local languageRevision, hadLanguageKeys = "", false
local responseRaw = ""
local translations, translatedValues, queued, sent, controls, originals = {}, {}, {}, {}, {}, {}
local queuedCount, controlCount = 0, 0
local queuedBytes, sentCount = 0, 0
local patchSignatures, installed = {}, false
local InstallPatches
local preload, preloadSteps = nil, 0
local lastError, translatedCount, nextStatus = "", 0, 0
local lastErrorKey=""
local captureTime,captureBudget=0,32
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
    lastError,lastErrorKey=message,key
    if warned[key] then return end
    warned[key] = true
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
        compatibilityCapture=settings.compatibility_capture==true
        local function Canonical(name)
            local lower=tostring(name):lower()
            local aliases={en="English",["zh-cn"]="Simplified Chinese",["zh-tw"]="Traditional Chinese"}
            if aliases[lower] then return aliases[lower] end
            for _, language in ipairs({"English","Simplified Chinese","Traditional Chinese","Japanese","Korean","Russian","German","French","Spanish","Brazilian Portuguese","Polish","Ukrainian","Turkish","Italian","Czech","Hungarian","Romanian"}) do
                if language:lower()==lower then return language end
            end
            return tostring(name)
        end
        sourceLanguage,targetLanguage=Canonical(sourceLanguage),Canonical(targetLanguage)
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
local function TextValue(value,localized)
    if type(value) == "string" then return value end
    if value == nil then return "" end
    if localized then
        -- Loaded prefab fields are LocalizedString, not RichString. Avoid
        -- exception-driven NestedStr/SanitizedValue probing for every field.
        local ok,text=pcall(function() return value.Value end)
        if ok and text~=nil then return tostring(text) end
        return tostring(value)
    end
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
-- Fixed-size render caches. They retain strings/results, never GUI objects.
local function Cache(limit,maxChars)
    return {rows={},ring={},cursor=1,count=0,chars=0,limit=limit,maxChars=maxChars}
end
local numericCache,tooltipCache=Cache(512,262144),Cache(64,262144)
ignoredCache=Cache(1024,131072)
local function Forget(cache,key)
    local previous=cache.rows[key]
    if previous then
        cache.chars=cache.chars-previous.cost;cache.count=cache.count-1
        cache.rows[key]=nil;cache.ring[previous.slot]=nil
    end
end
local function Remember(cache,key,value)
    local cost=#key+(value.weight or 0)
    Forget(cache,key)
    if cost>cache.maxChars then return end
    local function Remove(slot)
        local previous=cache.ring[slot]
        if previous then Forget(cache,previous) end
    end
    Remove(cache.cursor)
    while cache.chars+cost>cache.maxChars do
        cache.cursor=cache.cursor%cache.limit+1;Remove(cache.cursor)
    end
    value.cost=cost;value.slot=cache.cursor;cache.rows[key]=value;cache.ring[cache.cursor]=key
    cache.chars=cache.chars+cost;cache.count=cache.count+1
    cache.cursor=cache.cursor%cache.limit+1
end
local function Translated(text)
    if translations[text] then return translations[text] end
    if translatedValues[text] or type(text)~="string" or #text>20000 then return nil end
    local row=numericCache.rows[text]
    if not row then
        if patternBudget<=0 or #text>patternChars then return nil,true end
        patternBudget=patternBudget-1;patternChars=patternChars-#text
        local template,values=text,{}
        if text:find("%d") then template,values=Signature(text) end
        row={template=template,values=values,epoch=-1}
    end
    if row.epoch~=dictionaryEpoch then
        local target=translations[row.template]
        row.result=target and target:gsub("%[abyss_value_(%d+)%]",function(index) return row.values[tonumber(index)] or "" end) or false
        row.epoch=dictionaryEpoch
        row.weight=#row.template+(row.result and #row.result or 0)
        for _,value in ipairs(row.values) do row.weight=row.weight+#value end
        Remember(numericCache,text,row)
    end
    return row.result or nil
end
local function PutTranslation(source,target)
    local old=translations[source]
    if old==target then return end
    if old~=nil then
        targetUses[old]=(targetUses[old] or 1)-1
        if targetUses[old]<=0 then targetUses[old]=nil;translatedValues[old]=nil end
        translatedCount=translatedCount-1
    end
    dictionaryEpoch=dictionaryEpoch+1
    translations[source]=target
    if target~=nil then
        targetUses[target]=(targetUses[target] or 0)+1;translatedValues[target]=true
        translatedCount=translatedCount+1
    end
end
-- Owner paths are public game metadata, read once during bounded preload.
-- No filesystem scan or owner lookup is performed inside draw hooks.
local function ModOwner(package)
    local owner=""
    pcall(function()
        local path=tostring(package.Path):gsub("\\","/")
        local id=path:match("/(%d+)/[^/]+$")
        if id and #id>=8 and #id<=20 then owner=id end
    end)
    return owner
end

local function Observe(text, key, priority, context, modId)
    if not active or type(text) ~= "string" or #text < 2 or #text > 20000 then return end
    if text:find("译潜 · ",1,true)==1 or text:find("AbyssText · ",1,true)==1 then return end
    priority=priority or (key and key~="" and 3 or 1)
    if translatedValues[text] or translations[text] or ignoredCache.rows[text] then return end
    local rawIdentity=key and key~="" and (key.."\0"..text) or text
    if queued[rawIdentity] then
        if modId and modId~="" and not queued[rawIdentity].mod_id then queued[rawIdentity].mod_id=modId end
        if priority<queued[rawIdentity].priority then queued[rawIdentity].priority=priority;Enqueue(rawIdentity,priority) end
        return
    end
    if sent[rawIdentity]~=nil and (priority~=0 or sent[rawIdentity]==0) then return end
    if observeBudget<=0 then return end
    observeBudget=observeBudget-1
    -- MoonSharp uses .NET strings, not UTF-8 byte strings. Match Han directly.
    if sourceLanguage=="English" and (targetLanguage=="Simplified Chinese" or targetLanguage=="Traditional Chinese") and text:find("[㐀-䶿一-鿿]") then
        Remember(ignoredCache,text,{})
        return
    end
    if not (text:match("%a") or text:match("[\128-\255]")) or translatedValues[text] or translations[text] then return end
    if (key==nil or key=="") and #text<=2048 then
        local memo=numericCache.rows[text]
        if not memo then Translated(text);memo=numericCache.rows[text] end
        if not memo then return end -- exhausted this frame's normalization budget
        text=memo.template
    end
    if translatedValues[text] or translations[text] then return end
    local identity=key and key~="" and (key.."\0"..text) or text
    if queued[identity] then
        if priority<queued[identity].priority then queued[identity].priority=priority;Enqueue(identity,priority) end
        return
    end
    if sent[identity]~=nil and (priority~=0 or sent[identity]==0) then return end
    if queuedCount >= 10000 or sentCount >= 20000 or queuedBytes + #text + #(key or "") > 1000000 then return end
    queued[identity] = {text=text, key=key or "",priority=priority,context=context or "Visible GUI",mod_id=modId or ""}
    Enqueue(identity,priority)
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
    pendingLanguage=false
    if not unloadOnly then languageReloads=languageReloads+1;nextLanguageRefresh=Timer.GetTime()+5 end
end
local function QueueLanguageRefresh(now)
    if not pendingLanguage then languagePendingAt=now end
    pendingLanguage=true;languageQuietAt=now+0.5
end
local function FlushLanguageRefresh(now)
    if pendingLanguage and now>=nextLanguageRefresh and (now>=languageQuietAt or now-languagePendingAt>=5) then
        RefreshLanguage(false)
    end
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
        local owner="";pcall(function() owner=ModOwner(pack.ContentFile.ContentPackage) end)
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
                if not localized then Observe(text,key,nil,nil,owner) end
                Budget()
            end
        end
    end
end
local function CollectPrefabs()
    -- Avoid exception-driven probing and per-prefab metadata allocations.
    local fields={
        ItemPrefab={"Name","Description"},CharacterPrefab={"Name"},
        AfflictionPrefab={"Name","CauseOfDeathDescription","SelfCauseOfDeathDescription"},
        MissionPrefab={"Name","Description","SuccessMessage","FailureMessage"},
        JobPrefab={"Name","Description"}}
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
                    local owner="";pcall(function() owner=ModOwner(prefab.ContentPackage) end)
                    local function QueueValue(value,key,context)
                        local text=TextValue(value,true)
                        local localized=(targetLanguage=="Simplified Chinese" or targetLanguage=="Traditional Chinese") and text:find("[㐀-䶿一-鿿]")
                        if not localized then Observe(text,key,2,context,owner) end
                        preloadSteps=preloadSteps+1
                        if preloadSteps>=32 or queuedCount>=64 then preloadSteps=0;coroutine.yield() end
                    end
                    for _, field in ipairs(fields[registry]) do
                        pcall(function()
                            -- Names already displayed in Chinese need no English->Chinese request.
                            QueueValue(prefab[field],nil,registry.."."..field)
                        end)
                    end
                    if registry=="AfflictionPrefab" then
                        pcall(function()
                            for description in prefab.Descriptions do QueueValue(description.Text,tostring(description.TextTag),"AfflictionPrefab.Description") end
                        end)
                    elseif registry=="MissionPrefab" then
                        pcall(function() for message in prefab.Messages do QueueValue(message,nil,"MissionPrefab.Message") end end)
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
        File.Write(live.."status.json",json.serialize({protocol=1,runtime_build="snapshot-native-fix-20261023",active=active,preloading=preload~=nil,
            session_id=sessionId,source_language=sourceLanguage,target_language=targetLanguage,applied_sequence=appliedSequence,last_queue_visits=lastQueueVisits,
            queued_records=queuedCount,submitted_records=sentCount,translated_records=translatedCount,
            tracked_controls=controlCount,last_control_visits=lastControlVisits,
            capture_mode=compatibilityCapture and "compatibility" or "native",render_hook_calls=renderCallbacks,last_scan_nodes=lastScanNodes,
            numeric_cache_entries=numericCache.count,tooltip_cache_entries=tooltipCache.count,
            render_cache_chars=numericCache.chars+tooltipCache.chars+ignoredCache.chars,language_reloads=languageReloads,last_error=lastError}))
    end)
end
local function ResumePreload()
    if preload==nil or queuedCount>=64 then return end
    local ok, err=coroutine.resume(preload)
    if not ok then Warn("preload","Loaded-text capture failed: "..tostring(err));preload=nil
    elseif coroutine.status(preload)=="dead" then preload=nil end
end
local ApplyControl
local function DropControl(component,row)
    local old=originals[component]
    if old then pcall(function() if TextValue(component.Text)==old.display then component.Text=old.value end end) end
    originals[component]=nil;controls[component]=nil
    controlSlots[row.slot]=false;freeSlots[#freeSlots+1]=row.slot
    controlCount=controlCount-1
end
local function CollectControls(component)
    if not active or component==nil then return end
    local row=controls[component]
    if row then row.seen=captureTime end
    if captureBudget<=0 or (row and row.after>captureTime) then return end
    local ok,isText=true,row~=nil
    if not row then ok,isText=pcall(LuaUserData.IsTargetType,component,"Barotrauma.GUITextBlock") end
    if not ok or not isText then return end
    captureBudget=captureBudget-1
    -- At capacity the font hook still translates rendering. Never create an
    -- untracked restoration entry, which used to grow past the control cap.
    if not row then
        if controlCount>=3000 then return end
        local slot=table.remove(freeSlots) or (#controlSlots+1)
        row={slot=slot,seen=captureTime,after=0,epoch=-1}
        controls[component]=row;controlSlots[slot]=component;controlCount=controlCount+1
    end
    row.after=captureTime+0.5
    local read,text=pcall(function() return TextValue(component.Text) end)
    if read then Observe(text,nil,0);ApplyControl(component,text) end
end
ApplyControl = function(component,current)
    local row=controls[component]
    if not row then return end
    local ok=pcall(function()
        current=current or TextValue(component.Text)
        local old=originals[component]
        if old and current~=old.display then originals[component]=nil;old=nil end
        local source=old and TextValue(old.value) or current
        local target,deferred=Translated(source)
        if deferred then row.epoch=-1;return end
        row.source=source;row.epoch=dictionaryEpoch
        if old and target==old.display then return end
        if old then component.Text=old.value;originals[component]=nil end
        if target and component.TextGetter==nil then
            local original=old and old.value or component.Text
            if target:find("‖",1,true) then
                if richString==nil then return end
                component.Text=richString.Rich(target)
            else component.Text=target end
            originals[component]={value=original,display=TextValue(component.Text)}
        end
    end)
    if not ok then DropControl(component,row) end
end
local function ApplyControlBatch()
    lastControlVisits=0
    local size=#controlSlots
    for i=1,math.min(16,size) do
        if controlCursor>size then controlCursor=1 end
        local component=controlSlots[controlCursor];controlCursor=controlCursor+1
        lastControlVisits=lastControlVisits+1
        local row=component and controls[component]
        if row then
            if captureTime-row.seen>(compatibilityCapture and 10 or 60) then DropControl(component,row)
            elseif row.epoch~=dictionaryEpoch then
                local desired,deferred
                if row.source then desired,deferred=Translated(row.source) end
                local old=originals[component]
                if not deferred then
                    if desired~=(old and old.display or nil) then ApplyControl(component)
                    else row.epoch=dictionaryEpoch end
                end
            end
        end
    end
end
local function SendRequest()
    if not active or not dirty then return end
    -- Do not overwrite the single mailbox until the desktop has imported its
    -- records. A partial matching response acknowledges import, so visible
    -- tooltips can still take priority over accepted background work.
    if pending and not accepted then return end
    local records,candidates={},{}
    lastQueueVisits=0
    for priority=0,(pending and 0 or 3) do
        local bucket=buckets[priority]
        local cursor=bucket.head
        while cursor<=bucket.tail and #records<8 and lastQueueVisits<64 do
            local identity=bucket.items[cursor]
            local record=identity and queued[identity]
            lastQueueVisits=lastQueueVisits+1
            if record and record.priority==priority then
                records[#records+1]=record;candidates[#candidates+1]={identity=identity,priority=priority,position=cursor}
            else
                bucket.items[cursor]=nil
                if bucket.head==cursor then bucket.head=cursor+1 end
            end
            cursor=cursor+1
        end
        if #records>=8 or lastQueueVisits>=64 then break end
    end
    if #records == 0 then return end
    serial = serial + 1
    requestId = tostring(Timer.GetTime()) .. "." .. tostring(serial)
    File.Write(live .. "requests.json", json.serialize({protocol=1, session_id=sessionId,request_id=requestId, translate=true, response_mode="delta-v1",source_language=sourceLanguage, target_language=targetLanguage, records=records}))
    for i=1,#records do
        local candidate=candidates[i]
        local identity=candidate.identity
        local bucket=buckets[candidate.priority]
        bucket.items[candidate.position]=nil;bucket.head=candidate.position+1
        if bucket.head>bucket.tail then bucket.items={};bucket.head=1;bucket.tail=0 end
        if sent[identity]==nil then sentCount=sentCount+1 end
        sent[identity]=records[i].priority
        queuedBytes=queuedBytes-#queued[identity].text-#queued[identity].key
        queued[identity]=nil;queuedCount=queuedCount-1
    end
    dirty,pending,accepted=queuedCount>0,true,false
    if Timer.GetTime()>=nextRequestNotice then
        nextRequestNotice=Timer.GetTime()+5
        print("[AbyssTextLive] " .. Ui("已请求试译；请保持桌面工作台运行。条数：", "Translation requested. Keep the desktop workbench running. Records: ") .. #records)
    end
end
local function StartControlScan()
    controlScan=coroutine.create(function()
        local scanned=0
        local step=compatibilityCapture and 32 or 8
        local function Walk(component)
            if component==nil or scanned>=3000 then return end
            scanned=scanned+1;lastScanNodes=lastScanNodes+1
            local ok,visible=pcall(function() return component.Visible end)
            if ok and visible==false then
                if scanned%step==0 then coroutine.yield() end
                return
            end
            CollectControls(component)
            if scanned%step==0 then coroutine.yield() end
            if component.Children~=nil then for child in component.Children do Walk(child) end end
        end
        pcall(function() Walk(Canvas()) end)
    end)
end
local function ResumeControlScan(now)
    if not controlScan then return end
    local ok,err=coroutine.resume(controlScan)
    if not ok then Warn("controls-scan",tostring(err));controlScan=nil
    elseif coroutine.status(controlScan)=="dead" then controlScan=nil end
    if not controlScan then nextControlScan=now+0.5 end
end
local function Begin()
    if active then return end
    warned,lastError={},""
    local configured, err = pcall(ReadSettings)
    if not configured then Warn("settings", Ui("无法读取语言设置：", "Cannot read language settings: ") .. tostring(err)) end
    if sourceLanguage == targetLanguage then Warn("same", Ui("源语言与目标语言相同，请在桌面切换。", "Source and target languages match. Change them in the desktop workbench.")) return end
    active, pending = true, false
    generation=generation+1
    local ownGeneration=generation
    accepted=false
    appliedSequence,nextPreload=0,0
    nextPoll,nextSend,nextRequestNotice=0,0,0
    patternBudget,patternChars=64,8192
    responseRaw,revision="",""
    nextControlScan=Timer.GetTime()+1;renderCallbacks=0
    sessionId=tostring(Timer.GetTime())..".session."..tostring(generation).."."..tostring(serial+1)
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
        if not active or generation~=ownGeneration then return end
        StartControlScan();lastScanNodes=0
        ResumeControlScan(Timer.GetTime())
        local sentOk, sendError = pcall(SendRequest)
        if not sentOk then Warn("send", Ui("无法写入翻译请求：", "Cannot write translation request: ") .. tostring(sendError)) end
    end, 800)
end
local function Stop()
    active, pending, dirty = false, false, false
    generation=generation+1
    accepted=false
    preload=nil;controlScan=nil;appliedSequence=0;buckets=NewBuckets()
    responseRaw=""
    controlSlots,freeSlots,controlCursor={}, {}, 1
    numericCache,tooltipCache=Cache(512,262144),Cache(64,262144)
    dictionaryEpoch=dictionaryEpoch+1
    pendingLanguage,nextLanguageRefresh,languagePendingAt,languageQuietAt=false,0,0,0
    languageReloads=0
    languageRevision,hadLanguageKeys,revision="",false,""
    for component, old in pairs(originals) do
        pcall(function() if TextValue(component.Text) == old.display then component.Text = old.value end end)
    end
    originals, translations, translatedValues, queued, sent, controls = {}, {}, {}, {}, {}, {}
    targetUses={};ignoredCache=Cache(1024,131072);observeBudget=64
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
    renderCallbacks=renderCallbacks+1
    if type(text) ~= "string" then return end
    if translatedValues[text] or ignoredCache.rows[text] then return end
    local translated = Translated(text)
    if translated then parameters["text"] = translated else Observe(text,nil,0) end
end
InstallPatches = function()
    -- Exact overload signatures checked against public game source. A missing
    -- overload is reported once rather than breaking game startup.
    if compatibilityCapture then
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
            function(_, parameters) renderCallbacks=renderCallbacks+1;CollectControls(parameters["component"]) end, Hook.HookMethodType.Before)
    end)
    if not ok then Warn("controls", Ui("控件采集接口不可用：", "Control capture API unavailable: ") .. tostring(err)) end
    -- Popup/dropdown controls may not live below GUI.Canvas. Observe actual
    -- native text drawing too, and apply dictionary results to newly drawn
    -- controls without waiting for another desktop response.
    local textOk, textErr = pcall(function()
        Hook.Patch("abysstext.textdraw", "Barotrauma.GUITextBlock", "Draw", {"Microsoft.Xna.Framework.Graphics.SpriteBatch"},
            function(instance) renderCallbacks=renderCallbacks+1;CollectControls(instance) end, Hook.HookMethodType.Before)
    end)
    if not textOk then Warn("textdraw", Ui("动态文字控件接口不可用：", "Dynamic text-control API unavailable: ") .. tostring(textErr)) end
    else patchSignatures={} end
    local tooltipOk,tooltipErr=pcall(function()
        Hook.Patch("abysstext.tooltip","Barotrauma.GUIComponent","DrawToolTip",
            {"Microsoft.Xna.Framework.Graphics.SpriteBatch","Barotrauma.RichString","Microsoft.Xna.Framework.Rectangle","Barotrauma.Anchor","Barotrauma.Pivot"},
            function(_,parameters)
                if not active or richString==nil then return end
                local original=TextValue(parameters["toolTip"])
                if #original>20000 then return end
                local cached=tooltipCache.rows[original]
                if cached and cached.epoch==dictionaryEpoch and (cached.target or captureTime<cached.retryAt) then
                    if cached.target then parameters["toolTip"]=cached.target end
                    return
                end
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
                local rendered=target~=original and richString.Rich(target) or false
                Remember(tooltipCache,original,{epoch=dictionaryEpoch,target=rendered,retryAt=captureTime+0.5,weight=#target})
                if rendered then parameters["toolTip"]=rendered end
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
    captureTime,captureBudget=now,32
    patternBudget,patternChars=64,8192
    observeBudget=64
    if now>=nextStatus then nextStatus=now+2;ReportStatus() end
    if not active then
        if now >= nextSettings then nextSettings=now+2; pcall(ReadSettings) end
        return
    end
    lastScanNodes=0
    if not compatibilityCapture and not controlScan and now>=nextControlScan then StartControlScan() end
    ResumeControlScan(now)
    if now>=nextPreload then nextPreload=now+0.05;ResumePreload() end
    if now >= nextPoll then
        nextPoll = now + 0.25
        local ok, err = pcall(function()
            if File.Exists(live .. "response.json") then
                local raw=File.Read(live .. "response.json")
                if raw==responseRaw then return end
                local response = json.parse(raw)
                -- Deltas are ordered by session-wide sequence. A newly hovered
                -- control can submit the next request while an older delta is
                -- in flight; rejecting that delta deadlocks both mailboxes.
                -- Legacy responses still require the exact request ID.
                local matchesRequest=response.request_id==requestId
                local sessionDelta=response.delta==true and response.session_id==sessionId
                    and response.source_language==sourceLanguage and response.target_language==targetLanguage
                if response.protocol == 1 and (matchesRequest or sessionDelta)
                    and (response.session_id==nil or response.session_id==sessionId)
                    and (response.source_language==nil or response.source_language==sourceLanguage)
                    and (response.target_language==nil or response.target_language==targetLanguage) then
                    if response.delta then
                        if type(response.sequence)~="number" or response.sequence~=appliedSequence+1 or response.base_sequence~=appliedSequence then return end
                        local count=0
                        for source,target in pairs(response.translations or {}) do
                            count=count+1
                            if type(source)~="string" or type(target)~="string" or #source>20000 or #target>20000 then error("Invalid translation delta") end
                        end
                        for _,source in ipairs(response.removed or {}) do
                            count=count+1;if type(source)~="string" then error("Invalid removal delta") end
                        end
                        if count>8 then error("Translation delta exceeds eight records") end
                    end
                    if response.revision ~= revision then
                        if response.delta and response.reset then translations,translatedValues,targetUses={},{},{};translatedCount=0;dictionaryEpoch=dictionaryEpoch+1 end
                        for _,source in ipairs(response.removed or {}) do
                            PutTranslation(source,nil)
                        end
                        for source, target in pairs(response.translations or {}) do
                            PutTranslation(source,target)
                        end
                        if response.language_revision==nil then
                            if now>=nextLanguageRefresh then RefreshLanguage(false) else QueueLanguageRefresh(now) end -- Legacy first load remains immediate.
                        elseif response.language_revision~=languageRevision then
                            local hasKeys=(response.keys or 0)>0
                            if hasKeys or hadLanguageKeys then QueueLanguageRefresh(now) end
                            hadLanguageKeys=hasKeys;languageRevision=response.language_revision
                        end

                    end
                    revision=response.revision;responseRaw=raw
                    if lastErrorKey=="poll" then lastError,lastErrorKey="","" end
                    -- Receiving an older translation does not acknowledge that
                    -- the desktop has imported our newer request's records.
                    if matchesRequest then accepted=true end
                    if response.delta then appliedSequence=response.sequence;ReportStatus() end
                    if matchesRequest and response.complete ~= false then pending = false end
                end
            end
        end)
        -- The desktop writes atomically, but a sharing violation can still be transient.
        if not ok then Warn("poll", Ui("桥接刷新暂不可用：", "Bridge refresh temporarily unavailable: ") .. tostring(err)) end
    end
    local refreshed,refreshError=pcall(FlushLanguageRefresh,now)
    if not refreshed then Warn("language-refresh",tostring(refreshError)) end
    ApplyControlBatch()
    if now >= nextSend then
        nextSend = now + 0.25
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
