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

# Prompt de triagem
TRIAGEM_PROMPT = (
    "Você é um triador de Service Desk para políticas internas da empresa Carraro Desenvolvimento. "
    "Dada a mensagem do usuário, retorne SOMENTE um JSON com:\n"
    "{\n"
    '  "decisao": "AUTO_RESOLVER" | "PEDIR_INFO" | "ABRIR_CHAMADO",\n'
    '  "urgencia": "BAIXA" | "MEDIA" | "ALTA",\n'
    '  "campos_faltantes": ["..."]\n'
    "}\n"
    "Regras:\n"
    '- **AUTO_RESOLVER**: Perguntas claras sobre regras ou procedimentos descritos nas políticas.\n'
    '- **PEDIR_INFO**: Mensagens vagas ou que faltam informações.\n'
    '- **ABRIR_CHAMADO**: Pedidos de exceção, liberação, aprovação ou acesso especial.\n'
    "Analise a mensagem e decida a ação mais apropriada."
)

# Função de triagem com parsing robusto
def triagem(mensagem: str):
    prompt = f"{TRIAGEM_PROMPT}\n\nMensagem do usuário: {mensagem}"
    resposta = llm_triagem.invoke([HumanMessage(content=prompt)])
    conteudo = resposta.content.strip()

    # remove blocos de markdown ```json ... ```
    if conteudo.startswith("```"):
        conteudo = conteudo.strip("`")  # remove crases
        # corta a tag "json" se existir
        if conteudo.lower().startswith("json"):
            conteudo = conteudo[4:].strip()
    
    try:
        return json.loads(conteudo)  # tenta converter em JSON
    except json.JSONDecodeError:
        return {
            "erro": "Resposta não pôde ser convertida para JSON",
            "resposta_bruta": resposta.content
        }

# Testes
testes = [
    "Posso reembolsar a internet?",
    "Quero mais 5 dias de trabalho remoto. Como faço?",
    "Posso reembolsar cursos ou treinamentos da Alura?",
    "Quantas capivaras tem no Rio Pinheiros?"
]

for msg_teste in testes:
    print(f"Pergunta: {msg_teste}\n -> Resposta: {triagem(msg_teste)}\n")

docs = []

pdf_path = Path(r"C:\Users\Microsoft\Documents\Imersao IA")

# listar arquivos encontrados
print("Arquivos encontrados na pasta:")
for f in pdf_path.glob("*"):
    print("-", f.name)

# carregar PDFs
for n in pdf_path.glob("*.pdf"):  # ou pdf_path.rglob("*.pdf") se tiver subpastas
    try:
        loader = PyMuPDFLoader(str(n))
        docs.extend(loader.load())
        print(f"Carregado com sucesso: {n.name}")
    except Exception as e:
        print(f"Erro ao carregar {n.name}: {e}")

print(f"Total de documentos carregados: {len(docs)}")

#Cortar documentos em pedaços menores de 300 caracteres com sobreposição de 30 caracteres

splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)

chunks = splitter.split_documents(docs)

for chunk in chunks:
    print(chunk)
    print("------------------------------------")

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=api_key
)

vectorstore = FAISS.from_documents(chunks, embeddings)

retriever = vectorstore.as_retriever(search_type="similarity_score_threshold",
                                     search_kwargs={"score_threshold":0.3, "k": 4})

prompt_rag = ChatPromptTemplate.from_messages([
    ("system",
     "Você é um Assistente de Políticas Internas (RH/IT) da empresa Carraro Desenvolvimento. "
     "Responda SOMENTE com base no contexto fornecido. "
     "Se não houver base suficiente, responda apenas 'Não sei'."),

    ("human", "Pergunta: {input}\n\nContexto:\n{context}")
])

document_chain = create_stuff_documents_chain(llm_triagem, prompt_rag)

