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
File.Write=function(path,text) if fail then fail=false;error('temporary file lock') end;disk[path]=text;writes=writes+1 end
""", """
FlushTimers();commands.abyss_translate();FlushTimers();assert(writes==0)
Tick(3);assert(writes==1 and #RequestData().records>0)
""");
Console.WriteLine($"{checks} isolated LuaCs/MoonSharp bridge checks passed. No real game or paid API was called.");
