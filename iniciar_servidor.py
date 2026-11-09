"""
========================================================
  SERVIDOR DE PRODUÇÃO — Gerador de Atividades SENAI
  Powered by Waitress (WSGI para Windows)
========================================================

Como usar:
  Duplo clique no iniciar.bat  OU  execute no terminal:
      python iniciar_servidor.py

Acesso na rede local:
  http://<IP-DO-SERVIDOR>:5000

Para saber o IP do servidor, execute no terminal:
  ipconfig

Configuração do modelo de IA:
  Edite o arquivo .env na pasta do projeto.
========================================================
"""

import os
import sys
import subprocess
import time
import requests

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Garante que o diretório do projeto está no path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Se executado com o Python global, repassa automaticamente para o venv
venv_python = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
if os.path.exists(venv_python) and os.path.abspath(sys.executable).lower() != os.path.abspath(venv_python).lower():
    sys.exit(subprocess.call([venv_python] + sys.argv))

from dotenv import load_dotenv

# Carrega .env antes de importar o app
load_dotenv(os.path.join(BASE_DIR, ".env"))

def iniciar_ollama_se_necessario():
    """Garante que o Ollama esteja em execução em segundo plano."""
    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=1.5)
        if r.status_code == 200:
            print("  [IA] Servico Ollama ja esta em execucao.")
            return True
    except Exception:
        pass

    print("  [IA] Iniciando o servico Ollama em segundo plano...")
    try:
        flags = 0
        if os.name == 'nt':
            # DETACHED_PROCESS (0x00000008) + CREATE_NO_WINDOW (0x08000000)
            flags = 0x00000008 | 0x08000000

        caminho_ollama = "ollama"
        padrao_appdata = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        if os.path.exists(padrao_appdata):
            caminho_ollama = padrao_appdata

        subprocess.Popen(
            [caminho_ollama, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags
        )
        time.sleep(2)
        print("  [IA] Servico Ollama inicializado com sucesso.")
        return True
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel iniciar o Ollama automaticamente: {e}")
        return False

from waitress import serve
from app import app

HOST    = os.environ.get("SERVER_HOST",    "0.0.0.0")
PORT    = int(os.environ.get("SERVER_PORT",    "5000"))
THREADS = int(os.environ.get("SERVER_THREADS", "4"))
MODELO  = os.environ.get("OLLAMA_MODEL",   "llama3.2")
PROVIDER = os.environ.get("IA_PROVIDER",   "auto").strip().lower()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

if __name__ == "__main__":
    print("=" * 60)
    print("  GERADOR DE ATIVIDADES SENAI — Servidor Waitress")
    print("=" * 60)
    
    if PROVIDER in ("auto", "ollama"):
        iniciar_ollama_se_necessario()
        print(f"  [IA] Provedor Primario: Ollama ({MODELO})")
        if GEMINI_KEY:
            print("  [IA] Fallback de Nuvem: Google Gemini Ativo")
    elif PROVIDER == "gemini":
        print(f"  [IA] Provedor Ativo: Google Gemini ({os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')})")
    else:
        print(f"  [IA] Provedor Ativo: {PROVIDER}")

    print(f"  [OK] Servidor iniciado em http://{HOST}:{PORT}")
    print(f"  [OK] Threads: {THREADS} (conexoes simultaneas)")
    print(f"  [OK] Modo: PRODUCAO (Waitress WSGI)")
    print()
    print("  Compartilhe o endereco abaixo com os professores:")
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
        channel_timeout=300,
        cleanup_interval=30,
        connection_limit=100,
        asyncore_use_poll=True
    )
