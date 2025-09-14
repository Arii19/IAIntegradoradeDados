from dotenv import load_dotenv
import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
import re, pathlib
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END
from IPython.display import display, Image


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

# Prompt de triagem (apenas texto, sem "system")
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

# Função de triagem
def triagem(mensagem: str):
    prompt = f"{TRIAGEM_PROMPT}\n\nMensagem do usuário: {mensagem}"
    resposta = llm_triagem.invoke([HumanMessage(content=prompt)])
    conteudo = resposta.content.strip()

    # remove blocos de markdown ```json ... ```
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
# RAG
# =========================

docs = []

pdf_path = Path(r"C:\Users\Microsoft\Documents\Imersao IA")

for n in pdf_path.glob("*.pdf"):
    try:
        loader = PyMuPDFLoader(str(n))
        docs.extend(loader.load())
        print(f"Carregado com sucesso: {n.name}")
    except Exception as e:
        print(f"Erro ao carregar {n.name}: {e}")

splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
chunks = splitter.split_documents(docs)

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=api_key
)

vectorstore = FAISS.from_documents(chunks, embeddings)
retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold":0.3, "k": 4}
)

# Agora o prompt do RAG também vai inteiro no HumanMessage
def perguntar_politica_RAG(pergunta: str) -> dict:
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
# Testes
# =========================
testes = [
    "Posso reembolsar a internet?",
    "Quero mais 5 dias de trabalho remoto. Como faço?",
    "Posso reembolsar cursos ou treinamentos da Alura?",
    "Quantas capivaras tem no Rio Pinheiros?"
]

for msg_teste in testes:
    print(f"Pergunta: {msg_teste}\n -> Resposta: {triagem(msg_teste)}\n")

for msg_teste in testes:
    resposta = perguntar_politica_RAG(msg_teste)
    print(f"PERGUNTA: {msg_teste}")
    print(f"RESPOSTA: {resposta['answer']}")
    if resposta['contexto_encontrado']:
        print("CITAÇÕES:")
        for c in resposta['citacoes']:
            print(f" - Documento: {c['documento']}, Página: {c['pagina']}")
            print(f"   Trecho: {c['trecho']}")
        print("------------------------------------")

class AgentState(TypedDict, total = False):
    pergunta: str
    triagem: dict
    resposta: Optional[str]
    citacoes: list[dict]
    rag_sucesso: bool
    acao_final: str

def node_triagem(state: AgentState) -> AgentState:
    print("Executando nó de triagem...")
    return {"triagem": triagem(state["pergunta"])}

def node_auto_resolver(state: AgentState) -> AgentState:
    print("Executando nó de auto_resolver...")
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
    print("Executando nó de pedir_info...")
    faltantes = state["triagem"].get("campos_faltantes", [])
    if faltantes:
        detalhe = ",".join(faltantes)
    else:
        detalhe = "Tema e contexto específico"

    return {
        "resposta": f"Para avançar, preciso que detalhe: {detalhe}",
        "citacoes": [],
        "acao_final": "PEDIR_INFO"
    }

def node_abrir_chamado(state: AgentState) -> AgentState:
    print("Executando nó de abrir_chamado...")
    triagem = state["triagem"]

    return {
        "resposta": f"Abrindo chamado com urgência {triagem['urgencia']}. Descrição: {state['pergunta'][:140]}",
        "citacoes": [],
        "acao_final": "ABRIR_CHAMADO"
    }

KEYWORDS_ABRIR_TICKET = ["aprovação", "exceção", "liberação", "abrir ticket", "abrir chamado", "acesso especial"]

def decidir_pos_triagem(state: AgentState) -> str:
    print("Decidindo após a triagem...")
    decisao = state["triagem"]["decisao"]

    if decisao == "AUTO_RESOLVER": return "auto"
    if decisao == "PEDIR_INFO": return "info"
    if decisao == "ABRIR_CHAMADO": return "chamado"

def decidir_pos_auto_resolver(state: AgentState) -> str:
    print("Decidindo após o auto_resolver...")

    if state.get("rag_sucesso"):
        print("Rag com sucesso, finalizando o fluxo.")
        return "ok"

    state_da_pergunta = (state["pergunta"] or "").lower()

    if any(k in state_da_pergunta for k in KEYWORDS_ABRIR_TICKET):
        print("Rag falhou, mas foram encontradas keywords de abertura de ticket. Abrindo...")
        return "chamado"

    print("Rag falhou, sem keywords, vou pedir mais informações...")
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

graph_bytes = grafo.get_graph().draw_mermaid_png()
display(Image(graph_bytes))


testes = ["Posso reembolsar a internet?",
          "Quero mais 5 dias de trabalho remoto. Como faço?",
          "Posso reembolsar cursos ou treinamentos da Alura?",
          "É possível reembolsar certificações do Google Cloud?",
          "Posso obter o Google Gemini de graça?",
          "Qual é a palavra-chave da aula de hoje?",
          "Quantas capivaras tem no Rio Pinheiros?"]

for msg_test in testes:
    resposta_final = grafo.invoke({"pergunta": msg_test})

    triag = resposta_final.get("triagem", {})
    print(f"PERGUNTA: {msg_test}")
    print(f"DECISÃO: {triag.get('decisao')} | URGÊNCIA: {triag.get('urgencia')} | AÇÃO FINAL: {resposta_final.get('acao_final')}")
    print(f"RESPOSTA: {resposta_final.get('resposta')}")
    if resposta_final.get("citacoes"):
        print("CITAÇÕES:")
        for citacao in resposta_final.get("citacoes"):
            print(f" - Documento: {citacao['documento']}, Página: {citacao['pagina']}")
            print(f"   Trecho: {citacao['trecho']}")

    print("------------------------------------")