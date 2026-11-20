# tests

Suíte automatizada em Pytest.

```bash
python -m pytest -q                   # execução rápida
python scripts/rodar_testes.py        # execução + relatório em reports/
python -m pytest tests/test_security.py -v
```

| Arquivo | Foco |
| --- | --- |
| `conftest.py` | fixtures: banco e diretório de imagens isolados por teste, imagens JPEG sintéticas, sessões autenticadas, fábrica de avistamentos |
| `test_database.py` | esquema, índices, unicidade, constraints de domínio, integridade referencial, cascata, transações com rollback, persistência em disco |
| `test_sightings.py` | protocolo, registro completo, status inicial pendente, idempotência, validações, limpeza em falha, hash de contato |
| `test_geolocation.py` | coordenadas, área monitorada, distâncias, referências do litoral, precisão, arredondamento público |
| `test_inference.py` | pré-processamento, limiares de decisão, estados de indisponibilidade, métricas, divisão do dataset sem vazamento |
| `test_security.py` | senhas, autenticação, permissões, upload, EXIF, saneamento, travessia de diretório, limite de requisições |
| `test_dashboards.py` | KPIs, filtros, separação dos dados de demonstração, atualização após cadastro e validação, DBSCAN, exportação |

## Isolamento

Cada teste roda contra um banco SQLite **próprio**, em diretório temporário,
com diretório de imagens próprio e configuração recarregada. Isso dá isolamento
real e permite verificar persistência com arquivo em disco, não com banco em
memória.

## Estratégia para a IA

Os testes de inferência usam um **preditor injetado** — uma função que devolve
logits conhecidos. Isso verifica a lógica de decisão do serviço (faixas de
limiar, rebaixamento por qualidade de imagem, registro da versão) sem depender
de um modelo treinado. O desempenho do modelo real é medido por
`scripts/avaliar_modelo.py` sobre o conjunto de teste — não por esta suíte, que
não teria como fazê-lo de forma honesta.

Plano completo, incluindo o roteiro manual de 47 itens que só um navegador real
comprova (câmera, GPS, toque, acessibilidade): `docs/testes.md`.
