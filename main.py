import os
import pathlib
import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import TypedDict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, START, END

try:
    import streamlit as st
except ImportError:
    st = None
from dotenv import load_dotenv

# Função utilitária para instanciar o LLM
def get_llm():
    return ChatGoogleGenerativeAI(
        model="models/gemma-3-27b-it",
        google_api_key=os.getenv("API_KEY"),
        temperature=0.1,
        convert_system_message_to_human=True
    )

# Função stub para logar interações
def log_interacao(pergunta, resultado, acao_final):
    # Aqui você pode integrar com um sistema de log real, banco ou arquivo
    logger.info(f"[LOG_INTERACAO] Pergunta: {pergunta} | Ação: {acao_final} | Resposta: {str(resultado)[:120]}")


# Setup de logging e variáveis globais
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()
api_key = os.getenv("API_KEY")

# =========================
# RAG Avançado com múltiplas estratégias
# =========================
docs = []
retriever = None
retriever_keywords = None

# Cache de carregamento de documentos
if st:
    @st.cache_data(show_spinner=False)
    def carregar_docs_cache():
        docs = []
        docs_path = Path("docs")
        if docs_path.exists():
            for n in docs_path.glob("*.pdf"):
                try:
                    loader = PyMuPDFLoader(str(n))
                    doc_pages = loader.load()
                    for page in doc_pages:
                        page.metadata.update({
                            "filename": n.name,
                            "file_size": n.stat().st_size,
                            "content_type": "pdf_document"
                        })
                    docs.extend(doc_pages)
                except Exception as e:
                    print(f"[ERRO] Erro ao carregar PDF {n.name}: {e}")
            for n in docs_path.glob("*.md"):
                try:
                    with open(n, 'r', encoding='utf-8') as f:
                        content = f.read()
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
                except Exception as e:
                    print(f"[ERRO] Erro ao carregar Markdown {n.name}: {e}")
        return docs

    @st.cache_resource(show_spinner=False)
    def carregar_embeddings_cache(docs, api_key):
        if not docs or not api_key:
            return None, None
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""]
        )
        chunks = splitter.split_documents(docs)
        try:
            embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemma-3-27b-it",
                google_api_key=api_key
            )
            vectorstore = FAISS.from_documents(chunks, embeddings)
            retriever = vectorstore.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"score_threshold": 0.15, "k": 8}
            )
            retriever_keywords = vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={"k": 4, "fetch_k": 10}
            )
            return retriever, retriever_keywords
        except Exception as e:
            print(f"[AVISO] Erro ao inicializar embeddings: {e}")
            print(f"[INFO] Sistema entrará em modo fallback com busca textual")
            return None, None

    def carregar_documentos():
        global docs, retriever, retriever_keywords, api_key
        docs = carregar_docs_cache()
        retriever, retriever_keywords = carregar_embeddings_cache(docs, api_key)
else:
    def carregar_documentos():
        global docs, retriever, retriever_keywords, api_key
        docs = []
        docs_path = Path("docs")
        if docs_path.exists():
            for n in docs_path.glob("*.pdf"):
                try:
                    loader = PyMuPDFLoader(str(n))
                    doc_pages = loader.load()
                    for page in doc_pages:
                        page.metadata.update({
                            "filename": n.name,
                            "file_size": n.stat().st_size,
                            "content_type": "pdf_document"
                        })
                    docs.extend(doc_pages)
                except Exception as e:
                    print(f"[ERRO] Erro ao carregar PDF {n.name}: {e}")
            for n in docs_path.glob("*.md"):
                try:
                    with open(n, 'r', encoding='utf-8') as f:
                        content = f.read()
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
                except Exception as e:
                    print(f"[ERRO] Erro ao carregar Markdown {n.name}: {e}")
        retriever = None
        retriever_keywords = None
        if docs:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=100,
                separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""]
            )
            chunks = splitter.split_documents(docs)
            if api_key:
                try:
                    embeddings = GoogleGenerativeAIEmbeddings(
                        model="models/gemma-3-27b-it",
                        google_api_key=api_key
                    )
                    vectorstore = FAISS.from_documents(chunks, embeddings)
                    retriever = vectorstore.as_retriever(
                        search_type="similarity_score_threshold",
                        search_kwargs={"score_threshold": 0.15, "k": 8}
                    )
                    retriever_keywords = vectorstore.as_retriever(
                        search_type="mmr",
                        search_kwargs={"k": 4, "fetch_k": 10}
                    )
                except Exception as e:
                    print(f"[AVISO] Erro ao inicializar embeddings: {e}")
                    print(f"[INFO] Sistema entrará em modo fallback com busca textual")
                    retriever = None
                    retriever_keywords = None
            else:
                print("[AVISO] API_KEY não encontrada. Funcionalidades RAG não estarão disponíveis.")
                retriever = None
                retriever_keywords = None


# Só carrega documentos se rodar como script principal
if __name__ == "__main__":
    carregar_documentos()

def detectar_categoria_inteligente(pergunta: str) -> str:
    """Detecta categoria baseada em análise mais sofisticada"""
    pergunta_lower = pergunta.lower()
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



# =========================
# Sistema de busca textual alternativo (quando embeddings não estão disponíveis)
# =========================

def buscar_texto_simples(pergunta: str, docs_list: list) -> list:
    """Busca textual simples quando embeddings não estão disponíveis"""
    if not docs_list:
        return []
    
    pergunta_lower = pergunta.lower()
    palavras_busca = pergunta_lower.split()
    
    # Palavras-chave específicas para melhorar a busca
    palavras_expandidas = []
    for palavra in palavras_busca:
        palavras_expandidas.append(palavra)
        # Adicionar variações comuns
        if "aplicinsumo" in palavra:
            palavras_expandidas.extend(["insumo", "agric", "aplicação"])
        elif "int." in palavra:
            palavras_expandidas.extend(["procedure", "função", "sp_"])
        elif "origem" in palavra:
            palavras_expandidas.extend(["fonte", "erp", "sistema", "dados"])
    
    docs_relevantes = []
    for doc in docs_list:
        conteudo_lower = doc.page_content.lower()
        score = 0
        
        # Pontuar baseado em matches de palavras
        for palavra in palavras_expandidas:
            if palavra in conteudo_lower:
                score += conteudo_lower.count(palavra)
        
        # Bonus para matches exatos de frases importantes
        if "int.int_aplicinsumoagric" in conteudo_lower and ("aplicinsumo" in pergunta_lower or "int." in pergunta_lower):
            score += 10
        
        if score > 0:
            docs_relevantes.append((doc, score))
    
    # Ordenar por relevância e retornar os melhores
    docs_relevantes.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, score in docs_relevantes[:6]]  # Top 6 documentos


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
            logger.warning("[RAG] Retriever não disponível - tentando busca textual")
            if docs:  # Se temos documentos carregados, usar busca textual
                docs_relacionados = buscar_texto_simples(pergunta, docs)
                estrategia = "busca_textual_simples"
                logger.info(f"[RAG] Busca textual encontrou {len(docs_relacionados)} documentos")
            else:
                logger.warning("[RAG] Nenhum documento disponível")
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
        prompt = f"""🧠 Prompt: “Desenvolvedor ETL Agroindustrial (usinas de cana-de-açúcar)”
                        Você deve simular um desenvolvedor ETL pleno/sênior especializado em integração de dados entre sistemas ERP e bancos relacionais, com forte atuação no setor agroindustrial, especialmente em usinas de cana-de-açúcar.
                        Seu papel é projetar, otimizar e automatizar fluxos de dados complexos, garantindo qualidade, performance e rastreabilidade das informações.
                        🧩 Contexto do domínio
                        Você trabalha com dados de produção agrícola, insumos, operações mecanizadas, colheita, transporte, industrialização e manutenção de equipamentos agrícolas.
                        Os dados vêm de diversos ERPs e sistemas satélites (TOTVS, SAP, PIMS, Solinftec, Trimble, JDLink, entre outros) e precisam ser integrados em um Data Warehouse corporativo para análises de produtividade e custos.
                        💻 Stack técnica principal
                        SQL Server (T-SQL): desenvolvimento de procedures, funções, views, staging e transformação de dados.
                        Python + Apache Airflow: orquestração, agendamento e monitoramento de pipelines ETL/ELT.
                        APIs REST e SOAP: consumo e integração de dados externos (ERP, sensores, sistemas agrícolas).
                        Arquivos CSV, XML, JSON, Excel: tratamento e padronização de dados.
                        Controle de versionamento (Git) e boas práticas DevOps para pipelines de dados.
                        🧰 Diretrizes de comportamento
                        Sempre explique a lógica do fluxo de dados antes de apresentar o código.
                        Use boas práticas de engenharia de dados (tratamento de nulos, logs, idempotência, versionamento).
                        Respeite padrões de nomeação corporativa (ex: STG_, DW_, DIM_, FAT_, SP_).
                        Assegure que os processos sejam escaláveis, auditáveis e reexecutáveis.
                        Utilize comentários claros no código para fácil manutenção.
                        Sempre valide a consistência das chaves (PK/FK) e integridade referencial dos dados transformados.
                        Quando sugerir código, use sintaxe realista e pronta para execução (sem placeholders genéricos, a menos que explicitamente necessário).
                        🧾 Exemplos de entregas esperadas
                        Scripts T-SQL para criação de pipelines de integração entre sistemas agrícolas e ERP.
                        DAGs do Airflow para orquestrar extração e carga diária dos dados de produção.
                        Scripts Python para consumir APIs de sensores de campo e salvar no Data Lake.
                        Modelos de staging e DW para consolidar dados de colheita e custo operacional.
                        Estratégias para controle de incremental load, logs e retry de jobs.
                        🎯 Objetivo final
                        Atuar como especialista de integração de dados do agronegócio, com foco em eficiência, automação e qualidade das informações que alimentam painéis e relatórios estratégicos da usina.

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
    resposta: Optional[str]
    citacoes: list[dict]
    rag_sucesso: bool
    acao_final: str
    historico_tentativas: list[str]
    categoria: str



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
workflow.add_node("auto_resolver", node_auto_resolver)
workflow.add_node("pedir_info", node_pedir_info)
workflow.add_edge(START, "auto_resolver")
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
        
        # Garantir que o LLM está devidamente inicializado
        try:
            get_llm()
        except Exception as e:
            logger.error(f"Erro ao inicializar LLM: {e}")
            # Apenas loga o erro, não tenta resetar LLM (função removida)
        
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
        
        # Verificar se o retriever está inicializado - MODO FALLBACK SE NECESSÁRIO
        if retriever is None:
            logger.warning("Sistema de embeddings não disponível - usando modo inteligente")
            # Em vez de fallback básico, tentar busca textual se temos documentos
            if docs:
                logger.info("Tentando busca textual nos documentos carregados")
                return processar_pergunta_com_busca_textual(pergunta, historico_conversa)
            else:
                logger.warning("Nenhum documento disponível - usando modo fallback básico")
                return processar_pergunta_fallback(pergunta, historico_conversa)
        
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

def processar_pergunta_com_busca_textual(pergunta: str, historico_conversa: list = None) -> dict:
    """
    Processamento usando busca textual quando embeddings não estão disponíveis
    """
    try:
        logger.info(f"[BUSCA_TEXTUAL] Processando pergunta: {pergunta}")
        
        # Buscar documentos relevantes por texto
        docs_relacionados = buscar_texto_simples(pergunta, docs)
        
        if not docs_relacionados:
            logger.warning("[BUSCA_TEXTUAL] Nenhum documento relevante encontrado")
            return processar_pergunta_fallback(pergunta, historico_conversa)
        
        logger.info(f"[BUSCA_TEXTUAL] Encontrados {len(docs_relacionados)} documentos relevantes")
        
        # Criar contexto com os documentos encontrados
        contexto = "\n\n".join(d.page_content for d in docs_relacionados[:4])
        
        # Prompt específico para busca textual
        prompt = f"""🧠 Prompt: "Desenvolvedor ETL Agroindustrial (usinas de cana-de-açúcar)"
Você deve simular um desenvolvedor ETL pleno/sênior especializado em integração de dados entre sistemas ERP e bancos relacionais, com forte atuação no setor agroindustrial, especialmente em usinas de cana-de-açúcar.

💻 Contexto: Sistema de embeddings indisponível - usando busca textual nos documentos.

INSTRUÇÕES IMPORTANTES:
- Use o contexto fornecido como base principal
- SEJA CONCISO E DIRETO - respostas de no máximo 2-3 parágrafos
- Use linguagem técnica mas clara
- Evite introduções longas
- FOQUE NO QUE O USUÁRIO REALMENTE QUER SABER

PERGUNTA: {pergunta}

CONTEXTO DISPONÍVEL:
{contexto}

Resposta técnica e direta:"""

        resposta = get_llm().invoke([HumanMessage(content=prompt)])
        resposta_texto = (resposta.content or "").strip()
        
        # Validar e corrigir resposta
        resposta_final = validar_e_corrigir_resposta(resposta_texto, pergunta, docs_relacionados)
        
        # Adicionar disclaimer sobre busca textual
        resposta_final += "\n\n🔍 **Nota:** Busca realizada por texto (sistema de embeddings temporariamente indisponível)."
        
        return {
            "resposta": resposta_final,
            "citacoes": criar_citacoes_melhoradas(docs_relacionados),
            "acao_final": "AUTO_RESOLVER",
            "categoria": "GERAL",
            "melhorada": resposta_final != resposta_texto,
            "feedback_id": None,
            "modo": "BUSCA_TEXTUAL",
            "timestamp": datetime.now().isoformat(),
            "contexto_encontrado": True
        }
        
    except Exception as e:
        logger.error(f"[BUSCA_TEXTUAL] Erro: {type(e).__name__}: {str(e)}")
        return processar_pergunta_fallback(pergunta, historico_conversa)

def processar_pergunta_fallback(pergunta: str, historico_conversa: list = None) -> dict:
    """
    Função fallback quando o sistema RAG não está disponível (cota de embeddings excedida)
    Usa apenas o LLM diretamente com conhecimento básico
    """
    try:
        logger.info(f"[FALLBACK] Processando pergunta sem RAG: {pergunta}")
        
        # Prompt básico para responder sem documentos específicos
        prompt_fallback = f"""🧠 PERSONA: Desenvolvedor ETL Agroindustrial Sênior (Usinas de Cana-de-Açúcar)

Você é um especialista ETL com conhecimento em integração de dados no setor sucroenergético.

⚠️ MODO LIMITADO: Cota de embeddings excedida - sistema funcionando com conhecimento base.

🎯 INSTRUÇÃO: Responda com base no seu conhecimento técnico sobre:
• Procedures SQL para integração de dados agrícolas (especialmente INT.SP_AT_INT_APLICINSUMOAGRIC)
• Sistemas ERP (TOTVS, SAP) e integração de dados
• Aplicação de insumos agrícolas e controle de produção
• Padrões de ETL no agronegócio

📋 REGRAS:
• SEJA DIRETO - máximo 2 parágrafos
• Use termos técnicos seguidos de explicação simples
• Se não souber detalhes específicos, seja honesto
• Foque no que o usuário realmente quer saber

PERGUNTA: {pergunta}

Resposta técnica (baseada em conhecimento geral):"""

        resposta = get_llm().invoke([HumanMessage(content=prompt_fallback)])
        resposta_texto = (resposta.content or "").strip()
        
        resposta_final = resposta_texto
        
        return {
            "resposta": resposta_final,
            "citacoes": [],
            "acao_final": "AUTO_RESOLVER",
            "categoria": "GERAL",
            "melhorada": False,
            "feedback_id": None,
            "modo": "FALLBACK",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[FALLBACK] Erro: {type(e).__name__}: {str(e)}")
        return {
            "resposta": f"Sistema temporariamente indisponível. Erro: {str(e)}",
            "citacoes": [],
            "acao_final": "ERRO",
            "categoria": "ERRO",
            "erro": f"Fallback error: {str(e)}",
            "melhorada": False,
            "feedback_id": None,
            "modo": "FALLBACK_ERROR"
        }

# Função para compatibilidade com o app.py existente
def processar_mensagem(mensagem: str, historico_conversa: list = None) -> dict:
    """Wrapper para compatibilidade com interface existente"""
    return processar_pergunta(mensagem, historico_conversa)
