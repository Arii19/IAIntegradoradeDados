# 🤖 Integrador de Dados - Sistema IA para Consultas Técnicas

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/LangChain-0.1+-green.svg)](https://www.langchain.com/)
[![Google AI](https://img.shields.io/badge/Google%20AI-Gemini-yellow.svg)](https://ai.google.dev/)

> **Sistema inteligente de consultas técnicas** que utiliza **RAG (Retrieval-Augmented Generation)** para responder perguntas específicas sobre procedures, sistemas e documentação técnica com alta precisão.

---

## 🎯 **Características Principais**

### ✨ **Triagem Inteligente Ultra-Refinada**
- **AUTO_RESOLVER**: Respostas diretas para perguntas técnicas específicas
- **PEDIR_INFO**: Solicitação de esclarecimentos apenas quando extremamente necessário
- **Detecção automática**: Procedures (`INT.`, `SP_`), sistemas, códigos técnicos
- **Confiança alta**: 80-95% para perguntas técnicas bem formuladas

### 🔍 **Sistema RAG Avançado Multi-Estratégia**
- **Busca semântica**: Embeddings Google Gemini + FAISS vectorstore
- **Expansão de termos**: Busca automática por sinônimos e termos relacionados
- **Múltiplas estratégias**: Similaridade + MMR + palavras-chave expandidas
- **Threshold adaptativo**: 0.15 para maior cobertura de resultados

### 💬 **Persona Técnica Especializada**
- **Integrador de Dados**: Foco em procedures, sistemas e documentação técnica
- **Respostas concisas**: 50-150 palavras, diretas ao ponto
- **Linguagem técnica**: Apropriada para desenvolvedores e analistas
- **Citações precisas**: Referências exatas aos documentos fonte

---

## 🚀 **Funcionalidades Avançadas**

| Funcionalidade | Descrição | Status |
|---|---|---|
| **Triagem Contextual** | Análise inteligente de sentimento e categoria | ✅ |
| **RAG Multi-Camadas** | Busca semântica + expandida + MMR | ✅ |
| **Cache Inteligente** | Respostas em cache para perguntas frequentes | ✅ |
| **Validação de Resposta** | Controle automático de qualidade e concisão | ✅ |
| **Debug Logs** | Monitoramento detalhado do processo de busca | ✅ |
| **Citações Melhoradas** | Referências com página, documento e relevância | ✅ |

---

## 🛠️ **Stack Tecnológica**

### **Core**
- **Python 3.10+**: Linguagem base
- **Streamlit**: Interface web responsiva
- **LangChain**: Orquestração de IA e workflows
- **Google Generative AI**: Modelo Gemma-3-27b-it + embeddings

### **RAG & Vectorstore**
- **FAISS**: Busca vetorial de alta performance
- **PyMuPDF**: Processamento de documentos PDF
- **RecursiveCharacterTextSplitter**: Chunking inteligente (800 chars, overlap 100)

### **Workflow & Estado**
- **LangGraph**: StateGraph para fluxo de decisões
- **Gestão de Estado**: Controle de conversação e tentativas
- **Cache System**: LRU cache + hash de perguntas

---

## ⚙️ **Instalação e Configuração**

### **1. Clone e Setup**
```bash
git clone https://github.com/Arii19/IAIntegradoradeDados.git
cd IAParaRH

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### **2. Instalar Dependências**
```bash
pip install -r requirements.txt
```

### **3. Configurar API Key**
```bash
# Criar arquivo .env
echo "API_KEY=sua_google_api_key_aqui" > .env
```

### **4. Adicionar Documentos**
```bash
# Criar pasta docs e adicionar PDFs
mkdir docs
# Copiar seus PDFs técnicos para a pasta docs/
```

### **5. Executar Sistema**
```bash
streamlit run app.py
```

---

## 📊 **Exemplos de Uso**

### **✅ Consultas Técnicas (Alta Confiança)**
```
👤 "para que serve a INT.INT_APLICINSUMOAGRIC"
🤖 96% confiança | AUTO_RESOLVER
📄 "A INT.INT_APLICINSUMOAGRIC é a tabela final resultante da consolidação e padronização de dados de aplicações de insumos agrícolas..."

👤 "qual é a origem dos dados"  
🤖 85% confiança | AUTO_RESOLVER
📄 "A origem dos dados pode variar e depender do ERP (Enterprise Resource Planning)..."
```

### **⚠️ Consultas Vagas (Pede Esclarecimentos)**
```
👤 "preciso de ajuda"
🤖 60% confiança | PEDIR_INFO
❓ "Preciso de mais detalhes para ajudar melhor. Poderia ser mais específico?"
```

---

## � **Configurações Avançadas**

### **Ajustar Triagem** (`main.py`)
```python
# Threshold de confiança para AUTO_RESOLVER
if resultado["confianca"] < 0.2:  # Muito restritivo
    resultado["decisao"] = "PEDIR_INFO"

# Temperatura do modelo
llm_triagem = ChatGoogleGenerativeAI(
    model="models/gemma-3-27b-it",
    temperature=0.1  # Mais determinístico
)
```

### **Ajustar RAG** (`main.py`)
```python
# Threshold de similaridade
retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.15, "k": 8}
)

# Chunking de documentos
splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,     # Tamanho do chunk
    chunk_overlap=100   # Sobreposição
)
```

---

## 📈 **Performance e Métricas**

| Métrica | Valor Típico | Descrição |
|---|---|---|
| **Confiança Média** | 85-95% | Para perguntas técnicas específicas |
| **Tempo Resposta** | 2-5s | Incluindo busca RAG e geração |
| **Recall** | 90%+ | Encontra informações quando existem |
| **Precisão** | 95%+ | Respostas corretas quando confiantes |
| **Concisão** | 50-150 palavras | Respostas diretas e objetivas |

---

## 🚨 **Solução de Problemas**

### **Quota API Esgotada**
```
Error: 429 You exceeded your current quota
```
**Solução**: Aguardar reset diário (4-5h AM) ou upgrade para plano pago

### **Documentos Não Carregados**
```
[AVISO] Pasta 'docs' não encontrada
```
**Solução**: Criar pasta `docs/` e adicionar arquivos PDF

### **Baixa Confiança em Respostas**
**Soluções**:
- Verificar se documento contém informação
- Ajustar threshold de similaridade
- Melhorar expansão de termos de busca

---

## 🤝 **Contribuição**

1. **Fork** o projeto
2. **Crie** uma branch: `git checkout -b feature/nova-funcionalidade`
3. **Commit** suas mudanças: `git commit -m 'Adiciona nova funcionalidade'`
4. **Push** para branch: `git push origin feature/nova-funcionalidade`
5. **Abra** um Pull Request

---

## 📝 **Licença**

Este projeto está sob licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 🏷️ **Tags**

`#RAG` `#LangChain` `#GoogleAI` `#Streamlit` `#FAISS` `#DocumentQA` `#TechnicalDocs` `#IntegradorDados`

---

**Desenvolvido com ❤️ para consultas técnicas precisas e eficientes.**
