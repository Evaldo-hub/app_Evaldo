# 🚀 Variáveis de Ambiente - Render

## 📋 Variáveis Obrigatórias

Configure estas variáveis no painel do Render → Environment:

### 1. Banco de Dados (Supabase)
```
DATABASE_URL=postgresql://postgres.texwhpgiaazpyosctjia:@Neia171427@aws-1-sa-east-1.pooler.supabase.com:5432/postgres
```

### 2. API OpenAI (Essencial para IA)
```
OPENAI_API_KEY=sk-sua-chave-openai-aqui
```

### 3. Configurações Flask
```
FLASK_ENV=production
SECRET_KEY=sua-chave-secreta-para-producao
PORT=5000
```

## 🔧 Como Configurar

1. **Acessar painel do Render**
   - Dashboard → Your Service → Environment

2. **Adicionar variáveis**
   - Clique em "Add Environment Variable"
   - Adicione cada variável acima

3. **Rebuild necessário**
   - Após adicionar variáveis, clique "Manual Deploy"
   - Selecione "Latest Commit"

## ⚠️ Importante

- **OPENAI_API_KEY é OBRIGATÓRIA** para funcionalidades de IA
- Sem ela, o app inicia mas IA fica desativada
- Configure antes de fazer deploy

## 🧪 Teste

Após configurar, teste:
```bash
curl https://seu-app.onrender.com/health
```

Resposta esperada:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-02-13T..."
}
```
