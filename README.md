# 🎓 Gerador de Atividades e Planejamento Docente — SENAI

Sistema web para professores do SENAI gerarem **atividades avaliativas**, **planos de aula** e **planejamentos docentes** com auxílio de Inteligência Artificial (Ollama + LLaMA 3.1), com suporte a múltiplos usuários simultâneos em rede local.

---

## ✨ Funcionalidades

| Módulo | Descrição |
|--------|-----------|
| 🧠 **Gerador de Atividades** | Gera questões objetivas, discursivas ou mistas com base no conteúdo informado |
| 📋 **Planos de Aula** | Gera planos de aula a partir de PDF (Plano de Curso) ou Matriz de Referência Excel (SAEP) |
| 📊 **Planejamento Docente** | Gera a planilha Excel oficial com a Taxonomia de Bloom aplicada automaticamente |
| 🗂️ **Histórico** | Todas as atividades, planos e planejamentos ficam salvos por professor |
| 📥 **Download** | Exportação em Word (.docx), PDF e Excel |
| 👤 **Perfis** | Perfil `professor` (vê só o próprio) e `admin` (vê tudo) |

---

## 🏗️ Arquitetura

```
gerador_atividades/
│
├── app.py                        # Rotas Flask (toda a aplicação web)
├── iniciar_servidor.py           # Script de inicialização Waitress (produção)
├── .env                          # Configurações locais (banco, IA, servidor)
├── .env.example                  # Template de configuração para novo computador
├── requirements.txt              # Dependências Python
│
├── ia/
│   ├── gerador.py                # Geração de atividades via Ollama
│   ├── plano_aula.py             # Geração de planos de aula via Ollama
│   └── planejamento_bloom.py     # Planejamento Docente com Taxonomia de Bloom
│
├── database/
│   ├── conexao.py                # Pool de conexões PostgreSQL (thread-safe)
│   └── script_banco.sql          # Script de criação das tabelas
│
├── utils/
│   ├── docx_generator.py         # Geração de Word para planos
│   ├── docx_atividade_generator.py
│   ├── pdf_generator.py          # Conversão Word → PDF
│   ├── pdf_atividade_generator.py
│   ├── excel_planejamento_generator.py  # Geração da planilha oficial
│   ├── excel_reader.py           # Leitura de Matriz SAEP
│   ├── matriz_saep_reader.py
│   ├── planejamento_docente_reader.py
│   ├── pdf_plano_reader.py       # Extração de texto de PDF
│   └── texto_utils.py            # Limpeza e formatação de textos
│
├── templates/                    # HTMLs Jinja2
├── static/                       # CSS e imagens
├── uploads/                      # Arquivos enviados pelos professores
└── outputs/                      # Arquivos gerados (Excel, Word, PDF)
```

---

## ⚙️ Requisitos

- **Python** 3.11+
- **PostgreSQL** 14+
- **Ollama** com modelo `llama3.1:8b` baixado
- **Windows** (dependência `pywin32` para conversão PDF)

---

## 🚀 Instalação

### 1. Clonar o projeto

```bash
git clone <repositorio>
cd gerador_atividades
```

### 2. Criar ambiente virtual e instalar dependências

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

### 3. Configurar o banco de dados

Abra o **pgAdmin** ou o `psql` e execute:

```sql
CREATE DATABASE gerador_atividades;
```

Depois execute o script de criação das tabelas:

```powershell
psql -U postgres -d gerador_atividades -f database/script_banco.sql
```

### 4. Configurar o arquivo `.env`

Copie o exemplo e edite com suas configurações:

```powershell
copy .env.example .env
```

Edite o `.env`:

```env
# Banco de Dados
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=gerador_atividades
DB_USER=postgres
DB_PASSWORD=SUA_SENHA_AQUI

# Flask — gere uma chave segura:
# python -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY=cole_a_chave_gerada_aqui

# Ollama
OLLAMA_URL=http://localhost:11434

# Servidor
SERVER_HOST=0.0.0.0
SERVER_PORT=5000
SERVER_THREADS=4
```

### 5. Baixar o modelo de IA

```powershell
ollama pull llama3.1:8b
```

### 6. Iniciar o servidor

```powershell
venv\Scripts\python iniciar_servidor.py
```

Acesse: **http://localhost:5000**

---

## 🌐 Uso em Rede Local (Múltiplos Professores)

O sistema foi projetado para ser acessado por vários professores simultaneamente via rede local.

### Iniciar o servidor para a rede

```powershell
venv\Scripts\python iniciar_servidor.py
```

O servidor sobe em `0.0.0.0:5000` — visível para toda a rede local.

Para descobrir o IP do servidor:

```powershell
ipconfig
# Procure por "Endereço IPv4" — ex: 192.168.1.100
```

Professores acessam pelo navegador:

```
http://192.168.1.100:5000
```

### Arquitetura multi-usuário

```
👩‍🏫 Professor 1 ──┐
👨‍🏫 Professor 2 ──┼──► Waitress (4 threads) ──► Flask App ──► PostgreSQL (pool 20)
👩‍🏫 Professor 3 ──┘                                       └──► Ollama (llama3.1:8b)
```

- **Waitress**: servidor WSGI profissional para Windows — gerencia conexões em paralelo
- **Pool PostgreSQL**: até 20 conexões simultâneas thread-safe
- **Cache thread-safe**: resultados idênticos são reutilizados automaticamente com `threading.Lock()`
- **Sessões isoladas**: cada professor vê apenas seus próprios dados

---

## 🎮 Novo Computador com GPU

Para processar várias requisições de IA ao mesmo tempo, configure as variáveis de ambiente do Ollama no Windows:

**Painel de Controle → Sistema → Variáveis de Ambiente do Sistema:**

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `OLLAMA_NUM_PARALLEL` | `4` | Processa até 4 requisições de IA simultâneas na GPU |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | Mantém apenas 1 modelo carregado na VRAM |

Reinicie o serviço do Ollama após configurar.

---

## 📊 Módulos em Detalhe

### Gerador de Atividades

- Entrada: curso, disciplina, conteúdo, dificuldade, tipo (objetiva/discursiva/misto), quantidade
- Saída: atividade avaliativa em texto, exportável em Word ou PDF
- Modelo: `llama3.1:8b` · `num_predict: 900` · `timeout: 120s`

### Planos de Aula

- Entrada: PDF do Plano de Curso **ou** Excel da Matriz SAEP (SENAI) **ou** Excel do Planejamento Docente
- Saída: planos por dia/encontro, exportáveis individualmente ou em conjunto
- Geração em paralelo com `ThreadPoolExecutor`
- Fallback automático estruturado se a IA falhar ou demorar

### Planejamento Docente (Taxonomia de Bloom)

- Entrada: nome do curso, UC, carga horária, datas, PDF do Plano de Curso (opcional), Matriz SAEP (opcional)
- Saída: planilha Excel oficial SENAI preenchida com:
  - Capacidades e conhecimentos por encontro
  - Estratégias de ensino progressivas (Bloom: Lembrar → Entender → Aplicar → Analisar → Avaliar)
  - Critérios e instrumentos de avaliação
  - Datas calculadas automaticamente em dias úteis
- IA com `timeout: 20s` — se demorar, gera algoritmicamente em menos de 1 segundo

---

## 🗄️ Banco de Dados

```
usuarios           — professores e administradores
atividades         — atividades geradas, vinculadas ao professor
cursos_plano       — cursos cadastrados para planos de aula
planos_aula        — planos de aula por dia/encontro
planejamentos_docente — planejamentos gerados com Bloom
```

---

## 🔐 Segurança

- Autenticação por login/senha com sessão Flask
- Cada professor acessa apenas seus próprios dados
- `secret_key` configurável via `.env`
- Credenciais do banco via `.env` (não commitadas no código)

> **⚠️ Atenção:** As senhas dos usuários são armazenadas em texto puro. Para ambientes externos à rede escolar, implemente hash com `bcrypt`.

---

## 🛠️ Desenvolvimento

Para rodar em modo desenvolvimento (sem Waitress):

```powershell
venv\Scripts\python app.py
```

> Não usar `debug=True` em produção ou em rede compartilhada.

---

## 📦 Principais Dependências

| Pacote | Uso |
|--------|-----|
| `Flask` | Framework web |
| `waitress` | Servidor WSGI para produção no Windows |
| `psycopg2-binary` | Conexão com PostgreSQL |
| `python-dotenv` | Leitura do `.env` |
| `requests` | Chamadas ao Ollama |
| `openpyxl` | Geração do Excel do Planejamento Docente |
| `python-docx` | Geração de arquivos Word |
| `docx2pdf` | Conversão Word → PDF |
| `PyPDF2` / `pdfplumber` | Leitura de PDFs |

---

## 📝 Licença

Uso interno SENAI. Todos os direitos reservados.
