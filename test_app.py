import streamlit as st
from main import processar_pergunta
import traceback

st.title("Teste de Debug do Assistente")

# Input simples
pergunta = st.text_input("Digite sua pergunta:")

if st.button("Testar"):
    if pergunta:
        try:
            st.write("🔄 Processando pergunta...")
            
            # Testar a função
            resultado = processar_pergunta(pergunta)
            
            st.write("✅ Processamento concluído!")
            st.write("**Ação Final:**", resultado.get("acao_final", "N/A"))
            st.write("**Resposta:**")
            
            # Tentar exibir resposta de forma segura
            resposta = resultado.get("resposta", "Sem resposta")
            try:
                st.text(resposta)  # Usar st.text em vez de st.markdown
            except Exception as e:
                st.error(f"Erro ao exibir resposta: {e}")
                # Tentar versão sanitizada
                resposta_safe = resposta.encode('ascii', 'ignore').decode('ascii')
                st.text(resposta_safe)
            
            st.write("**Citações:**", len(resultado.get("citacoes", [])))
            
        except Exception as e:
            st.error(f"❌ ERRO: {type(e).__name__}: {str(e)}")
            st.code(traceback.format_exc())