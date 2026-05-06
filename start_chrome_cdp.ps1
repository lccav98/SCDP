# Abre o Google Chrome com depuração remota ativa na porta 9222.
# Execute no PowerShell antes de rodar o bot.

$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"

if (-Not (Test-Path $chromePath)) {
    $chromePath = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
}

if (-Not (Test-Path $chromePath)) {
    Write-Error "Chrome não encontrado. Instale o Google Chrome e tente novamente."
    exit 1
}

# Fecha instâncias existentes do Chrome
Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Abrindo Chrome com CDP na porta 9222..."
Start-Process $chromePath -ArgumentList "--remote-debugging-port=9222", "--profile-directory=Default"

Write-Host ""
Write-Host "Chrome aberto. Faça login no SCDP normalmente."
Write-Host "Quando estiver em Aprovação -> Autoridade Superior, rode:"
Write-Host "  venv\Scripts\activate"
Write-Host "  python -m scdp_bot"
