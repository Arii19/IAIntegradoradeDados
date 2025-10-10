# Configurações da IA - INTEGRADOR DE DADOS CONCISO
# ========================================================

# Configurações do modelo
MODEL_CONFIG = {
    "triagem_model": "models/gemma-3-27b-it",
    "temperature": 0.1,
    "max_tokens": 1024  # Reduzido para forçar concisão
}

# Estratégia: MÁXIMA CONCISÃO
STRATEGY_CONFIG = {
    "role": "Integrador de dados",
    "max_response_words": 80,  # Limite rigoroso
    "ideal_response_words": 50,
    "avoid_introductions": True,
    "technical_language": True,
    "direct_answers_only": True
}

# Thresholds de concisão (mais rigorosos)
CONCISENESS_THRESHOLDS = {
    "ideal": 50,      # ≤50 palavras = ideal
    "good": 80,       # ≤80 palavras = bom  
    "acceptable": 150, # ≤150 palavras = aceitável
    "too_long": 150   # >150 palavras = penalizado
}

# Categorias e palavras-chave
CATEGORIES = {
    "RH": ["férias", "salário", "benefício", "contrato", "demissão", "admissão"],
    "TI": ["sistema", "acesso", "senha", "computador", "rede", "software"],
    "FINANCEIRO": ["reembolso", "pagamento", "nota", "despesa", "orçamento"],
    "OPERACIONAL": ["processo", "procedimento", "fluxo", "aprovação", "prazo"],
    "GERAL": ["política", "regra", "norma", "regulamento", "orientação"]
}

# Palavras que indicam urgência (mas não geram chamados)
URGENCY_KEYWORDS = {
    "ALTA": ["urgente", "crítico", "prioritário", "importante", "prazo", "emergência"],
    "MEDIA": ["normal", "rotina", "procedimento", "consulta"],
    "BAIXA": ["informação", "esclarecimento", "dúvida", "orientação"]
}

# Configurações de logging
LOGGING_CONFIG = {
    "log_level": "INFO",
    "log_interactions": True,
    "log_file": "ia_interactions.log",
    "metrics_tracking": True
}

# Configurações da interface
UI_CONFIG = {
    "show_confidence": True,
    "show_citations": True,
    "show_metrics": True,
    "max_chat_history": 50,
    "auto_save_chats": True
}

# Mensagens padrão - VERSÃO ÚTIL (sem chamados)
MESSAGES = {
    "welcome": "👋 Olá! Sou seu assistente para políticas e procedimentos da Carraro Desenvolvimento. Vou sempre tentar ajudar você da melhor forma possível!",
    "no_documents": "📚 Mesmo sem documentos específicos, vou fornecer orientações úteis baseadas em boas práticas.",
    "error": "😕 Ocorreu um erro, mas vou tentar ajudar de outra forma. Pode reformular sua pergunta?",
    "low_confidence": "💡 Esta é uma orientação geral. Para informações mais específicas, você pode fornecer mais detalhes.",
    "info_needed": "❓ Para dar uma resposta mais precisa, você poderia me fornecer mais detalhes sobre sua situação?",
    "always_helpful": "🎯 Meu objetivo é sempre ser útil e fornecer as melhores orientações possíveis!"
}

# Princípios da IA
PRINCIPLES = {
    "always_try_to_help": "Sempre tente ser útil, mesmo com informações limitadas",
    "be_constructive": "Forneça orientações construtivas e próximos passos",
    "never_give_up": "Nunca apenas diga 'não sei' - sempre tente ajudar",
    "be_friendly": "Seja amigável, profissional e acolhedor",
    "provide_guidance": "Ofereça orientações práticas quando possível"
}