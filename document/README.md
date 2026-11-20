# document

Documentos da entrega.

| Arquivo | Conteúdo |
| --- | --- |
| `LionGuard_AI_Global_Solution_2026_2.pdf` | **PDF único da entrega**, com as 27 seções exigidas: capa, identificação do grupo, introdução, contexto, justificativa, problema, público, objetivos, fundamentação, arquitetura, funcionamento, experiência do cidadão, IA, pipeline de dados, modelo SQL, dashboards, análise exploratória, análise geográfica, segurança, testes, resultados (obtidos e esperados, separados), limitações, ODS 14, conclusão, referências e os links do vídeo e do repositório |
| `other/` | documentos complementares |

O PDF é **gerado por script**, não editado à mão:

```bash
python scripts/rodar_testes.py        # 1. produz o relatório de testes
python scripts/diagnostico.py         # 2. produz o diagnóstico dos critérios
python scripts/gerar_evidencias.py    # 3. produz as evidências de execução
python scripts/gerar_pdf.py \
    --integrantes "Nome Um (RM000000)" "Nome Dois (RM000000)" \
    --turma "SUA_TURMA" \
    --video "https://youtu.be/..." \
    --repositorio "https://github.com/..." \
    --concorrer                       # 4. monta o PDF com esses insumos
```

Os números do PDF (indicadores, resultado dos testes, critérios de aceite,
métricas de IA) vêm desses relatórios e de consultas ao banco. Rode os passos
1 a 3 **antes** do passo 4, para que o documento reflita o estado atual.

A documentação técnica em Markdown — arquitetura com os seis diagramas,
implantação, limitações, plano de testes, acessibilidade e roteiro do vídeo —
está em `docs/`.
