"""
========================================================
  SERVIDOR DE PRODUÇÃO — Gerador de Atividades SENAI
  Powered by Waitress (WSGI para Windows)
========================================================

Como usar:
  Duplo clique neste arquivo  OU  execute no terminal:
      python iniciar_servidor.py

Acesso na rede local:
  http://<IP-DO-SERVIDOR>:5000

Para saber o IP do servidor, execute no terminal:
  ipconfig

Configuração no novo computador (GPU):
  Edite o arquivo .env na pasta do projeto.
  Variáveis de ambiente adicionais do Ollama (Windows):
    OLLAMA_NUM_PARALLEL = 4
    OLLAMA_MAX_LOADED_MODELS = 1
========================================================
"""

import os
import sys
from dotenv import load_dotenv

# Garante que o diretório do projeto está no path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Carrega .env antes de importar o app
load_dotenv(os.path.join(BASE_DIR, ".env"))

from waitress import serve
from app import app

HOST    = os.environ.get("SERVER_HOST",    "0.0.0.0")
PORT    = int(os.environ.get("SERVER_PORT",    "5000"))
THREADS = int(os.environ.get("SERVER_THREADS", "4"))

if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 GERADOR DE ATIVIDADES SENAI — Servidor Waitress")
    print("=" * 60)
    print(f"  ✅ Servidor iniciado em http://{HOST}:{PORT}")
    print(f"  ✅ Threads: {THREADS} (conexões simultâneas)")
    print(f"  ✅ Modo: PRODUÇÃO (Waitress WSGI)")
    print()
    print("  📡 Compartilhe o endereço abaixo com os professores:")
    print(f"     http://<SEU-IP-LOCAL>:{PORT}")
    print()
    print("  Para descobrir seu IP: execute  ipconfig  no terminal")
    print("  Pressione CTRL+C para encerrar o servidor.")
    print("=" * 60)

    serve(
        app,
        host=HOST,
        port=PORT,
        threads=THREADS,
        channel_timeout=300,       # Aguarda até 5 min por requisição (geração de IA)
        cleanup_interval=30,       # Limpeza de conexões a cada 30s
        connection_limit=100,      # Máximo de conexões simultâneas
        asyncore_use_poll=True
    )
