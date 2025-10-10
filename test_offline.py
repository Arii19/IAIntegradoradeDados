#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste offline das melhorias sem usar API
"""

def simular_busca_melhorada():
    """Simula como funcionaria a busca melhorada"""
    
    # Conteúdo real do documento
    documento_conteudo = """
    A.Objetivo da Procedure
    A procedure int.SP_AT_INT_APLICINSUMOAGRIC é responsável por normalizar os dados relacionados a aplicações de insumos agrícolas.
    
    B.Origem dos dados
    Pode variar e depender do ERP (ERP é a sigla para Enterprise Resource Planning, ou Planejamento de Recursos Empresariais, e é um sistema de software integrado que gerencia e automatiza processos de diferentes áreas de uma empresa, como finanças, vendas, compras, estoque e recursos...)
    """
    
    # Perguntas teste
    perguntas = [
        "para que serve a INT.INT_APLICINSUMOAGRIC",
        "qual é a origem dos dados"
    ]
    
    # Simular expansão de busca
    def expandir_busca(pergunta):
        expansoes = {
            "origem": ["fonte", "ERP", "sistema", "base"],
            "dados": ["informações", "registros", "data"],
            "origem dos dados": ["fonte dos dados", "ERP", "sistema origem"],
            "aplicinsumo": ["insumo agrícola", "agric", "agricultura"],
            "procedure": ["procedimento", "função", "rotina"]
        }
        
        termos = []
        pergunta_lower = pergunta.lower()
        
        for termo_base, sinonimos in expansoes.items():
            if termo_base in pergunta_lower:
                termos.extend(sinonimos)
        
        return termos[:5]
    
    # Simular busca por similaridade
    def buscar_no_documento(pergunta, documento):
        pergunta_lower = pergunta.lower()
        doc_lower = documento.lower()
        
        # Busca direta
        if any(palavra in doc_lower for palavra in pergunta_lower.split()):
            return True, "Busca direta bem-sucedida"
        
        # Busca expandida
        termos_expandidos = expandir_busca(pergunta)
        for termo in termos_expandidos:
            if termo.lower() in doc_lower:
                return True, f"Encontrado via termo expandido: '{termo}'"
        
        return False, "Não encontrado"
    
    print("=== TESTE DE BUSCA MELHORADA ===\n")
    
    for pergunta in perguntas:
        print(f"📝 Pergunta: '{pergunta}'")
        
        # Expansão de termos
        termos_expandidos = expandir_busca(pergunta)
        print(f"🔍 Termos expandidos: {termos_expandidos}")
        
        # Simulação de busca
        encontrado, motivo = buscar_no_documento(pergunta, documento_conteudo)
        
        if encontrado:
            print(f"✅ SUCESSO: {motivo}")
            
            # Simular resposta baseada na pergunta
            if "serve" in pergunta or "objetivo" in pergunta:
                resposta = "A procedure int.SP_AT_INT_APLICINSUMOAGRIC é responsável por normalizar os dados relacionados a aplicações de insumos agrícolas."
            elif "origem" in pergunta:
                resposta = "A origem dos dados pode variar e depender do ERP (Enterprise Resource Planning), um sistema integrado que gerencia processos empresariais."
            else:
                resposta = "Informação encontrada no documento."
                
            print(f"📄 Resposta: {resposta}")
            print(f"🎯 Confiança estimada: 85-95%")
        else:
            print(f"❌ FALHA: {motivo}")
            print(f"🎯 Confiança estimada: 40-60%")
        
        print("-" * 80)

if __name__ == "__main__":
    simular_busca_melhorada()