# Execução local e implantação

## 1. Execução local (recomendado para a demonstração)

```bash
# 1. ambiente virtual
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. dependências da aplicação
pip install -r requirements.txt

# 3. configuração
cp .env.example .env
# edite .env e defina LIONGUARD_ADMIN_PASS e LIONGUARD_PESQ_PASS

# 4. dados de demonstração (opcional, para os painéis não ficarem vazios)
python scripts/semear_demonstracao.py --quantidade 150

# 5. subir a aplicação
streamlit run app/main.py
```

A aplicação abre em `http://localhost:8501`. Se as senhas não forem definidas
no `.env`, uma senha aleatória é gerada para `admin` e `pesquisador` e
**impressa no terminal** na primeira execução — anote, porque não é exibida de
novo.

### Verificar a instalação

```bash
python scripts/diagnostico.py       # critérios de aceite, um por um
python scripts/rodar_testes.py      # suíte de testes + relatório
python scripts/gerar_evidencias.py  # fluxo completo sem interface
```

### Testar no celular na mesma rede

```bash
streamlit run app/main.py --server.address 0.0.0.0
```

Depois acesse `http://SEU_IP_LOCAL:8501` pelo celular. **Atenção:** nesse
endereço o navegador trata a origem como insegura e **não libera o GPS** — o
botão de localização não vai funcionar e o fluxo cai no mapa manual. Para
testar o GPS no celular há dois caminhos:

1. **Túnel HTTPS** (mais simples):
   ```bash
   # em outro terminal, com a aplicação rodando
   npx localtunnel --port 8501
   # ou: cloudflared tunnel --url http://localhost:8501
   ```
   Acesse a URL `https://...` gerada no celular e autorize a localização.

2. **Certificado local** com `mkcert`, configurando
   `server.sslCertFile` e `server.sslKeyFile` no `.streamlit/config.toml`.

---

## 2. Treinamento do modelo

Só é necessário na máquina que vai treinar, e **exige internet** para baixar as
imagens.

```bash
pip install -r requirements.txt -r requirements-treino.txt

python scripts/baixar_dados.py --limite 300    # iNaturalist, só licenças CC
python scripts/preparar_dataset.py             # valida, deduplica, divide
python scripts/treinar_modelo.py               # MobileNetV3, exporta ONNX
python scripts/avaliar_modelo.py               # gera reports/metricas_modelo.json
```

Depois disso, reinicie a aplicação: o serviço de inferência encontra
`models/model_card.json`, carrega o ONNX e o Dashboard de IA passa a exibir as
métricas do conjunto de teste. Antes disso, o painel mostra o estado
`SEM_MODELO` — por projeto, não por falha.

Para GPU NVIDIA, instale o PyTorch pelo índice da sua versão de CUDA antes do
`requirements-treino.txt`. O treinamento detecta CUDA, MPS (Apple Silicon) ou
usa CPU.

| Ambiente | Tempo esperado (12 épocas, ~600 imagens) |
| --- | --- |
| GPU dedicada (CUDA) | poucos minutos |
| Apple Silicon (MPS) | 10–25 minutos |
| CPU | 40–90 minutos |

---

## 3. Implantação em nuvem

### 3.1 O problema da persistência

**Não presuma que a hospedagem preserva arquivos.** Em plataformas com disco
efêmero (Streamlit Community Cloud, planos gratuitos de PaaS, contêineres sem
volume), tudo que foi gravado no sistema de arquivos desaparece a cada
*redeploy*, reinício ou hibernação. Para este projeto isso significa:

- o arquivo `data/lionguard.db` volta vazio — **todos os avistamentos somem**;
- as imagens em `data/images/` somem, e os registros passam a apontar para
  arquivos inexistentes (a aba Auditoria da Administração detecta e lista esses
  casos).

Por isso o SQLite local é adequado ao desenvolvimento e à demonstração, e
**não** a uma operação real.

### 3.2 Configuração mínima para produção

| Componente | Desenvolvimento | Produção |
| --- | --- | --- |
| Banco de dados | SQLite em arquivo | PostgreSQL gerenciado, com backup |
| Imagens | sistema de arquivos local | armazenamento de objetos (S3, R2, GCS) |
| Modelo | `models/*.onnx` no repositório | mesmo arquivo, ou baixado no início |
| Segredos | `.env` local | variáveis de ambiente do provedor |
| HTTPS | opcional (localhost) | **obrigatório** — sem ele não há GPS |

### 3.3 Migração para PostgreSQL

O código concentra todo o SQL em dois módulos (`src/database/repositories.py` e
`src/database/queries.py`) e as consultas usam SQL padrão. As adaptações
necessárias:

1. **DDL** (`src/database/schema.py`): trocar
   `INTEGER PRIMARY KEY AUTOINCREMENT` por `GENERATED ALWAYS AS IDENTITY` e
   `TEXT` de datas por `TIMESTAMPTZ`;
2. **Conexão** (`src/database/connection.py`): substituir `sqlite3` por
   `psycopg`, mantendo a mesma interface (`transacao`, `consultar`,
   `consultar_um`, `consultar_escalar`). Os `PRAGMA` saem;
3. **Marcadores de parâmetro**: `?` passa a `%s`;
4. **Funções de data**: `strftime('%Y-%m', coluna)` passa a
   `to_char(coluna, 'YYYY-MM')`, e `julianday(a) - julianday(b)` passa a
   subtração de timestamps com `EXTRACT(EPOCH FROM ...)`.

As consultas afetadas por (4) são: `evolucao_mensal`,
`evolucao_mensal_por_estado`, `distribuicao_por_hora`,
`duracoes_revisao_horas` e `possiveis_duplicatas`. Os testes em
`tests/test_dashboards.py` cobrem o resultado esperado de todas elas, o que
torna a migração verificável.

### 3.4 Armazenamento de imagens

A interface pública de `ArmazenamentoImagens` (`salvar`, `ler`, `existe`,
`remover`, `caminho_de`) é propositalmente pequena. Para objetos em nuvem,
basta uma implementação alternativa com os mesmos cinco métodos; nada mais no
sistema muda.

### 3.5 Custos e limitações das opções comuns

| Opção | Custo | Persistência | HTTPS | Observação |
| --- | --- | --- | --- | --- |
| Streamlit Community Cloud | gratuito | **não** (disco efêmero) | sim | serve para demonstrar a interface; dados se perdem |
| Hugging Face Spaces | gratuito | só com volume pago | sim | CPU limitada; ONNX roda bem |
| PaaS com volume (Railway, Render, Fly) | US$ 5–20/mês | sim, com volume/Postgres | sim | opção realista para a POC |
| VPS (Hetzner, DigitalOcean, Oracle Free) | US$ 0–6/mês | sim | configurar (Caddy/Nginx + Let's Encrypt) | mais controle, mais trabalho |
| PostgreSQL gerenciado (Neon, Supabase) | camada gratuita disponível | sim | sim | combina bem com qualquer das opções acima |

Nenhuma dessas implantações foi realizada por este projeto: a tabela registra
as opções consideradas e os seus limites, não um ambiente em operação.

### 3.6 Lista de verificação antes de publicar

- [ ] `.env` **não** está no repositório (já consta no `.gitignore`);
- [ ] senhas vindas de variáveis de ambiente do provedor;
- [ ] `LIONGUARD_DB` apontando para PostgreSQL, ou aviso explícito de que os
      dados são temporários;
- [ ] HTTPS ativo (sem ele, o GPS não funciona);
- [ ] `enableXsrfProtection = true` (padrão do `config.toml` do projeto);
- [ ] `showErrorDetails = false`, para não expor rastreamento de pilha;
- [ ] limite de upload coerente entre `config.toml` e
      `LIONGUARD_UPLOAD_MAX_BYTES`;
- [ ] `python scripts/diagnostico.py` sem itens em FALHA;
- [ ] se o modelo estiver publicado, `reports/metricas_modelo.json` presente.
