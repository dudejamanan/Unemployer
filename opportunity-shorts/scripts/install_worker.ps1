$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$taskPythonPath = (Get-Command python).Source
$venvPythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPythonPath) { $taskPythonPath = $venvPythonPath }
$resolvedPythonPath = (& $taskPythonPath -c 'import sys; print(sys.executable)').Trim()
if (Test-Path -LiteralPath $resolvedPythonPath) { $taskPythonPath = $resolvedPythonPath }
$hiddenPythonPath = Join-Path (Split-Path -Parent $taskPythonPath) 'pythonw.exe'
if (Test-Path -LiteralPath $hiddenPythonPath) { $taskPythonPath = $hiddenPythonPath }
$workerScriptPath = Join-Path $PSScriptRoot 'worker.py'
$taskAction = New-ScheduledTaskAction -Execute $taskPythonPath -Argument ('"' + $workerScriptPath + '"') -WorkingDirectory $projectPath
$taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$taskSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
$taskPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'OpportunityShortsWorker' -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -Principal $taskPrincipal -Force | Out-Null
Start-ScheduledTask -TaskName 'OpportunityShortsWorker'
Write-Output 'Worker installed and started. Log: data/opportunities.worker.log. The computer must stay awake and connected.'
