-- ============================================================
-- SCRIPT COMPLETO PARA CRIAÇÃO DO BANCO NO POSTGRESQL
-- Sistema: Gerador de Atividades e Planos de Aula
-- Banco: PostgreSQL
-- ============================================================

-- 1) CRIAR BANCO (descomente e execute conectado ao postgres, não ao banco alvo)
-- CREATE DATABASE gerador_atividades
--     WITH 
--     ENCODING = 'UTF8'
--     LC_COLLATE = 'pt_BR.UTF-8'
--     LC_CTYPE = 'pt_BR.UTF-8'
--     TEMPLATE = template0;

-- 2) CONECTAR AO BANCO gerador_atividades ANTES DE EXECUTAR OS COMANDOS ABAIXO
-- \c gerador_atividades

-- ============================================================
-- TABELA: usuarios
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    senha       VARCHAR(255) NOT NULL,
    perfil      VARCHAR(20) NOT NULL DEFAULT 'professor'
);

COMMENT ON TABLE usuarios IS 'Usuários do sistema (professores e administradores)';
COMMENT ON COLUMN usuarios.perfil IS 'Perfil do usuário: professor ou admin';

-- ============================================================
-- TABELA: atividades
-- ============================================================
CREATE TABLE IF NOT EXISTS atividades (
    id               SERIAL PRIMARY KEY,
    curso            VARCHAR(100) NOT NULL,
    disciplina       VARCHAR(100) NOT NULL,
    conteudo         VARCHAR(255) NOT NULL,
    dificuldade      VARCHAR(50) NOT NULL,
    atividade_gerada TEXT,
    origem           VARCHAR(50) DEFAULT 'ia',
    data_criacao     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario_id       INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

COMMENT ON TABLE atividades IS 'Atividades geradas pela IA ou compostas pelo repositório';
COMMENT ON COLUMN atividades.dificuldade IS 'Nível de dificuldade: fácil, médio, difícil';
COMMENT ON COLUMN atividades.atividade_gerada IS 'Texto completo da atividade gerada pela IA';
COMMENT ON COLUMN atividades.origem IS 'Origem da geração: ia, repositorio ou misto';

CREATE INDEX IF NOT EXISTS idx_atividades_curso ON atividades(curso);
CREATE INDEX IF NOT EXISTS idx_atividades_usuario ON atividades(usuario_id);
CREATE INDEX IF NOT EXISTS idx_atividades_data ON atividades(data_criacao DESC);

-- ============================================================
-- TABELA: repositorio_atividades
-- ============================================================
CREATE TABLE IF NOT EXISTS repositorio_atividades (
    id               SERIAL PRIMARY KEY,
    curso            VARCHAR(150) NOT NULL,
    disciplina       VARCHAR(150) NOT NULL,
    conteudo         VARCHAR(255) NOT NULL,
    dificuldade      VARCHAR(50) NOT NULL DEFAULT 'médio',
    tipo             VARCHAR(50) NOT NULL DEFAULT 'objetiva',
    enunciado        TEXT NOT NULL,
    alternativas     TEXT,
    resposta_correta TEXT,
    origem           VARCHAR(20) NOT NULL DEFAULT 'professor',
    usuario_id       INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    data_criacao     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE repositorio_atividades IS 'Banco/Repositório de questões criadas por professores e pela IA';
COMMENT ON COLUMN repositorio_atividades.origem IS 'Origem da questão: professor ou ia';

CREATE INDEX IF NOT EXISTS idx_repositorio_curso ON repositorio_atividades(curso);
CREATE INDEX IF NOT EXISTS idx_repositorio_disciplina ON repositorio_atividades(disciplina);
CREATE INDEX IF NOT EXISTS idx_repositorio_usuario ON repositorio_atividades(usuario_id);
CREATE INDEX IF NOT EXISTS idx_repositorio_origem ON repositorio_atividades(origem);
CREATE INDEX IF NOT EXISTS idx_repositorio_dificuldade ON repositorio_atividades(dificuldade);
CREATE INDEX IF NOT EXISTS idx_repositorio_tipo ON repositorio_atividades(tipo);

-- ============================================================
-- TABELA: cursos_plano
-- ============================================================
CREATE TABLE IF NOT EXISTS cursos_plano (
    id              SERIAL PRIMARY KEY,
    nome_curso      VARCHAR(200) NOT NULL,
    carga_horaria   INTEGER NOT NULL,
    aulas_por_dia   INTEGER NOT NULL,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    data_criacao    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE cursos_plano IS 'Cursos cadastrados para geração de planos de aula';
COMMENT ON COLUMN cursos_plano.carga_horaria IS 'Carga horária total do curso em horas';
COMMENT ON COLUMN cursos_plano.aulas_por_dia IS 'Quantidade de aulas por dia';

CREATE INDEX IF NOT EXISTS idx_cursos_plano_usuario ON cursos_plano(usuario_id);
CREATE INDEX IF NOT EXISTS idx_cursos_plano_data ON cursos_plano(data_criacao DESC);

-- ============================================================
-- TABELA: planos_aula
-- ============================================================
CREATE TABLE IF NOT EXISTS planos_aula (
    id              SERIAL PRIMARY KEY,
    curso_id        INTEGER NOT NULL REFERENCES cursos_plano(id) ON DELETE CASCADE,
    dia             INTEGER NOT NULL,
    tema            VARCHAR(300),
    plano_gerado    TEXT NOT NULL,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    data_criacao    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE planos_aula IS 'Planos de aula gerados para cada dia de um curso';
COMMENT ON COLUMN planos_aula.dia IS 'Número do dia/aula do plano';
COMMENT ON COLUMN planos_aula.plano_gerado IS 'Conteúdo completo do plano de aula gerado pela IA';

CREATE INDEX IF NOT EXISTS idx_planos_aula_curso ON planos_aula(curso_id);
CREATE INDEX IF NOT EXISTS idx_planos_aula_usuario ON planos_aula(usuario_id);
CREATE INDEX IF NOT EXISTS idx_planos_aula_dia ON planos_aula(curso_id, dia);

-- ============================================================
-- TABELA: planejamentos_docente
-- ============================================================
CREATE TABLE IF NOT EXISTS planejamentos_docente (
    id                  SERIAL PRIMARY KEY,
    nome_curso          VARCHAR(255) NOT NULL,
    unidade_curricular  VARCHAR(255) NOT NULL,
    turma               VARCHAR(100),
    unidade_escolar     VARCHAR(255),
    carga_horaria       INTEGER NOT NULL,
    horas_por_dia       INTEGER NOT NULL,
    data_inicio         DATE,
    data_fim            DATE,
    total_aulas         INTEGER NOT NULL,
    arquivo_excel       VARCHAR(255),
    curso_id            INTEGER REFERENCES cursos_plano(id) ON DELETE SET NULL,
    modalidade          VARCHAR(100),
    usuario_id          INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
    data_criacao        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_planejamentos_usuario ON planejamentos_docente(usuario_id);
CREATE INDEX IF NOT EXISTS idx_planejamentos_data ON planejamentos_docente(data_criacao DESC);
