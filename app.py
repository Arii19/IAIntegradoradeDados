
import streamlit as st
from dotenv import load_dotenv
from main import processar_pergunta
from pathlib import Path
import json
from datetime import datetime
import unicodedata
import re
from db_sqlalchemy import ChatHistory, salvar_chat,buscar_historico
from db_sqlalchemy import criar_tabelas

    # Garante que a tabela do banco será criada se não existir
criar_tabelas()
def sanitize_text(text):
    """Remove ou substitui caracteres problemáticos para Windows/Streamlit"""
    if not text:
        return ""
    
    # Normalizar unicode e remover acentos
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    
    # Substituir caracteres problemáticos
    replacements = {
        'ç': 'c', 'Ç': 'C',
        'ã': 'a', 'Ã': 'A',
        'á': 'a', 'Á': 'A',
        'à': 'a', 'À': 'A',
        'â': 'a', 'Â': 'A',
        'é': 'e', 'É': 'E',
        'ê': 'e', 'Ê': 'E',
        'í': 'i', 'Í': 'I',
        'ó': 'o', 'Ó': 'O',
        'ô': 'o', 'Ô': 'O',
        'õ': 'o', 'Õ': 'O',
        'ú': 'u', 'Ú': 'U',
        'ü': 'u', 'Ü': 'U',
        '`': "'",
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '–': '-',
        '—': '-',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Manter apenas caracteres ASCII seguros + alguns extras
    text = re.sub(r'[^\x00-\x7F\n\r\t]', '', text)
    
    return text

load_dotenv()
st.set_page_config(
    page_title="Integrador de Dados", 
    layout="wide",
    initial_sidebar_state="expanded",
)

#         <h3>🔗 Integrador de Dados </h3>SS customizado para o layout
st.markdown("""
<style>
    /* Customização da sidebar */
    .css-1d391kg {
        background-color: #1e1e2e;
    }
    
    /* Estilo da área principal */
    .main {
        background-color: #0f0f23;
        color: white;
    }
    
    /* Estilo para as mensagens do chat */
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        display: flex;
        align-items: flex-start;
    }
    
    .user-message {
        background: linear-gradient(135deg, #6b7c6e 0%, #5a8d8a 100%);
        margin-left: 20%;
        color: white;
    }
    
    .assistant-message {
        background: linear-gradient(135deg, #7d8a7f 0%, #4a6962 100%);
        margin-right: 20%;
        color: white;
    }
    
    /* Estilo para o input de mensagem */
    .stTextInput > div > div > input {
        background-color: #32424a;
        color: white;
        border: 1px solid #4a676a;
        border-radius: 10px;
    }
    
    /* Estilo para o input quando clicado/focado */
    .stTextInput > div > div > input:focus {
        border: 2px solid #40e0d0 !important;
        outline: none !important;
        box-shadow: 0 0 10px rgba(64, 224, 208, 0.3) !important;
    }
    
    /* Estilo para botões */
    .stButton > button {
        background: linear-gradient(135deg, #3b5859 0%, #52a1a1 100%);
        color: white;
        border: none;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem !important;
        padding: 0.8rem 1.5rem !important;
        height: 3rem !important;
        min-height: 3rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        transition: all 0.3s ease;
    }
    
    /* Botões do histórico na sidebar */
    .css-1d391kg .stButton > button {
        background: linear-gradient(135deg, #2a2a3e 0%, #3a3a4e 100%);
        font-size: 0.9rem !important;
        padding: 0.6rem 1rem !important;
        height: auto !important;
        min-height: 2.5rem !important;
        text-transform: none;
        text-align: left;
        border-left: 3px solid #667eea;
    }
    
    .css-1d391kg .stButton > button:hover {
        background: linear-gradient(135deg, #3a3a4e 0%, #4a4a5e 100%);
        border-left-color: #93f8fb;
        transform: translateX(5px);
        border: 2px solid #40e0d0 !important;
        outline: none !important;
        box-shadow: 0 0 10px rgba(64, 224, 208, 0.3) !important;
    }
    
    /* Histórico de chats na sidebar */
    .chat-history-item {
        background-color: #2a2a3e;
        padding: 0.8rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 3px solid #667eea;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .chat-history-item:hover {
        background-color: #3a3a4e;
        border-left-color: #93f8fb;
    }
</style>
""", unsafe_allow_html=True)


# Buscar histórico do banco ao abrir o app
if "historico" not in st.session_state:
    try:
        historico_db = buscar_historico(user_id="default", limit=20)
        # Monta o formato esperado para o chat
        st.session_state.historico = [
            {
                "pergunta": h.pergunta,
                "resposta": h.resposta,
                "citacoes": [],
                "acao": "",
                "timestamp": h.created_at.isoformat() if hasattr(h.created_at, 'isoformat') else str(h.created_at)
            }
            for h in reversed(historico_db)
        ]
    except Exception as e:
        st.session_state.historico = []
        st.warning(f"Não foi possível carregar histórico do banco: {e}")

if "mensagem" not in st.session_state:
    st.session_state.mensagem = ""

if "chats_salvos" not in st.session_state:
    st.session_state.chats_salvos = []

if "chat_atual_id" not in st.session_state:
    st.session_state.chat_atual_id = 0

def enviar_mensagem():
    if st.session_state.mensagem.strip():
        try:
            resposta_final = processar_pergunta(st.session_state.mensagem, st.session_state.historico)
            resposta_sanitizada = sanitize_text(resposta_final.get("resposta", ""))
            citacoes_sanitizadas = []
            for cit in resposta_final.get("citacoes", []):
                cit_sanitizada = {
                    "documento": sanitize_text(cit.get("documento", "")),
                    "pagina": cit.get("pagina", 1),
                    "trecho": sanitize_text(cit.get("trecho", ""))[:300],
                    "relevancia": sanitize_text(cit.get("relevancia", "Fonte"))
                }
                citacoes_sanitizadas.append(cit_sanitizada)
            st.session_state.historico.append({
                "pergunta": sanitize_text(st.session_state.mensagem),
                "resposta": resposta_sanitizada,
                "citacoes": citacoes_sanitizadas,
                "acao": resposta_final.get("acao_final", ""),
                "timestamp": resposta_final.get("timestamp", datetime.now().isoformat())
            })
            # Salva no banco (user_id pode ser customizado, aqui é 'default')
            try:
                salvar_chat(
                    user_id="default",
                    pergunta=sanitize_text(st.session_state.mensagem),
                    resposta=resposta_sanitizada
                )
            except Exception as e:
                st.warning(f"Não foi possível salvar no banco: {e}")
            st.session_state.mensagem = ""
        except UnicodeEncodeError as e:
            st.session_state.historico.append({
                "pergunta": st.session_state.mensagem,
                "resposta": f"Erro de codificacao: {str(e)}. Resposta contem caracteres especiais nao suportados.",
                "citacoes": [],
                "acao": "ERRO",
                "timestamp": datetime.now().isoformat()
            })
            st.session_state.mensagem = ""
        except Exception as e:
            st.session_state.historico.append({
                "pergunta": st.session_state.mensagem,
                "resposta": f"Erro ao processar sua pergunta: {type(e).__name__}: {str(e)}",
                "citacoes": [],
                "acao": "ERRO",
                "timestamp": datetime.now().isoformat()
            })
            st.session_state.mensagem = ""

def novo_chat():
    # Salvar chat atual se houver mensagens
    if st.session_state.historico:
        primeiro_pergunta = st.session_state.historico[0]["pergunta"][:50] + "..." if len(st.session_state.historico[0]["pergunta"]) > 50 else st.session_state.historico[0]["pergunta"]
        st.session_state.chats_salvos.append({
            "id": len(st.session_state.chats_salvos),
            "titulo": primeiro_pergunta,
            "historico": st.session_state.historico.copy()
        })
    
    # Limpar chat atual
    st.session_state.historico = []
    st.session_state.mensagem = ""
    st.session_state.chat_atual_id = len(st.session_state.chats_salvos)

def carregar_chat(chat_id):
    chat_selecionado = next((chat for chat in st.session_state.chats_salvos if chat["id"] == chat_id), None)
    if chat_selecionado:
        st.session_state.historico = chat_selecionado["historico"].copy()
        st.session_state.chat_atual_id = chat_id
        st.session_state.mensagem = ""  # Limpar mensagem atual
        return True
    return False

# SIDEBAR - Histórico de Chats
with st.sidebar:
    # Logo no topo da sidebar
    logo_path = Path("logo")
    if logo_path.exists():
        logo_files = list(logo_path.glob("*.png")) + list(logo_path.glob("*.jpg")) + list(logo_path.glob("*.jpeg")) + list(logo_path.glob("*.svg"))
        if logo_files:
            st.image(str(logo_files[0]), width=180)
    st.markdown("### Integrador de Dados")
    st.markdown("**Smartbreeder**")
    
    st.markdown("---")
    
    # Botão para novo chat
    if st.button("Novo Chat", use_container_width=True):
        novo_chat()
    
    st.markdown("### Historico de Chats")
    
    # Mostrar chat atual se há conversas ativas
    if st.session_state.historico and st.session_state.chat_atual_id not in [chat["id"] for chat in st.session_state.chats_salvos]:
        st.markdown("**Chat Atual** (nao salvo)")
        st.markdown(f"*{len(st.session_state.historico)} mensagem(s)*")
        st.markdown("---")
    
    # Mostrar chats salvos
    if st.session_state.chats_salvos:
        for chat in reversed(st.session_state.chats_salvos):
            # Destacar o chat atual
            if st.session_state.chat_atual_id == chat["id"]:
                button_label = f">> {chat['titulo']}"
                button_help = "Chat atual"
            else:
                button_label = f"- {chat['titulo']}"
                button_help = f"Clique para carregar este chat ({len(chat['historico'])} mensagens)"
            
            if st.button(button_label, key=f"chat_{chat['id']}", use_container_width=True, help=button_help):
                carregar_chat(chat["id"])
        
        st.markdown("---")
        st.markdown(f"*Total: {len(st.session_state.chats_salvos)} chat(s) salvos*")
    else:
        if not st.session_state.historico:
            st.markdown("*Nenhum chat iniciado*")
            st.markdown("*Clique em 'Novo Chat' para comecar*")

# ÁREA PRINCIPAL - Chat
st.markdown("""
<div style="text-align: center; padding: 2rem;">
    <h1 style="color: #b4e6ed; font-size: 2.5rem; margin-bottom: 0.5rem;">
        Assistente de Regras de Negocio
    </h1>
    <p style="color: #a0a0a0; font-size: 1.2rem;">
        Integrador de Dados - Consulta tecnica de procedures e estruturas
    </p>
</div>
""", unsafe_allow_html=True)

# Área de input de mensagem
st.markdown("### Digite sua mensagem:")
mensagem_input = st.text_input("Digite sua pergunta", key="mensagem", placeholder="Digite sua pergunta aqui...", label_visibility="collapsed")

# Botões de ação centralizados
col1, col2, col3, col4, col5 = st.columns([2, 1, 0.5, 1, 2])
with col2:
    if st.button("Enviar", on_click=enviar_mensagem, use_container_width=True):
        pass
with col4:
    if st.button("Novo Chat", on_click=novo_chat, use_container_width=True):
        pass

# Área do chat
if st.session_state.historico:
    st.markdown("---")
    st.markdown("### Conversa")
    
    # Container para o chat com scroll
    chat_container = st.container()
    
    with chat_container:
        for i, item in enumerate(st.session_state.historico):
            # Mensagem do usuário
            st.markdown(f"""
            <div class="chat-message user-message">
                <div>
                    <strong>Voce:</strong><br>
                    {item['pergunta']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Obter dados do item
            acao = item.get('acao', 'N/A')
         
            # Ícone baseado na ação - usando texto simples para evitar problemas de codificação
            icone_acao = {
                'AUTO_RESOLVER': '[OK]',
                'PEDIR_INFO': '[?]',
                'ERRO': '[ERRO]'
            }.get(acao, '[BOT]')
            
            # Mensagem do assistente
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <strong>{icone_acao} Assistente</strong>
                    </div>
                    {item['resposta']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Citações (se houver)
            if item["citacoes"]:
                with st.expander(f"Ver Citacoes ({len(item['citacoes'])})", expanded=False):
                    for j, cit in enumerate(item["citacoes"]):
                        relevancia = cit.get('relevancia', f'Fonte {j+1}')
                        st.markdown(f"""
                        **{relevancia}** | **{cit['documento']}** | **Pagina {cit['pagina']}**
                        
                        > {cit['trecho']}
                        """)
            
            st.markdown("<br>", unsafe_allow_html=True)
else:
    # Tela inicial quando não há mensagens
    st.markdown("""
    <div style="text-align: center; padding: 3rem; color: #a0a0a0;">
        <h3>Integrador de Dados</h3>
        <p>Digite uma pergunta tecnica sobre procedures, estruturas de dados ou integracao.</p>
        <p><em>Respostas diretas e tecnicas para suas consultas de dados.</em></p>
    </div>
    """, unsafe_allow_html=True)