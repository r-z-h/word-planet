# 一键重建 RAG 知识库索引。
# 用法（仓库根目录）：  .\tools\rebuild_kb.ps1
# 说明：重建后，正在运行的后端会在下一次提问时自动热加载新索引，无需重启。

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'

Write-Host "重建知识库索引 ..." -ForegroundColor Cyan
Push-Location $Backend
try {
    & '.\.venv\Scripts\python.exe' -m rag_engine.build_index
} finally {
    Pop-Location
}
Write-Host "完成。后端下一次提问会自动加载新索引（无需重启）。" -ForegroundColor Green
