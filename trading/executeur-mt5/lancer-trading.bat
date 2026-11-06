@echo off
rem Agents de trading automatiques : lancé par le Planificateur de tâches Windows à 8h55, du lundi au vendredi.
rem Repasse chaque minute jusqu'à 17h35. MetaTrader 5 doit être ouvert, avec Algo Trading au vert.
cd /d "%~dp0"
if not exist rapports mkdir rapports
py -I executeur_mt5.py --boucle >> rapports\boucle.log 2>&1
