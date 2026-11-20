# app

Interface web em Streamlit. Ponto de entrada: `app/main.py`.

```bash
streamlit run app/main.py
```

| Pasta / arquivo | Conteúdo |
| --- | --- |
| `main.py` | roteador: monta a navegação conforme o perfil autenticado e delega para a página escolhida |
| `paginas/` | 11 páginas — 6 públicas (início, registrar, mapa, indicadores, sobre a espécie, sobre o projeto) e 5 restritas (visão geral, científico, IA, validação, administração), além da tela de acesso |
| `components/` | componentes reutilizáveis: `ui` (cards, indicadores, estados vazios, avisos), `upload`, `location` (GPS e fallback), `ai_result`, `charts`, `maps`, `tables`, `filters`, `auth_ui` |
| `styles/` | identidade visual: paleta validada, CSS mobile-first, cores e ícones de status |

## Por que `paginas/` e não `pages/`

O Streamlit detecta automaticamente um diretório `pages/` ao lado do arquivo de
entrada. Como esta aplicação usa `st.navigation` para montar o menu conforme a
permissão do usuário, os dois mecanismos entrariam em conflito — o próprio
Streamlit emite aviso de comportamento indeterminado nesse caso. Por isso o
diretório usa o nome em português, que não é reservado.

## Regra estrutural

A interface **não acessa o banco diretamente**: chama serviços de `src/`, que
usam repositórios. Verificações de permissão existem aqui para dar uma mensagem
clara ao usuário, mas quem realmente impede a ação é a camada de serviço —
esconder um botão não é controle de acesso.

Nenhuma consulta de leitura é cacheada, de propósito: assim um registro novo ou
uma validação recém-feita aparecem na consulta seguinte, sem invalidação manual.
