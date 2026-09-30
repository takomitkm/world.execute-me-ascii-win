param([Parameter(Mandatory = $true)][string]$Media)
# Windows stand-in for the macOS `audio-clock` helper: same line protocol,
# WPF MediaPlayer (Media Foundation) backend. MCI has no MP3 decoder reachable
# from a 64-bit process on this OS, so mciSendString cannot be used here.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationCore

$mp = New-Object System.Windows.Media.MediaPlayer
$mp.Volume = 0.75
$full = [System.IO.Path]::GetFullPath($Media)
$uri = New-Object Uri ('file:///' + ($full -replace '\\', '/'))
[void]$mp.Open($uri)

$deadline = [Diagnostics.Stopwatch]::StartNew()
while (-not $mp.NaturalDuration.HasTimeSpan) {
  if ($deadline.Elapsed.TotalSeconds -gt 10) {
    [Console]::Out.WriteLine('{"error":"media never opened"}'); exit 1
  }
  Start-Sleep -Milliseconds 10
}
$duration = $mp.NaturalDuration.TimeSpan.TotalSeconds
$inv = [System.Globalization.CultureInfo]::InvariantCulture

$stdIn = [Console]::OpenStandardInput()
$buffer = New-Object 'byte[]' 256
$pending = ''
$closing = $false

function Apply([string]$line) {
  $fields = $line.Split(' ')
  if ($fields.Count -lt 1) { return }
  switch ($fields[0]) {
    'play' { $mp.Play(); $script:playing = $true; break }
    'pause' { $mp.Pause(); $script:playing = $false; break }
    'quit' { $script:closing = $true; break }
    'seek' {
      if ($fields.Count -gt 1 -and $fields[1] -match '^[-+]?[0-9.]+$') {
        $t = [double]$fields[1]
        if ($t -lt 0) { $t = 0 }
        if ($t -gt ($duration - 0.01)) { $t = $duration - 0.01 }
        $mp.Position = [TimeSpan]::FromSeconds($t)
      }
      break
    }
    'volume' {
      if ($fields.Count -gt 1 -and $fields[1] -match '^[-+]?[0-9.]+$') {
        $v = [double]$fields[1]
        if ($v -lt 0) { $v = 0 }
        if ($v -gt 1) { $v = 1 }
        $mp.Volume = $v
      }
      break
    }
  }
}

$async = $stdIn.BeginRead($buffer, 0, $buffer.Length, $null, $null)
# WPF MediaPlayer.IsPlaying is only reliably updated through its dispatcher, which a
# console host has none of, so mirror the command stream instead of reading it back.
$playing = $false
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
  while (-not $closing) {
    $t = $mp.Position.TotalSeconds
    if ($playing -and $t -ge ($duration - 0.02)) { $playing = $false }
    [Console]::Out.WriteLine([string]::Format(
      $inv, '{{"time":{0:F6},"duration":{1:F6},"playing":{2}}}', $t, $duration, $(if ($playing) { 'true' } else { 'false' })))
    [Console]::Out.Flush()
    while ($async.IsCompleted) {
      $n = $stdIn.EndRead($async)
      if ($n -le 0) { $closing = $true; break }
      $pending += [Text.Encoding]::UTF8.GetString($buffer, 0, $n)
      while ($pending.Contains("`n")) {
        $idx = $pending.IndexOf("`n")
        $line = $pending.Substring(0, $idx)
        $pending = $pending.Substring($idx + 1)
        Apply $line.Trim()
      }
      if ($closing) { break }
      $async = $stdIn.BeginRead($buffer, 0, $buffer.Length, $null, $null)
    }
    if ($closing) { break }
    $budget = 16 - $sw.ElapsedMilliseconds
    $sw.Restart()
    if ($budget -gt 1) { [Threading.Thread]::Sleep([int]$budget) }
  }
} finally {
  [void]$mp.Stop()
  [void]$mp.Close()
}
