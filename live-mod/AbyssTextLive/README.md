# AbyssTextLive / 译潜实时试译客户端

Experimental LuaCs client companion. Install LuaCs client, copy this folder into LocalMods, enable it, then connect its folder from the AbyssText desktop workbench. Keep the workbench running. Choose source/target languages and offline/local model there. Click **Translate** to collect displayed text and request translations; click **Stop** to restore. Native text-pack overrides require the game's target language. Change language pairs only between sessions. No HTTP requests are made by this module.

实验插件：需 LuaCs 客户端。启用后在桌面工作台连接该目录、选择源/目标语言和离线/本机模型，保持桌面运行。游戏点“一键试译”，再次点击停止恢复。原生语言键需要游戏语言与目标一致；切换语言对时先停止再开始。无翻译字幕层，不改其他模组源码。

F3: `abyss_translate`, `abyss_stop`, `abyss_apply`.

No real-game certification yet. Images/custom renderers/unvisited screens/direct colored font indices are not guaranteed. Cached screens can need reopening. See the repository validation and local test handoff before publishing.

尚未通过真实游戏验收；图片、自定义渲染、未触发界面和直接颜色索引字体调用不保证覆盖。缓存界面可能需重开。发布前请完成仓库中的本机验收。
