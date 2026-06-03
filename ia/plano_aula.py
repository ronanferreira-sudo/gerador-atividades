import requests

def gerar_plano_aula(texto_pdf, carga_horaria, aulas_por_dia):

    total_dias = int(carga_horaria) // int(aulas_por_dia)

    prompt = f"""
Você é um coordenador pedagógico especialista em educação profissional.

Analise o conteúdo abaixo:

{texto_pdf[:1000]}

Informações do curso:

- Carga horária total: {carga_horaria} horas
- Horas por dia: {aulas_por_dia} horas
- Total de dias previstos: {total_dias}

Crie APENAS os 5 primeiros dias de aula.

Para cada dia utilize exatamente a estrutura abaixo:

================================================

PLANO DE AULA - DIA 1

1. Dados de Identificação

Tema da Aula:
Carga Horária:
Professor:

2. Objetivos

Objetivo Geral:

Objetivos Específicos:

3. Conteúdo Programático

4. Estratégia Didática e Atividades Práticas

5. Recursos Didáticos

6. Avaliação

================================================

PLANO DE AULA - DIA 2

1. Dados de Identificação

Tema da Aula:
Carga Horária:
Professor:

2. Objetivos

Objetivo Geral:

Objetivos Específicos:

3. Conteúdo Programático

4. Estratégia Didática e Atividades Práticas

5. Recursos Didáticos

6. Avaliação

================================================

Seja detalhado.
Não faça apenas uma lista de conteúdos.
Crie um plano pedagógico completo.
"""

    print("Chamando Ollama...")

    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1:8b",
            "prompt": prompt,
            "stream": False
        },
        timeout=600
    )

    print("Resposta recebida do Ollama!")

    return resposta.json()["response"]