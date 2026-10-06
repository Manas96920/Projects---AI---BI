param(
    [ValidateSet('weekly', 'monthly')][string]$Frequency = 'monthly',
    [ValidateSet('historical', 'calendar')][string]$Mode = 'historical',
    [ValidateSet('auto', 'off', 'required')][string]$Ai = 'auto',
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')][string]$At = '09:00',
    [string]$PythonExecutable,
    [switch]$Register
)
$ErrorActionPreference = 'Stop'
$reportRoot = $PSScriptRoot
# Resolve and verify global 3.12 instead of relying on an unconfigured py launcher.
$reportCandidates = @()
if ($PythonExecutable) { $reportCandidates += $PythonExecutable }
else {
    $reportCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($reportCommand) { $reportCandidates += $reportCommand.Source }
    $reportCandidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
}
$reportPython = $null
foreach ($reportCandidate in $reportCandidates) {
    if (-not (Test-Path -LiteralPath $reportCandidate)) { continue }
    $reportDetected = & $reportCandidate -c "import sys; print(sys.executable if sys.version_info[:2] == (3,12) and sys.prefix == sys.base_prefix else '')"
    if ($LASTEXITCODE -eq 0 -and $reportDetected) {
        $reportPython = $reportDetected.Trim()
        break
    }
}
if (-not $reportPython) {
    throw 'Global Python 3.12 was not found. Pass -PythonExecutable with its absolute python.exe path.'
}
$reportScript = Join-Path $reportRoot 'run_report.py'
$reportArguments = '"{0}" --frequency {1} --mode {2} --ai {3}' -f $reportScript, $Frequency, $Mode, $Ai
$taskName = 'Olist-Recurring-Report-{0}' -f $Frequency
Write-Output "Task: $taskName"
Write-Output "Python: $reportPython"
Write-Output "Arguments: $reportArguments"
Write-Output "Working directory: $reportRoot"
Write-Output "Schedule: $Frequency at $At in the Windows local timezone"
Write-Output 'Historical mode replays a static dataset; calendar mode requires ongoing ingestion.'
# Prepare native Task Scheduler XML without needing WMI trigger classes.
# Reference: Microsoft's DaysOfMonth/monthlyScheduleType XML example.
$reportBoundary = (Get-Date -Date $At).ToString('yyyy-MM-ddTHH:mm:ss')
if ($Frequency -eq 'weekly') {
    $reportCalendar = '<ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><Monday/></DaysOfWeek></ScheduleByWeek>'
} else {
    $reportCalendar = '<ScheduleByMonth><DaysOfMonth><Day>1</Day></DaysOfMonth><Months><January/><February/><March/><April/><May/><June/><July/><August/><September/><October/><November/><December/></Months></ScheduleByMonth>'
}
$reportUserSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$reportCommandXml = [System.Security.SecurityElement]::Escape($reportPython)
$reportArgumentsXml = [System.Security.SecurityElement]::Escape($reportArguments)
$reportDirectoryXml = [System.Security.SecurityElement]::Escape($reportRoot)
$reportTaskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Read-only Olist PostgreSQL to PDF pipeline, global Python 3.12</Description></RegistrationInfo>
  <Triggers><CalendarTrigger><StartBoundary>$reportBoundary</StartBoundary><Enabled>true</Enabled>$reportCalendar</CalendarTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>$reportUserSid</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled><ExecutionTimeLimit>PT15M</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>$reportCommandXml</Command><Arguments>$reportArgumentsXml</Arguments><WorkingDirectory>$reportDirectoryXml</WorkingDirectory></Exec></Actions>
</Task>
"@
# XML parsing catches malformed paths/content before writing or registration.
$null = [xml]$reportTaskXml
$reportScheduleDir = Join-Path $reportRoot 'schedules'
$null = New-Item -ItemType Directory -Path $reportScheduleDir -Force
$reportXmlPath = Join-Path $reportScheduleDir ('olist_{0}.xml' -f $Frequency)
$reportTaskXml | Set-Content -LiteralPath $reportXmlPath -Encoding Unicode
Write-Output "Prepared task XML: $reportXmlPath"
if (-not $Register) {
    Write-Output 'Preview only. Add -Register to create the scheduled task.'
    return
}
# Do not silently replace an unrelated or customized existing task.
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    throw "Task $taskName already exists. Review or remove it in Task Scheduler before registering again."
}
Register-ScheduledTask -TaskName $taskName -Xml $reportTaskXml | Select-Object TaskName, State
Write-Output "Registered. Test with: Start-ScheduledTask -TaskName '$taskName'"
