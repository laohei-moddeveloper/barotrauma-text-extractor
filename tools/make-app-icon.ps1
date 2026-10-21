$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$assets=Join-Path (Split-Path $PSScriptRoot -Parent) 'assets'
$bitmap=[Drawing.Bitmap]::new(1024,1024)
$g=[Drawing.Graphics]::FromImage($bitmap)
$g.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.ScaleTransform(2,2)
$plum=[Drawing.ColorTranslator]::FromHtml('#704a82')
$cream=[Drawing.ColorTranslator]::FromHtml('#fcf8ef')
$gold=[Drawing.ColorTranslator]::FromHtml('#dfb66c')
$path=[Drawing.Drawing2D.GraphicsPath]::new()
$path.AddArc(16,16,224,224,180,90);$path.AddArc(272,16,224,224,270,90)
$path.AddArc(272,272,224,224,0,90);$path.AddArc(16,272,224,224,90,90);$path.CloseFigure()
$brush=[Drawing.SolidBrush]::new($plum);$g.FillPath($brush,$path)
$pen=[Drawing.Pen]::new($cream,40);$pen.StartCap='Round';$pen.EndCap='Round';$pen.LineJoin='Round'
$p=[Drawing.Drawing2D.GraphicsPath]::new();$p.AddLine(144,310,242,126);$p.AddBezier(242,126,250,110,262,110,270,126);$p.AddLine(270,126,368,310);$g.DrawPath($pen,$p)
$g.DrawLine($pen,190,252,322,252)
$p.Reset();$p.AddBezier(106,330,156,316,206,323,256,350);$p.AddBezier(256,350,306,323,356,316,406,330)
$p.AddLine(406,330,406,385);$p.AddBezier(406,385,356,373,306,379,256,404);$p.AddBezier(256,404,206,379,156,373,106,385);$p.CloseFigure()
$brush.Color=$cream;$g.FillPath($brush,$p)
$pen.Color=$plum;$pen.Width=12;$g.DrawLine($pen,256,354,256,391)
$pen.Color=$gold;$pen.Width=15;$p.Reset();$p.AddBezier(181,434,206,421,231,421,256,434);$p.AddBezier(256,434,281,447,306,447,331,434);$g.DrawPath($pen,$p)
$bitmap.Save((Join-Path $assets 'abysstext.png'),[Drawing.Imaging.ImageFormat]::Png)
$sizes=@(16,24,32,48,64,128,256);$images=@()
foreach($size in $sizes){
 $small=[Drawing.Bitmap]::new($size,$size);$sg=[Drawing.Graphics]::FromImage($small)
 $sg.InterpolationMode='HighQualityBicubic';$sg.DrawImage($bitmap,0,0,$size,$size)
 $stream=[IO.MemoryStream]::new();$small.Save($stream,[Drawing.Imaging.ImageFormat]::Png)
 $images+=,@($stream.ToArray());$sg.Dispose();$small.Dispose();$stream.Dispose()
}
$file=[IO.File]::Create((Join-Path $assets 'abysstext.ico'));$writer=[IO.BinaryWriter]::new($file)
try{
 $writer.Write([uint16]0);$writer.Write([uint16]1);$writer.Write([uint16]$sizes.Count)
 $offset=6+16*$sizes.Count
 for($i=0;$i -lt $sizes.Count;$i++){
  $dimension=if($sizes[$i] -eq 256){0}else{$sizes[$i]}
  $writer.Write([byte]$dimension);$writer.Write([byte]$dimension);$writer.Write([byte]0);$writer.Write([byte]0)
  $writer.Write([uint16]1);$writer.Write([uint16]32);$writer.Write([uint32]$images[$i].Length);$writer.Write([uint32]$offset)
  $offset+=$images[$i].Length
 }
 foreach($data in $images){$writer.Write([byte[]]$data)}
}finally{$writer.Dispose();$file.Dispose();$g.Dispose();$bitmap.Dispose();$brush.Dispose();$pen.Dispose();$p.Dispose();$path.Dispose()}
Write-Output 'assets/abysstext.png + abysstext.ico generated from the SVG design'
