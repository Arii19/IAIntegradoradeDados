#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de debug para identificar o problema com a IA
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

def teste_api_key():
    """Testa se a API Key está funcionando"""
    print("=== TESTE API KEY ===")
    load_dotenv()
    api_key = os.getenv("API_KEY")
    
    if not api_key:
        print("❌ API_KEY não encontrada")
        return False
    
    print(f"✅ API_KEY encontrada (length: {len(api_key)})")
    
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            temperature=0.1,
            google_api_key=api_key
        )
        
        resposta = llm.invoke([HumanMessage(content="Teste simples: responda apenas 'OK'")])
        print(f"✅ LLM funcionando: {resposta.content}")
        return True
        
    except Exception as e:
        print(f"❌ Erro no LLM: {e}")
        return False

def teste_documentos():
    """Testa se os documentos estão sendo carregados"""
    print("\n=== TESTE DOCUMENTOS ===")
    
    docs_path = Path("docs")
    if not docs_path.exists():
        print("❌ Pasta docs não existe")
        return [], False
    
    print(f"✅ Pasta docs existe")
    
    arquivos_md = list(docs_path.glob("*.md"))
    print(f"✅ Encontrados {len(arquivos_md)} arquivos .md")
    
    docs = []
    for arquivo in arquivos_md:
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                content = f.read()
            
            doc = Document(
                page_content=content,
                metadata={"source": str(arquivo)}
            )
            docs.append(doc)
            print(f"✅ Carregado: {arquivo.name} ({len(content)} chars)")
            
        except Exception as e:
            print(f"❌ Erro ao carregar {arquivo.name}: {e}")
    
    return docs, len(docs) > 0

def teste_embeddings(docs):
    """Testa se os embeddings estão funcionando"""
    print("\n=== TESTE EMBEDDINGS ===")
    
    if not docs:
        print("❌ Nenhum documento para testar")
        return None, False
    
    load_dotenv()
    api_key = os.getenv("API_KEY")
    
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=api_key
        )
        print("✅ Embeddings inicializados")
        
        # Testar com um pedaço pequeno
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        chunks = splitter.split_documents(docs[:1])  # Apenas o primeiro doc
        print(f"✅ Criados {len(chunks)} chunks")
        
        # Testar FAISS
        vectorstore = FAISS.from_documents(chunks, embeddings)
        print("✅ FAISS criado com sucesso")
        
        retriever = vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"score_threshold": 0.1, "k": 3}
        )
        print("✅ Retriever criado")
        
        return retriever, True
        
    except Exception as e:
        print(f"❌ Erro nos embeddings: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None, False

def teste_busca(retriever):
    """Testa uma busca simples"""
    print("\n=== TESTE BUSCA ===")
    
    if not retriever:
        print("❌ Retriever não disponível")
        return False
    
    pergunta = "para que serve a SP_AT_INT_APLICINSUMOAGRIC"
    
    try:
        docs_encontrados = retriever.invoke(pergunta)
        print(f"✅ Busca executada - {len(docs_encontrados)} documentos encontrados")
        
        for i, doc in enumerate(docs_encontrados):
            preview = doc.page_content[:100].replace('\n', ' ')
            print(f"  Doc {i+1}: {preview}...")
        
        return len(docs_encontrados) > 0
        
    except Exception as e:
        print(f"❌ Erro na busca: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def teste_resposta_completa():
    """Testa uma resposta completa como no main.py"""
    print("\n=== TESTE RESPOSTA COMPLETA ===")
    
    pergunta = "para que serve a SP_AT_INT_APLICINSUMOAGRIC"
    
    # Carregando como no main.py
    load_dotenv()
    api_key = os.getenv("API_KEY")
    
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            temperature=0.1,
            google_api_key=api_key
        )
        
        # Buscar informação específica nos documentos
        docs_path = Path("docs")
        doc_file = docs_path / "SP_AT_INT_APLICINSUMOAGRIC_Documentacao_Tecnica.md"
        
        if doc_file.exists():
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extrair informação relevante
            sections = content.split("##")
            objetivo_section = ""
            
            for section in sections:
                if "objetivo" in section.lower() or "visão geral" in section.lower():
                    objetivo_section = section[:1000]  # Primeiro 1000 chars
                    break
            
            prompt = f"""Baseado na documentação fornecida, explique de forma clara e concisa para que serve a procedure int.SP_AT_INT_APLICINSUMOAGRIC.

DOCUMENTAÇÃO:
{objetivo_section}

Responda de forma técnica mas compreensível:"""

            resposta = llm.invoke([HumanMessage(content=prompt)])
            print(f"✅ Resposta gerada:")
            print(f"{resposta.content}")
            return True
            
        else:
            print("❌ Arquivo de documentação não encontrado")
            return False
            
    except Exception as e:
        print(f"❌ Erro na resposta completa: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🔍 INICIANDO DIAGNÓSTICO COMPLETO")
    print("=" * 50)
    
    # Sequência de testes
    api_ok = teste_api_key()
    
    if api_ok:
        docs, docs_ok = teste_documentos()
        
        if docs_ok:
            retriever, embed_ok = teste_embeddings(docs)
            
            if embed_ok:
                busca_ok = teste_busca(retriever)
                
            # Teste alternativo mais simples
            resposta_ok = teste_resposta_completa()
        
    print("\n" + "=" * 50)
    print("🏁 DIAGNÓSTICO CONCLUÍDO")