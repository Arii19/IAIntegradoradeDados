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
                resposta_resumida = llm_triagem.invoke([HumanMessage(content=prompt_resumir)])
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
            "estrategia_usada": "resposta_generica"
        }

    # Remover duplicatas e ordenar por relevância
    docs_unicos = remover_duplicatas_docs(docs_relacionados)
    print(f"[DEBUG] Total de documentos únicos encontrados: {len(docs_unicos)}")
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

    resposta = llm_triagem.invoke([HumanMessage(content=prompt)])
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

    return {
        "answer": resposta_final,
        "citacoes": criar_citacoes_melhoradas(docs_unicos),
        "contexto_encontrado": True,
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
    resposta_rag = perguntar_politica_RAG(state["pergunta"])
    
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

def processar_pergunta(pergunta: str, historico_conversa: list = None) -> dict:
    """
    Função principal melhorada para processar perguntas
    Retorna resposta estruturada
    """
    try:
        if not pergunta.strip():
            return {
                "resposta": "Por favor, faça uma pergunta específica sobre procedimentos da integração.",
                "citacoes": [],
                "acao_final": "PEDIR_INFO",
                "categoria": "GERAL",
                "melhorada": False,
                "feedback_id": None
            }
        
        # Analisar contexto do histórico para perguntas vagas
        pergunta_contextualizada = analisar_contexto_historico(pergunta, historico_conversa)
        
        # Executar o workflow
        resultado = grafo.invoke({"pergunta": pergunta_contextualizada})
        
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
        logger.error(f"Erro ao processar pergunta: {e}")
        return {
            "resposta": "Ocorreu um erro interno. Por favor, tente novamente ou contate o suporte.",
            "citacoes": [],
            "acao_final": "ERRO",
            "categoria": "ERRO",
            "erro": str(e),
            "melhorada": False,
            "feedback_id": None
        }

def analisar_contexto_historico(pergunta: str, historico_conversa: list = None) -> str:
    """Analisa o contexto do histórico para enriquecer perguntas vagas"""
    if not historico_conversa or len(historico_conversa) == 0:
        return pergunta
    
    pergunta_lower = pergunta.lower().strip()
    
    # Detectar perguntas que fazem referência ao contexto anterior
    referencias_contexto = [
        "origem dos dados", "origem", "onde vem", "fonte", 
        "qual a origem", "de onde vem", "procedência",
        "como é feito", "como funciona", "processo",
        "mais detalhes", "especificamente", "detalhe"
    ]
    
    # Palavras que indicam referência à conversa anterior
    referencias_anteriores = [
        "dessa", "desse", "desta", "deste", "nisso", "isso",
        "anterior", "que falamos", "mencionado", "citado"
    ]
    
    tem_referencia_contexto = any(ref in pergunta_lower for ref in referencias_contexto)
    tem_referencia_anterior = any(ref in pergunta_lower for ref in referencias_anteriores)
    
    # Se a pergunta é vaga mas tem referência ao contexto ou à conversa anterior
    if (tem_referencia_contexto or tem_referencia_anterior or len(pergunta.split()) <= 6):
        # Pegar a última mensagem que teve sucesso (resposta técnica)
        ultima_resposta_tecnica = None
        ultimo_assunto = None
        
        for item in reversed(historico_conversa[-3:]):  # Últimas 3 mensagens
            if item.get("acao") == "AUTO_RESOLVER" and item.get("citacoes"):
                ultima_resposta_tecnica = item.get("resposta", "")
                ultimo_assunto = item.get("pergunta", "")
                break
        
        if ultima_resposta_tecnica and ultimo_assunto:
            # Extrair palavras-chave técnicas da conversa anterior
            palavras_chave_anteriores = extrair_palavras_chave_tecnicas(ultimo_assunto, ultima_resposta_tecnica)
            
            # Contextualizar a pergunta atual
            if palavras_chave_anteriores:
                pergunta_contextualizada = f"{pergunta} (contexto: {ultimo_assunto[:100]}... - palavras-chave: {', '.join(palavras_chave_anteriores[:3])})"
                logger.info(f"Pergunta contextualizada: {pergunta} -> {pergunta_contextualizada}")
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
