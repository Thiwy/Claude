@echo off
rem Rapport de fin de journée : lancé par le Planificateur de tâches Windows à 17h45.
rem MetaTrader 5 doit être ouvert et connecté.
cd /d "%~dp0"
if not exist rapports mkdir rapports
claude -p "Utilise le skill rapport-journee pour faire le rapport de fin de journee." >> rapports\derniere-execution.log 2>&1
rem Copie des rapports dans OneDrive (Documents\trading\rapports), lisibles depuis le téléphone avec l'app OneDrive.
if defined OneDrive robocopy rapports "%OneDrive%\Documents\trading\rapports" *.md /NJH /NJS /NFL /NDL /NP >nul
py -I executeur_mt5.py --notifier "Le rapport du jour est pret : OneDrive > Documents > trading > rapports" >nul 2>&1
exit /b 0
