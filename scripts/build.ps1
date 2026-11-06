# VideoSlim 构建脚本（PowerShell 版，等价于 build.cmd）
# 用法：
#   pwsh -File scripts/build.ps1
#   pwsh scripts/build.ps1

$ErrorActionPreference = 'Stop'

# 只影响本脚本的调用环境，不污染用户的会话
$env:PYTHONUTF8 = '1'

# 切换到项目根目录（脚本所在目录的上一级），保证相对路径解析正确
$scriptDir = $PSScriptRoot
$projectRoot = Split-Path -Parent $scriptDir
Push-Location $projectRoot

try {
    # 定位项目本地 venv：优先 .venv，回退 venv
    $venvPy = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        $venvPy = Join-Path $projectRoot 'venv\Scripts\python.exe'
    }
    if (-not (Test-Path $venvPy)) {
        Write-Host '未找到 .venv 或 venv，请先创建虚拟环境并安装依赖：'
        Write-Host '    python -m venv .venv'
        Write-Host '    .venv\Scripts\python.exe -m pip install -e .[dev]'
        exit 1
    }

    # 构建目录（产物统一放在 scripts/output/，避免污染项目根）
    $buildDir = Join-Path $scriptDir 'output'
    $distDir = Join-Path $buildDir 'dist'
    $workDir = Join-Path $buildDir 'build'

    New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

    # 使用 venv 中的 PyInstaller 构建单文件应用
    # 路径全部用绝对路径：相对路径会以 --specpath 为基准解析，
    # 而 --specpath 设到 scripts/output/，会把 ./tools/... 解析错。
    # --add-data 的 "源;目标目录" 需先拼成单个字符串（逗号优先级高于 +，不能内联拼接）
    $ffmpegData = (Join-Path $projectRoot 'tools\ffmpeg.exe') + ';tools'
    $iconData = (Join-Path $projectRoot 'tools\icon.ico') + ';tools'

    $pyInstallerArgs = @(
        '-m', 'PyInstaller'
        '--onefile'
        '--name', 'VideoSlim'
        '--noconsole'
        '--icon', (Join-Path $projectRoot 'tools\icon.ico')
        '--add-data', $ffmpegData
        '--add-data', $iconData
        '--specpath', $buildDir
        '--distpath', $distDir
        '--workpath', $workDir
        (Join-Path $projectRoot 'main.py')
    )

    # 清掉上一次残留的退出码，避免把旧值误判为本次失败
    $global:LASTEXITCODE = 0
    & $venvPy @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host '构建失败！'
        exit $LASTEXITCODE
    }

    Write-Host "build success! executable file is located at: $(Join-Path $distDir 'VideoSlim.exe')"

    # 复制配置文件和其他必要文件到输出目录
    Copy-Item -Force -Path (Join-Path $projectRoot 'config.json') -Destination $distDir -ErrorAction SilentlyContinue

    # 清理临时文件（可选）
    # Remove-Item -Recurse -Force $workDir -ErrorAction SilentlyContinue

    # 交互式运行时保持窗口不关闭；CI 中不阻塞
    if (-not $env:CI) {
        Read-Host '按 Enter 键退出' | Out-Null
    }
}
finally {
    Pop-Location
}
