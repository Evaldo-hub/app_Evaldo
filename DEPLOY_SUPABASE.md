# 🚀 Deploy no Render com Supabase

## 📋 O que foi implementado

Sistema completo com SQLAlchemy para rodar tanto local (SQLite) quanto em produção (Supabase PostgreSQL).

## 🔧 Configuração de Ambiente

### Variáveis de Ambiente no Render

Adicione estas variáveis no painel do Render:

```
# Principal
DATABASE_URL=postgresql://postgres.texwhpgiaazpyosctjia:@Neia171427@aws-1-sa-east-1.pooler.supabase.com:5432/postgres

# Aplicação
FLASK_ENV=production
SECRET_KEY=sua-chave-secreta-para-producao
PORT=5000
```

## 📦 Instalação de Dependências

```bash
pip install -r requirements.txt
```

## 🗄️ Inicialização do Banco

### Opção 1 - Automática (Recomendada)
Após o deploy, acesse:
```
https://seu-app.onrender.com/init_db
```

### Opção 2 - Via Shell
No painel do Render → Shell:
```bash
python -c "from app import init_db; init_db()"
```

## 🚀 Deploy

1. **Fazer commit**:
```bash
git add .
git commit -m "Implementando SQLAlchemy para Supabase"
git push origin main
```

2. **Configurar Render**:
- Conectar ao repositório GitHub
- Adicionar variáveis de ambiente
- Fazer deploy

3. **Inicializar banco**:
- Acessar `/init_db`
- Verificar se as tabelas foram criadas

## 📊 Estrutura do Banco

### Tabelas Criadas Automaticamente:
- ✅ `questoes` - Banco de questões
- ✅ `desempenho` - Respostas dos usuários  
- ✅ `plano_estudos` - Plano de estudos semanal
- ✅ `ia_feedback` - Feedback da IA

### Schema PostgreSQL:
```sql
CREATE TABLE IF NOT EXISTS questoes (
    id BIGSERIAL PRIMARY KEY,
    disciplina TEXT NOT NULL,
    semana INTEGER NOT NULL,
    nivel TEXT NOT NULL CHECK (nivel IN ('Básico', 'Alto', 'Pegadinha')),
    banca TEXT NOT NULL,
    enunciado TEXT NOT NULL,
    alternativas TEXT NOT NULL,
    resposta_correta TEXT NOT NULL,
    comentario TEXT NOT NULL
);
```

## 🔄 Funcionalidades

### Funciona Local (SQLite):
- ✅ Desenvolvimento completo
- ✅ Importação de questões
- ✅ Simulados
- ✅ IA integrada

### Funciona em Produção (Supabase):
- ✅ Persistência de dados real
- ✅ Multi-usuário
- ✅ Backup automático
- ✅ Escalabilidade

## 🧪 Testes

### Teste Local:
```bash
python app.py
# Acessar http://localhost:5000
```

### Teste Produção:
```bash
# Verificar health check
curl https://seu-app.onrender.com/health

# Verificar inicialização do banco
curl https://seu-app.onrender.com/init_db
```

## 🔍 Debug

### Logs no Render:
- Painel → Services → Logs
- Verificar erros de conexão
- Confirmar variáveis de ambiente

### Comandos úteis:
```bash
# Verificar conexão com Supabase
python -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ.get('DATABASE_URL'))
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print('PostgreSQL conectado:', result.scalar())
"
```

## ✅ Sucesso!

Após seguir estes passos:
- ✅ Aplicação funcionando no Render
- ✅ Dados persistindo no Supabase
- ✅ Todas as funcionalidades operacionais
- ✅ Sistema pronto para uso real

**Seu app EBSERH Study está pronto para produção!** 🎉
