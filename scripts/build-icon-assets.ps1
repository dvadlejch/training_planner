# Rebuild committed icon assets on Windows using only .NET (no extra dependencies).
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Drawing
$root = Split-Path -Parent $PSScriptRoot
$assetRoot = Join-Path $root 'assets\icons'

function New-IconBitmap {
    param([xml]$Svg, [int]$Size)
    $bitmap = [Drawing.Bitmap]::new($Size, $Size)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.ScaleTransform($Size / 256.0, $Size / 256.0)
        foreach ($shape in $Svg.DocumentElement.ChildNodes) {
            if ($shape -isnot [Xml.XmlElement]) { continue }
            $path = [Drawing.Drawing2D.GraphicsPath]::new()
            try {
                switch ($shape.LocalName) {
                    'rect' {
                        $x = [single]$shape.GetAttribute('x')
                        $y = [single]$shape.GetAttribute('y')
                        $w = [single]$shape.GetAttribute('width')
                        $h = [single]$shape.GetAttribute('height')
                        $r = [single]$shape.GetAttribute('rx')
                        if ($r -gt 0) {
                            $d = 2 * $r
                            $path.AddArc($x, $y, $d, $d, 180, 90)
                            $path.AddArc(($x + $w - $d), $y, $d, $d, 270, 90)
                            $path.AddArc(($x + $w - $d), ($y + $h - $d), $d, $d, 0, 90)
                            $path.AddArc($x, ($y + $h - $d), $d, $d, 90, 90)
                            $path.CloseFigure()
                        } else {
                            $path.AddRectangle([Drawing.RectangleF]::new($x, $y, $w, $h))
                        }
                    }
                    'circle' {
                        $r = [single]$shape.GetAttribute('r')
                        $path.AddEllipse(([single]$shape.GetAttribute('cx') - $r), ([single]$shape.GetAttribute('cy') - $r), (2 * $r), (2 * $r))
                    }
                    'polyline' {
                        [Drawing.PointF[]]$points = @($shape.GetAttribute('points').Split(' ') | Where-Object { $_ } | ForEach-Object {
                            $xy = $_.Split(',')
                            [Drawing.PointF]::new([single]$xy[0], [single]$xy[1])
                        })
                        $path.AddLines($points)
                    }
                    default { throw "Unsupported SVG element: $($shape.LocalName)" }
                }
                $fill = $shape.GetAttribute('fill')
                if ($fill -and $fill -ne 'none') {
                    $brush = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($fill))
                    try { $graphics.FillPath($brush, $path) } finally { $brush.Dispose() }
                }
                $stroke = $shape.GetAttribute('stroke')
                if ($stroke -and $stroke -ne 'none') {
                    $pen = [Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml($stroke), [single]$shape.GetAttribute('stroke-width'))
                    $pen.StartCap = $pen.EndCap = [Drawing.Drawing2D.LineCap]::Round
                    $pen.LineJoin = [Drawing.Drawing2D.LineJoin]::Round
                    try { $graphics.DrawPath($pen, $path) } finally { $pen.Dispose() }
                }
            } finally { $path.Dispose() }
        }
    } finally { $graphics.Dispose() }
    return ,$bitmap
}

function Export-Icon {
    param([xml]$Svg, [string]$Name)
    # PNG-backed ICO frames retain alpha at all standard Windows display scales.
    $sizes = @(16, 20, 24, 32, 40, 48, 64, 128, 256)
    $frames = @()
    foreach ($size in $sizes) {
        $bitmap = New-IconBitmap $Svg $size
        $stream = [IO.MemoryStream]::new()
        try {
            $bitmap.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
            $frames += ,$stream.ToArray()
            if ($size -eq 256) { $bitmap.Save((Join-Path $assetRoot "$Name.png"), [Drawing.Imaging.ImageFormat]::Png) }
        } finally { $stream.Dispose(); $bitmap.Dispose() }
    }
    $writer = [IO.BinaryWriter]::new([IO.File]::Create((Join-Path $assetRoot "$Name.ico")))
    try {
        $writer.Write([uint16]0)
        $writer.Write([uint16]1)
        $writer.Write([uint16]$sizes.Count)
        $offset = 6 + 16 * $sizes.Count
        for ($i = 0; $i -lt $sizes.Count; $i++) {
            $dimension = $sizes[$i] % 256
            $writer.Write([byte]$dimension)
            $writer.Write([byte]$dimension)
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([uint16]1)
            $writer.Write([uint16]32)
            $writer.Write([uint32]$frames[$i].Length)
            $writer.Write([uint32]$offset)
            $offset += $frames[$i].Length
        }
        foreach ($frame in $frames) { $writer.Write([byte[]]$frame) }
    } finally { $writer.Dispose() }
}

foreach ($name in @('summit-calendar', 'training-pulse', 'progress-trail')) {
    Export-Icon ([xml](Get-Content -LiteralPath (Join-Path $assetRoot "$name.svg") -Raw)) $name
}

# The installer panel uses Inno Setup's 164:314 aspect ratio at 3x resolution.
$panel = [Drawing.Bitmap]::new(492, 942)
$graphics = [Drawing.Graphics]::FromImage($panel)
$icon = [Drawing.Image]::FromFile((Join-Path $assetRoot 'summit-calendar.png'))
$brush = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml('#fffefa'))
$accent = [Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml('#e8bd70'), 4)
$titleFont = [Drawing.Font]::new('Segoe UI', 29, [Drawing.FontStyle]::Bold, [Drawing.GraphicsUnit]::Pixel)
$bodyFont = [Drawing.Font]::new('Segoe UI', 20, [Drawing.FontStyle]::Regular, [Drawing.GraphicsUnit]::Pixel)
try {
    $graphics.Clear([Drawing.ColorTranslator]::FromHtml('#1c4134'))
    $graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.DrawImage($icon, 118, 185, 256, 256)
    $graphics.DrawLine($accent, 58, 503, 126, 503)
    $graphics.DrawString("Training`nPlanner", $titleFont, $brush, 56, 540)
    $graphics.DrawString("Plan. Train. Explore.", $bodyFont, $brush, 58, 654)
    $panel.Save((Join-Path $assetRoot 'installer-panel.png'), [Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose(); $panel.Dispose(); $icon.Dispose()
    $brush.Dispose(); $accent.Dispose(); $titleFont.Dispose(); $bodyFont.Dispose()
}
Copy-Item -LiteralPath (Join-Path $assetRoot 'summit-calendar.svg') -Destination (Join-Path $root 'frontend\public\favicon.svg')
Write-Host 'Rebuilt three icon designs, installer panel, and browser favicon.'
