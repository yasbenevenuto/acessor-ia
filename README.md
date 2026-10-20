# Assessor.IA

Assistente pessoal de **finanças** e **agenda** por conversa, feito com **FastAPI**, **LangChain/LangGraph** e **Google Calendar (MCP)**. O usuário fala em linguagem natural ("gastei 50 reais no mercado", "marca uma reunião amanhã às 10h") e um grafo de agentes decide quem responde, usa as ferramentas certas e devolve uma resposta no chat.

## O que ele faz

- **Finanças:** registra, consulta e atualiza lançamentos (entradas e gastos), informa saldo do dia e saldo geral, e classifica por categoria (comida, transporte, moradia, saúde, lazer, contas, investimento, salário, compras e outras).
- **Agenda (Google Calendar):** consulta compromissos e disponibilidade, cria, atualiza e cancela eventos. Verifica conflito antes de criar e pede confirmação antes de excluir. Não envia convites a terceiros.
- **FAQ:** responde dúvidas sobre as regras e limites do próprio assistente, com base na Instrução Normativa (`data/FAQ_assessor_v1.2.pdf`), por busca semântica.
- **Perfil:** o usuário cadastra renda, objetivo, tolerância a risco e preferências na tela de Perfil, e o assistente lê esses dados para orientar.
- **Memória de longo prazo:** ao encerrar uma sessão é gerado um resumo, que pode ser consultado em conversas futuras.
- **Segurança:** dados pessoais (CPF, CNPJ, telefone, e-mail, conta, cartão) são anonimizados antes do processamento. Há bloqueio de prompt injection, de pedidos ofensivos, perigosos, ilícitos, políticos e de indicação de ativos específicos, além de revisão de compliance na saída.
- **Monitoramento:** painel com as chamadas aos modelos e o status de cada turno.

## Como funciona

```
mensagem
   │
   ▼
guardrail de entrada  (anonimiza dados pessoais, checa injeção e conteúdo proibido)
   │
   ▼
roteador ──► financeiro ──┐
         ├─► agenda ──────┼─► orquestrador ─► guardrail de saída ─► resposta
         └─► faq ─────────┴──────────────────────────────────────►
```

| Agente | Função | Fontes e ferramentas |
|---|---|---|
| Roteador | Classifica a intenção e encaminha | Memória de conversas anteriores |
| Financeiro | Opera os lançamentos | PostgreSQL, memória, perfil |
| Agenda | Opera o calendário | Google Calendar via MCP, memória |
| FAQ | Responde sobre regras do sistema | Qdrant (PDF do FAQ) |
| Orquestrador | Formata a resposta final ao usuário | n/a |

**Modelos:** Gemini 2.5 Flash (com Groq como reserva) para os especialistas, e modelos rápidos da Groq para roteamento, guardrails e orquestração.

**Dados:** PostgreSQL (lançamentos), MongoDB (sessões, resumos e perfis) e Qdrant (embeddings de memória, perfil e FAQ).

## Estrutura do projeto

```
.
├── app/
│   ├── main.py            # FastAPI: rotas, arquivos estáticos e /health
│   ├── core/              # config, modelos (llms) e schemas
│   ├── graph/             # grafo LangGraph, agentes, prompts e guardrails
│   ├── domain/            # memória, perfil, vector store e observabilidade
│   ├── tools/             # ferramentas dos agentes (financeiro, calendar_mcp, faq...)
│   ├── routes/            # /chat, /sessions, /perfil, /monitor
│   └── scripts/           # ingest_faq.py e mcp_server.py
├── data/                  # PDF do FAQ
├── frontend/              # chat, perfil e monitor (HTML/CSS/JS puro)
├── requirements.txt
└── .env.example
```

## Pré-requisitos

- Python 3.11 ou superior
- Node.js (versão LTS), usado pelo `npx` que sobe o MCP do Google Calendar
- PostgreSQL, MongoDB e uma instância do Qdrant (local ou cloud)
- Chaves de API do Gemini e da Groq
- Credenciais OAuth do Google Calendar (veja abaixo)

## Instalação

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite o `.env` e preencha as variáveis:

| Variável | Para que serve |
|---|---|
| `GEMINI_API_KEY` | Modelo principal e embeddings |
| `GROQ_API_KEY` | Modelos rápidos e reserva |
| `DATABASE_URL` | Conexão com o PostgreSQL |
| `MONGODB_URI` | Conexão com o MongoDB (padrão: `mongodb://localhost:27017`) |
| `QDRANT_URL` / `QDRANT_API_KEY` | Banco vetorial |
| `GOOGLE_OAUTH_CREDENTIALS` | Caminho do JSON de credenciais OAuth do Google |
| `GOOGLE_CALENDAR_MCP_TOKEN_PATH` | Opcional: onde guardar o token do Google |

O arquivo `.env` e as credenciais do Google **não** devem ir para o Git (já estão no `.gitignore`).

> O esquema SQL do PostgreSQL (tabelas `transactions`, `transaction_types` e `categories`) ainda não está versionado neste repositório.

### Google Calendar

1. No [Google Cloud Console](https://console.cloud.google.com), crie um projeto e ative a **Google Calendar API**.
2. Crie um **ID do cliente OAuth** do tipo **App para computador** (dados do usuário) e baixe o JSON.
3. Na tela de público, adicione seu e-mail como **usuário de teste**.
4. Salve o JSON em `secrets/gcp-oauth.keys.json` e aponte `GOOGLE_OAUTH_CREDENTIALS` para ele no `.env`.
5. Faça o login uma vez:

```powershell
$env:GOOGLE_OAUTH_CREDENTIALS="C:\caminho\para\secrets\gcp-oauth.keys.json"
npx @cocal/google-calendar-mcp auth
```

A conexão com o Calendar só é aberta na primeira mensagem de agenda, e o servidor sobe mesmo que o Google esteja indisponível. Com o app em modo "Teste", o token expira em cerca de 7 dias; basta repetir o `auth`.

### FAQ

Indexe o PDF do FAQ no Qdrant (o comando limpa a coleção e reinsere, então é seguro repetir):

```powershell
python -m app.scripts.ingest_faq
```

## Executando

```powershell
python -m uvicorn app.main:app --reload
```

| Endereço | O que é |
|---|---|
| http://127.0.0.1:8000/ | Chat |
| http://127.0.0.1:8000/perfil | Tela de Perfil |
| http://127.0.0.1:8000/painel | Painel de monitoramento |
| http://127.0.0.1:8000/docs | Documentação interativa da API (Swagger) |
| http://127.0.0.1:8000/health | Diagnóstico de configuração |

Comece pelo `/health`: ele lista qualquer variável ou arquivo que esteja faltando.

## API

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/chat` | Envia uma mensagem (`session_id`, `user_id`, `question`) e recebe `response`, `agentes_chamados` e `raciocinio` |
| `POST` | `/sessions/{session_id}/iniciar` | Abre uma sessão |
| `POST` | `/sessions/{session_id}/encerrar` | Encerra a sessão e gera o resumo da conversa |
| `POST` | `/perfil` | Salva o perfil financeiro do usuário |
| `GET` | `/monitor` | Dados do painel (JSON) |
| `GET` | `/health` | Status e problemas de configuração |

Exemplo:

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"session_id":"teste-123","question":"gastei 50 reais no mercado"}'
```

## Servidor MCP financeiro (opcional)

`app/scripts/mcp_server.py` expõe as ferramentas financeiras (`add_transaction`, `query_transactions`, `total_balance`, `daily_balance` e `update_transaction`) para clientes MCP externos, como o Cline. O app principal não depende dele.

## Limitações conhecidas

- O Google Calendar usa **uma única conta Google** para todos os usuários do serviço.
- As sessões ativas e o estado do grafo ficam em memória: reiniciar o servidor perde a conversa em andamento.
- O assistente não lê arquivos, não faz pagamentos e não apaga lançamentos de forma definitiva (a remoção marca o lançamento como "Removido pelo usuário" e zera o valor).

## Licença

[MIT](LICENSE)
