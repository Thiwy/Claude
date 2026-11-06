@echo off
rem Agents de trading automatiques : lancé par le Planificateur de tâches Windows à 8h55, du lundi au vendredi.
rem Repasse chaque minute jusqu'à 17h35. MetaTrader 5 doit être ouvert, avec Algo Trading au vert.
rem Ce qui s'affiche est aussi écrit dans rapports\boucle.log.
title Agents de trading - NE PAS FERMER
cd /d "%~dp0"
py -I executeur_mt5.py --boucle
