import requests
import hashlib

cache_planos = {}


def gerar_hash_plano(texto_pdf, carga_horaria, aulas_por_dia, dia):
    base = f"{texto_pdf[:800]}-{carga_horaria}-{aulas_por_dia}-{dia}"
    return hashlib.md5(base.encode()).hexdigest()


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:800]


def gerar_plano_aula(texto_pdf, carga_horaria, aulas_por_dia, dia):

    key = gerar_hash_plano(texto_pdf, carga_horaria, aulas_por_dia, dia)

    # 🔥 CACHE
    if key in cache_planos:
        print("CACHE PLANO HIT - resposta instantânea")
        return cache_planos[key]

    print("Chamando Ollama...")

    prompt = f"""
Crie o plano de aula do DIA {dia}.

Conteúdo base:
{preprocessar_texto(texto_pdf)}

Gere APENAS o plano de aula com a estrutura abaixo, em texto puro, sem formatação markdown, sem símbolos especiais, sem asteriscos, sem negrito, sem itálico:

1. Identificação:
2. Objetivos:
3. Conteúdo Programático:
4. Estratégia Didática:
5. Recursos Didáticos:
6. Avaliação:

Não escreva introduções, não escreva explicações, não use markdown. Comece diretamente com "1. Identificação:".
"""

    try:
        resposta = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 500
                }
            },
            timeout=1200
        )

        if resposta.status_code != 200:
            return "Erro ao gerar plano"

        data = resposta.json()
        plano = data.get("response", "")

        # 🔥 salva no cache
        cache_planos[key] = plano

        return plano

    except Exception as e:
        print("Erro na IA:", e)
        return "Erro ao conectar com a IA"