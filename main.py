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

# =========================
# Configurações e Logging
# =========================
# Setup de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
api_key = os.getenv("API_KEY")

# Modelo Gemma com temperatura baixa para mais consistência
llm_triagem = ChatGoogleGenerativeAI(
    model="models/gemma-3-27b-it",
    temperature=0.1,  # Mais baixa para respostas mais consistentes
    api_key=api_key
)

# =========================
# Sistema de Cache e Otimização
# =========================
# Cache para respostas frequentes
CACHE_RESPOSTAS = {}

def gerar_hash_pergunta(pergunta: str) -> str:
    """Gera hash da pergunta para cache"""
    return hashlib.md5(pergunta.lower().strip().encode()).hexdigest()

@lru_cache(maxsize=100)
def cache_triagem(pergunta_hash: str, pergunta: str):
    """Cache para triagem - evita reprocessar perguntas similares"""
    return triagem(pergunta)

def log_interacao(pergunta: str, resposta: dict, acao: str):
    """Log das interações para monitoramento"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "pergunta": pergunta[:200],  # Limitar tamanho
            "acao": acao,
            "confianca": resposta.get("confianca_geral", 0.0),
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
    '  \"categoria\": \"RH\" | \"TI\" | \"FINANCEIRO\" | \"OPERACIONAL\" | \"GERAL\",\n'
    '  \"confianca\": 0.0-1.0\n'
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
        "RH": {
            "palavras": ["salário", "férias", "benefício", "contrato", "admissão", "demissão", "funcionário", "colaborador", "pagamento", "folha"],
            "peso_base": 0
        },
        "FINANCEIRO": {
            "palavras": ["reembolso", "nota fiscal", "despesa", "orçamento", "compra", "pagamento", "fatura", "custo"],
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
    if any(palavra in mensagem_lower for palavra in palavras_tecnicas):
        decisao = "AUTO_RESOLVER"
        confianca = 0.8  # Alta confiança para perguntas técnicas
    elif any(palavra in mensagem_lower for palavra in palavras_info) and len(mensagem.split()) > 2:
        decisao = "AUTO_RESOLVER"
        confianca = 0.7
    elif len(mensagem.split()) > 3:  # Se tem conteúdo suficiente, tentar resolver
        decisao = "AUTO_RESOLVER" 
        confianca = 0.6
    else:
        decisao = "AUTO_RESOLVER"  # Mudei de PEDIR_INFO para AUTO_RESOLVER
        confianca = 0.5  # Aumentei a confiança mínima
    
    urgencia = "ALTA" if any(palavra in mensagem_lower for palavra in palavras_urgentes) else "MEDIA"
    
    return {
        "decisao": decisao,
        "urgencia": urgencia,
        "confianca": confianca,
        "categoria": "GERAL",
        "campos_faltantes": [],  # Removido condição de campos faltantes
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
    
    resposta = llm_triagem.invoke([HumanMessage(content=prompt_contextual)])
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
        
        # Validação e enriquecimento dos dados
        if "confianca" not in resultado:
            resultado["confianca"] = 0.5
        
        # Ajustar decisão baseada no sentimento
        if sentimento["tom"] == "urgente_frustrado" and resultado["urgencia"] not in ["ALTA", "CRITICA"]:
            resultado["urgencia"] = "ALTA"
            
        if sentimento["frustacao"] and resultado["decisao"] == "AUTO_RESOLVER":
            # Se pessoa está frustrada, pode ser melhor abrir chamado
            resultado["confianca"] = max(0.3, resultado["confianca"] - 0.2)
        
        # Ajustar decisão baseada na confiança - mais permissivo
        if resultado["confianca"] < 0.2:  # Só vai para PEDIR_INFO se muito baixa
            resultado["decisao"] = "PEDIR_INFO"
        elif resultado["confianca"] > 0.6 and resultado["decisao"] == "PEDIR_INFO":  # Mais permissivo
            resultado["decisao"] = "AUTO_RESOLVER"
            
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
pdf_path = Path("docs")

if pdf_path.exists():
    for n in pdf_path.glob("*.pdf"):
        try:
            loader = PyMuPDFLoader(str(n))
            doc_pages = loader.load()
            
            # Enriquecer metadados
            for page in doc_pages:
                page.metadata.update({
                    "filename": n.name,
                    "file_size": n.stat().st_size,
                    "content_type": "policy_document"
                })
            
            docs.extend(doc_pages)
            print(f"[OK] Carregado: {n.name} ({len(doc_pages)} páginas)")
        except Exception as e:
            print(f"[ERRO] Erro ao carregar {n.name}: {e}")
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

def calcular_confianca_resposta(pergunta: str, resposta: str, docs: list) -> float:
    """Calcula a confiança da resposta baseado em vários fatores"""
    confianca = 0.5  # Base
    
    # Fator 1: Tamanho da resposta (respostas muito curtas são suspeitas)
    if len(resposta.split()) > 10:
        confianca += 0.1
    if len(resposta.split()) > 30:
        confianca += 0.1
    
    # Fator 2: Número de documentos encontrados
    if len(docs) >= 3:
        confianca += 0.2
    elif len(docs) >= 2:
        confianca += 0.1
    
    # Fator 3: Presença de palavras-chave da pergunta na resposta
    palavras_pergunta = set(pergunta.lower().split())
    palavras_resposta = set(resposta.lower().split())
    overlap = len(palavras_pergunta.intersection(palavras_resposta))
    if overlap > 2:
        confianca += 0.1
    
    # Fator 4: Indicadores de incerteza na resposta
    indicadores_incerteza = ["talvez", "pode ser", "não tenho certeza", "possivelmente"]
    if any(ind in resposta.lower() for ind in indicadores_incerteza):
        confianca -= 0.2
    
    return min(1.0, max(0.0, confianca))

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

def validar_e_corrigir_resposta(resposta: str, pergunta: str, docs: list) -> tuple[str, float]:
    """Valida e corrige a resposta do RAG - PRIORIZANDO MÁXIMA CONCISÃO"""
    resposta_original = resposta
    confianca_base = calcular_confianca_resposta(pergunta, resposta, docs)
    
    # Verificações de qualidade com foco em concisão
    problemas = []
    
    # 1. Resposta muito longa (MAIS RIGOROSO)
    palavras = len(resposta.split())
    if palavras > 150:  # Reduzido de 200 para 150
        problemas.append("resposta_muito_longa")
        confianca_base -= 0.2
        # Tentar encurtar drasticamente
        if docs:
            prompt_resumir = f"""
            Resuma em NO MÁXIMO 50 palavras, mantendo APENAS o essencial:
            
            Pergunta: {pergunta}
            Resposta: {resposta}
            
            Versão ultra-resumida (máximo 50 palavras):
            """
            try:
                resposta_resumida = llm_triagem.invoke([HumanMessage(content=prompt_resumir)])
                resposta_nova = resposta_resumida.content.strip()
                if len(resposta_nova.split()) < 80:  # Aceitar se ficar menor que 80 palavras
                    resposta = resposta_nova
                    confianca_base += 0.2  # Bonificar por encurtar
            except Exception:
                pass
    elif palavras > 100:  # Moderadamente longa
        problemas.append("resposta_longa")
        confianca_base -= 0.1
    elif palavras < 10:  # Muito curta
        problemas.append("resposta_muito_curta")
        confianca_base -= 0.15
    else:
        # Bonificar respostas concisas (10-100 palavras)
        confianca_base += 0.1
    
    # 2. Detectar introduções desnecessárias
    introducoes_ruins = [
        "olá", "como especialista", "posso te ajudar", "vou te explicar",
        "bem-vindo", "fico feliz", "é um prazer"
    ]
    inicio_resposta = resposta[:100].lower()
    if any(intro in inicio_resposta for intro in introducoes_ruins):
        problemas.append("introducao_desnecessaria")
        confianca_base -= 0.15
        # Tentar remover introdução
        linhas = resposta.split('\n')
        if len(linhas) > 1:
            # Pular primeira linha se for introdução
            resposta_sem_intro = '\n'.join(linhas[1:]).strip()
            if len(resposta_sem_intro) > 20:
                resposta = resposta_sem_intro
                confianca_base += 0.1
    
    # 3. Resposta genérica demais
    palavras_genericas = ["talvez", "pode ser", "geralmente", "normalmente", "às vezes"]
    if sum(1 for palavra in palavras_genericas if palavra in resposta.lower()) > 1:
        problemas.append("resposta_generica")
        confianca_base -= 0.1
    
    # Garantir confiança mínima e máxima
    confianca_final = max(0.0, min(1.0, confianca_base))
    
    return resposta, confianca_final

def gerar_resposta_sem_documentos(pergunta: str) -> str:
    """Gera uma resposta útil mas CONCISA mesmo sem documentos específicos"""
    
    prompt = f"""Você é um Integrador de dados da Carraro Desenvolvimento.

INSTRUÇÃO: Forneça uma resposta BREVE e TÉCNICA para a pergunta.

REGRAS:
- Máximo 2 parágrafos
- Linguagem técnica mas clara
- Vá direto ao ponto
- Evite rodeios e saudações

PERGUNTA: {pergunta}

Resposta técnica:"""
    
    resposta = llm_triagem.invoke([HumanMessage(content=prompt)])
    txt = (resposta.content or "").strip()
    
    # Adicionar disclaimer breve
    return f"{txt}\n\n💡 **Para detalhes específicos, consulte a documentação técnica.**"

def perguntar_politica_RAG(pergunta: str) -> dict:
    if not retriever:
        return {
            "answer": "Sistema de documentos não disponível no momento.",
            "citacoes": [],
            "contexto_encontrado": False,
            "confianca": 0.0,
            "estrategia_usada": "nenhuma"
        }

    # Estratégia 1: Busca semântica principal
    docs_relacionados = retriever.invoke(pergunta)
    estrategia = "similaridade_semantica"
    
    # Estratégia 2: SEMPRE tentar busca expandida com termos relacionados
    termos_expandidos = expandir_busca(pergunta)
    print(f"[DEBUG] Termos expandidos para '{pergunta}': {termos_expandidos}")
    
    for termo in termos_expandidos:
        docs_extra = retriever.invoke(termo)
        docs_relacionados.extend(docs_extra[:3])  # Aumentei para 3 docs por termo
        print(f"[DEBUG] Encontrados {len(docs_extra)} docs para termo '{termo}'")
    
    # Estratégia 3: Se poucos resultados, tentar busca por palavras-chave
    if len(docs_relacionados) < 3 and retriever_keywords:
        docs_keywords = retriever_keywords.invoke(pergunta)
        docs_relacionados.extend(docs_keywords)
        estrategia = "semantica_e_palavras_chave_expandida"
    else:
        estrategia = "busca_expandida"

    if not docs_relacionados:
        # Mesmo sem documentos específicos, tentar fornecer resposta útil
        resposta_generica = gerar_resposta_sem_documentos(pergunta)
        return {
            "answer": resposta_generica,
            "citacoes": [],
            "contexto_encontrado": False,
            "confianca": 0.4,  # Confiança moderada para respostas genéricas
            "estrategia_usada": "resposta_generica"
        }

    # Remover duplicatas e ordenar por relevância
    docs_unicos = remover_duplicatas_docs(docs_relacionados)
    print(f"[DEBUG] Total de documentos únicos encontrados: {len(docs_unicos)}")
    contexto = "\n\n".join(d.page_content for d in docs_unicos[:4])  # Limitar contexto
    
    # Prompt mais útil e CONCISO
    prompt = f"""Você é um Integrador de dados da Carraro Desenvolvimento.

INSTRUÇÕES IMPORTANTES:
- Use o contexto fornecido como base principal
- SEJA CONCISO E DIRETO - respostas de no máximo 2-3 parágrafos
- Vá direto ao ponto, sem rodeios
- Use linguagem técnica mas clara
- Evite introduções longas ("Olá! Como Especialista...")
- PARE quando der a informação principal - não detalhe demais
- FOQUE NO QUE O USUÁRIO REALMENTE QUER SABER

PERGUNTA: {pergunta}

CONTEXTO DISPONÍVEL:
{contexto}

Resposta técnica e direta:"""

    resposta = llm_triagem.invoke([HumanMessage(content=prompt)])
    txt = (resposta.content or "").strip()

    # Calcular confiança baseada no contexto encontrado
    confianca_inicial = calcular_confianca_resposta(pergunta, txt, docs_unicos)
    
    # Validar e potencialmente corrigir a resposta
    resposta_final, confianca_final = validar_e_corrigir_resposta(txt, pergunta, docs_unicos)
    
    if "não disponível" in resposta_final.lower() or "não sei" in resposta_final.lower() or confianca_final < 0.3:
        return {
            "answer": "Informação não encontrada nos documentos. Recomendo abrir um chamado para esclarecimentos específicos.",
            "citacoes": [],
            "contexto_encontrado": False,
            "confianca": confianca_final,
            "estrategia_usada": estrategia,
            "melhorada": False
        }

    return {
        "answer": resposta_final,
        "citacoes": criar_citacoes_melhoradas(docs_unicos),
        "contexto_encontrado": True,
        "confianca": confianca_final,
        "estrategia_usada": estrategia,
        "melhorada": resposta_final != txt  # Indica se foi melhorada
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
    confianca_geral: float
    historico_tentativas: list[str]
    categoria: str

def node_triagem(state: AgentState) -> AgentState:
    resultado_triagem = triagem(state["pergunta"])
    return {
        "triagem": resultado_triagem,
        "categoria": resultado_triagem.get("categoria", "GERAL"),
        "confianca_geral": resultado_triagem.get("confianca", 0.5),
        "historico_tentativas": ["triagem"]
    }

def node_auto_resolver(state: AgentState) -> AgentState:
    resposta_rag = perguntar_politica_RAG(state["pergunta"])
    
    # Combinar confiança da triagem com confiança do RAG
    confianca_triagem = state.get("confianca_geral", 0.5)
    confianca_rag = resposta_rag.get("confianca", 0.0)
    confianca_final = (confianca_triagem + confianca_rag) / 2
    
    update: AgentState = {
        "resposta": resposta_rag["answer"],
        "citacoes": resposta_rag.get("citacoes", []),
        "rag_sucesso": resposta_rag["contexto_encontrado"],
        "confianca_geral": confianca_final,
        "historico_tentativas": state.get("historico_tentativas", []) + ["auto_resolver"]
    }
    
    # Decisão mais inteligente baseada em confiança
    if resposta_rag["contexto_encontrado"] and confianca_final >= 0.6:
        update["acao_final"] = "AUTO_RESOLVER"
    elif resposta_rag["contexto_encontrado"] and confianca_final >= 0.4:
        # Resposta com baixa confiança - adicionar aviso
        update["resposta"] = f"⚠️ **Resposta com confiança moderada ({confianca_final:.1%})**\n\n{resposta_rag['answer']}\n\n*Recomenda-se confirmar esta informação abrindo um chamado se necessário.*"
        update["acao_final"] = "AUTO_RESOLVER"
    
    return update

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
    confianca = state.get("confianca_geral", 0.0)
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

def processar_pergunta(pergunta: str) -> dict:
    """
    Função principal melhorada para processar perguntas
    Retorna resposta estruturada com métricas de qualidade
    """
    try:
        if not pergunta.strip():
            return {
                "resposta": "Por favor, faça uma pergunta específica sobre políticas ou procedimentos da empresa.",
                "citacoes": [],
                "acao_final": "PEDIR_INFO",
                "confianca_geral": 0.0,
                "categoria": "GERAL",
                "melhorada": False,
                "feedback_id": None
            }
        
        # Executar o workflow
        resultado = grafo.invoke({"pergunta": pergunta.strip()})
        
        # Log da interação
        log_interacao(pergunta, resultado, resultado.get("acao_final", "ERRO"))
        
        # Enriquecer resposta com metadados
        resultado["timestamp"] = datetime.now().isoformat()
        resultado["qualidade_resposta"] = avaliar_qualidade_resposta(resultado)
        
        # Verificar se precisa de ajustes baseado em feedback histórico
        ajustes = verificar_ajustes_necessarios(pergunta, resultado)
        if ajustes:
            resultado["ajustes_aplicados"] = ajustes
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao processar pergunta: {e}")
        return {
            "resposta": "Ocorreu um erro interno. Por favor, tente novamente ou abra um chamado.",
            "citacoes": [],
            "acao_final": "ERRO",
            "confianca_geral": 0.0,
            "categoria": "ERRO",
            "erro": str(e),
            "melhorada": False,
            "feedback_id": None
        }

def verificar_ajustes_necessarios(pergunta: str, resultado: dict) -> list:
    """Verifica se são necessários ajustes baseado no histórico"""
    ajustes = []
    
    # Sistema de feedback removido - foco em resolver sempre que possível
    ajustes = []
    
    return ajustes

def avaliar_qualidade_resposta(resultado: dict) -> str:
    """Avalia a qualidade da resposta baseado em métricas"""
    confianca = resultado.get("confianca_geral", 0.0)
    tem_citacoes = len(resultado.get("citacoes", [])) > 0
    acao = resultado.get("acao_final", "")
    
    if acao == "AUTO_RESOLVER" and confianca >= 0.8 and tem_citacoes:
        return "EXCELENTE"
    elif acao == "AUTO_RESOLVER" and confianca >= 0.6:
        return "BOA"
    elif acao == "AUTO_RESOLVER" and confianca >= 0.4:
        return "MODERADA"
    elif acao == "AUTO_RESOLVER":
        return "BASICA"  # Resolveu mas com baixa confiança
    elif acao == "PEDIR_INFO":
        return "INFORMACAO_INSUFICIENTE"
    else:
        return "BAIXA"

# Função para compatibilidade com o app.py existente
def processar_mensagem(mensagem: str) -> dict:
    """Wrapper para compatibilidade com interface existente"""
    return processar_pergunta(mensagem)
