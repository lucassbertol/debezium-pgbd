@echo off
rem Abre o psql do PostgreSQL de origem no ambiente criado por iniciar-web.ps1.
cd /d "%~dp0"
docker compose -p debezium-pgbd-demo-vazia -f compose.yaml -f compose.demo.yaml exec origem psql -U postgres -d catalogo
if errorlevel 1 pause
