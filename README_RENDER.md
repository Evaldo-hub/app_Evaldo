# 🚀 Deploy no Render - Guia Rápido

## 📋 Pré-requisitos

1. **Conta no Render** criada
2. **Repositório GitHub** com o código
3. **Database Supabase** configurada

## 🔧 Configuração no Render

### 1. Criar Web Service
- Dashboard → New → Web Service
- Conectar ao repositório GitHub
- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `./start.sh`

### 2. Variáveis de Ambiente

Adicione estas variáveis no painel do Render → Environment:

```bash
# Banco de Dados (OBRIGATÓRIO)
DATABASE_URL=postgresql://postgres.texwhpgiaazpyosctjia:@Neia171427@aws-1-sa-east-1.pooler.supabase.com:5432/postgres

# API OpenAI (OBRIGATÓRIO para IA)
OPENAI_API_KEY=sk-sua-chave-openai-aqui

# Configurações Flask
FLASK_ENV=production
SECRET_KEY=sua-chave-secreta-para-producao
PORT=5000

# Configurações RAG
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini
```

### 3. Permissões do Script
O `start.sh` precisa ser executável:
- No GitHub: Garanta que o arquivo tenha permissões de execução
- Ou use: `chmod +x start.sh`

## 🗄️ Inicialização do Banco

O banco é inicializado automaticamente no primeiro deploy.

Para verificar manualmente:
```bash
curl https://seu-app.onrender.com/init_db
```

## 🧪 Testes

### Health Check
```bash
curl https://seu-app.onrender.com/health
```

### Testar Funcionalidades
- **Acessar**: `https://seu-app.onrender.com`
- **Importar questões**: Funciona sem OpenAI
- **Funcionalidades IA**: Requer OPENAI_API_KEY

## ⚠️ Troubleshooting

### Erro: OPENAI_API_KEY
```
OpenAIError: The api_key client option must be set
```
**Solução**: Configure a variável no Render → Environment

### Erro: DATABASE_URL
```
OperationalError: could not connect
```
**Solução**: Verifique a URL do Supabase

### Erro: Permissão start.sh
```
Permission denied
```
**Solução**: Adicione permissão de execução no GitHub

## 📊 Status das Funcionalidades

| Funcionalidade | Requer OPENAI_API_KEY | Status |
|---------------|---------------------|--------|
| Importação de Questões | ❌ | ✅ Funciona |
| Listagem/Filtros | ❌ | ✅ Funciona |
| Simulados | ❌ | ✅ Funciona |
| IA Explicações | ✅ | ⚠️ Requer API |
| IA Dicas | ✅ | ⚠️ Requer API |
| IA Geração | ✅ | ⚠️ Requer API |

## 🎉 Deploy Concluído!

Após seguir estes passos:
- ✅ App funcionando no Render
- ✅ Banco PostgreSQL conectado
- ✅ Funcionalidades básicas operacionais
- ✅ IA pronta (com API key)

**Seu app EBSERH Study está no ar!** 🚀
