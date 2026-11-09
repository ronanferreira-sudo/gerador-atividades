import os
import json
import logging
import requests
import urllib3
from dotenv import load_dotenv

# Desativa alertas de certificados em redes corporativas com proxy (ex: SENAI)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# Configuração de logger específico para IA
logger = logging.getLogger("ia_client")


def obter_config_ia():
    """
    Retorna a configuração dinâmica de IA baseada no arquivo .env atualizado.
    Suporta: Ollama, Gemini, Grok (xAI), Groq e OpenAI.
    """
    provider = os.environ.get("IA_PROVIDER", "auto").strip().lower()
    
    # 1. Configurações do Ollama
    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b").strip()
    try:
        ollama_timeout = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
    except ValueError:
        ollama_timeout = 120

    # 2. Configurações do Google Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    try:
        gemini_timeout = int(os.environ.get("GEMINI_TIMEOUT", "30"))
    except ValueError:
        gemini_timeout = 30

    # 3. Configurações do Grok (xAI)
    grok_key = (os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY") or "").strip()
    grok_url = os.environ.get("GROK_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    grok_model = os.environ.get("GROK_MODEL", "grok-2-latest").strip()

    # 4. Configurações do Groq (GroqCloud - Ultra Rápido)
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    groq_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

    # 5. Configurações Genéricas OpenAI / LM Studio
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    openai_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

    return {
        "provider": provider,
        "ollama": {
            "url": ollama_url,
            "model": ollama_model,
            "timeout": ollama_timeout
        },
        "gemini": {
            "api_key": gemini_key,
            "model": gemini_model,
            "timeout": gemini_timeout
        },
        "grok": {
            "api_key": grok_key,
            "base_url": grok_url,
            "model": grok_model,
            "timeout": 45
        },
        "groq": {
            "api_key": groq_key,
            "base_url": groq_url,
            "model": groq_model,
            "timeout": 30
        },
        "openai": {
            "api_key": openai_key,
            "base_url": openai_url,
            "model": openai_model,
            "timeout": 45
        }
    }


def verificar_ollama_online(timeout=1.5):
    """Verifica rapidamente se o Ollama está rodando localmente."""
    cfg = obter_config_ia()["ollama"]
    try:
        r = requests.get(f"{cfg['url']}/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _chamar_gemini(prompt: str, system_prompt: str = None, max_tokens: int = 2000, temperature: float = 0.2, timeout: int = 30) -> str:
    """Chamada REST direta para a API do Google Gemini."""
    cfg = obter_config_ia()["gemini"]
    api_key = cfg["api_key"]
    if not api_key:
        return ""

    model = cfg["model"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    contents = []
    if system_prompt:
        contents.append({
            "role": "user",
            "parts": [{"text": f"Instrução do Sistema:\n{system_prompt}\n\nTarefa:\n{prompt}"}]
        })
    else:
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
    }

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=timeout or cfg["timeout"]
    )

    if resp.status_code == 200:
        dados = resp.json()
        candidatos = dados.get("candidates", [])
        if candidatos:
            partes = candidatos[0].get("content", {}).get("parts", [])
            textos = [p.get("text", "") for p in partes if "text" in p]
            return "".join(textos).strip()
    return ""


def _chamar_api_compativel(base_url: str, api_key: str, model: str, prompt: str, system_prompt: str = None, max_tokens: int = 2000, temperature: float = 0.2, timeout: int = 45) -> str:
    """Chamada para APIs no padrão OpenAI (Grok, Groq, LM Studio, OpenAI)."""
    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        return ""

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout, verify=False)
    if resp.status_code == 200:
        dados = resp.json()
        escolhas = dados.get("choices", [])
        if escolhas:
            return escolhas[0].get("message", {}).get("content", "").strip()
    else:
        logger.warning(f"Erro na API ({resp.status_code}): {resp.text[:200]}")
    return ""


def _chamar_ollama(prompt: str, system_prompt: str = None, max_tokens: int = 2000, temperature: float = 0.2, timeout: int = None) -> str:
    """Chamada local para o Ollama."""
    cfg = obter_config_ia()["ollama"]
    prompt_completo = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    payload = {
        "model": cfg["model"],
        "prompt": prompt_completo,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }

    resp = requests.post(
        f"{cfg['url']}/api/generate",
        json=payload,
        timeout=timeout or cfg["timeout"]
    )

    if resp.status_code == 200:
        return resp.json().get("response", "").strip()
    return ""


def chamar_ia(prompt: str, system_prompt: str = None, max_tokens: int = 2000, temperature: float = 0.2, timeout: int = None) -> str:
    """
    Chama a IA de acordo com a estratégia configurada em .env com fallback automático.
    Suporta: Grok, Groq, Gemini, Ollama e OpenAI.
    """
    config = obter_config_ia()
    provider = config["provider"]

    # 1. Se GROK (xAI) for selecionado
    if provider == "grok":
        g = config["grok"]
        try:
            res = _chamar_api_compativel(g["base_url"], g["api_key"], g["model"], prompt, system_prompt, max_tokens, temperature, timeout or g["timeout"])
            if res:
                return res
        except Exception as e:
            logger.warning(f"[IA] Falha ao chamar Grok: {e}")

    # 2. Se GROQ (GroqCloud) for selecionado
    elif provider == "groq":
        q = config["groq"]
        try:
            res = _chamar_api_compativel(q["base_url"], q["api_key"], q["model"], prompt, system_prompt, max_tokens, temperature, timeout or q["timeout"])
            if res:
                return res
        except Exception as e:
            logger.warning(f"[IA] Falha ao chamar Groq: {e}")

    # 3. Se GEMINI for selecionado
    elif provider == "gemini":
        try:
            res = _chamar_gemini(prompt, system_prompt, max_tokens, temperature, timeout)
            if res:
                return res
        except Exception as e:
            logger.warning(f"[IA] Falha ao chamar Gemini: {e}")

    # 4. Se OPENAI genérico for selecionado
    elif provider == "openai":
        o = config["openai"]
        try:
            res = _chamar_api_compativel(o["base_url"], o["api_key"], o["model"], prompt, system_prompt, max_tokens, temperature, timeout or o["timeout"])
            if res:
                return res
        except Exception as e:
            logger.warning(f"[IA] Falha ao chamar OpenAI: {e}")

    # 5. Padrão (Ollama ou Auto com Fallback Inteligente)
    # Tenta Ollama local primeiro se estiver online
    if verificar_ollama_online():
        try:
            res = _chamar_ollama(prompt, system_prompt, max_tokens, temperature, timeout)
            if res:
                return res
        except Exception as e:
            logger.warning(f"[IA] Ollama falhou ou timed out: {e}")

    # Fallback para Grok se a chave estiver configurada
    if config["grok"]["api_key"]:
        g = config["grok"]
        try:
            res = _chamar_api_compativel(g["base_url"], g["api_key"], g["model"], prompt, system_prompt, max_tokens, temperature, timeout or g["timeout"])
            if res:
                return res
        except Exception:
            pass

    # Fallback para Groq se a chave estiver configurada
    if config["groq"]["api_key"]:
        q = config["groq"]
        try:
            res = _chamar_api_compativel(q["base_url"], q["api_key"], q["model"], prompt, system_prompt, max_tokens, temperature, timeout or q["timeout"])
            if res:
                return res
        except Exception:
            pass

    # Fallback para Gemini se existir chave
    if config["gemini"]["api_key"]:
        try:
            res = _chamar_gemini(prompt, system_prompt, max_tokens, temperature, timeout)
            if res:
                return res
        except Exception:
            pass

    return ""
