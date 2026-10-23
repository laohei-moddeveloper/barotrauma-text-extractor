using MoonSharp.Interpreter;

if (args.Length==4 && args[0]=="--benchmark")
{
    string fixturePath=Path.Combine(AppContext.BaseDirectory,"fixture.lua");
    Dictionary<string,object> Measure(string modulePath)
    {
        string moduleText=File.ReadAllText(modulePath).Replace("local function Signature(text)","local function Signature(text) signatureCalls=(signatureCalls or 0)+1");
        var script=new Script(CoreModules.Preset_Complete);script.Options.DebugPrint=_=>{};
        script.DoString(File.ReadAllText(fixturePath)+"\n"+"""
reads,richCalls,signatureCalls=0,0,0
LuaUserData.CreateStatic=function() return {Rich=function(value) richCalls=richCalls+1;return value end} end
GUI.Canvas.Children={}
for i=1,800 do
 GUI.Canvas.Children[i]=setmetatable({isControl=true,Children={}},{__index=function(_,key)
  if key=='Text' then reads=reads+1;return 'Static untouched label' end
 end})
end
""");
        script.Call(script.LoadString(moduleText),DynValue.NewString("/LocalMods/AbyssTextLive"));
        script.DoString("FlushTimers();commands.abyss_translate();FlushTimers();for i=1,40 do Tick(0.01) end;request=RequestData();reads=0;richCalls=0;signatureCalls=0");
        long allocatedBefore=GC.GetAllocatedBytesForCurrentThread();var watch=System.Diagnostics.Stopwatch.StartNew();
        script.DoString("""
for seq=1,100 do Delta(request,seq,{['Unrelated label']='无关 '..seq});Tick(0.25) end
unrelatedReads=reads
Delta(request,101,{['Large tooltip paragraph']='长提示文本'});Tick(0.25)
local body=('Large tooltip paragraph\n'):rep(200)
for i=1,500 do patches['abysstext.tooltip'](nil,{toolTip=body}) end
tooltipRichCalls=richCalls
signatureCalls=0
for frame=1,100 do
 Tick(0.01)
 for i=1,200 do patches['abysstext.draw.1'](nil,{text='Pressure reading '..tostring(i)}) end
end
numericSignatures=signatureCalls
local before=versions
for seq=102,141 do
 disk[root..'/Live/response.json']=json.serialize({protocol=1,request_id=request.request_id,
  session_id=request.session_id,source_language=request.source_language,target_language=request.target_language,
  delta=true,sequence=seq,base_sequence=seq-1,revision=tostring(seq),
  language_revision='keyed-'..seq,keys=seq,translations={Tool='工具 '..seq},removed={}})
 Tick(0.25)
end
languageReloadCount=versions-before
Tick(12);for i=1,220 do Tick(0.01) end
retained=json.parse(disk[root..'/Live/status.json']).tracked_controls
""");
        watch.Stop();
        var result=new Dictionary<string,object>();
        foreach(string key in new[]{"unrelatedReads","tooltipRichCalls","numericSignatures","languageReloadCount","retained"}) result[key]=script.Globals.Get(key).Number;
        result["elapsed_ms"]=watch.Elapsed.TotalMilliseconds;result["managed_allocated_bytes"]=GC.GetAllocatedBytesForCurrentThread()-allocatedBefore;
        return result;
    }
    var before=Measure(args[1]);var after=Measure(args[2]);
    if ((double)after["unrelatedReads"]!=0 || (double)after["tooltipRichCalls"]!=1 || (double)after["retained"]!=0 ||
        (double)after["numericSignatures"]>=(double)before["numericSignatures"] || (double)after["languageReloadCount"]>3)
        throw new Exception("Bounded-render pressure benchmark failed");
    string report=System.Text.Json.JsonSerializer.Serialize(new {before,after,game_tested=false,notes="Synthetic MoonSharp trace; operation counts are not real-game FPS."},new System.Text.Json.JsonSerializerOptions{WriteIndented=true});
    File.WriteAllText(args[3],report+"\n");Console.WriteLine(report);return;
}
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
ItemPrefab={Prefabs={{Name='New background item'}}};hooks.roundStart()
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
local texts={}
for cycle=1,4 do
 local request=RequestData()
 for _,record in ipairs(request.records) do texts[record.text]=true end
 Response(request.request_id,'prefab'..cycle,true,{});Tick(3)
end
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
for cycle=1,100 do
 local request=RequestData()
 assert(#request.records<=8)
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
local initial=RequestData();local first=initial.request_id
local chinese={text='已经汉化 English'};patches['abysstext.draw.1'](nil,chinese)
local p={toolTip='‖color:1,2,3‖Spineling Head‖color:end‖\nA hollow head.'}
patches['abysstext.tooltip'](nil,p);Tick(3)
assert(RequestData().request_id==first and writes==1)
Response(first,'accepted',false,{});Tick(3)
local request=RequestData();assert(request.request_id~=first)
local texts={};for _,record in ipairs(request.records) do texts[record.text]=true;assert(record.priority==0) end
assert(texts['Spineling Head'] and texts['A hollow head.'] and not texts['已经汉化 English'])
Response(request.request_id,'tooltip',true,{['Spineling Head']='尖刺怪头部',['A hollow head.']='空心头部。'});Tick(3)
patches['abysstext.tooltip'](nil,p)
assert(p.toolTip=='‖color:1,2,3‖尖刺怪头部‖color:end‖\n空心头部。',p.toolTip)
commands.abyss_stop();assert(patches['abysstext.tooltip']==nil)
""");
Check("Han strings never enter initial or later capture queues", """
control.Text='已有中文 English'
ItemPrefab={Prefabs={{Name='已经汉化',Description='中文 English mixed'}}}
TextManager.TextPacks.English={{Texts={{Key='zh',Value={{String='中文'}}},{Key='en',Value={{String='Untranslated item'}}}}}}
""", """
FlushTimers();commands.abyss_translate();FlushTimers()
local request=RequestData()
for _,r in ipairs(request.records) do assert(not r.text:find('[㐀-䶿一-鿿]'),r.text) end
Response(request.request_id,'empty',true,{});Tick(3)
patches['abysstext.draw.1'](nil,{text='另一个中文 English'})
local before=writes;Tick(3);assert(writes==before)
""");
Check("literal-only replies avoid global language reload and apply incrementally", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
local before=versions
disk[root..'/Live/response.json']=json.serialize({protocol=1,request_id=request.request_id,
 revision='literal',language_revision='empty-xml',keys=0,complete=true,translations={['Open hatch']='打开舱门'}})
Tick(1);assert(control.Text=='打开舱门' and versions==before)
local count=versions;Tick(2);assert(versions==count)
commands.abyss_stop();assert(control.Text=='Open hatch')
""");
Check("visible tooltip promotes already submitted background text once", """
ItemPrefab={Prefabs={{Name='Spineling Head'}}}
""", """
FlushTimers();commands.abyss_translate();FlushTimers();local first=RequestData()
Response(first.request_id,'waiting',false,{});Tick(1)
patches['abysstext.tooltip'](nil,{toolTip='Spineling Head'});Tick(3)
local request=RequestData();assert(request.request_id~=first.request_id)
assert(#request.records==1 and request.records[1].text=='Spineling Head' and request.records[1].priority==0)
local before=writes;patches['abysstext.tooltip'](nil,{toolTip='Spineling Head'});Tick(3);assert(writes==before)
""");
Check("stop and restart accepts cached translations with unchanged revision", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Response(request.request_id,'same-cache',true,{['Open hatch']='打开舱门'});Tick(1)
assert(control.Text=='打开舱门');commands.abyss_stop();assert(control.Text=='Open hatch')
commands.abyss_translate();FlushTimers();request=RequestData()
Response(request.request_id,'same-cache',true,{['Open hatch']='打开舱门'});Tick(2)
assert(control.Text=='打开舱门')
""");
Check("matching request with wrong session or target cannot acknowledge or apply", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
for _,field in ipairs({'session_id','source_language','target_language'}) do
 local response={protocol=1,request_id=request.request_id,revision=field,complete=true,
  session_id=request.session_id,source_language=request.source_language,target_language=request.target_language,
  translations={['Open hatch']='错误'}}
 response[field]='wrong'
 disk[root..'/Live/response.json']=json.serialize(response);Tick(1)
 assert(control.Text=='Open hatch')
end
patches['abysstext.tooltip'](nil,{toolTip='Visible next'});Tick(3)
assert(writes==1)
Response(request.request_id,'correct',false,{});Tick(3);assert(writes==2)
""");
Check("stopped generation cannot submit a later restart early", "", """
FlushTimers();commands.abyss_translate();commands.abyss_stop();commands.abyss_translate()
local pendingTimers=timers;timers={}
assert(#pendingTimers==2)
pendingTimers[1]();assert(writes==0)
pendingTimers[2]();assert(writes==1)
""");
Check("case insensitive source aliases still skip existing Chinese", """
control.Text='已有汉化 English'
disk[root..'/Live/settings.json']=json.serialize({source_language='en',target_language='zh-cn'})
""", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
assert(request.source_language=='English' and request.target_language=='Simplified Chinese')
for _,r in ipairs(request.records) do assert(r.text~='已有汉化 English') end
""");
Check("delta acknowledgements preserve prior translations and reject sequence gaps", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
assert(request.response_mode=='delta-v1')
Delta(request,1,{['Open hatch']='打开舱门'});Tick(0.25)
assert(control.Text=='打开舱门' and json.parse(disk[root..'/Live/status.json']).applied_sequence==1)
Delta(request,2,{Tool='工具'});Tick(0.25)
local p={text='Tool'};patches['abysstext.draw.1'](nil,p);assert(p.text=='工具')
assert(control.Text=='打开舱门')
Delta(request,4,{['Open hatch']='错误'});Tick(0.25)
assert(control.Text=='打开舱门' and json.parse(disk[root..'/Live/status.json']).applied_sequence==2)
""");
Check("oversized delta is rejected before any application", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
local many={['Open hatch']='错误'};for i=1,8 do many['Extra '..i]='多余' end
Delta(request,1,many);Tick(0.25);assert(control.Text=='Open hatch')
assert(json.parse(disk[root..'/Live/status.json']).applied_sequence==0)
Delta(request,1,{['Open hatch']='打开舱门'});Tick(0.25);assert(control.Text=='打开舱门')
""");
Check("removing and correcting a delta restores or updates original controls", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Delta(request,1,{['Open hatch']='第一译文'});Tick(0.25);assert(control.Text=='第一译文')
Delta(request,2,{['Open hatch']='修正译文'});Tick(0.25);assert(control.Text=='修正译文')
Delta(request,3,{}, {'Open hatch'});Tick(0.25);assert(control.Text=='Open hatch')
""");
Check("continuous deltas cannot starve later controls", """
GUI.Canvas.Children={}
for i=1,180 do GUI.Canvas.Children[i]={isControl=true,Text='Open hatch',Children={}} end
""", """
FlushTimers();commands.abyss_translate();FlushTimers()
for i=1,8 do Tick(0.01) end
local request=RequestData()
for sequence=1,10 do Delta(request,sequence,{['Open hatch']='译文 '..sequence});Tick(0.25) end
for i=1,16 do Tick(0.01) end
for _,c in ipairs(GUI.Canvas.Children) do assert(c.Text=='译文 10',c.Text) end
""");
Check("initial control traversal yields every 32 nodes", """
reads=0;GUI.Canvas.Children={}
for i=1,500 do
 GUI.Canvas.Children[i]=setmetatable({isControl=true,Children={}},{__index=function(_,key)
  if key=='Text' then reads=reads+1;return 'Unseen control' end
 end})
end
""", """
FlushTimers();commands.abyss_translate();FlushTimers();assert(reads<=64,tostring(reads))
for i=1,8 do local before=reads;Tick(0.01);assert(reads-before<=64,tostring(reads-before)) end
""");
Check("bounded queue selection retains visible priority", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local first=RequestData()
for frame=1,10 do
 Tick(0.01)
 for i=1,100 do patches['abysstext.draw.1'](nil,{text='Visible label '..string.char(64+frame)..string.char(65+math.floor((i-1)/26))..string.char(65+(i-1)%26)}) end
end
Delta(first,1,{}, {},true);Tick(0.25)
local second=RequestData();assert(#second.records<=8 and second.request_id~=first.request_id)
Tick(3);local status=json.parse(disk[root..'/Live/status.json'])
assert(status.last_queue_visits<=64 and status.queued_records>0)
""");
Check("in-flight delta survives a newer visible request without acknowledging its import", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local first=RequestData()
Delta(first,1,{});Tick(0.25)
patches['abysstext.tooltip'](nil,{toolTip='New visible item'});Tick(0.25)
local second=RequestData();assert(second.request_id~=first.request_id)
Delta(first,2,{['Open hatch']='打开舱门'});Tick(0.25)
assert(control.Text=='打开舱门','older in-flight delta was rejected')
assert(json.parse(disk[root..'/Live/status.json']).applied_sequence==2)
patches['abysstext.tooltip'](nil,{toolTip='Third visible item'});Tick(0.25)
assert(RequestData().request_id==second.request_id,'old response acknowledged a new request')
Delta(second,3,{Tool='工具'});Tick(0.25)
assert(RequestData().request_id~=second.request_id)
""");
Check("different-request delta requires the complete matching session and language pair", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
for _,field in ipairs({'session_id','source_language','target_language'}) do
 local packet={protocol=1,request_id='unknown-request',session_id=request.session_id,
  source_language=request.source_language,target_language=request.target_language,
  delta=true,sequence=1,base_sequence=0,reset=true,revision='1',keys=0,
  translations={['Open hatch']='错误'},removed={}}
 packet[field]=nil
 disk[root..'/Live/response.json']=json.serialize(packet);Tick(0.25)
 assert(control.Text=='Open hatch')
 assert(json.parse(disk[root..'/Live/status.json']).applied_sequence==0)
end
""");
Check("language and prefab owner scope stays in bounded request", """
TextManager.TextPacks.English[1].ContentFile={ContentPackage={Path='C:/WorkshopMods/Installed/1234567890/filelist.xml'}}
ItemPrefab={Prefabs={{Name='Scoped phantom wrench',ContentPackage={Path='C:\\WorkshopMods\\Installed\\2222222222\\filelist.xml'}}}}
""", """
FlushTimers();commands.abyss_translate();FlushTimers()
local seen={}
for _,r in ipairs(RequestData().records) do seen[r.text]=r.mod_id end
assert(seen.Tool=='1234567890' and seen['Scoped phantom wrench']=='2222222222')
""");
Check("native GUI emits explicit empty owner rather than null", "", """
FlushTimers();commands.abyss_translate();FlushTimers()
local found=false
for _,r in ipairs(RequestData().records) do
 if r.text=='Open hatch' then assert(r.mod_id=='');found=true end
end
assert(found)
""");
Check("unrelated deltas do not reread every tracked control", """
reads=0;GUI.Canvas.Children={}
for i=1,800 do
 GUI.Canvas.Children[i]=setmetatable({isControl=true,Children={}},{__index=function(_,key)
  if key=='Text' then reads=reads+1;return 'Static untouched label' end
 end})
end
""", """
FlushTimers();commands.abyss_translate();FlushTimers()
for i=1,40 do Tick(0.01) end
local before=reads;local request=RequestData()
for seq=1,20 do Delta(request,seq,{['Unrelated label']='无关 '..seq});Tick(0.25) end
assert(reads==before,'unrelated replies reread controls: '..tostring(reads-before))
local status=json.parse(disk[root..'/Live/status.json']);assert(status.last_control_visits<=16)
""");
Check("repeated large translated tooltip reuses rich object", """
richCalls=0
LuaUserData.CreateStatic=function() return {Rich=function(value) richCalls=richCalls+1;return value end} end
""", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Delta(request,1,{['Large tooltip paragraph']='长提示文本'});Tick(0.25)
local body=('Large tooltip paragraph\n'):rep(200)
for frame=1,100 do
 local p={toolTip=body};patches['abysstext.tooltip'](nil,p)
 assert(p.toolTip:find('长提示文本',1,true));Tick(0.01)
end
assert(richCalls==1,'reconstructed unchanged tooltip '..tostring(richCalls)..' times')
Delta(request,2,{['Large tooltip paragraph']='更新后的文本'});Tick(0.25)
local p={toolTip=body};patches['abysstext.tooltip'](nil,p)
assert(p.toolTip:find('更新后的文本',1,true) and richCalls==2)
""");
Check("control cap includes restoration and stale pages are reclaimed", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Delta(request,1,{['Overflow label']='已翻译'});Tick(0.25)
local all={}
for frame=1,110 do
 Tick(0.01)
 for i=1,32 do
  local c={isControl=true,Text='Overflow label',Children={}};all[#all+1]=c
  patches['abysstext.controls'](nil,{component=c})
 end
end
Tick(2)
local status=json.parse(disk[root..'/Live/status.json']);assert(status.tracked_controls<=3000)
local mutated=0;for _,c in ipairs(all) do if c.Text=='已翻译' then mutated=mutated+1 end end
assert(mutated<=3000,'untracked restoration entries exceeded cap')
Tick(11);for i=1,220 do Tick(0.01) end
status=json.parse(disk[root..'/Live/status.json']);assert(status.tracked_controls==0)
local fresh={isControl=true,Text='Overflow label',Children={}}
patches['abysstext.controls'](nil,{component=fresh});assert(fresh.Text=='已翻译')
commands.abyss_stop();assert(fresh.Text=='Overflow label')
""");
Check("render caches stay bounded under thousands of numeric labels", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData()
Delta(request,1,{['Oxygen: [abyss_value_1]%']='氧气：[abyss_value_1]%'});Tick(0.25)
local p={text='Oxygen: 80%'};patches['abysstext.draw.1'](nil,p);assert(p.text=='氧气：80%')
for frame=1,40 do
 Tick(0.01)
 for i=1,200 do patches['abysstext.draw.1'](nil,{text='Dynamic '..tostring(frame*200+i)}) end
end
Tick(2)
local status=json.parse(disk[root..'/Live/status.json'])
assert(status.numeric_cache_entries<=512 and status.tooltip_cache_entries<=64 and status.render_cache_chars<=655360)
""");
Check("continuous keyed responses coalesce reloads without starving final flush", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local request=RequestData();local before=versions
for seq=1,30 do
 disk[root..'/Live/response.json']=json.serialize({protocol=1,request_id=request.request_id,
  session_id=request.session_id,source_language=request.source_language,target_language=request.target_language,
  delta=true,sequence=seq,base_sequence=seq-1,reset=seq==1,revision=tostring(seq),
  language_revision='keyed-'..seq,keys=seq,translations={Tool='工具 '..seq},removed={}})
 Tick(0.25)
end
assert(versions-before<=2,'language cache reloaded too frequently: '..tostring(versions-before))
local previous=versions;Tick(5);assert(versions==previous+1,'final language revision starved')
local p={text='Tool'};patches['abysstext.draw.1'](nil,p);assert(p.text=='工具 30')
commands.abyss_stop()
""");
Check("dense Chinese page cannot permanently starve later English capture", "", """
FlushTimers();commands.abyss_translate();FlushTimers();local first=RequestData()
Delta(first,1,{}, {},true);Tick(0.25)
for frame=1,12 do
 Tick(0.01)
 for i=1,500 do patches['abysstext.draw.1'](nil,{text='已有汉化 '..i}) end
 patches['abysstext.draw.1'](nil,{text='Untranslated late label'})
end
Tick(1)
local found=false
for _,r in ipairs(RequestData().records) do
 assert(not r.text:find('已有汉化',1,true))
 if r.text=='Untranslated late label' then found=true end
end
assert(found,'later English text starved behind already-localized text')
""");
Console.WriteLine($"{checks} isolated LuaCs/MoonSharp bridge checks passed. No real game or paid API was called.");
