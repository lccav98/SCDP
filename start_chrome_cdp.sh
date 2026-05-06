#!/bin/bash
# Fecha o Chrome normal e reabre com depuração remota ativa na porta 9222.
# O perfil padrão do seu usuário é mantido — sessões e senhas salvas funcionam normalmente.

echo "Fechando o Chrome..."
osascript -e 'quit app "Google Chrome"' 2>/dev/null
sleep 2

echo "Abrindo Chrome com CDP na porta 9222..."
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Default" &

echo "Chrome aberto. Faça login no SCDP normalmente."
echo "Quando estiver na tela de Aprovação → Autoridade Superior, rode: python -m scdp_bot"
