$ErrorActionPreference = 'Stop'
$composeArgs = @('compose', '-p', 'debezium-pgbd-demo-vazia', '-f', 'compose.yaml', '-f', 'compose.demo.yaml')

Push-Location -LiteralPath $PSScriptRoot
try {
    Write-Host 'Recriando o ambiente de demonstracao com dados vazios.'
    & docker @composeArgs down --volumes
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & docker @composeArgs up -d --build --wait --wait-timeout 180
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & docker @composeArgs exec -T web python /demo/inicializar.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host 'Abra http://127.0.0.1:18000/'
} finally {
    Pop-Location
}
