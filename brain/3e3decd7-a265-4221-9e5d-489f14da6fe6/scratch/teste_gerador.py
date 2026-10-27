import sys
import os
sys.path.insert(0, r'c:\Users\SENAI\Downloads\gerador-atividades')
os.chdir(r'c:\Users\SENAI\Downloads\gerador-atividades')

from dotenv import load_dotenv
load_dotenv()

from ia.gerador import gerar_atividade
import re

conteudo = 'Flask e um microframework Python para desenvolvimento web. Permite criar rotas, views e templates HTML usando Jinja2. As rotas sao definidas com o decorador @app.route. O Flask possui suporte a sessoes, cookies e upload de arquivos. O Flask usa o servidor Werkzeug e e leve e flexivel.'
dificuldade = 'Medio'

for qtd in [3, 5]:
    print(f'\n{"="*50}')
    print(f'TESTANDO COM QUANTIDADE = {qtd}')
    print('='*50)
    resultado = gerar_atividade(conteudo, dificuldade, 'objetiva', qtd)
    print(resultado)
    questoes = re.findall(r'[Qq]uest[aã]o \d+:', resultado)
    print(f'\n>>> Questoes encontradas: {len(questoes)} de {qtd} pedidas')
