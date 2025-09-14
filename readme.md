# 📄 Assistente de Políticas Internas – Carraro Desenvolvimento


# 📄 Acesse: https://iapararh-fnjcw4zw9hwfkctuvc9a87.streamlit.app/


Este projeto implementa um **Assistente de Service Desk** especializado em **políticas internas** (RH/IT) da empresa *Carraro Desenvolvimento*, utilizando **LangChain**, **Google Generative AI** e **Streamlit** para oferecer:

- **Triagem automática** de solicitações (`AUTO_RESOLVER`, `PEDIR_INFO`, `ABRIR_CHAMADO`)
- **RAG (Retrieval-Augmented Generation)** para responder com base em documentos PDF internos
- **Fluxo de decisão** com `StateGraph` para determinar a ação final
- **Interface web** simples e interativa via **Streamlit**

---

## 🚀 Funcionalidades

- **Triagem inteligente**: Classifica a solicitação do usuário em três categorias:
  - `AUTO_RESOLVER`: Resposta direta com base nas políticas
  - `PEDIR_INFO`: Solicita mais informações
  - `ABRIR_CHAMADO`: Encaminha para abertura de ticket
- **Busca contextual (RAG)**: Pesquisa em PDFs internos usando embeddings e FAISS
- **Citações**: Retorna trechos e páginas dos documentos usados na resposta
- **Interface Streamlit**: Campo para digitar mensagem, exibir resposta e botão de "Novo Chat"

---

## 🛠️ Tecnologias Utilizadas

- [Python 3.10+](https://www.python.org/)
- [Streamlit](https://streamlit.io/)
- [LangChain](https://www.langchain.com/)
- [Google Generative AI](https://ai.google.dev/)
- [FAISS](https://faiss.ai/)
- [PyMuPDF](https://pymupdf.readthedocs.io/)
- [dotenv](https://pypi.org/project/python-dotenv/)

---



## ⚙️ Instalação

1. **Clone o repositório**
   ```bash
   git clone https://github.com/seu-usuario/seu-repo.git
   cd seu-repo
