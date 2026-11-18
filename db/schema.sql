-- AlertaBueiro: schema PostgreSQL + PostGIS (Neon)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Ponto = boca de lobo agrupada (relatos a até 30 m)
CREATE TABLE IF NOT EXISTS ponto (
    id             SERIAL PRIMARY KEY,
    geom           geography(Point, 4326) NOT NULL,
    classe         TEXT,                       -- limpa | parcial | total (último relato)
    tipo_residuo   TEXT,                       -- lixo | entulho | folhas | sedimento
    gravidade      REAL NOT NULL DEFAULT 0,    -- fator G (0..1)
    confianca      REAL NOT NULL DEFAULT 0,    -- confiança agregada dos relatos
    score          REAL NOT NULL DEFAULT 0,    -- 0..100
    fatores        JSONB NOT NULL DEFAULT '{}'::jsonb,  -- explicabilidade (RNF05)
    status         TEXT NOT NULL DEFAULT 'aberto'
                   CHECK (status IN ('aberto', 'em_servico', 'limpo')),
    n_relatos      INT NOT NULL DEFAULT 0,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ponto_geom_idx   ON ponto USING GIST (geom);
CREATE INDEX IF NOT EXISTS ponto_status_idx ON ponto (status, score DESC);

-- Relato = foto enviada pelo morador
CREATE TABLE IF NOT EXISTS relato (
    id            SERIAL PRIMARY KEY,
    ponto_id      INT REFERENCES ponto(id) ON DELETE CASCADE,
    geom          geography(Point, 4326) NOT NULL,
    foto_blur     BYTEA,                      -- já anonimizada (RNF03)
    classe        TEXT,
    tipo_residuo  TEXT,
    confianca     REAL,
    tel_hash      TEXT,                       -- HMAC-SHA256, nunca o número
    origem        TEXT NOT NULL DEFAULT 'pwa', -- pwa | whatsapp | simulado
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS relato_ponto_idx ON relato (ponto_id);
CREATE INDEX IF NOT EXISTS relato_geom_idx  ON relato USING GIST (geom);

-- Ordem de serviço
CREATE TABLE IF NOT EXISTS ordem_servico (
    id                SERIAL PRIMARY KEY,
    ponto_id          INT NOT NULL REFERENCES ponto(id) ON DELETE CASCADE,
    equipe            TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'aberta'
                      CHECK (status IN ('aberta', 'concluida', 'reprovada')),
    foto_antes        BYTEA,
    foto_depois       BYTEA,
    classe_depois     TEXT,
    confianca_depois  REAL,
    aberta_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechada_em        TIMESTAMPTZ
);

-- Alerta preventivo (chuva prevista >= 30 mm/24 h)
CREATE TABLE IF NOT EXISTS alerta (
    id         SERIAL PRIMARY KEY,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    chuva_mm   REAL NOT NULL,
    pontos     INT[] NOT NULL
);

-- Ocorrências de alagamento do CGE (fator H)
CREATE TABLE IF NOT EXISTS ocorrencia_cge (
    id         SERIAL PRIMARY KEY,
    geom       geography(Point, 4326) NOT NULL,
    data       DATE NOT NULL,
    descricao  TEXT,
    fonte      TEXT NOT NULL DEFAULT 'CGE'    -- CGE | simulado
);
CREATE INDEX IF NOT EXISTS ocorrencia_geom_idx ON ocorrencia_cge USING GIST (geom);

-- Setores censitários do IBGE (fator V)
CREATE TABLE IF NOT EXISTS setor_censitario (
    cod_setor        TEXT PRIMARY KEY,
    geom             geometry(MultiPolygon, 4326) NOT NULL,
    densidade        REAL,
    renda            REAL,
    vulnerabilidade  REAL NOT NULL            -- 0..1
);
CREATE INDEX IF NOT EXISTS setor_geom_idx ON setor_censitario USING GIST (geom);
