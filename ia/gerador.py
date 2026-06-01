import requests

def gerar_atividade(
    conteudo,
    dificuldade,
    tipo,
    quantidade
):

    prompt = f"""
    

CURSO: _________
DISCIPLINA: _________
ALUNO: ___________________________
DATA: ____/____/____

    Tema: {conteudo}
  
    Gere:
    - 5 questões objetivas
    - 4 alternativas por questão
    - informe o gabarito
    - 1 atividade prática
    """

    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "gemma3:4b",
            "prompt": prompt,
            "stream": False
        },
        timeout=300
    )

    return resposta.json()["response"]