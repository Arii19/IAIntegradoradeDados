import streamlit as st
from dotenv import load_dotenv
import os
import json
from main import *


# =========================
# Configuração inicial
# =========================
load_dotenv()
st.set_page_config(page_title="Assistente de Políticas Internas", layout="centered")

# =========================
# Estado da sessão
# =========================
if "historico" not in st.session_state:
    st.session_state.historico = []

if "mensagem" not in st.session_state:
    st.session_state.mensagem = ""

# =========================
# Funções auxiliares
# =========================
def enviar_mensagem():
    if st.session_state.mensagem.strip():
        resposta_final = grafo.invoke({"pergunta": st.session_state.mensagem})
        st.session_state.historico.append({
            "pergunta": st.session_state.mensagem,
            "resposta": resposta_final.get("resposta", ""),
            "citacoes": resposta_final.get("citacoes", []),
        })
        st.session_state.mensagem = ""  # limpa campo

def novo_chat():
    st.session_state.historico = []
    st.session_state.mensagem = ""

# =========================
# Layout da página
# =========================
st.title("💬 Assistente de Políticas Internas - Carraro Desenvolvimento")

# Campo de entrada
st.text_input("Digite sua mensagem:", key="mensagem", on_change=enviar_mensagem)

# Botões
col1, col2 = st.columns([1, 1])
with col1:
    st.button("Enviar", on_click=enviar_mensagem, use_container_width=True)
with col2:
    st.button("Novo Chat", on_click=novo_chat, use_container_width=True)

st.markdown("---")

# Histórico de mensagens
for item in reversed(st.session_state.historico):
    st.markdown(f"**Você:** {item['pergunta']}")
    st.markdown(f"**Assistente:** {item['resposta']}")
    if item["citacoes"]:
        with st.expander("📄 Citações"):
            for cit in item["citacoes"]:
                st.markdown(f"- **Documento:** {cit['documento']}, **Página:** {cit['pagina']}")
                st.markdown(f"  Trecho: {cit['trecho']}")
    st.markdown("---")
