$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $StartupPath "RemotePrintAgent.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\Users\zesky\-remote-print-agent\dist\RemotePrintAgent.exe"
$Shortcut.WorkingDirectory = "C:\Users\zesky\-remote-print-agent"
$Shortcut.Description = "Remote Print Agent"
$Shortcut.Save()

Write-Host "Startup shortcut created at: $ShortcutPath"
