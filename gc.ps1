# 安全的 git commit 助手 —— 绕过 PowerShell 的长输入 / 编码坑
#
# 为什么需要它？
#   PowerShell 5.1 有两个反复咬人的问题：
#
#   ① PSReadLine 遇到【长多行输入】会崩：
#        System.ArgumentOutOfRangeException: top 实际值是 -7
#      它会把整个输入历史反复重渲染、刷屏堆栈，
#      而且崩溃后该终端里后续命令（如 git push）可能静默超时。
#      → 本项目已踩坑 2 次，都是在大段中文 commit message 上。
#
#   ② 本脚本自身必须是 UTF-8【带 BOM】的 .ps1，
#      否则 PowerShell 5.1 会按 GBK 解码中文注释，
#      报出"字符串缺少终止符"之类完全不相干的错误。
#
# 用法：
#   .\gc.ps1 -Message "简短标题"                 # 单行消息
#   .\gc.ps1 -MessageFile .\_msg.txt            # 从文件读（多行推荐）
#   .\gc.ps1 -MessageFile .\_msg.txt -NoPush    # 只提交不推送
#
# 多行消息工作流：
#   1. 把 message 写进 UTF-8 的 .txt（用 VSCode，别用命令行 here-string）
#      文件名以 _msg 开头 —— .gitignore 已忽略，不会误入库
#   2. 执行  .\gc.ps1 -MessageFile .\_msg.txt
#   3. 确认后删掉临时文件

# 注意参数名不用 -File：
#   -File 是 PowerShell 宿主自己的保留参数（powershell.exe -File ...），
#   作为脚本参数名容易出诡异问题，故用 -MessageFile。
param(
    [Parameter(Position = 0)]
    [string]$Message,

    [string]$MessageFile,

    [switch]$NoPush
)

$ErrorActionPreference = 'Stop'

function Write-Info($text) { Write-Host $text -ForegroundColor Cyan }
function Write-Warn2($text) { Write-Host $text -ForegroundColor Yellow }
function Write-Fail($text) { Write-Host $text -ForegroundColor Red }

# 统一在仓库根目录执行（脚本所在目录）
Push-Location $PSScriptRoot
try {
    Write-Info "工作目录：$PWD"

    # 1. 暂存 + 安全检查：绝对不能提交 .env
    git add -A
    $staged = @(git diff --cached --name-only)

    if ($staged.Count -eq 0) {
        Write-Warn2 "[跳过] 没有需要提交的改动"
        return
    }

    Write-Info "待提交文件（$($staged.Count) 个）："
    $staged | ForEach-Object { Write-Host "  $_" }

    if ($staged -contains '.env') {
        Write-Fail "!! 危险：.env 被暂存了，已中止提交！"
        Write-Fail "   请检查 .gitignore 里是否有 .env"
        git reset | Out-Null
        return
    }

    # 2. 提交
    #    刻意不用 elseif：PowerShell 里 else/elseif 必须跟在
    #    上一个 } 的同一行，写在下一行会被当成新语句而报语法错。
    #    用「提前 return + 单层 if/else」最不容易踩坑。
    Write-Info "正在提交……"

    if ($MessageFile) {
        if (-not (Test-Path $MessageFile)) {
            Write-Fail "找不到文件：$MessageFile"
            return
        }
        # -F 让 git 从文件读 message，彻底不在命令行传长字符串
        git commit -F $MessageFile
    } else {
        if (-not $Message) {
            Write-Warn2 "请提供消息：.\gc.ps1 -Message '标题'  或  .\gc.ps1 -MessageFile .\_msg.txt"
            return
        }
        git commit -m $Message
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "提交失败（exit $LASTEXITCODE）"
        return
    }

    # 3. 推送
    #    单独一步，这样即使网络失败也能看清"提交成功但推送失败"的状态
    if ($NoPush) {
        Write-Warn2 "已按 -NoPush 跳过推送。需要时执行：git push"
        return
    }

    Write-Info "正在推送……"
    git push
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "推送失败（exit $LASTEXITCODE）。"
        Write-Warn2 "提交已在本地保存，网络恢复后重跑：git push"
        return
    }

    Write-Info "完成。"
}
finally {
    Pop-Location
}
