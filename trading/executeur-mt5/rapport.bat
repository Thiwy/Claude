@echo off
rem Rapport de fin de journée : lancé par le Planificateur de tâches Windows à 17h45.
rem MetaTrader 5 doit être ouvert et connecté.
cd /d "%~dp0"
if not exist rapports mkdir rapports
claude -p "Utilise le skill rapport-journee pour faire le rapport de fin de journee." >> rapports\derniere-execution.log 2>&1
