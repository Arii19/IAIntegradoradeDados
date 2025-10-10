from pathlib import Path
from dotenv import load_dotenv
import os
import json
import pathlib
import logging
from datetime import datetime
from typing import TypedDict, Optional
from functools import lru_cache
import hashlib
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, START, END
import pymupdf4llm

# =========================
# Configurações e Logging
# =========================
# Setup de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
api_key = os.getenv("API_KEY")

# Modelo Gemma com temperatura baixa para mais consistência
llm_triagem = None

def get_llm():
    """Lazy initialization of LLM"""
    global llm_triagem
    if llm_triagem is None:
        if not api_key:
            raise ValueError("API_KEY not found in environment variables")
        try:
            llm_triagem = ChatGoogleGenerativeAI(
                model="models/gemma-3-27b-it",
                temperature=0.9,  # Mais baixa para respostas mais consistentes
                google_api_key=api_key,
                # Removendo parâmetros que podem causar conflito
                request_timeout=60,
                # max_retries removido para evitar TypeError
            )
        except Exception as e:
            logger.error(f"Erro ao inicializar LLM: {e}")
            # Fallback para configuração mais simples
            llm_triagem = ChatGoogleGenerativeAI(
                model="models/gemma-3-27b-it",
                temperature=0.1,
                google_api_key=api_key
            )
    return llm_triagem

# =========================
# Sistema de Cache e Otimização Avançado para Batch Processing
# =========================
# Cache para respostas frequentes
CACHE_RESPOSTAS = {}
CACHE_RAG = {}  # Cache específico para resultados RAG
CACHE_LLM = {}  # Cache para respostas do LLM

# Estatísticas de cache
CACHE_STATS = {
    'hits': 0,
    'misses': 0,
    'total_saves': 0
}

@lru_cache(maxsize=200)  # Aumentado para batch processing
def cache_resposta_llm(prompt_hash: str, prompt: str):
    """Cache específico para respostas do LLM"""
    if prompt_hash in CACHE_LLM:
        CACHE_STATS['hits'] += 1
        return CACHE_LLM[prompt_hash]
    
    # Processar com LLM
    resposta = get_llm().invoke([HumanMessage(content=prompt)])
    resultado = resposta.content.strip() if resposta.content else ""
    
    # Salvar no cache
    CACHE_LLM[prompt_hash] = resultado
    CACHE_STATS['misses'] += 1
    CACHE_STATS['total_saves'] += 1
    
    return resultado

def limpar_cache():
    """Limpa todos os caches - útil para batch processing"""
    global CACHE_RESPOSTAS, CACHE_RAG, CACHE_LLM
    CACHE_RESPOSTAS.clear()
    CACHE_RAG.clear() 
    CACHE_LLM.clear()
    
    # Reset stats
    CACHE_STATS['hits'] = 0
    CACHE_STATS['misses'] = 0
    CACHE_STATS['total_saves'] = 0
    
    logger.info("Cache limpo para novo processamento em lote")

def get_cache_stats():
    """Retorna estatísticas do cache"""
    total = CACHE_STATS['hits'] + CACHE_STATS['misses']
    hit_rate = (CACHE_STATS['hits'] / total * 100) if total > 0 else 0
    
    return {
        'cache_hits': CACHE_STATS['hits'],
        'cache_misses': CACHE_STATS['misses'],
        'hit_rate_percent': round(hit_rate, 2),
        'total_cached_items': len(CACHE_RESPOSTAS) + len(CACHE_RAG) + len(CACHE_LLM),
        'cache_sizes': {
            'respostas': len(CACHE_RESPOSTAS),
            'rag': len(CACHE_RAG),
            'llm': len(CACHE_LLM)
        }
    }

def gerar_hash_pergunta(pergunta: str) -> str:
    """Gera hash da pergunta para cache"""
    return hashlib.md5(pergunta.lower().strip().encode()).hexdigest()

@lru_cache(maxsize=200)  # Aumentado para batch processing
def cache_triagem_otimizado(pergunta_hash: str, pergunta: str):
    """Cache otimizado para triagem - evita reprocessar perguntas similares"""
    # Verificar cache específico primeiro
    if pergunta_hash in CACHE_RESPOSTAS:
        CACHE_STATS['hits'] += 1
        logger.debug(f"Cache hit para triagem: {pergunta_hash[:8]}")
        return CACHE_RESPOSTAS[pergunta_hash]
    
    # Processar triagem
    resultado = triagem(pergunta)
    
    # Salvar no cache
    CACHE_RESPOSTAS[pergunta_hash] = resultado
    CACHE_STATS['misses'] += 1
    CACHE_STATS['total_saves'] += 1
    
    return resultado

def cache_rag_resultado(pergunta_hash: str, pergunta: str):
    """Cache específico para resultados RAG"""
    if pergunta_hash in CACHE_RAG:
        CACHE_STATS['hits'] += 1
        logger.debug(f"Cache hit para RAG: {pergunta_hash[:8]}")
        return CACHE_RAG[pergunta_hash]
    
    # Processar RAG
    resultado = perguntar_politica_RAG(pergunta)
    
    # Salvar no cache
    CACHE_RAG[pergunta_hash] = resultado
    CACHE_STATS['misses'] += 1
    CACHE_STATS['total_saves'] += 1
    
    return resultado
    return hashlib.md5(pergunta.lower().strip().encode()).hexdigest()

@lru_cache(maxsize=200)  # Aumentado para batch processing
def cache_triagem(pergunta_hash: str, pergunta: str):
    """Cache otimizado para triagem - evita reprocessar perguntas similares"""
    # Verificar cache específico primeiro
    if pergunta_hash in CACHE_RESPOSTAS:
        CACHE_STATS['hits'] += 1
        logger.debug(f"Cache hit para triagem: {pergunta_hash[:8]}")
        return CACHE_RESPOSTAS[pergunta_hash]
    
    # Processar triagem
    resultado = triagem(pergunta)
    
    # Salvar no cache
    CACHE_RESPOSTAS[pergunta_hash] = resultado
    CACHE_STATS['misses'] += 1
    CACHE_STATS['total_saves'] += 1
    
    return resultado

def log_interacao(pergunta: str, resposta: dict, acao: str):
    """Log das interações para monitoramento"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "pergunta": pergunta[:200],  # Limitar tamanho
            "acao": acao,
            "categoria": resposta.get("categoria", "N/A"),
            "sucesso": acao == "AUTO_RESOLVER"
        }
        logger.info(f"Interação: {log_entry}")
    except Exception as e:
        logger.error(f"Erro ao fazer log: {e}")

TRIAGEM_PROMPT = (
    "Analise a mensagem e retorne SOMENTE um JSON:\n\n"
    "{\n"
    '  \"decisao\": \"AUTO_RESOLVER\" | \"PEDIR_INFO\",\n'
    '  \"urgencia\": \"BAIXA\" | \"MEDIA\" | \"ALTA\",\n'
    '  \"categoria\": \"ETL\" | \"TI\" | \"DADOS\" | \"SQL\" | \"GERAL\"\n'
    "}\n\n"
    "**REGRAS PRINCIPAIS:**\n"
    "1. SEMPRE prefira AUTO_RESOLVER para perguntas técnicas específicas (procedures, sistemas, processos)\n"
    "2. AUTO_RESOLVER para qualquer pergunta que mencione códigos, funções, ou nomes específicos\n"
    "3. Use PEDIR_INFO apenas se a pergunta for extremamente vaga (ex: 'preciso de ajuda')\n"
    "4. Perguntas sobre 'INT.', 'SP_', procedures, ou códigos específicos = AUTO_RESOLVER\n"
    "**OBJETIVO:** Fornecer respostas técnicas precisas e diretas."
)

def detectar_categoria_inteligente(pergunta: str) -> str:
    """Detecta categoria baseada em análise mais sofisticada"""
    pergunta_lower = pergunta.lower()
    
    # Dicionário de categorias com pesos
    categorias_pesos = {
        "OPERACIONAL": {
            "palavras": ["processo", "procedimento", "fluxo", "aprovação", "prazo", "documento", "assinatura", "protocolo", 
                        "int.", "sp_", "procedure", "função", "aplicinsumo", "agric", "sistema", "dados"],
            "peso_base": 0
        },
        "TI": {
            "palavras": ["sistema", "acesso", "senha", "login", "computador", "software", "rede", "internet", "backup", "segurança",
                        "código", "aplicação", "banco", "dados"],
            "peso_base": 0
        },
        "ETL": {
            "palavras": ["extração", "transformação", "carga", "pipeline", "integração", "migração", "processamento", "batch", "streaming", "warehouse"],
            "peso_base": 0
        },
        "DADOS": {
            "palavras": ["database", "tabela", "consulta", "relatório", "análise", "dashboard", "indicador", "métrica", "kpi", "business intelligence"],
            "peso_base": 0
        }
    }
    
    # Calcular pontuação para cada categoria
    for categoria, dados in categorias_pesos.items():
        for palavra in dados["palavras"]:
            if palavra in pergunta_lower:
                dados["peso_base"] += 1
    
    # Encontrar categoria com maior pontuação
    categoria_detectada = max(categorias_pesos.items(), key=lambda x: x[1]["peso_base"])
    
    if categoria_detectada[1]["peso_base"] > 0:
        return categoria_detectada[0]
    
    return "GERAL"

def analisar_sentimento_pergunta(pergunta: str) -> dict:
    """Analisa o sentimento e tom da pergunta"""
    pergunta_lower = pergunta.lower()
    
    indicadores_urgencia = ["urgente", "rápido", "imediato", "emergência", "crítico", "problema"]
    indicadores_frustacao = ["não consigo", "não funciona", "erro", "falha", "quebrado", "parado"]
    indicadores_duvida = ["como", "onde", "quando", "qual", "posso", "devo", "seria possível"]
    
    sentimento = {
        "urgencia": any(ind in pergunta_lower for ind in indicadores_urgencia),
        "frustacao": any(ind in pergunta_lower for ind in indicadores_frustacao),
        "duvida_simples": any(ind in pergunta_lower for ind in indicadores_duvida),
        "tom": "neutro"
    }
    
    if sentimento["urgencia"] and sentimento["frustacao"]:
        sentimento["tom"] = "urgente_frustrado"
    elif sentimento["urgencia"]:
        sentimento["tom"] = "urgente"
    elif sentimento["frustacao"]:
        sentimento["tom"] = "frustrado"
    elif sentimento["duvida_simples"]:
        sentimento["tom"] = "consultivo"
    
    return sentimento

def analisar_fallback(mensagem: str) -> dict:
    """Análise de fallback quando o JSON falha - SEMPRE TENTA RESOLVER"""
    mensagem_lower = mensagem.lower()
    
    # Palavras-chave para diferentes categorias  
    palavras_info = ["como", "onde", "quando", "qual", "quem", "posso", "devo"]
    palavras_urgentes = ["urgente", "crítico", "emergência", "bloqueado", "parado", "falha"]
    palavras_tecnicas = ["int.", "sp_", "procedure", "função", "sistema", "código", "aplicinsumo"]
    
    # SEMPRE tentar resolver, especialmente para perguntas técnicas
    decisao = "AUTO_RESOLVER"
    
    urgencia = "ALTA" if any(palavra in mensagem_lower for palavra in palavras_urgentes) else "MEDIA"
    
    return {
        "decisao": decisao,
        "urgencia": urgencia,
        "categoria": "GERAL",
        "campos_faltantes": [],
        "palavras_chave": [palavra for palavra in palavras_info if palavra in mensagem_lower],
        "contexto_detectado": "Análise de fallback - sempre tenta resolver",
        "tecnica_detectada": any(palavra in mensagem_lower for palavra in palavras_tecnicas)
    }

def triagem(mensagem: str):
    # Verificar cache primeiro
    hash_pergunta = gerar_hash_pergunta(mensagem)
    if hash_pergunta in CACHE_RESPOSTAS:
        logger.info("Resposta recuperada do cache")
        return CACHE_RESPOSTAS[hash_pergunta]
    
    # Análises preliminares
    categoria_detectada = detectar_categoria_inteligente(mensagem)
    sentimento = analisar_sentimento_pergunta(mensagem)
    
    # Ajustar prompt baseado no contexto detectado
    prompt_contextual = f"{TRIAGEM_PROMPT}\n\n"
    prompt_contextual += f"CONTEXTO DETECTADO:\n"
    prompt_contextual += f"- Categoria provável: {categoria_detectada}\n"
    prompt_contextual += f"- Tom da mensagem: {sentimento['tom']}\n"
    prompt_contextual += f"- Indicadores: Urgência={sentimento['urgencia']}, Frustração={sentimento['frustacao']}\n\n"
    prompt_contextual += f"Mensagem do usuário: {mensagem}"
    
    resposta = get_llm().invoke([HumanMessage(content=prompt_contextual)])
    conteudo = resposta.content.strip()

    # Limpeza mais robusta do JSON
    if conteudo.startswith("```"):
        conteudo = conteudo.strip("`")
        if conteudo.lower().startswith("json"):
            conteudo = conteudo[4:].strip()
    
    try:
        resultado = json.loads(conteudo)
        
        # Enriquecer com análises contextuais
        resultado["categoria"] = categoria_detectada
        resultado["sentimento"] = sentimento
        
        # Ajustar decisão baseada no sentimento
        if sentimento["tom"] == "urgente_frustrado" and resultado["urgencia"] not in ["ALTA", "CRITICA"]:
            resultado["urgencia"] = "ALTA"
            
        # Detectar palavras-chave críticas
        palavras_criticas = ["urgente", "crítico", "bloqueado", "parado", "emergência", "falha", "erro"]
        if any(palavra in mensagem.lower() for palavra in palavras_criticas):
            if resultado["urgencia"] in ["BAIXA", "MEDIA"]:
                resultado["urgencia"] = "ALTA"
        
        # Salvar no cache
        CACHE_RESPOSTAS[hash_pergunta] = resultado
        
        return resultado
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao processar JSON: {e}")
        # Fallback inteligente baseado em análise de texto
        resultado_fallback = analisar_fallback(mensagem)
        resultado_fallback["categoria"] = categoria_detectada
        resultado_fallback["sentimento"] = sentimento
        return resultado_fallback

# =========================
# RAG Avançado com múltiplas estratégias
# =========================
docs = []

# Carregar documentos com melhor tratamento de erro
docs_path = Path("docs")

if docs_path.exists():
    # Carregar PDFs
    for n in docs_path.glob("*.pdf"):
        try:
            loader = PyMuPDFLoader(str(n))
            doc_pages = loader.load()
            
            # Enriquecer metadados
            for page in doc_pages:
                page.metadata.update({
                    "filename": n.name,
                    "file_size": n.stat().st_size,
                    "content_type": "pdf_document"
                })
            
            docs.extend(doc_pages)
            print(f"[OK] PDF Carregado: {n.name} ({len(doc_pages)} páginas)")
        except Exception as e:
            print(f"[ERRO] Erro ao carregar PDF {n.name}: {e}")
    
    # Carregar Markdown files
    for n in docs_path.glob("*.md"):
        try:
            with open(n, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Criar documento único para markdown
            from langchain_core.documents import Document
            md_doc = Document(
                page_content=content,
                metadata={
                    "filename": n.name,
                    "file_size": n.stat().st_size,
                    "content_type": "markdown_document",
                    "source": str(n)
                }
            )
            
            docs.append(md_doc)
            print(f"[OK] Markdown Carregado: {n.name} ({len(content)} caracteres)")
        except Exception as e:
            print(f"[ERRO] Erro ao carregar Markdown {n.name}: {e}")
else:
    print("[AVISO] Pasta 'docs' não encontrada. Nenhum documento carregado.")

retriever = None
retriever_keywords = None

if docs:
    # Splitter mais inteligente para diferentes tipos de conteúdo
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,  # Aumentado para mais contexto
        chunk_overlap=100,  # Mais overlap para continuidade
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""]
    )
    chunks = splitter.split_documents(docs)
    
    print(f"[CHUNKS] Total de chunks criados: {len(chunks)}")

    if api_key:
        try:
            embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=api_key
            )

            # Retriever principal por similaridade semântica
            vectorstore = FAISS.from_documents(chunks, embeddings)
            retriever = vectorstore.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"score_threshold": 0.15, "k": 8}  # Threshold ainda menor, mais resultados
            )
            
            # Retriever por palavras-chave (backup)
            retriever_keywords = vectorstore.as_retriever(
                search_type="mmr",  # Maximum Marginal Relevance para diversidade
                search_kwargs={"k": 4, "fetch_k": 10}
            )
        except Exception as e:
            print(f"[AVISO] Erro ao inicializar embeddings: {e}")
            retriever = None
            retriever_keywords = None
    else:
        print("[AVISO] API_KEY não encontrada. Funcionalidades RAG não estarão disponíveis.")
        retriever = None
        retriever_keywords = None

def expandir_busca(pergunta: str) -> list[str]:
    """Expande a busca com termos relacionados"""
    expansoes = {
        "férias": ["feriado", "descanso", "licença"],
        "salário": ["remuneração", "pagamento", "vencimento"],
        "trabalho": ["emprego", "função", "cargo", "atividade"],
        "hora": ["horário", "tempo", "expediente"],
        "benefits": ["benefícios", "vantagens", "auxílio"],
        "contrato": ["acordo", "termo", "documento"],
        "politica": ["regra", "procedimento", "norma"],
        "acesso": ["permissão", "autorização", "login"],
        "origem": ["fonte", "proveniência", "procedência", "ERP", "sistema", "base"],
        "dados": ["informações", "registros", "data", "informação"],
        "origem dos dados": ["fonte dos dados", "procedência dos dados", "ERP", "sistema origem", "base de dados"],
        "procedure": ["procedimento", "função", "rotina", "processo"],
        "aplicinsumo": ["insumo agrícola", "agric", "agricultura", "aplicação"]
    }
    
    termos = []
    pergunta_lower = pergunta.lower()
    
    for termo_base, sinonimos in expansoes.items():
        if termo_base in pergunta_lower:
            termos.extend(sinonimos)
    
    return termos[:5]  # Aumentei para 5 termos extras

def remover_duplicatas_docs(docs_list):
    """Remove documentos duplicados baseado no conteúdo"""
    vistos = set()
    docs_unicos = []
    
    for doc in docs_list:
        # Usar hash do conteúdo para identificar duplicatas
        conteudo_hash = hash(doc.page_content[:100])  # Primeiros 100 chars
        if conteudo_hash not in vistos:
            vistos.add(conteudo_hash)
            docs_unicos.append(doc)
    
    return docs_unicos

def criar_citacoes_melhoradas(docs: list) -> list[dict]:
    """Cria citações mais informativas"""
    citacoes = []
    
    for i, doc in enumerate(docs[:3]):  # Máximo 3 citações
        try:
            citacao = {
                "documento": pathlib.Path(doc.metadata.get("source", "")).name,
                "pagina": int(doc.metadata.get("page", 0)) + 1,
                "trecho": doc.page_content[:250] + "..." if len(doc.page_content) > 250 else doc.page_content,
                "relevancia": f"Fonte {i+1}",
                "tamanho_arquivo": doc.metadata.get("file_size", "N/A")
            }
            citacoes.append(citacao)
        except Exception as e:
            print(f"Erro ao criar citação: {e}")
            continue
    
    return citacoes

def validar_e_corrigir_resposta(resposta: str, pergunta: str, docs: list) -> str:
    """Valida e corrige a resposta do RAG - PRIORIZANDO MÁXIMA CONCISÃO"""
    resposta_original = resposta
    
    # Verificações de qualidade com foco em concisão
    problemas = []
    
    # 1. Resposta muito longa (MAIS RIGOROSO)
    palavras = len(resposta.split())
    if palavras > 150:  # Reduzido de 200 para 150
        problemas.append("resposta_muito_longa")
        # Tentar encurtar drasticamente
        if docs:
            prompt_resumir = f"""
            Resuma em NO MÁXIMO 50 palavras, mantendo APENAS o essencial:
            
            Pergunta: {pergunta}
            Resposta: {resposta}
            
            Versão ultra-resumida (máximo 50 palavras):
            """
            try:
                resposta_resumida = get_llm().invoke([HumanMessage(content=prompt_resumir)])
                resposta_nova = resposta_resumida.content.strip()
                if len(resposta_nova.split()) < 80:  # Aceitar se ficar menor que 80 palavras
                    resposta = resposta_nova
            except Exception:
                pass
    elif palavras > 100:  # Moderadamente longa
        problemas.append("resposta_longa")
    elif palavras < 10:  # Muito curta
        problemas.append("resposta_muito_curta")
    
    # 2. Detectar introduções desnecessárias
    introducoes_ruins = [
        "olá", "como especialista", "posso te ajudar", "vou te explicar",
        "bem-vindo", "fico feliz", "é um prazer"
    ]
    inicio_resposta = resposta[:100].lower()
    if any(intro in inicio_resposta for intro in introducoes_ruins):
        problemas.append("introducao_desnecessaria")
        # Tentar remover introdução
        linhas = resposta.split('\n')
        if len(linhas) > 1:
            # Pular primeira linha se for introdução
            resposta_sem_intro = '\n'.join(linhas[1:]).strip()
            if len(resposta_sem_intro) > 20:
                resposta = resposta_sem_intro
    
    # 3. Resposta genérica demais
    palavras_genericas = ["talvez", "pode ser", "geralmente", "normalmente", "às vezes"]
    if sum(1 for palavra in palavras_genericas if palavra in resposta.lower()) > 1:
        problemas.append("resposta_generica")
    
    return resposta

def gerar_resposta_sem_documentos(pergunta: str) -> str:
    """Gera uma resposta útil mas CONCISA mesmo sem documentos específicos"""
    
    prompt = f"""Você é um Integrador de dados e desenvolvedor ETL da empresa SmartBreeder.

INSTRUÇÃO: Forneça uma resposta BREVE e TÉCNICA para a pergunta.

REGRAS:
- Máximo 2 parágrafos
- Linguagem técnica mas clara
- Vá direto ao ponto
- Evite rodeios e saudações

PERGUNTA: {pergunta}

Resposta técnica:"""
    
    resposta = get_llm().invoke([HumanMessage(content=prompt)])
    txt = (resposta.content or "").strip()
    
    # Adicionar disclaimer breve
    return f"{txt}\n\n💡 **Para detalhes específicos, consulte a documentação técnica.**"

def perguntar_politica_RAG(pergunta: str) -> dict:
    try:
        logger.info(f"[RAG] Iniciando busca para: {pergunta}")
        
        if not retriever:
            logger.warning("[RAG] Retriever não disponível")
            return {
                "answer": "Sistema de documentos não disponível no momento.",
                "citacoes": [],
                "contexto_encontrado": False,
                "estrategia_usada": "nenhuma"
            }

        # Estratégia 1: Busca semântica principal
        logger.info("[RAG] Executando busca semântica principal")
        docs_relacionados = retriever.invoke(pergunta)
        estrategia = "similaridade_semantica"
        logger.info(f"[RAG] Busca principal encontrou {len(docs_relacionados)} documentos")
        
        # Estratégia 2: SEMPRE tentar busca expandida com termos relacionados
        termos_expandidos = expandir_busca(pergunta)
        logger.info(f"[RAG] Termos expandidos para '{pergunta}': {termos_expandidos}")
        
        for termo in termos_expandidos:
            docs_extra = retriever.invoke(termo)
            docs_relacionados.extend(docs_extra[:3])  # Aumentei para 3 docs por termo
            logger.info(f"[RAG] Encontrados {len(docs_extra)} docs para termo '{termo}'")
        
        # Estratégia 3: Se poucos resultados, tentar busca por palavras-chave
        if len(docs_relacionados) < 3 and retriever_keywords:
            logger.info("[RAG] Executando busca por palavras-chave")
            docs_keywords = retriever_keywords.invoke(pergunta)
            docs_relacionados.extend(docs_keywords)
            estrategia = "semantica_e_palavras_chave_expandida"
        else:
            estrategia = "busca_expandida"

        if not docs_relacionados:
            # Mesmo sem documentos específicos, tentar fornecer resposta útil
            logger.warning("[RAG] Nenhum documento encontrado, gerando resposta genérica")
            resposta_generica = gerar_resposta_sem_documentos(pergunta)
            return {
                "answer": resposta_generica,
                "citacoes": [],
                "contexto_encontrado": False,
                "estrategia_usada": "resposta_generica"
            }

        # Remover duplicatas e ordenar por relevância
        docs_unicos = remover_duplicatas_docs(docs_relacionados)
        logger.info(f"[RAG] Total de documentos únicos encontrados: {len(docs_unicos)}")
        contexto = "\n\n".join(d.page_content for d in docs_unicos[:4])  # Limitar contexto
    
        # Prompt mais útil e CONCISO
        prompt = f"""Você é um Integrador de dados e desenvolvedor ETL da empresa SmartBreeder.

INSTRUÇÕES IMPORTANTES:
- Use o contexto fornecido como base principal
- SEJA CONCISO E DIRETO - respostas de no máximo 2-3 parágrafos
- Vá direto ao ponto, mas aplique a llm para passar as respostas, mas não se esqueça de usar os termos técnicos e depois faça um resumo curto explicando de forma mais simples
- Use linguagem técnica mas clara
- Evite introduções longas ("Olá! Como Especialista...")
- PARE quando der a informação principal - não detalhe demais
- FOQUE NO QUE O USUÁRIO REALMENTE QUER SABER

PERGUNTA: {pergunta}

CONTEXTO DISPONÍVEL:
{contexto}

Resposta técnica e direta:"""

        logger.info("[RAG] Executando prompt com LLM")
        resposta = get_llm().invoke([HumanMessage(content=prompt)])
        txt = (resposta.content or "").strip()

        # Validar e potencialmente corrigir a resposta
        resposta_final = validar_e_corrigir_resposta(txt, pergunta, docs_unicos)
        
        if "não disponível" in resposta_final.lower() or "não sei" in resposta_final.lower():
            return {
                "answer": "Informação não encontrada nos documentos. Recomendo contatar um integrador esclarecimentos específicos.",
                "citacoes": [],
                "contexto_encontrado": False,
                "estrategia_usada": estrategia,
                "melhorada": False
            }

        logger.info(f"[RAG] Resposta gerada com sucesso, contexto_encontrado=True")
        return {
            "answer": resposta_final,
            "citacoes": criar_citacoes_melhoradas(docs_unicos),
            "contexto_encontrado": True,
            "estrategia_usada": estrategia,
            "melhorada": resposta_final != txt  # Indica se foi melhorada
        }
        
    except Exception as e:
        logger.error(f"[RAG] Erro: {type(e).__name__}: {str(e)}")
        return {
            "answer": f"Erro no sistema RAG: {str(e)}",
            "citacoes": [],
            "contexto_encontrado": False,
            "estrategia_usada": "erro",
            "melhorada": False
        }

# =========================
# Fluxo de decisão aprimorado
# =========================
class AgentState(TypedDict, total=False):
    pergunta: str
    triagem: dict
    resposta: Optional[str]
    citacoes: list[dict]
    rag_sucesso: bool
    acao_final: str
    historico_tentativas: list[str]
    categoria: str

def node_triagem(state: AgentState) -> AgentState:
    resultado_triagem = triagem(state["pergunta"])
    return {
        "triagem": resultado_triagem,
        "categoria": resultado_triagem.get("categoria", "GERAL"),
        "historico_tentativas": ["triagem"]
    }

def node_auto_resolver(state: AgentState) -> AgentState:
    try:
        logger.info(f"[AUTO_RESOLVER] Iniciando para pergunta: {state['pergunta']}")
        resposta_rag = perguntar_politica_RAG(state["pergunta"])
        logger.info(f"[AUTO_RESOLVER] RAG retornou: contexto_encontrado={resposta_rag['contexto_encontrado']}")
        
        update: AgentState = {
            "resposta": resposta_rag["answer"],
            "citacoes": resposta_rag.get("citacoes", []),
            "rag_sucesso": resposta_rag["contexto_encontrado"],
            "historico_tentativas": state.get("historico_tentativas", []) + ["auto_resolver"]
        }
        
        # Decisão baseada no sucesso do RAG
        if resposta_rag["contexto_encontrado"]:
            update["acao_final"] = "AUTO_RESOLVER"
        else:
            update["acao_final"] = "AUTO_RESOLVER"  # Sempre tenta resolver
        
        logger.info(f"[AUTO_RESOLVER] Finalizando com acao_final: {update['acao_final']}")
        return update
        
    except Exception as e:
        logger.error(f"[AUTO_RESOLVER] Erro: {type(e).__name__}: {str(e)}")
        return {
            "resposta": f"Erro no processamento automático: {str(e)}",
            "citacoes": [],
            "rag_sucesso": False,
            "acao_final": "ERRO",
            "historico_tentativas": state.get("historico_tentativas", []) + ["auto_resolver_erro"]
        }

def node_pedir_info(state: AgentState) -> AgentState:
    # Resposta mais concisa para pedir informações
    resposta = "❓ **Preciso de mais detalhes para ajudar melhor.**\n\nPoderia ser mais específico sobre o que você quer saber?"
    
    return {
        "resposta": resposta,
        "citacoes": [],
        "acao_final": "PEDIR_INFO",
        "historico_tentativas": state.get("historico_tentativas", []) + ["pedir_info"]
    }

def decidir_pos_triagem(state: AgentState) -> str:
    decisao = state["triagem"]["decisao"]
    
    # Só há duas opções agora: AUTO_RESOLVER ou PEDIR_INFO
    if decisao == "AUTO_RESOLVER": 
        return "auto"
    else:  # decisao == "PEDIR_INFO" ou qualquer outra coisa
        return "info"

def decidir_pos_auto_resolver(state: AgentState) -> str:
    rag_sucesso = state.get("rag_sucesso", False)
    tentativas = len(state.get("historico_tentativas", []))
    
    # Se já tentou resolver várias vezes, tentar mais uma vez com abordagem diferente
    if tentativas > 3:
        return "info"  # Pedir mais informações em vez de abrir chamado
    
    # Se RAG teve sucesso, sempre retorna resposta
    if rag_sucesso:
        return "ok"
    
    # Se não teve sucesso, pedir mais informações para tentar novamente
    return "info"

workflow = StateGraph(AgentState)
workflow.add_node("triagem", node_triagem)
workflow.add_node("auto_resolver", node_auto_resolver)
workflow.add_node("pedir_info", node_pedir_info)

workflow.add_edge(START, "triagem")
workflow.add_conditional_edges("triagem", decidir_pos_triagem, {
    "auto": "auto_resolver",
    "info": "pedir_info"
})
workflow.add_conditional_edges("auto_resolver", decidir_pos_auto_resolver, {
    "info": "pedir_info", 
    "ok": END
})
workflow.add_edge("pedir_info", END)

grafo = workflow.compile()

def processar_pergunta(pergunta: str, historico_conversa: list = None) -> dict:
    """
    Função principal melhorada para processar perguntas
    Retorna resposta estruturada
    """
    try:
        logger.info(f"Iniciando processamento da pergunta: {pergunta}")
        
        if not pergunta.strip():
            return {
                "resposta": "Por favor, faça uma pergunta específica sobre procedimentos da integração.",
                "citacoes": [],
                "acao_final": "PEDIR_INFO",
                "categoria": "GERAL",
                "melhorada": False,
                "feedback_id": None
            }
        
        # Verificar se a API key está disponível
        if not api_key:
            logger.error("API_KEY não encontrada")
            return {
                "resposta": "Erro de configuração: API_KEY não encontrada. Verifique suas configurações.",
                "citacoes": [],
                "acao_final": "ERRO",
                "categoria": "ERRO",
                "erro": "API_KEY não encontrada",
                "melhorada": False,
                "feedback_id": None
            }
        
        # Verificar se o retriever está inicializado
        if retriever is None:
            logger.error("Sistema de documentos não inicializado")
            return {
                "resposta": "Sistema de documentos não disponível. Verifique se os documentos foram carregados corretamente.",
                "citacoes": [],
                "acao_final": "ERRO",
                "categoria": "ERRO",
                "erro": "Retriever não inicializado",
                "melhorada": False,
                "feedback_id": None
            }
        
        # Analisar contexto do histórico para perguntas vagas
        logger.info("Analisando contexto do histórico")
        pergunta_contextualizada = analisar_contexto_historico(pergunta, historico_conversa)
        logger.info(f"Pergunta contextualizada: {pergunta_contextualizada}")
        
        # Executar o workflow
        logger.info("Executando workflow do grafo")
        resultado = grafo.invoke({"pergunta": pergunta_contextualizada})
        logger.info(f"Resultado do grafo: {resultado.get('acao_final', 'N/A')}")
        
        # Log da interação
        log_interacao(pergunta, resultado, resultado.get("acao_final", "ERRO"))
        
        # Enriquecer resposta com metadados
        resultado["timestamp"] = datetime.now().isoformat()
        
        # Verificar se precisa de ajustes baseado em feedback histórico
        ajustes = verificar_ajustes_necessarios(pergunta, resultado)
        if ajustes:
            resultado["ajustes_aplicados"] = ajustes
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao processar pergunta: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "resposta": f"Ocorreu um erro interno ({type(e).__name__}). Por favor, tente novamente ou contate o suporte.",
            "citacoes": [],
            "acao_final": "ERRO",
            "categoria": "ERRO",
            "erro": f"{type(e).__name__}: {str(e)}",
            "melhorada": False,
            "feedback_id": None
        }

def analisar_contexto_historico(pergunta: str, historico_conversa: list = None) -> str:
    """Analisa o contexto do histórico para enriquecer perguntas vagas"""
    if not historico_conversa or len(historico_conversa) == 0:
        return pergunta
    
    pergunta_lower = pergunta.lower().strip()
    
    # Detectar perguntas que fazem referência ao contexto anterior
    referencias_contexto = {
    "origem": [
        "origem dos dados", "origem", "onde vem", "fonte", "qual a origem", "de onde vem", "procedência",
        "fonte de informação", "base de origem", "local de extração", "ponto de coleta", 
        "banco de origem", "sistema de origem", "origem da informação", "proveniência", 
        "origem do registro", "onde foram capturados", "onde estão armazenados", "fonte original", 
        "de onde foram obtidos", "origem do conteúdo", "de qual sistema vem", "de qual base provém", 
        "de onde foi coletado", "qual a proveniência", "de que lugar vem", "de que tabela vem", 
        "onde foi obtido", "onde está localizado", "de onde foi extraído"
    ],

    "processo": [
        "como é feito", "como funciona", "processo", "método de funcionamento", "forma de geração", 
        "modo de operação", "fluxo de processamento", "procedimento adotado", "lógica de cálculo", 
        "passo a passo", "sequência de etapas", "pipeline de dados", "regra de negócio", 
        "tratamento aplicado", "transformação dos dados", "rotina executada"
    ],

    "detalhes": [
        "mais detalhes", "especificamente", "detalhe", "informações adicionais", "explicação detalhada", 
        "aprofundamento", "descrição completa", "contexto adicional", "detalhamento", 
        "maiores informações", "em detalhe", "explicação minuciosa", "esclarecimento", 
        "visão ampliada"
    ],

    "identificacao": [
        "identificação", "campo", "como é identificado", "atributo identificador", "chave primária", 
        "nome do campo", "código", "label", "identificador único", "coluna correspondente", 
        "parâmetro de identificação", "referência de campo", "tag", "ID de origem", 
        "valor identificador"
    ]
}

    # Palavras que indicam referência à conversa anterior
    referencias_anteriores = [
        "dessa", "desse", "desta", "deste", "nisso", "isso",
        "anterior", "que falamos", "mencionado", "citado",
        "na", "no", "da", "do"  # Preposições que podem indicar continuidade
    ]
    
    tem_referencia_contexto = any(ref in pergunta_lower for ref in referencias_contexto)
    tem_referencia_anterior = any(ref in pergunta_lower for ref in referencias_anteriores)
    
    # Detectar perguntas sobre campos específicos sem mencionar a tabela/procedure
    campos_tecnicos = ["se_usina", "se_insumo", "se_aplicinsumo", "datafinal", "quantidade", "dosagem"]
    pergunta_sobre_campo = any(campo in pergunta_lower for campo in campos_tecnicos)
    
    # Perguntas curtas (até 8 palavras) provavelmente precisam de contexto
    pergunta_curta = len(pergunta.split()) <= 8
    
    # Se a pergunta precisa de contexto
    if (tem_referencia_contexto or tem_referencia_anterior or pergunta_sobre_campo or pergunta_curta):
        # Pegar as últimas mensagens que tiveram sucesso (não apenas com citações)
        ultima_resposta_tecnica = None
        ultimo_assunto = None
        
        # Procurar nas últimas 5 mensagens (mais contexto)
        for item in reversed(historico_conversa[-5:]):
            # Relaxar os critérios - qualquer resposta que não seja erro
            if item.get("acao") == "AUTO_RESOLVER" and item.get("resposta"):
                ultima_resposta_tecnica = item.get("resposta", "")
                ultimo_assunto = item.get("pergunta", "")
                break
        
        if ultima_resposta_tecnica and ultimo_assunto:
            # Extrair palavras-chave técnicas da conversa anterior
            palavras_chave_anteriores = extrair_palavras_chave_tecnicas(ultimo_assunto, ultima_resposta_tecnica)
            
            # Contextualizar a pergunta atual
            if palavras_chave_anteriores:
                # Melhor contextualização: adicionar contexto mais direto
                contexto_principal = ""
                for palavra in palavras_chave_anteriores[:2]:  # Top 2 palavras-chave
                    if "sp_at_int_aplicinsumoagric" in palavra.lower():
                        contexto_principal = "na procedure int.SP_AT_INT_APLICINSUMOAGRIC"
                        break
                    elif "aplicinsumo" in palavra.lower():
                        contexto_principal = "no contexto de aplicação de insumos agrícolas"
                        break
                
                if contexto_principal:
                    pergunta_contextualizada = f"{pergunta} {contexto_principal}"
                else:
                    pergunta_contextualizada = f"{pergunta} (contexto: {ultimo_assunto[:100]}... - palavras-chave: {', '.join(palavras_chave_anteriores[:3])})"
                
                logger.info(f"Pergunta contextualizada: '{pergunta}' -> '{pergunta_contextualizada}'")
                return pergunta_contextualizada
    
    return pergunta

def extrair_palavras_chave_tecnicas(pergunta_anterior: str, resposta_anterior: str) -> list:
    """Extrai palavras-chave técnicas da conversa anterior"""
    texto_completo = f"{pergunta_anterior} {resposta_anterior}".lower()
    
    # Palavras-chave técnicas relevantes
    palavras_tecnicas = [
        "int.int_aplicinsumoagric", "aplicinsumoagric", "procedure", "tabela",
        "sp_des_int_aplicinsumoagric", "sp_at_int_aplicinsumoagric",
        "temp_des_aplicinsumoagric", "tblf_transfere_fazendas",
        "erp", "sistema", "dados", "origem", "fonte", "normalização",
        "consolidação", "regras de negócio", "fazenda", "insumo", "agrícola"
    ]
    
    palavras_encontradas = []
    for palavra in palavras_tecnicas:
        if palavra in texto_completo:
            palavras_encontradas.append(palavra)
    
    return palavras_encontradas[:5]  # Máximo 5 palavras-chave

def verificar_ajustes_necessarios(pergunta: str, resultado: dict) -> list:
    """Verifica se são necessários ajustes baseado no histórico"""
    ajustes = []
    
    # Sistema de feedback removido - foco em resolver sempre que possível
    ajustes = []
    
    return ajustes

# Função para compatibilidade com o app.py existente
def processar_mensagem(mensagem: str, historico_conversa: list = None) -> dict:
    """Wrapper para compatibilidade com interface existente"""
    return processar_pergunta(mensagem, historico_conversa)
