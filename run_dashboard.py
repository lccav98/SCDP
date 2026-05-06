#!/usr/bin/env python3
"""
Inicia o painel de acompanhamento de auditorias.
Acesse http://localhost:5000 após executar.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from scdp_bot.dashboard import run

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"Painel disponível em http://localhost:{port}")
    run(port=port)
