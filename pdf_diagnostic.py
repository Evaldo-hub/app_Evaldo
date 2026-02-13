#!/usr/bin/env python3
"""
Ferramenta de diagnóstico para PDFs
Ajuda a identificar problemas com arquivos PDF antes de usar no RAG
"""

import os
import sys
from PyPDF2 import PdfReader
import re

def diagnose_pdf(pdf_path: str):
    """Diagnostica um arquivo PDF"""
    
    if not os.path.exists(pdf_path):
        print(f"❌ Arquivo não encontrado: {pdf_path}")
        return
    
    print(f"🔍 Diagnóstico do PDF: {os.path.basename(pdf_path)}")
    print("=" * 60)
    
    try:
        # Informações básicas
        file_size = os.path.getsize(pdf_path)
        print(f"📁 Tamanho: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
        
        # Tentar ler o PDF
        reader = PdfReader(pdf_path)
        
        print(f"📄 Total de páginas: {len(reader.pages)}")
        
        # Metadados
        if reader.metadata:
            print("\n📋 Metadados:")
            for key, value in reader.metadata.items():
                print(f"   {key}: {value}")
        else:
            print("\n📋 Metadados: Não encontrados")
        
        # Verificar se está criptografado
        if reader.is_encrypted:
            print("\n🔒 PDF está CRIPTOGRAFADO!")
            print("   ❌ Este PDF não pode ser processado sem senha")
            return
        
        # Análise de texto página por página
        print("\n📝 Análise de Texto:")
        total_text = ""
        pages_with_text = 0
        pages_with_images = 0
        
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                text_length = len(page_text.strip())
                
                if text_length > 0:
                    pages_with_text += 1
                    total_text += page_text + "\n"
                    print(f"   Página {i+1}: ✅ {text_length} caracteres")
                else:
                    pages_with_images += 1
                    print(f"   Página {i+1}: ❌ Sem texto (pode ser imagem)")
                    
            except Exception as e:
                print(f"   Página {i+1}: ⚠️ Erro ao ler: {e}")
        
        # Resumo
        print(f"\n📊 Resumo:")
        print(f"   Páginas com texto: {pages_with_text}/{len(reader.pages)}")
        print(f"   Páginas sem texto: {pages_with_images}/{len(reader.pages)}")
        print(f"   Total de caracteres extraídos: {len(total_text):,}")
        
        # Análise da qualidade do texto
        clean_text = re.sub(r'\s+', ' ', total_text).strip()
        
        if len(clean_text) > 100:
            print(f"   ✅ PDF tem texto extraível ({len(clean_text)} caracteres)")
            
            # Verificar se é texto significativo
            words = clean_text.split()
            unique_words = len(set(word.lower() for word in words))
            
            print(f"   Total de palavras: {len(words):,}")
            print(f"   Palavras únicas: {unique_words:,}")
            
            if unique_words > 50:
                print("   ✅ PDF parece ter conteúdo de qualidade")
            else:
                print("   ⚠️ PDF pode ter conteúdo repetitivo ou pobre")
                
        else:
            print("   ❌ PDF NÃO tem texto extraível suficiente")
            print("\n🔍 Possíveis causas:")
            print("   1. PDF é baseado em imagens (scaneado)")
            print("   2. PDF usa fontes não padronizadas")
            print("   3. PDF tem proteção especial")
            print("   4. PDF está corrompido")
            
            print("\n💡 Soluções:")
            print("   1. Use um PDF com texto digital")
            print("   2. Converta imagens para texto usando OCR")
            print("   3. Tente 'Salvar como texto' no leitor de PDF")
            print("   4. Use ferramentas online de extração de texto")
        
        # Salvar texto extraído para análise
        if len(clean_text) > 0:
            output_file = pdf_path.replace('.pdf', '_extraido.txt')
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(clean_text)
            print(f"\n💾 Texto extraído salvo em: {output_file}")
        
    except Exception as e:
        print(f"\n❌ Erro crítico ao processar PDF: {e}")
        print("\n🔍 Verificações:")
        print("   1. O arquivo é realmente um PDF?")
        print("   2. O arquivo não está corrompido?")
        print("   3. Tente abrir em um visualizador de PDF")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python pdf_diagnostic.py <caminho_do_pdf>")
        print("Exemplo: python pdf_diagnostic.py documento.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    diagnose_pdf(pdf_path)
