param(
    [Parameter(Mandatory=$true)][string]$InputDirectory,
    [Parameter(Mandatory=$true)][string]$OutputJsonl
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
function Await($WinRtTask, $ResultType) {
    $method = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1
    })[0]
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($WinRtTask))
    $task.Wait()
    return $task.Result
}
[void][Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
[void][Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
$language = [Windows.Globalization.Language]::new('zh-Hant-TW')
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) { throw 'WINDOWS_OCR_ZH_HANT_UNAVAILABLE' }
$writer = [System.IO.StreamWriter]::new($OutputJsonl, $false, [System.Text.UTF8Encoding]::new($false))
try {
    foreach ($image in Get-ChildItem -LiteralPath $InputDirectory -Filter '*.png' -File | Sort-Object Name) {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($image.FullName)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines = @()
        foreach ($line in $result.Lines) {
            $words = @()
            foreach ($word in $line.Words) {
                $r = $word.BoundingRect
                $words += [ordered]@{text=$word.Text; x=[math]::Round($r.X,2); y=[math]::Round($r.Y,2); width=[math]::Round($r.Width,2); height=[math]::Round($r.Height,2)}
            }
            $lines += [ordered]@{text=$line.Text; words=$words}
        }
        $row = [ordered]@{image=$image.Name; text=$result.Text; lines=$lines}
        $writer.WriteLine(($row | ConvertTo-Json -Depth 8 -Compress))
        $stream.Dispose()
    }
}
finally { $writer.Dispose() }
