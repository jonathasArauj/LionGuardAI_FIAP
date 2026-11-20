# data

Dados do projeto. **Nada aqui é versionado** além deste arquivo: o conteúdo é
gerado localmente e está no `.gitignore`.

| Pasta | Conteúdo | Como é produzida |
| --- | --- | --- |
| `raw/` | imagens baixadas das bases abertas e `manifesto.csv` com a procedência de cada arquivo (fonte, URL, licença, autor, identificador da observação, hash) | `python scripts/baixar_dados.py` |
| `processed/` | dataset dividido em `train/`, `val/` e `test/`, mais `divisao_dataset.json` com o registro da divisão e a verificação de vazamento | `python scripts/preparar_dataset.py` |
| `images/` | fotografias enviadas pelos usuários, com nome gerado pela aplicação (UUID) e sem metadados EXIF | gravadas pela aplicação |
| `demo/` | espaço reservado para arquivos de demonstração | — |
| `lionguard.db` | banco SQLite | criado na primeira execução |
| `conteudo_educativo.json` | textos, links oficiais e vídeos da área pública | `python -c "from src.data.conteudo import gravar_modelo; print(gravar_modelo())"` |

### Como acrescentar o vídeo da entrega

A lista `videos` do arquivo acima nasce vazia de propósito: nenhum endereço de
vídeo é embutido no código, para não publicar um link que ninguém conferiu.
Para exibir o vídeo na página inicial, acrescente um objeto:

```json
"videos": [
  {
    "titulo": "LionGuard AI — demonstração da plataforma",
    "url": "https://www.youtube.com/watch?v=SEU_ID",
    "descricao": "Fluxo completo: registro, IA, mapa e validação.",
    "fonte": "Equipe LionGuard AI"
  }
]
```

Endereço sem esquema (`http`/`https`) ou sem host é descartado na leitura — a
seção fica vazia em vez de mostrar um player quebrado.

## Procedência e licenças

As imagens de treinamento vêm do **iNaturalist**, e apenas quando há licença
Creative Commons declarada — observações sem licença explícita são ignoradas.
O manifesto preserva a atribuição de cada arquivo.

As ocorrências importadas de bases externas (**GBIF**, **iNaturalist**) entram
com `tipo_dado = IMPORTADO` e registram a fonte na tabela `fonte_dados`. Elas
mantêm o status **pendente**: uma base externa não é validação da equipe de
avaliação desta plataforma.

## Atenção em produção

Em hospedagem com disco efêmero, tudo nesta pasta — inclusive o banco e as
fotografias — é perdido a cada *redeploy*. Ver `docs/deploy.md`.
