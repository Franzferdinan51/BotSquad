$action = New-ScheduledTaskAction -Execute "C:\Users\franz\AgentShared\scripts\run-orchestrator.cmd"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "BotSquadOrchestrator" -Action $action -Trigger $trigger -Settings $settings -Description "Runs the Watcher -> Brain -> Executor loop every 2 hours for the multi-agent Bot Squad system." -Force
