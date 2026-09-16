# 安全的 git commit 助手 —— 绕过 PowerShell/PSReadLine 的长输入崩溃
#
# 为什么需要它？
#   PowerShell 5.1 的 PSReadLine 在遇到【长多行输入】时会崩：
#       System.ArgumentOutOfRangeException: top 实际值是 -7
#   它会把整个输入历史反复重渲染，最后堆栈刷屏，
#   而且崩溃后终端里后续的命令（比如 git push）可能静默超时。
#
#   本项目已踩坑 2 次，都是在大段中文 commit message 上。
#
# 用法：
#   .\gc.ps1 "简短标题"                      # 单行消息
#   .\gc.ps1 -File .\commit_msg.txt          # 从文件读（推荐，支持多行）
#
# 推荐工作流（多行消息）：
#   1. 用编辑器/VSCode 把 message 写进一个 .txt（UTF-8）
#   2. 执行：  .\gc.ps1 -File .\commit_msg.txt
#   3. 脚本自动 commit + push，并顺手清理临时文件

param(
    [Parameter(Position = 0)]
    [string]$Message,

    [string]$File,

    [switch]$NoPush
)

$ErrorActionPreference = 'Stop'

# 统一在仓库根目录执行（脚本所在目录）
Push-Location $PSScriptRoot
try {
    # ---------------------------------------------------------------
    # 1. 安全检查：绝对不能提交 .env
    # ---------------------------------------------------------------
    git add -A
    $staged = git diff --cached --name-only
    if (-not $staged) {
        Write-Host "[跳过] 没有需要提交的改动" -ForegroundColor Yellow
        return
    }
    if ($staged -contains '.env') {
        Write-Host "!! 危险：.env 被暂存了，已中止提交！" -ForegroundColor Red
        Write-Host "   请检查 .gitignore 里是否有 .env" -ForegroundColor Red
        git reset | Out-Null
        return
    }
    Write-Host "待提交文件：" -ForegroundColor Cyan
    $staged | ForEach-Object { Write-Host "  $_" }

    # ---------------------------------------------------------------
    # 2. 提交
    #    -F 从文件读 message，彻底避免命令行传长字符串
    #
    #    ⚠️ 注意这里刻意【不用 elseif】：
    #       PowerShell 里 elseif/else 必须跟在上一个 } 的【同一行】，
    #       写在下一行会被当成新语句而报语法错
    #       （报错还挺有迷惑性：Try 语句缺少自己的 Catch 或 Finally 块）。
    #       用「提前 return + 单层 if/else」最不容易踩坑。
    # ---------------------------------------------------------------
    if ($File) {
        if (-not (Test-Path $File)) {
            Write-Host "找不到文件：$File" -ForegroundColor Red
            return
        }
        # 用 -F 读文件；git 会按 UTF-8 处理
        git commit -F $File
    } else {
        if (-not $Message) {
            Write-Host "请提供消息：.\gc.ps1 '标题'  或  .\gc.ps1 -File .\msg.txt" -ForegroundColor Yellow
            return
        }
        # 单行消息用 -m 没问题；多行请改用 -File
        git commit -m $Message
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "提交失败（exit $LASTEXITCODE）" -ForegroundColor Red
        return
    }

    # ---------------------------------------------------------------
    # 3. 推送
    #    单独一步，这样即使网络失败也能看到"提交成功但推送失败"的明确状态
    # ---------------------------------------------------------------
    if (-not $NoPush) {
        Write-Host "`n===== 推送 =====" -ForegroundColor Cyan
        git push
        if ($LASTEXITCODE -ne 0) {
            Write-Host "`n推送失败。提交已在本地，网络恢复后重跑：git push" -ForegroundColor Yellow
        }
    }
}
finally {
    Pop-Location
}
