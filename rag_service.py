"""
RAG Service - Retrieval-Augmented Generation para EBSERH Study
Processa PDFs, cria embeddings e gera questões baseadas no conteúdo
"""

import os
import json
import sqlite3
import numpy as np
import faiss
from typing import List, Dict, Tuple, Optional
from PyPDF2 import PdfReader
import openai
from openai import OpenAI
import tiktoken
import re
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

class RAGService:
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("AVISO: OPENAI_API_KEY não configurada. RAG Service desativado.")
            self.client = None
            self.enabled = False
            return
        
        self.client = OpenAI(api_key=api_key)
        self.enabled = True
        self.embedding_model = "text-embedding-3-small"
        self.chat_model = "gpt-4o-mini"
        self.chunk_size = 1000
        self.chunk_overlap = 200
        self.max_tokens = 8192
        
        # Diretórios
        self.pdf_dir = "pdfs"
        self.embeddings_dir = "embeddings"
        
        # Criar diretórios se não existirem
        os.makedirs(self.pdf_dir, exist_ok=True)
        os.makedirs(self.embeddings_dir, exist_ok=True)
        
        # Inicializar banco de dados
        self.init_rag_db()
        
    def init_rag_db(self):
        """Inicializa banco de dados para RAG"""
        conn = sqlite3.connect('ebserh_study.db')
        cursor = conn.cursor()
        
        # Tabela de documentos PDF
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdf_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                title TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_pages INTEGER,
                total_chunks INTEGER
            )
        ''')
        
        # Tabela de chunks de texto
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdf_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                page_number INTEGER,
                embedding_id TEXT,
                FOREIGN KEY (document_id) REFERENCES pdf_documents (id)
            )
        ''')
        
        # Tabela de questões geradas por RAG
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rag_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_ids TEXT,
                question TEXT NOT NULL,
                alternatives TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                difficulty TEXT DEFAULT 'Médio',
                discipline TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES pdf_documents (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, Dict]:
        """
        Extrai texto de PDF e retorna metadados
        Tenta múltiplos métodos para extração de texto
        """
        try:
            reader = PdfReader(pdf_path)
            text = ""
            metadata = {
                'total_pages': len(reader.pages),
                'title': reader.metadata.get('/Title', os.path.basename(pdf_path)) if reader.metadata else os.path.basename(pdf_path),
                'pages': [],
                'has_text': False,
                'extraction_method': 'PyPDF2'
            }
            
            # Método 1: Extração padrão
            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text += page_text + "\n"
                        metadata['pages'].append({
                            'page_number': page_num + 1,
                            'text_length': len(page_text),
                            'has_text': bool(page_text.strip())
                        })
                    else:
                        metadata['pages'].append({
                            'page_number': page_num + 1,
                            'text_length': 0,
                            'has_text': False
                        })
                except Exception as e:
                    print(f"Erro ao extrair texto da página {page_num + 1}: {e}")
                    metadata['pages'].append({
                        'page_number': page_num + 1,
                        'text_length': 0,
                        'has_text': False,
                        'error': str(e)
                    })
            
            # Verificar se encontrou texto significativo
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 50:  # Pelo menos 50 caracteres
                metadata['has_text'] = True
                return clean_text, metadata
            
            # Método 2: Tentar extração por caracteres (para PDFs problemáticos)
            print("Tentando método alternativo de extração de texto...")
            text = ""
            for page_num, page in enumerate(reader.pages):
                try:
                    # Tentar extrair caractere por caractere
                    page_text = ""
                    if hasattr(page, '_objects'):
                        for obj in page._objects:
                            if hasattr(obj, 'get_text'):
                                try:
                                    page_text += obj.get_text() + " "
                                except:
                                    continue
                    
                    if page_text.strip():
                        text += page_text + "\n"
                        metadata['pages'][page_num]['has_text'] = True
                        metadata['pages'][page_num]['text_length'] = len(page_text)
                except Exception as e:
                    print(f"Erro no método alternativo página {page_num + 1}: {e}")
            
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 50:
                metadata['has_text'] = True
                metadata['extraction_method'] = 'PyPDF2-Alternative'
                return clean_text, metadata
            
            # Se ainda não encontrou texto, retornar informação detalhada
            metadata['extraction_method'] = 'Failed'
            
            # Análise do PDF para ajudar no diagnóstico
            pages_with_text = sum(1 for p in metadata['pages'] if p['has_text'])
            total_chars = sum(p['text_length'] for p in metadata['pages'])
            
            error_msg = f"""
            PDF não contém texto extraível ou está protegido.
            
            Diagnóstico:
            - Total de páginas: {metadata['total_pages']}
            - Páginas com texto: {pages_with_text}
            - Total de caracteres: {total_chars}
            - Método tentado: {metadata['extraction_method']}
            
            Possíveis causas:
            1. PDF é baseado em imagens (scaneado)
            2. PDF tem proteção por senha
            3. PDF usa fontes não padronizadas
            4. PDF está corrompido
            
            Soluções:
            1. Use um PDF com texto digital
            2. Converta o PDF para texto usando OCR
            3. Tente outro arquivo PDF
            """
            
            raise Exception(error_msg)
            
        except Exception as e:
            # Erro crítico na extração
            error_msg = f"""
            Erro crítico ao processar PDF: {str(e)}
            
            Verificações:
            1. O arquivo é um PDF válido?
            2. O arquivo não está corrompido?
            3. Você tem permissão para ler o arquivo?
            
            Tente abrir o PDF em um visualizador para verificar se está íntegro.
            """
            raise Exception(error_msg)
    
    def chunk_text(self, text: str, metadata: Dict) -> List[Dict]:
        """
        Divide o texto em chunks com sobreposição
        """
        # Limpar texto
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Usar tiktoken para contar tokens
        encoding = tiktoken.encoding_for_model(self.chat_model)
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Encontrar o final do chunk baseado no número de tokens
            end = start + self.chunk_size
            
            # Se não for o último chunk, tentar cortar em ponto final
            if end < len(text):
                # Procurar ponto final próximo ao final
                period_pos = text.rfind('.', start, end + 100)
                if period_pos > start:
                    end = period_pos + 1
                else:
                    # Procurar quebra de linha
                    newline_pos = text.rfind('\n', start, end + 50)
                    if newline_pos > start:
                        end = newline_pos + 1
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                # Estimar em qual página está este chunk
                page_number = self._estimate_page_number(start, len(text), metadata['total_pages'])
                
                chunks.append({
                    'text': chunk_text,
                    'start_char': start,
                    'end_char': end,
                    'page_number': page_number,
                    'token_count': len(encoding.encode(chunk_text))
                })
            
            start = end - self.chunk_overlap if end < len(text) else end
        
        return chunks
    
    def _estimate_page_number(self, char_position: int, total_chars: int, total_pages: int) -> int:
        """Estima em qual página o caractere está"""
        ratio = char_position / total_chars if total_chars > 0 else 0
        return min(int(ratio * total_pages) + 1, total_pages)
    
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Cria embeddings usando OpenAI API
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            return embeddings
            
        except Exception as e:
            raise Exception(f"Erro ao criar embeddings: {str(e)}")
    
    def save_document(self, pdf_path: str) -> int:
        """
        Processa e salva um documento PDF completo
        """
        # Extrair texto
        text, metadata = self.extract_text_from_pdf(pdf_path)
        
        if not text.strip():
            raise Exception("PDF não contém texto extraível")
        
        # Criar chunks
        chunks = self.chunk_text(text, metadata)
        
        if not chunks:
            raise Exception("Não foi possível criar chunks do texto")
        
        # Salvar documento no banco
        conn = sqlite3.connect('ebserh_study.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO pdf_documents (filename, title, total_pages, total_chunks)
            VALUES (?, ?, ?, ?)
        ''', (os.path.basename(pdf_path), metadata['title'], metadata['total_pages'], len(chunks)))
        
        document_id = cursor.lastrowid
        
        # Salvar chunks
        chunk_texts = [chunk['text'] for chunk in chunks]
        embeddings = self.create_embeddings(chunk_texts)
        
        # Criar índice FAISS
        dimension = len(embeddings[0])
        index = faiss.IndexFlatL2(dimension)
        
        # Adicionar embeddings ao índice
        embedding_array = np.array(embeddings).astype('float32')
        index.add(embedding_array)
        
        # Salvar índice e chunks
        embedding_id = f"doc_{document_id}"
        index_path = os.path.join(self.embeddings_dir, f"{embedding_id}.faiss")
        faiss.write_index(index, index_path)
        
        # Salvar chunks no banco
        for i, chunk in enumerate(chunks):
            cursor.execute('''
                INSERT INTO pdf_chunks (document_id, chunk_index, text, page_number, embedding_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (document_id, i, chunk['text'], chunk['page_number'], embedding_id))
        
        conn.commit()
        conn.close()
        
        return document_id
    
    def search_relevant_chunks(self, query: str, document_id: Optional[int] = None, top_k: int = 5) -> List[Dict]:
        """
        Busca chunks relevantes para uma query
        """
        try:
            # Criar embedding da query
            query_embedding = self.create_embeddings([query])[0]
            query_array = np.array([query_embedding]).astype('float32')
            
            conn = sqlite3.connect('ebserh_study.db')
            cursor = conn.cursor()
            
            # Buscar documentos
            if document_id:
                cursor.execute('SELECT DISTINCT embedding_id FROM pdf_chunks WHERE document_id = ?', (document_id,))
            else:
                cursor.execute('SELECT DISTINCT embedding_id FROM pdf_chunks')
            
            embedding_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            all_results = []
            
            # Buscar em cada índice
            for embedding_id in embedding_ids:
                index_path = os.path.join(self.embeddings_dir, f"{embedding_id}.faiss")
                
                if not os.path.exists(index_path):
                    continue
                
                # Carregar índice
                index = faiss.read_index(index_path)
                
                # Buscar
                distances, indices = index.search(query_array, min(top_k, index.ntotal))
                
                # Recuperar chunks
                conn = sqlite3.connect('ebserh_study.db')
                cursor = conn.cursor()
                
                for i, idx in enumerate(indices[0]):
                    if idx == -1:  # FAISS retorna -1 para resultados inválidos
                        continue
                    
                    cursor.execute('''
                        SELECT pc.id, pc.document_id, pc.chunk_index, pc.text, pc.page_number, pd.filename, pd.title
                        FROM pdf_chunks pc
                        JOIN pdf_documents pd ON pc.document_id = pd.id
                        WHERE pc.embedding_id = ? AND pc.chunk_index = ?
                    ''', (embedding_id, int(idx)))
                    
                    result = cursor.fetchone()
                    if result:
                        chunk_id, doc_id, chunk_idx, text, page_num, filename, title = result
                        all_results.append({
                            'chunk_id': chunk_id,
                            'document_id': doc_id,
                            'chunk_index': chunk_idx,
                            'text': text,
                            'page_number': page_num,
                            'filename': filename,
                            'title': title,
                            'similarity_score': float(1 / (1 + distances[0][i]))  # Converter distância para similaridade
                        })
                
                conn.close()
            
            # Ordenar por similaridade e retornar top_k
            all_results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return all_results[:top_k]
            
        except Exception as e:
            raise Exception(f"Erro na busca semântica: {str(e)}")
    
    def generate_questions_from_content(self, document_id: int, num_questions: int = 5, difficulty: str = "Médio") -> List[Dict]:
        """
        Gera questões baseadas no conteúdo do documento
        """
        try:
            # Buscar chunks representativos do documento
            conn = sqlite3.connect('ebserh_study.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT text FROM pdf_chunks 
                WHERE document_id = ? 
                ORDER BY RANDOM() 
                LIMIT ?
            ''', (document_id, min(num_questions * 2, 20)))  # Pegar mais chunks para ter variedade
            
            chunks = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not chunks:
                raise Exception("Nenhum chunk encontrado para o documento")
            
            questions = []
            
            # Gerar questões para cada chunk
            for i, chunk in enumerate(chunks[:num_questions]):
                prompt = f"""
                Com base no seguinte trecho de um documento educativo, crie uma questão de múltipla escolha:

                CONTEÚDO:
                {chunk}

                INSTRUÇÕES:
                1. Crie uma questão clara e objetiva
                2. Elabore 4 alternativas (A, B, C, D)
                3. Apenas uma alternativa deve estar correta
                4. Inclua uma explicação breve da resposta correta
                5. Dificuldade: {difficulty}
                6. Formato JSON:
                {{
                    "question": "texto da questão",
                    "alternatives": {{
                        "A": "alternativa A",
                        "B": "alternativa B", 
                        "C": "alternativa C",
                        "D": "alternativa D"
                    }},
                    "correct_answer": "A",
                    "explanation": "explicação",
                    "discipline": "disciplina estimada"
                }}
                """
                
                response = self.client.chat.completions.create(
                    model=self.chat_model,
                    messages=[
                        {"role": "system", "content": "Você é um especialista em criar questões educativas de alta qualidade."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                
                try:
                    question_data = json.loads(response.choices[0].message.content)
                    questions.append(question_data)
                except json.JSONDecodeError:
                    continue
            
            return questions
            
        except Exception as e:
            raise Exception(f"Erro ao gerar questões: {str(e)}")
    
    def answer_question_about_content(self, question: str, document_id: Optional[int] = None) -> Dict:
        """
        Responde perguntas sobre o conteúdo dos documentos
        """
        try:
            # Buscar chunks relevantes
            relevant_chunks = self.search_relevant_chunks(question, document_id, top_k=5)
            
            if not relevant_chunks:
                return {
                    "answer": "Não encontrei informações relevantes para responder sua pergunta nos documentos disponíveis.",
                    "sources": []
                }
            
            # Preparar contexto
            context = "\n\n".join([f"Trecho {i+1} (página {chunk['page_number']}):\n{chunk['text']}" 
                                   for i, chunk in enumerate(relevant_chunks)])
            
            prompt = f"""
            Com base nos seguintes trechos de documento, responda à pergunta do usuário:

            CONTEXTO:
            {context}

            PERGUNTA: {question}

            INSTRUÇÕES:
            1. Responda com base APENAS nas informações fornecidas no contexto
            2. Se a informação não estiver no contexto, diga que não encontrou
            3. Seja claro e objetivo
            4. Cite as fontes (páginas) quando possível
            5. Formato JSON:
            {{
                "answer": "sua resposta",
                "sources": [{{"document": "nome do documento", "page": número_página}}]
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado em responder perguntas baseadas em documentos fornecidos."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                return result
            except json.JSONDecodeError:
                return {
                    "answer": response.choices[0].message.content,
                    "sources": [{"document": chunk["title"], "page": chunk["page_number"]} for chunk in relevant_chunks]
                }
                
        except Exception as e:
            raise Exception(f"Erro ao responder pergunta: {str(e)}")
    
    def get_documents_list(self) -> List[Dict]:
        """Lista todos os documentos processados"""
        conn = sqlite3.connect('ebserh_study.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, filename, title, total_pages, total_chunks, upload_date
            FROM pdf_documents
            ORDER BY upload_date DESC
        ''')
        
        documents = []
        for row in cursor.fetchall():
            documents.append({
                'id': row[0],
                'filename': row[1],
                'title': row[2],
                'total_pages': row[3],
                'total_chunks': row[4],
                'upload_date': row[5]
            })
        
        conn.close()
        return documents
    
    def save_generated_questions(self, document_id: int, questions: List[Dict]) -> int:
        """Salva questões geradas no banco"""
        conn = sqlite3.connect('ebserh_study.db')
        cursor = conn.cursor()
        
        saved_count = 0
        for question in questions:
            try:
                cursor.execute('''
                    INSERT INTO rag_questions (document_id, chunk_ids, question, alternatives, correct_answer, explanation, difficulty, discipline)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    document_id,
                    json.dumps([]),  # TODO: Implementar rastreamento de chunks usados
                    question['question'],
                    json.dumps(question['alternatives']),
                    question['correct_answer'],
                    question.get('explanation', ''),
                    question.get('difficulty', 'Médio'),
                    question.get('discipline', 'Geral')
                ))
                saved_count += 1
            except Exception as e:
                print(f"Erro ao salvar questão: {e}")
                continue
        
        conn.commit()
        conn.close()
        return saved_count

# Instância global
rag_service = RAGService()
