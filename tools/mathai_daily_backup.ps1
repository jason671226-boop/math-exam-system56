param(
    [switch]$AuditOnly,
    [int]$MaxBackups = 14,
    [string]$BackupTarget = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Section([string]$Text) {
    Write-Host ""
    Write-Host ("=" * 64) -ForegroundColor DarkCyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host ("=" * 64) -ForegroundColor DarkCyan
}

function Get-RepoRoot {
    $here = Split-Path -Parent $PSScriptRoot
    Push-Location $here
    try {
        $root = (& git rev-parse --show-toplevel 2>$null).Trim()
        if (-not $root) { throw "C:\MathAI 目前不是可辨識的 Git repository。" }
        return (Resolve-Path $root).Path
    }
    finally { Pop-Location }
}

function Test-ExcludedPath([string]$RelativePath) {
    $p = $RelativePath.Replace('/', '\')
    $segments = $p.Split('\')
    $excludedDirs = @(
        '.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache',
        '.ruff_cache', '.cache', '.local', 'node_modules', 'dist', 'build',
        '_research_tmp', '_repo_tmp', 'tmp', 'temp'
    )
    foreach ($seg in $segments) {
        if ($excludedDirs -contains $seg) { return $true }
    }
    if ($p -match '(^|\\)backup(s)?(\\|$)') { return $true }
    if ($p -match '(^|\\)\.streamlit\\secrets\.toml$') { return $true }
    if ($p -match '(^|\\)app\\\.streamlit\\secrets\.toml$') { return $true }
    if ($p -match '(^|\\)\.env($|\.)') { return $true }
    if ($p -match '(^|\\)(credentials|token)(\.json)?$') { return $true }
    if ($p -match 'service[-_]?account.*\.json$') { return $true }
    if ($p -match '\.(pyc|pyo|log|tmp)$') { return $true }
    if ($p -match '(^|\\)MathAI_Backup_\d{8}_\d{4}.*\.zip$') { return $true }
    return $false
}

function Get-BackupFiles([string]$Root) {
    $files = Get-ChildItem -LiteralPath $Root -File -Recurse -Force -ErrorAction SilentlyContinue
    $included = New-Object System.Collections.Generic.List[object]
    $excluded = New-Object System.Collections.Generic.List[object]
    foreach ($file in $files) {
        $rel = [IO.Path]::GetRelativePath($Root, $file.FullName)
        if (Test-ExcludedPath $rel) { $excluded.Add($file) } else { $included.Add($file) }
    }
    return [pscustomobject]@{ Included = $included; Excluded = $excluded }
}

function Find-GoogleDriveTarget([string]$Root, [string]$ExplicitTarget) {
    if ($ExplicitTarget) { return $ExplicitTarget }

    $targetFile = Join-Path $Root '.mathai_backup_target.txt'
    if (Test-Path $targetFile) {
        $configured = (Get-Content -LiteralPath $targetFile -Raw).Trim()
        if ($configured) { return $configured }
    }

    if ($env:MATHAI_BACKUP_DIR) { return $env:MATHAI_BACKUP_DIR }

    $names = @('My Drive', '我的雲端硬碟', 'Google Drive', 'Google 雲端硬碟')
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($name in $names) {
        $candidates.Add((Join-Path $env:USERPROFILE $name))
    }
    foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
        if (-not $drive.Root) { continue }
        foreach ($name in $names) { $candidates.Add((Join-Path $drive.Root $name)) }
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path $candidate) {
            return (Join-Path $candidate 'MathAI_Backups')
        }
    }
    return (Join-Path $env:USERPROFILE 'MathAI_Backups_Local')
}

function Get-GitInfo([string]$Root) {
    Push-Location $Root
    try {
        $branch = (& git branch --show-current 2>$null).Trim()
        $commit = (& git rev-parse HEAD 2>$null).Trim()
        $remote = (& git remote get-url origin 2>$null).Trim()
        $status = @(& git status --porcelain=v1 --untracked-files=all 2>$null)
        return [pscustomobject]@{
            branch = $branch
            commit = $commit
            remote = $remote
            dirty = ($status.Count -gt 0)
            status = $status
        }
    }
    finally { Pop-Location }
}

function Format-Bytes([long]$Bytes) {
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N2} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N2} KB' -f ($Bytes / 1KB)) }
    return "$Bytes bytes"
}

$repoRoot = Get-RepoRoot
$git = Get-GitInfo $repoRoot
$fileSets = Get-BackupFiles $repoRoot
$includedBytes = [long](($fileSets.Included | Measure-Object -Property Length -Sum).Sum)
if (-not $includedBytes) { $includedBytes = 0 }
$excludedBytes = [long](($fileSets.Excluded | Measure-Object -Property Length -Sum).Sum)
if (-not $excludedBytes) { $excludedBytes = 0 }
$targetRoot = Find-GoogleDriveTarget $repoRoot $BackupTarget
$looksCloud = ($targetRoot -notlike (Join-Path $env:USERPROFILE 'MathAI_Backups_Local*'))

Write-Section 'MathAI 每日備份盤點'
Write-Host "Repo          : $repoRoot"
Write-Host "Branch        : $($git.branch)"
Write-Host "Commit        : $($git.commit)"
Write-Host "Git dirty     : $($git.dirty)"
Write-Host "Included files: $($fileSets.Included.Count)"
Write-Host "Included size : $(Format-Bytes $includedBytes)"
Write-Host "Excluded files: $($fileSets.Excluded.Count)"
Write-Host "Excluded size : $(Format-Bytes $excludedBytes)"
Write-Host "Backup target : $targetRoot"
Write-Host "Cloud detected: $looksCloud"
Write-Host "14份粗估上限 : $(Format-Bytes ($includedBytes * [long]$MaxBackups))"

if ($AuditOnly) {
    Write-Host ""
    Write-Host 'AUDIT ONLY：沒有建立 ZIP，也沒有修改任何專案檔案。' -ForegroundColor Yellow
    if (-not $looksCloud) {
        Write-Host '尚未偵測到 Google Drive 同步路徑；正式備份前可用 .mathai_backup_target.txt 指定。' -ForegroundColor Yellow
    }
    exit 0
}

New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmm'
$shortSha = if ($git.commit.Length -ge 8) { $git.commit.Substring(0,8) } else { $git.commit }
$safeBranch = ($git.branch -replace '[^A-Za-z0-9._-]', '-')
$baseName = "MathAI_Backup_${stamp}_${safeBranch}_${shortSha}"
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) $baseName
$payload = Join-Path $tempRoot 'MathAI'
$manifestPath = Join-Path $tempRoot 'BACKUP_MANIFEST.json'
$restorePath = Join-Path $tempRoot 'RESTORE_README.txt'
$zipPath = Join-Path $targetRoot ($baseName + '.zip')
$shaPath = $zipPath + '.sha256.txt'

if (Test-Path $tempRoot) { Remove-Item -Recurse -Force $tempRoot }
New-Item -ItemType Directory -Force -Path $payload | Out-Null

try {
    Write-Section '建立換機備份包'
    $n = 0
    foreach ($file in $fileSets.Included) {
        $rel = [IO.Path]::GetRelativePath($repoRoot, $file.FullName)
        $dest = Join-Path $payload $rel
        $parent = Split-Path -Parent $dest
        if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
        $n++
        if (($n % 500) -eq 0) { Write-Host "Copied $n / $($fileSets.Included.Count)" }
    }

    $manifest = [ordered]@{
        created_at = (Get-Date).ToString('o')
        machine = $env:COMPUTERNAME
        repo_root = $repoRoot
        git = $git
        included_file_count = $fileSets.Included.Count
        included_bytes = $includedBytes
        excluded_file_count = $fileSets.Excluded.Count
        excluded_bytes = $excludedBytes
        backup_target = $targetRoot
        cloud_target_detected = $looksCloud
        secrets_included = $false
        note = 'Local secrets/API keys are intentionally excluded. Restore them from Streamlit Cloud/password manager, not from this ZIP.'
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    @"
MathAI 換機備份

1. 正式程式碼優先從 GitHub clone：$($git.remote)
2. 此 ZIP 用來補回未追蹤資料、文件、資料包與本機工作成果。
3. .venv / cache / .git 未收錄；新電腦請重新建立虛擬環境。
4. secrets.toml / .env / credentials / token 未收錄，避免 API Key 明文進雲端。
5. 目前備份 branch：$($git.branch)
6. 目前 commit：$($git.commit)
7. 還原後先執行 requirements 安裝與 smoke tests，再開始開發。
"@ | Set-Content -LiteralPath $restorePath -Encoding UTF8

    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
    Compress-Archive -Path (Join-Path $tempRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
    "$hash  $(Split-Path -Leaf $zipPath)" | Set-Content -LiteralPath $shaPath -Encoding ASCII

    # Simple capacity-safe retention: keep the newest N backup ZIPs and matching checksums.
    $backups = @(Get-ChildItem -LiteralPath $targetRoot -Filter 'MathAI_Backup_*.zip' -File | Sort-Object LastWriteTime -Descending)
    if ($backups.Count -gt $MaxBackups) {
        foreach ($old in $backups[$MaxBackups..($backups.Count - 1)]) {
            $oldSha = $old.FullName + '.sha256.txt'
            Remove-Item -LiteralPath $old.FullName -Force
            if (Test-Path $oldSha) { Remove-Item -LiteralPath $oldSha -Force }
        }
    }

    $zipBytes = (Get-Item -LiteralPath $zipPath).Length
    $allZipBytes = [long]((Get-ChildItem -LiteralPath $targetRoot -Filter 'MathAI_Backup_*.zip' -File | Measure-Object Length -Sum).Sum)
    Write-Host ""
    Write-Host 'BACKUP PASS' -ForegroundColor Green
    Write-Host "ZIP           : $zipPath"
    Write-Host "ZIP size      : $(Format-Bytes $zipBytes)"
    Write-Host "Retained ZIPs : $((Get-ChildItem -LiteralPath $targetRoot -Filter 'MathAI_Backup_*.zip' -File).Count) / $MaxBackups"
    Write-Host "Backup usage  : $(Format-Bytes $allZipBytes)"
    if (-not $looksCloud) {
        Write-Host '注意：這次只備份到本機 fallback，尚未確認 Google Drive 同步。' -ForegroundColor Yellow
    }
}
finally {
    if (Test-Path $tempRoot) { Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue }
}
