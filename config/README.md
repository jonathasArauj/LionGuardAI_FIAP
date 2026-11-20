# config

Parâmetros e ajustes do projeto.

A configuração fica em três lugares, cada um por um motivo:

| Arquivo | Papel | Por que não está nesta pasta |
| --- | --- | --- |
| `.env.example` | modelo das variáveis de ambiente (banco, senhas, limiares da IA, limites de upload, privacidade) | o `python-dotenv` lê `.env` da **raiz** do projeto |
| `.streamlit/config.toml` | tema, limite de upload e segurança do servidor Streamlit | o Streamlit exige exatamente esse caminho |
| `src/config.py` | leitura tipada das variáveis, com valores padrão e criação de diretórios | é código, e fica junto do código |
| `pytest.ini` | configuração da suíte de testes | o Pytest procura na raiz |

Nenhuma credencial fica no código nem versionada: o `.env` está no
`.gitignore`, e as senhas das contas de acesso vêm de variáveis de ambiente.
Quando não são definidas, o sistema gera uma senha aleatória e a imprime **uma
única vez** no terminal.

Para configurar:

```bash
cp .env.example .env
# edite .env e defina LIONGUARD_ADMIN_PASS e LIONGUARD_PESQ_PASS
```
