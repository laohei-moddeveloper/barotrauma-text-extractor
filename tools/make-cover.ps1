$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$img=[Drawing.Bitmap]::new(1200,1200)
$g=[Drawing.Graphics]::FromImage($img)
$g.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint=[Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$bg=[Drawing.Drawing2D.LinearGradientBrush]::new([Drawing.Rectangle]::new(0,0,1200,1200),[Drawing.ColorTranslator]::FromHtml('#081621'),[Drawing.ColorTranslator]::FromHtml('#173b43'),70)
$g.FillRectangle($bg,0,0,1200,1200)
$grid=[Drawing.Pen]::new([Drawing.Color]::FromArgb(15,115,218,207),1)
for($i=0;$i -le 1200;$i+=60){$g.DrawLine($grid,$i,0,$i,1200);$g.DrawLine($grid,0,$i,1200,$i)}
$ring=[Drawing.Pen]::new([Drawing.Color]::FromArgb(30,75,221,200),2)
foreach($r in @(390,510,630)){$g.DrawEllipse($ring,870-$r,190-$r,2*$r,2*$r)}
function Text([string]$value,[float]$size,[float]$x,[float]$y,[string]$color,[bool]$bold=$false){$style=if($bold){[Drawing.FontStyle]::Bold}else{[Drawing.FontStyle]::Regular};$font=[Drawing.Font]::new('Microsoft YaHei UI',$size,$style,[Drawing.GraphicsUnit]::Pixel);$brush=[Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($color));$g.DrawString($value,$font,$brush,$x,$y);$font.Dispose();$brush.Dispose()}
$accent=[Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml('#86e0cd'))
$g.FillRectangle($accent,80,78,12,36)
Text 'BAROTRAUMA / TRANSLATION TOOL' 24 110 77 '#9bc2c8'
Text '译潜' 162 72 154 '#f3e9ce' $true
Text 'AbyssText' 76 85 345 '#87e5cf' $true
Text '汉化文字提取器' 39 88 446 '#d7e4e3'
$panel=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(195,6,18,28));$g.FillRectangle($panel,80,565,1040,365)
$border=[Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml('#33575f'),2);$g.DrawRectangle($border,80,565,1040,365)
Text 'XML   /   LUA   /   C#' 29 116 593 '#80b1ba'
Text '<name> Hull breach! </name>' 35 116 665 '#c3d8db'
Text '→' 74 530 721 '#86e0cd' $true
Text '原文  ·  出处  ·  上下文' 37 116 837 '#f3e9ce'
Text '提取文字，让翻译有据可依。' 35 86 988 '#d4dfdf'
Text 'EXTRACT FIRST. TRANSLATE WITH CONTEXT.' 22 89 1061 '#8caab2'
Text 'CSV + JSON' 22 890 1061 '#86e0cd' $true
$g.Dispose();$bg.Dispose();$grid.Dispose();$ring.Dispose();$panel.Dispose();$border.Dispose();$accent.Dispose()
$destination=Join-Path $PSScriptRoot '..\workshop\cover.png'
$img.Save($destination,[Drawing.Imaging.ImageFormat]::Png);$img.Dispose()
Get-Item -LiteralPath $destination | Select-Object Name,Length
