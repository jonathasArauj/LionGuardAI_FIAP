# src

Código-fonte da aplicação, sem dependência da interface.

| Pacote | Conteúdo |
| --- | --- |
| `config.py` | configuração lida de variáveis de ambiente, com padrões |
| `database/` | `schema.py` (DDL e enumerações), `connection.py` (conexões e transações), `models.py` (dataclasses de domínio), `repositories.py` (persistência) e `queries.py` (consultas analíticas) |
| `services/` | `sightings.py` (registro), `geolocation.py` (coordenadas e referências), `image_storage.py` (arquivos), `validation.py` (revisão humana), `analytics.py` (indicadores e exportação), `spatial.py` (DBSCAN) |
| `ai/` | `preprocessing.py` (letterbox e normalização), `inference.py` (serviço de inferência), `train.py` e `evaluate.py` (offline) |
| `security/` | `auth.py` (scrypt e sessão), `permissions.py` (matriz de perfis), `uploads.py` (validação de imagem), `rate_limit.py`, `sanitize.py` |
| `data/` | `dataset.py` (aquisição e divisão), `demo_seed.py` (dados de demonstração), `importers.py` (GBIF/iNaturalist) |

**Regra estrutural:** a interface (`app/`) nunca acessa o banco diretamente —
chama serviços, que usam repositórios. É isso que permite testar toda a regra
de negócio sem subir o Streamlit, e é por isso que a suíte de testes cobre o
fluxo completo em segundos.
