import requests

def gerar_atividade(conteudo, dificuldade, tipo, quantidade):

    prompt = f"""
Crie uma atividade educacional.

Conteúdo: {conteudo}
Dificuldade: {dificuldade}
Tipo: {tipo}
Quantidade: {quantidade}
"""

    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1:8b",
            "prompt": prompt,
            "stream": False
        },
        timeout=300
    )

    return resposta.json()["response"]