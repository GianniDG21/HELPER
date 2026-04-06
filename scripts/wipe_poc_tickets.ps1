# Azzera tutti i ticket (DB reparto) e tutte le righe registry pratiche.
# Eseguite da cartella progetto con Docker Compose attivo:
#   .\scripts\wipe_poc_tickets.ps1
#
# Non tocca aziende, dipendenti o clienti seed — solo tickets, mail simulate e pratiche.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$sectorSql = "TRUNCATE TABLE tickets RESTART IDENTITY CASCADE;"
$praticheSql = "TRUNCATE TABLE pratiche RESTART IDENTITY;"

$services = @("postgres_vendita", "postgres_acquisto", "postgres_manutenzione")
foreach ($s in $services) {
    Write-Host "Wipe tickets: $s ..."
    docker compose exec -T $s psql -U team -d tickets -v ON_ERROR_STOP=1 -c $sectorSql
}
Write-Host "Wipe registry pratiche ..."
docker compose exec -T pratiche psql -U team -d pratiche -v ON_ERROR_STOP=1 -c $praticheSql

Write-Host "Fatto. Riavvia o aggiorna la pagina /ui e svuota cache locale (opzionale: sessionStorage/localStorage browser)."
