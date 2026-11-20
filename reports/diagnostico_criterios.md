# LionGuard AI — diagnóstico dos critérios de aceite

Gerado por `scripts/diagnostico.py` em 2026-11-19T22:37:28.

| Critério | Estado | Detalhe |
| --- | --- | --- |
| Dependência `streamlit` (interface web) | **FALHA** | instale com `pip install -r requirements.txt` |
| Dependência `folium` (mapa) | **FALHA** | instale com `pip install -r requirements.txt` |
| Dependência `streamlit_folium` (mapa no Streamlit) | **FALHA** | instale com `pip install -r requirements.txt` |
| Dependência `streamlit_js_eval` (GPS do navegador) | **FALHA** | instale com `pip install -r requirements.txt` |
| Dependência `plotly` (gráficos) | **FALHA** | instale com `pip install -r requirements.txt` |
| Dependência `pandas` (análise de dados) | **OK** | — |
| Dependência `sklearn` (DBSCAN e métricas) | **OK** | — |
| Dependência `PIL` (processamento de imagem) | **OK** | — |
| Dependência `onnxruntime` (inferência ONNX) | **OK** | — |
| Dependência `torch` (treinamento (opcional em produção)) | **PENDENTE** | instale com `pip install -r requirements-treino.txt` |
| Dependência `reportlab` (geração do PDF da entrega) | **OK** | — |
| Aplicação inicializa corretamente | **PENDENTE** | Streamlit não instalado neste ambiente |
| Usuário consegue abrir no celular | **MANUAL** | layout mobile-first implementado (CSS em app/styles/theme.py); confirme em um aparelho real na mesma rede |
| É possível capturar ou enviar fotografia | **MANUAL** | st.camera_input e st.file_uploader em app/components/upload.py; a câmera depende de permissão do navegador |
| IA executa inferência real | **PARCIAL — EXPERIMENTAL** | TorchScript publicado (`models/lionguard_experimental_icmbio.pt`), inferência real integrada. Dataset muito pequeno; sem avaliação independente, portanto desempenho não validado. Veja `docs/modelo_experimental.md`. |
| Sistema solicita permissão de localização | **MANUAL** | componente de GPS em app/components/location.py; o navegador exibe o pedido |
| GPS funciona em ambiente compatível | **MANUAL** | exige contexto seguro (HTTPS ou localhost); a interface diagnostica e avisa |
| Existe fallback de localização manual | **OK** | mapa: Guarapari/ES (MAPA_MANUAL); região: Guarapari/ES (REGIAO_APROXIMADA) |
| Usuário consegue confirmar o registro | **OK** | retorno: Avistamento registrado com sucesso! Protocolo LG-2026-8GCHSK. |
| Banco salva os dados | **OK** | ocorrência relida do banco: LG-2026-8GCHSK |
| Protocolo é gerado | **OK** | formato LG-ANO-XXXXXX → LG-2026-8GCHSK |
| Registro duplicado por duplo clique é impedido | **OK** | duplicado=True, total=1 |
| Dashboard apresenta os registros | **OK** | KPIs calculados do banco: total=1, pendentes=1 |
| Mapa apresenta a localização aproximada | **OK** | 1 ponto(s); primeira coordenada pública: -20.67, -40.5 (2 casas decimais) |
| Pesquisador consegue revisar a ocorrência | **OK** | Ocorrência LG-2026-8GCHSK atualizada: PENDENTE → CONFIRMADO. |
| Status é atualizado | **OK** | status no banco: CONFIRMADO |
| Gráficos refletem a revisão | **OK** | confirmados 0 → 1; validados 100.0% |
| Dados demonstrativos estão identificados | **OK** | com demonstração=21, sem demonstração=1 (rótulo tipo_dado=DEMO e filtro de procedência) |
| Controle de acesso funciona | **OK** | visitante anônimo é recusado em todas as permissões restritas |
| Resultados de IA estão documentados | **PENDENTE** | reports/metricas_modelo.json é gerado por scripts/avaliar_modelo.py; o painel de IA exibe estado de indisponibilidade até então |
| Testes foram executados | **MANUAL** | 11 arquivo(s) de teste; rode `python -m pytest -q` (o resultado da última execução está em reports/) |
| README e PDF estão completos | **OK** | todos presentes |
| Limitações foram identificadas | **OK** | /home/claude/lionguard-ai/docs/limitacoes.md |
| Persistência após reinicialização | **OK** | 21 registro(s) antes e depois de fechar as conexões |

Legenda: **OK** verificado automaticamente · **MANUAL** implementado, confirmável só no navegador · **PENDENTE** depende de etapa externa (internet, PyTorch, execução) · **FALHA** verificado e não atendido.
