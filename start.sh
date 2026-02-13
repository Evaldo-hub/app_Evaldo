#!/bin/bash

# Script de inicialização para Render
# Verifica se as variáveis de ambiente estão configuradas

echo "🚀 Iniciando EBSERH Study App..."

# Verificar OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  AVISO: OPENAI_API_KEY não configurada"
    echo "   Funcionalidades de IA ficarão desativadas"
    echo "   Configure no painel do Render → Environment"
else
    echo "✅ OPENAI_API_KEY configurada"
fi

# Verificar DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERRO: DATABASE_URL não configurada"
    echo "   Configure no painel do Render → Environment"
    exit 1
else
    echo "✅ DATABASE_URL configurada"
fi

# Inicializar banco de dados
echo "🗄️  Inicializando banco de dados..."
python -c "
from app import init_db
try:
    init_db()
    print('✅ Banco de dados inicializado com sucesso!')
except Exception as e:
    print(f'❌ Erro ao inicializar banco: {e}')
    exit(1)
"

# Iniciar aplicação
echo "🌐 Iniciando servidor web..."
exec gunicorn app:app --bind 0.0.0.0:$PORT
