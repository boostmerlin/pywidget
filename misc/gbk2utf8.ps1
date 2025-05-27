<#
.SYNOPSIS
    将 GB2312/GBK 编码文件批量转换为 UTF-8 编码（无 BOM）
.PARAMETER Path
    目标目录路径（默认当前目录）
.PARAMETER Filter
    文件扩展名过滤（默认 *.cpp）
.PARAMETER Recurse
    是否递归处理子目录
.EXAMPLE
    .\gbk2utf8.ps1 -Path "C:\Files" -Filter "*.csv" -Recurse
#>
param(
    [string]$Path = ".",
    [string]$Filter = "*.cpp",
    [switch]$Recurse
)

# 添加编码支持
Add-Type -AssemblyName System.Text.Encoding
Add-Type -AssemblyName System.IO

# 使用更可靠的编码检测方法
function Test-FileEncoding {
    param([string]$FilePath)
    
    try {
        # 先读取文件开头的几个字节来检测BOM标记
        $stream = New-Object System.IO.FileStream($FilePath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read)
        $bom = New-Object byte[](4)
        $bytesRead = $stream.Read($bom, 0, 4)
        $stream.Close()
        
        # 检测BOM标记
        if ($bytesRead -ge 3 -and $bom[0] -eq 0xEF -and $bom[1] -eq 0xBB -and $bom[2] -eq 0xBF) { 
            return 'UTF8-BOM' 
        }
        elseif ($bytesRead -ge 2 -and $bom[0] -eq 0xFF -and $bom[1] -eq 0xFE) { 
            return 'Unicode' 
        }
        elseif ($bytesRead -ge 2 -and $bom[0] -eq 0xFE -and $bom[1] -eq 0xFF) { 
            return 'BigEndianUnicode' 
        }
        else {
            # 进一步检测，尝试判断是否为GB2312/GBK
            # 这里做一个简单的启发式判断：尝试以GB2312解码再以UTF8重编码，
            # 如果过程中出现解码错误或内容变化，则可能是UTF8而非GB2312
            $bytes = [System.IO.File]::ReadAllBytes($FilePath)
            
            # 尝试用UTF8解码
            $utf8Encoding = [System.Text.Encoding]::UTF8
            $isValidUtf8 = $true
            
            # 检查是否为有效的UTF8编码
            try {
                $utf8Encoding.GetString($bytes) | Out-Null
            }
            catch {
                $isValidUtf8 = $false
            }
            
            if ($isValidUtf8) {
                # 进一步验证UTF8有效性
                $charCount = 0
                for ($i = 0; $i -lt $bytes.Length; $i++) {
                    if (($bytes[$i] -band 0x80) -eq 0) {
                        # ASCII字符
                        $charCount++
                        continue
                    }
                    elseif (($bytes[$i] -band 0xE0) -eq 0xC0) {
                        # 2字节UTF8序列
                        if ($i + 1 -lt $bytes.Length -and ($bytes[$i + 1] -band 0xC0) -eq 0x80) {
                            $charCount++
                            $i += 1
                            continue
                        }
                    }
                    elseif (($bytes[$i] -band 0xF0) -eq 0xE0) {
                        # 3字节UTF8序列
                        if ($i + 2 -lt $bytes.Length -and 
                            ($bytes[$i + 1] -band 0xC0) -eq 0x80 -and 
                            ($bytes[$i + 2] -band 0xC0) -eq 0x80) {
                            $charCount++
                            $i += 2
                            continue
                        }
                    }
                    elseif (($bytes[$i] -band 0xF8) -eq 0xF0) {
                        # 4字节UTF8序列
                        if ($i + 3 -lt $bytes.Length -and 
                            ($bytes[$i + 1] -band 0xC0) -eq 0x80 -and 
                            ($bytes[$i + 2] -band 0xC0) -eq 0x80 -and 
                            ($bytes[$i + 3] -band 0xC0) -eq 0x80) {
                            $charCount++
                            $i += 3
                            continue
                        }
                    }
                    
                    # 如果到这里，说明不是有效的UTF8
                    $isValidUtf8 = $false
                    break
                }
            }
            
            # 如果是有效的UTF8编码但没有BOM，返回UTF8
            if ($isValidUtf8) {
                return 'UTF8'
            }
            
            # 否则假定为GB2312/GBK
            return 'GB2312/GBK'
        }
    }
    catch {
        Write-Error "检测文件编码时出错: $_"
        return 'Unknown'
    }
}

# 核心转换函数
function Convert-FileEncoding {
    param(
        [string]$FilePath,
        [string]$FromEncoding,
        [string]$ToEncoding
    )
    
    try {
        # 根据源编码读取内容
        $srcEncoding = switch ($FromEncoding) {
            'GB2312/GBK' { [System.Text.Encoding]::GetEncoding(936) } # 936是GB2312/GBK的代码页
            'UTF8-BOM'   { [System.Text.Encoding]::UTF8 }
            'UTF8'       { [System.Text.Encoding]::UTF8 }
            'Unicode'    { [System.Text.Encoding]::Unicode }
            'BigEndianUnicode' { [System.Text.Encoding]::BigEndianUnicode }
            default      { [System.Text.Encoding]::Default }
        }
        
        # 目标编码设置
        $destEncoding = switch ($ToEncoding) {
            'UTF8-BOM'   { [System.Text.Encoding]::UTF8 }
            'UTF8'       { New-Object System.Text.UTF8Encoding($false) } # 无BOM的UTF8
            default      { New-Object System.Text.UTF8Encoding($false) }
        }
        
        # 读取全部字节
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        
        # 解码为字符串
        $content = $srcEncoding.GetString($bytes)
        
        # 重新编码并写入
        [System.IO.File]::WriteAllText($FilePath, $content, $destEncoding)
        
        return $true
    }
    catch {
        Write-Error "转换文件编码时出错 [$FilePath]: $_"
        return $false
    }
}

# 主处理逻辑
Write-Host "开始扫描文件..." -ForegroundColor Cyan
$files = Get-ChildItem -Path $Path -Filter $Filter -Recurse:$Recurse -File
$totalFiles = $files.Count
$convertedCount = 0
$skippedCount = 0
$errorCount = 0

Write-Host "找到 $totalFiles 个文件，开始处理..." -ForegroundColor Cyan

foreach ($file in $files) {
    $encoding = Test-FileEncoding $file.FullName
    
    if ($encoding -eq 'GB2312/GBK') {
        Write-Host "处理文件: $($file.FullName) (检测为 $encoding)" -ForegroundColor Yellow
        
        $result = Convert-FileEncoding -FilePath $file.FullName -FromEncoding $encoding -ToEncoding 'UTF8'
        
        if ($result) {
            $convertedCount++
            Write-Host "  √ 转换成功!" -ForegroundColor Green
        }
        else {
            $errorCount++
            Write-Host "  × 转换失败!" -ForegroundColor Red
        }
    }
    else {
        $skippedCount++
        Write-Host "跳过文件: $($file.FullName) (检测为 $encoding)" -ForegroundColor DarkGray
    }
}

Write-Host "`n处理完成！" -ForegroundColor Cyan
Write-Host "总计扫描: $totalFiles 个文件" -ForegroundColor Cyan
Write-Host "成功转换: $convertedCount 个文件" -ForegroundColor Green
Write-Host "跳过文件: $skippedCount 个文件" -ForegroundColor Yellow
Write-Host "失败文件: $errorCount 个文件" -ForegroundColor Red
