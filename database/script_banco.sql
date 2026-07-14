-- ============================================================
-- SCRIPT DE CRIAÇÃO DO BANCO DE DADOS
-- Sistema: Gerador de Atividades e Planos de Aula
-- Banco: PostgreSQL
-- ============================================================

-- Criação do banco (executar manualmente se necessário)
-- CREATE DATABASE gerador_atividades;

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
    data_criacao     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario_id       INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

COMMENT ON TABLE atividades IS 'Atividades geradas pela IA';
COMMENT ON COLUMN atividades.dificuldade IS 'Nível de dificuldade: fácil, médio, difícil';
COMMENT ON COLUMN atividades.atividade_gerada IS 'Texto completo da atividade gerada pela IA';

-- Índice para busca por curso, disciplina e conteúdo
CREATE INDEX IF NOT EXISTS idx_atividades_curso ON atividades(curso);
CREATE INDEX IF NOT EXISTS idx_atividades_usuario ON atividades(usuario_id);
CREATE INDEX IF NOT EXISTS idx_atividades_data ON atividades(data_criacao DESC);

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
-- SEQUENCES (criadas automaticamente pelo SERIAL, apenas para referência)
-- ============================================================
-- SELECT setval('usuarios_id_seq', COALESCE((SELECT MAX(id) FROM usuarios), 1));
-- SELECT setval('atividades_id_seq', COALESCE((SELECT MAX(id) FROM atividades), 1));
-- SELECT setval('cursos_plano_id_seq', COALESCE((SELECT MAX(id) FROM cursos_plano), 1));
-- SELECT setval('planos_aula_id_seq', COALESCE((SELECT MAX(id) FROM planos_aula), 1));

-- ============================================================
-- INSERTS PADRÃO (opcionais)
-- ============================================================

-- Usuário administrador padrão (senha: admin123)
-- INSERT INTO usuarios (nome, email, senha, perfil)
-- VALUES ('Administrador', 'admin@admin.com', 'admin123', 'admin');

-- ============================================================
-- DROP TABLES (caso precise recriar tudo)
-- ============================================================
-- DROP TABLE IF EXISTS planos_aula CASCADE;
-- DROP TABLE IF EXISTS cursos_plano CASCADE;
-- DROP TABLE IF EXISTS atividades CASCADE;
-- DROP TABLE IF EXISTS usuarios CASCADE;