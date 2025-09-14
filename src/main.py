from pathlib import Path
from dotenv import load_dotenv
import os
import json
import pathlib
from typing import TypedDict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, START, END

# =========================
# Configurações
# =========================
load_dotenv()
api_key = os.getenv("API_KEY")

# Modelo Gemma
llm_triagem = ChatGoogleGenerativeAI(
    model="models/gemma-3-27b-it",
    temperature=0.0,
    api_key=api_key
)

TRIAGEM_PROMPT = (
    "Você é um triador de Service Desk para políticas internas da empresa Carraro Desenvolvimento. "
    "Dada a mensagem do usuário, retorne SOMENTE um JSON com:\n"
    "{\n"
    '  \"decisao\": \"AUTO_RESOLVER\" | \"PEDIR_INFO\" | \"ABRIR_CHAMADO\",\n'
    '  \"urgencia\": \"BAIXA\" | \"MEDIA\" | \"ALTA\",\n'
    '  \"campos_faltantes\": [\"...\"]\n'
    "}\n"
    "Regras:\n"
    "- **AUTO_RESOLVER**: Perguntas claras sobre regras ou procedimentos descritos nas políticas.\n"
    "- **PEDIR_INFO**: Mensagens vagas ou que faltam informações.\n"
    "- **ABRIR_CHAMADO**: Pedidos de exceção, liberação, aprovação ou acesso especial.\n"
    "Analise a mensagem e decida a ação mais apropriada."
)

def triagem(mensagem: str):
    prompt = f"{TRIAGEM_PROMPT}\n\nMensagem do usuário: {mensagem}"
    resposta = llm_triagem.invoke([HumanMessage(content=prompt)])
    conteudo = resposta.content.strip()

    if conteudo.startswith("```"):
        conteudo = conteudo.strip("`")
        if conteudo.lower().startswith("json"):
            conteudo = conteudo[4:].strip()
    
    try:
        return json.loads(conteudo)
    except json.JSONDecodeError:
        return {
            "erro": "Resposta não pôde ser convertida para JSON",
            "resposta_bruta": resposta.content
        }

# =========================
# RAG com proteção
# =========================
docs = []

# Caminho relativo para funcionar no deploy
pdf_path = Path("docs")  # coloque seus PDFs nesta pasta no repositório

if pdf_path.exists():
    for n in pdf_path.glob("*.pdf"):
        try:
            loader = PyMuPDFLoader(str(n))
            docs.extend(loader.load())
            print(f"Carregado com sucesso: {n.name}")
        except Exception as e:
            print(f"Erro ao carregar {n.name}: {e}")
else:
    print("⚠️ Pasta 'docs' não encontrada. Nenhum documento carregado.")

retriever = None
if docs:
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
    chunks = splitter.split_documents(docs)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=api_key
    )

    vectorstore = FAISS.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"score_threshold": 0.3, "k": 4}
    )

def perguntar_politica_RAG(pergunta: str) -> dict:
    if not retriever:
        return {"answer": "Nenhum documento carregado para consulta.",
                "citacoes": [],
                "contexto_encontrado": False}

    docs_relacionados = retriever.invoke(pergunta)

    if not docs_relacionados:
        return {"answer": "Não sei.",
                "citacoes": [],
                "contexto_encontrado": False}

    contexto = "\n\n".join(d.page_content for d in docs_relacionados)

    prompt = (
        "Você é um Assistente de Políticas Internas (RH/IT) da empresa Carraro Desenvolvimento.\n"
        "Responda SOMENTE com base no contexto fornecido.\n"
        "Se não houver base suficiente, responda apenas 'Não sei'.\n\n"
        f"Pergunta: {pergunta}\n\n"
        f"Contexto:\n{contexto}"
    )

    resposta = llm_triagem.invoke([HumanMessage(content=prompt)])
    txt = (resposta.content or "").strip()

    if txt.rstrip(".!?") == "Não sei":
        return {"answer": "Não sei.",
                "citacoes": [],
                "contexto_encontrado": False}

    return {"answer": txt,
            "citacoes": [{"documento": pathlib.Path(d.metadata.get("source","")).name,
                          "pagina": int(d.metadata.get("page", 0)) + 1,
                          "trecho": d.page_content[:300]} for d in docs_relacionados],
            "contexto_encontrado": True}

# =========================
# Fluxo de decisão
# =========================
class AgentState(TypedDict, total=False):
    pergunta: str
    triagem: dict
    resposta: Optional[str]
    citacoes: list[dict]
    rag_sucesso: bool
    acao_final: str

def node_triagem(state: AgentState) -> AgentState:
    return {"triagem": triagem(state["pergunta"])}

def node_auto_resolver(state: AgentState) -> AgentState:
    resposta_rag = perguntar_politica_RAG(state["pergunta"])
    update: AgentState = {
        "resposta": resposta_rag["answer"],
        "citacoes": resposta_rag.get("citacoes", []),
        "rag_sucesso": resposta_rag["contexto_encontrado"],
    }
    if resposta_rag["contexto_encontrado"]:
        update["acao_final"] = "AUTO_RESOLVER"
    return update

def node_pedir_info(state: AgentState) -> AgentState:
    faltantes = state["triagem"].get("campos_faltantes", [])
    detalhe = ",".join(faltantes) if faltantes else "Tema e contexto específico"
    return {
        "resposta": f"Para avançar, preciso que detalhe: {detalhe}",
        "citacoes": [],
        "acao_final": "PEDIR_INFO"
    }

def node_abrir_chamado(state: AgentState) -> AgentState:
    triagem_data = state["triagem"]
    return {
        "resposta": f"Abrindo chamado com urgência {triagem_data['urgencia']}. Descrição: {state['pergunta'][:140]}",
        "citacoes": [],
        "acao_final": "ABRIR_CHAMADO"
    }

KEYWORDS_ABRIR_TICKET = ["aprovação", "exceção", "liberação", "abrir ticket", "abrir chamado", "acesso especial"]

def decidir_pos_triagem(state: AgentState) -> str:
    decisao = state["triagem"]["decisao"]
    if decisao == "AUTO_RESOLVER": return "auto"
    if decisao == "PEDIR_INFO": return "info"
    if decisao == "ABRIR_CHAMADO": return "chamado"

def decidir_pos_auto_resolver(state: AgentState) -> str:
    if state.get("rag_sucesso"):
        return "ok"
    state_da_pergunta = (state["pergunta"] or "").lower()
    if any(k in state_da_pergunta for k in KEYWORDS_ABRIR_TICKET):
        return "chamado"
    return "info"

workflow = StateGraph(AgentState)
workflow.add_node("triagem", node_triagem)
workflow.add_node("auto_resolver", node_auto_resolver)
workflow.add_node("pedir_info", node_pedir_info)
workflow.add_node("abrir_chamado", node_abrir_chamado)

workflow.add_edge(START, "triagem")
workflow.add_conditional_edges("triagem", decidir_pos_triagem, {
    "auto": "auto_resolver",
    "info": "pedir_info",
    "chamado": "abrir_chamado"
})
workflow.add_conditional_edges("auto_resolver", decidir_pos_auto_resolver, {
    "info": "pedir_info",
    "chamado": "abrir_chamado",
    "ok": END
})
workflow.add_edge("pedir_info", END)
workflow.add_edge("abrir_chamado", END)

grafo = workflow.compile()
