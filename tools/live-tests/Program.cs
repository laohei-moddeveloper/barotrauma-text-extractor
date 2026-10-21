using MoonSharp.Interpreter;

if (args.Length != 1) throw new Exception("Pass live-mod/AbyssTextLive/Lua/Autorun/abysstext.lua");
string module=File.ReadAllText(args[0]);
string fixture=File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"fixture.lua"));
int checks=0;
void Check(string name,string before,string after)
{
    var script=new Script(CoreModules.Preset_Complete);
    script.Options.DebugPrint=_=>{};
    try
    {
        script.DoString(fixture+"\n"+before);
        script.Call(script.LoadString(module),DynValue.NewString("/LocalMods/AbyssTextLive"));
        script.DoString(after);
    }
    catch(InterpreterException error) { throw new Exception(name+": "+error.DecoratedMessage,error); }
    checks++;Console.WriteLine("PASS "+name);
}
Check("server no-op","CLIENT=false","assert(next(commands)==nil and next(patches)==nil and #timers==0)");
Check("startup idle no draw patches","","assert(next(patches)==nil);FlushTimers();assert(gameButton~=nil and not language.loaded)");
Check("LuaCs canvas constructor is not the canvas instance","""
local instance=GUI.Canvas
GUI.GUI={Canvas=instance}
GUI.Canvas={constructor=true}
GUI.RectTransform=function(size,parent,anchor) assert(parent==instance);return {} end
""","FlushTimers();assert(gameButton~=nil);commands.abyss_translate();FlushTimers();assert(RequestData().protocol==1)");
Check("one click collects and deduplicates native text","","""
FlushTimers();commands.abyss_translate();FlushTimers()
local data=RequestData();assert(data.protocol==1 and data.translate)
local texts={};for _,r in ipairs(data.records) do texts[r.text]=true end
assert(texts.Tool and texts['Open hatch'] and not texts['Already localized'])
assert(patches['abysstext.draw.1']~=nil and patches['abysstext.controls']~=nil)
Tick(3);assert(writes==1)
""");
Check("native control and draw text replace without overlay","","""
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Response(request.request_id,'one',true,{['Open hatch']='打开舱门',Tool='工具'})
Tick(1);assert(language.loaded and control.Text=='打开舱门')
local parameters={text='Tool'};patches['abysstext.draw.1'](nil,parameters)
assert(parameters.text=='工具')
""");
Check("numeric values reuse a translation template","","""
FlushTimers();commands.abyss_translate()
patches['abysstext.draw.1'](nil,{text='Oxygen: 80%'})
FlushTimers();local request=RequestData();local found=false
for _,r in ipairs(request.records) do if r.text=='Oxygen: [abyss_value_1]%' then found=true end end
assert(found)
Response(request.request_id,'one',true,{['Oxygen: [abyss_value_1]%']='氧气：[abyss_value_1]%'})
Tick(1)
local parameters={text='Oxygen: 75%'};patches['abysstext.draw.1'](nil,parameters)
assert(parameters.text=='氧气：75%')
""");
Check("stale response rejected","","""
FlushTimers();commands.abyss_translate();FlushTimers()
Response('older-request','one',true,{['Open hatch']='错误'})
Tick(1);assert(control.Text=='Open hatch')
""");
Check("same-revision completion acknowledged","","""
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Response(request.request_id,'one',false,{Tool='工具'});Tick(1)
patches['abysstext.draw.1'](nil,{text='New display'})
Tick(3);assert(writes==1)
Response(request.request_id,'one',true,{Tool='工具'});Tick(3)
assert(writes==2)
""");
Check("stop restores native text and removes patches","","""
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Response(request.request_id,'one',true,{['Open hatch']='打开舱门'});Tick(1)
assert(control.Text=='打开舱门')
commands.abyss_stop();assert(control.Text=='Open hatch' and not language.loaded)
assert(next(patches)==nil)
local count=writes;Tick(5);assert(writes==count)
""");
Check("missing hook APIs degrade to native commands","Hook.Patch=function() error('unsupported signature') end","FlushTimers();commands.abyss_translate();FlushTimers();assert(RequestData().protocol==1)");
Check("dropdown opened after response reuses native text translation", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Response(request.request_id,'one',true,{Balloon='气球'});Tick(1)
local popup={isControl=true,Text='Balloon',Children={}}
patches['abysstext.textdraw'](popup,{})
assert(popup.Text=='气球')
commands.abyss_stop();assert(popup.Text=='Balloon' and next(patches)==nil)
""");
Check("new dropdown text is collected and own button is excluded", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Response(request.request_id,'one',true,{});Tick(1)
patches['abysstext.textdraw']({isControl=true,Text='Barahna',Children={}},{})
patches['abysstext.textdraw']({isControl=true,Text='译潜 · 停止试译',Children={}},{})
Tick(3)
local found=false
for _,record in ipairs(RequestData().records) do
 if record.text=='Barahna' then found=true end
 assert(record.text~='译潜 · 停止试译')
end
assert(found)
""");
Check("loaded inventory buff and creature names are queued before display", """
ItemPrefab={Prefabs={{Name='Unseen wrench',Description='Repairs the hull'}}}
AfflictionPrefab={Prefabs={{Name='Unseen fever',Description='Raises temperature',Descriptions={{Text='Severe fever',TextTag='fever.severe'}}}}}
CharacterPrefab={Prefabs={{Name='Unseen crawler'}}}
MissionPrefab={Prefabs={{Name='Unseen rescue',Description='Find the missing captain',Messages={'Speak to the captain'},SuccessMessage='Rescue complete',FailureMessage='Rescue failed'}}}
JobPrefab={Prefabs={{Name='Unseen medic',Description='Treat injured crew'}}}
""", """
FlushTimers();commands.abyss_translate();FlushTimers()
local texts={};for _,record in ipairs(RequestData().records) do texts[record.text]=true end
assert(texts['Unseen wrench'] and texts['Repairs the hull'] and texts['Unseen fever'] and texts['Raises temperature'] and texts['Unseen crawler'])
assert(texts['Unseen rescue'] and texts['Find the missing captain'] and texts['Unseen medic'] and texts['Treat injured crew'])
assert(texts['Severe fever'] and texts['Speak to the captain'] and texts['Rescue complete'] and texts['Rescue failed'])
""");
Check("rich markers retained in observed source","control.Text={NestedStr={Value='‖color:1,2,3‖Warning‖color:end‖'},SanitizedValue='Warning'}","""
FlushTimers();commands.abyss_translate();FlushTimers()
local found=false
for _,r in ipairs(RequestData().records) do if r.text=='‖color:1,2,3‖Warning‖color:end‖' then found=true end end
assert(found)
""");
Check("bilingual controls and non-English source pair", """
TextManager.AvailableLanguages={"Japanese","French"}
TextManager.TextPacks={Japanese={{Texts={{Key="hello",Value={{String="こんにちは"}}}}}},French={}}
control.Text="こんにちは"
disk[root.."/Live/settings.json"]=json.serialize({ui_language="en",source_language="Japanese",target_language="French"})
""", """
FlushTimers();assert(gameButton.Text=='AbyssText · Translate')
commands.abyss_translate();FlushTimers();assert(gameButton.Text=='AbyssText · Stop')
local request=RequestData();assert(request.source_language=='Japanese' and request.target_language=='French')
local found=false;for _,record in ipairs(request.records) do if record.text=='こんにちは' then found=true end end;assert(found)
Response(request.request_id,'one',true,{['こんにちは']='Bonjour'});Tick(1);assert(control.Text=='Bonjour')
commands.abyss_stop();assert(control.Text=='こんにちは' and gameButton.Text=='AbyssText · Translate')
""");
Check("request write failure remains retryable", """
local fail=true
File.Write=function(path,text)
 if path:find('requests.json',1,true) then
  if fail then fail=false;error('temporary file lock') end
  writes=writes+1
 end
 disk[path]=text
end
""", """
FlushTimers();commands.abyss_translate();FlushTimers();assert(writes==0)
Tick(3);assert(writes==1 and #RequestData().records>0)
""");
Check("preloaded language catalog resumes across bounded requests without loss", """
TextManager.TextPacks.English={{Texts={}}}
for i=1,700 do table.insert(TextManager.TextPacks.English[1].Texts,{Key='unseen.'..i,Value={{String='Unseen label '..i}}}) end
""", """
FlushTimers();commands.abyss_translate();FlushTimers()
local seen={}
for cycle=1,60 do
 local request=RequestData()
 assert(#request.records<=16)
 for _,record in ipairs(request.records) do if record.key:find('unseen.',1,true)==1 then seen[record.key]=true end end
 Response(request.request_id,tostring(cycle),true,{})
 Tick(3)
end
local count=0;for key in pairs(seen) do count=count+1 end
assert(count==700,tostring(count))
""");
Check("one click stays active across a round and captures new mission text", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Response(request.request_id,'one',true,{Tool='工具'});Tick(3)
MissionPrefab={Prefabs={{Name='Next round mission',Description='Speak to the survivor'}}}
hooks.roundStart();Tick(3)
local texts={};for _,record in ipairs(RequestData().records) do texts[record.text]=true end
assert(texts['Next round mission'] and texts['Speak to the survivor'])
local p={text='Tool'};patches['abysstext.draw.1'](nil,p);assert(p.text=='工具')
commands.abyss_stop();Tick(3);assert(json.parse(disk[root..'/Live/status.json']).active==false)
""");
Check("Chinese excluded and rich tooltip prioritized during pending request", "", """
FlushTimers();commands.abyss_translate();FlushTimers()
local first=RequestData().request_id
local chinese={text='已经汉化 English'};patches['abysstext.draw.1'](nil,chinese)
local p={toolTip='‖color:1,2,3‖Spineling Head‖color:end‖\nA hollow head.'}
patches['abysstext.tooltip'](nil,p);Tick(3)
local request=RequestData();assert(request.request_id~=first)
local texts={};for _,record in ipairs(request.records) do texts[record.text]=true;assert(record.priority==0) end
assert(texts['Spineling Head'] and texts['A hollow head.'] and not texts['已经汉化 English'])
Response(request.request_id,'tooltip',true,{['Spineling Head']='尖刺怪头部',['A hollow head.']='空心头部。'});Tick(3)
patches['abysstext.tooltip'](nil,p)
assert(p.toolTip=='‖color:1,2,3‖尖刺怪头部‖color:end‖\n空心头部。',p.toolTip)
commands.abyss_stop();assert(patches['abysstext.tooltip']==nil)
""");
Console.WriteLine($"{checks} isolated LuaCs/MoonSharp bridge checks passed. No real game or paid API was called.");
