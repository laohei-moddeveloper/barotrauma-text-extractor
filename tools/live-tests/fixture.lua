CLIENT = true
now, timers, commands, patches, hooks, disk, writes, versions = 0, {}, {}, {}, {}, {}, 0, 0
root = "/LocalMods/AbyssTextLive"
Timer = {GetTime=function() return now end, Wait=function(fn,delay) timers[#timers+1]=fn end}
function FlushTimers()
    local pending = timers
    timers = {}
    for _, fn in ipairs(pending) do fn() end
end
File = {Exists=function(path) return disk[path]~=nil end, Read=function(path) return disk[path] end,
    Write=function(path,text) disk[path]=text;if path:find('requests.json',1,true) then writes=writes+1 end end}
Game = {AddCommand=function(name,help,fn) commands[name]=fn end}
Hook = {HookMethodType={Before=0},
    Add=function(name,id,fn) hooks[name]=fn end,
    Patch=function(id,class,method,types,fn,kind) patches[id]=fn end,
    RemovePatch=function(id,class,method,types,kind) patches[id]=nil end}
LuaUserData = {
    RegisterType=function() end,
    CreateStatic=function() return {Rich=function(value) return value end} end,
    IsTargetType=function(value,name)
        if name=="Barotrauma.TextFile" then return value.isText==true end
        if name=="Barotrauma.GUITextBlock" then return value.isControl==true end
        return false
    end}
language = {isText=true,Path={Value=root.."/Live/Translations.xml"},loaded=true,
    LoadFile=function() language.loaded=true end, UnloadFile=function() language.loaded=false end}
ContentPackageManager = {EnabledPackages={All={{Dir=root,Files={language}}}}}
TextManager = {
    DefaultLanguage="English",
    AvailableLanguages={"English","Simplified Chinese"},
    IncrementLanguageVersion=function() versions=versions+1 end,
    GetAllTagTextPairs=function() return {{Key="already",Value="已有汉化"}} end,
    TextPacks={["Simplified Chinese"]={{Texts={{Key="already",Value={{String="已有汉化"}}}}}},English={{Texts={{Key="entityname.tool",Value={{String="Tool"}}},{Key="already",Value={{String="Already localized"}}}}}}}}
control = {isControl=true,Text="Open hatch",Children={}}
GUI = {Canvas={Children={control}},Anchor={TopRight=1},
    RectTransform=function(...) return {} end,
    Button=function(rect,text) gameButton={Text=text,AddToGUIUpdateList=function() end};return gameButton end}
Vector2=function(x,y) return {} end
Color=function(r,g,b) return {} end
function Response(request,revision,complete,translations)
    disk[root.."/Live/response.json"]=json.serialize({protocol=1,request_id=request,revision=revision,complete=complete,translations=translations})
end
function RequestData() return json.parse(disk[root.."/Live/requests.json"]) end
function Tick(seconds) now=now+seconds;hooks.think() end

function Delta(request,sequence,translations,removed,complete)
    disk[root.."/Live/response.json"]=json.serialize({protocol=1,request_id=request.request_id,
        session_id=request.session_id,source_language=request.source_language,target_language=request.target_language,
        delta=true,sequence=sequence,base_sequence=sequence-1,reset=sequence==1,revision=tostring(sequence),
        language_revision='empty-xml',keys=0,complete=complete==true,translations=translations,removed=removed or {}})
end

-- Broad rendering scenarios opt in; production defaults to native scanning.
disk[root.."/Live/settings.json"]=json.serialize({compatibility_capture=true})
