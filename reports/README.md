# reports

Relatórios **gerados por execução**. Nenhum valor aqui é escrito à mão, e todos
são reproduzíveis a qualquer momento.

| Arquivo | Produzido por | Conteúdo |
| --- | --- | --- |
| `testes_execucao.md` | `scripts/rodar_testes.py` | saída real do Pytest, com data, versão do Python, contagem por arquivo e log completo |
| `diagnostico_criterios.md` | `scripts/diagnostico.py` | critérios de aceite, um por um, classificados em OK / MANUAL / PENDENTE / FALHA |
| `evidencias_execucao.md` | `scripts/gerar_evidencias.py` | fluxo de ponta a ponta sem interface: esquema, segurança, cadastro, validação, indicadores antes e depois, DBSCAN, persistência |
| `metricas_modelo.json` | `scripts/avaliar_modelo.py` | métricas do conjunto de teste — **a única fonte** dos números do painel de IA |
| `historico_treinamento.json` | `scripts/treinar_modelo.py` | curvas de perda e métricas por época |
| `figuras/` | `scripts/gerar_pdf.py` | gráficos gerados a partir de consultas reais, embutidos no PDF |

Os arquivos gerados estão no `.gitignore`: o que se versiona é o script que os
produz, não o resultado de uma execução específica.
