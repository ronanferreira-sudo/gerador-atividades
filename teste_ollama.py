import requests
import time

print("INICIO")

inicio = time.time()

resposta = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen3",
        "prompt": "Diga apenas: teste ok",
        "stream": False
    },
    timeout=300
)

fim = time.time()

print("STATUS:", resposta.status_code)
print("TEMPO:", round(fim - inicio, 2), "segundos")
print(resposta.json()["response"])

print("FIM")