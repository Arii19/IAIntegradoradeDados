#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste simples para verificar se a IA está funcionando sem abrir chamados
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import processar_pergunta

def testar_ia_sem_chamados():
    """Testa se a IA não abre chamados e sempre tenta resolver ou pede informações"""
    
    perguntas_teste = [
        "Como solicitar férias?",
        "Preciso de aprovação para comprar equipamento",
        "Não consigo acessar o sistema", 
        "Qual a política de reembolso?",
        "Problema urgente no computador",
        "Como funciona o trabalho remoto?",
        "Preciso criar um novo usuário",
        "xyz abc indefinido"
    ]
    
    print("🧪 TESTANDO IA SEM ABERTURA DE CHAMADOS")
    print("=" * 50)
    
    todos_sucesso = True
    
    for i, pergunta in enumerate(perguntas_teste, 1):
        print(f"\n📝 TESTE {i}: '{pergunta}'")
        print("-" * 40)
        
        try:
            resultado = processar_pergunta(pergunta)
            
            acao = resultado.get("acao_final", "ERRO")
            confianca = resultado.get("confianca_geral", 0.0)
            categoria = resultado.get("categoria", "N/A")
            resposta = resultado.get("resposta", "")[:100] + "..."
            
            print(f"✅ Ação: {acao}")
            print(f"📊 Confiança: {confianca:.1%}")
            print(f"📂 Categoria: {categoria}")
            print(f"💬 Resposta: {resposta}")
            
            # Verificar se não abriu chamado
            if acao == "ABRIR_CHAMADO":
                print("❌ ERRO: Sistema ainda está abrindo chamados!")
                todos_sucesso = False
            elif acao in ["AUTO_RESOLVER", "PEDIR_INFO"]:
                print("✅ OK: Não abriu chamado")
            else:
                print(f"⚠️ AÇÃO INESPERADA: {acao}")
                todos_sucesso = False
                
        except Exception as e:
            print(f"❌ ERRO na pergunta '{pergunta}': {e}")
            todos_sucesso = False
    
    print("\n" + "=" * 50)
    if todos_sucesso:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("✅ A IA não está mais abrindo chamados")
        print("✅ Sempre tenta resolver ou pede mais informações")
    else:
        print("❌ ALGUNS TESTES FALHARAM!")
        print("⚠️ Verifique os problemas acima")
    
    return todos_sucesso

def teste_rapido():
    """Teste super rápido"""
    print("🚀 TESTE RÁPIDO")
    
    resultado = processar_pergunta("Como solicitar férias?")
    acao = resultado.get("acao_final")
    
    if acao != "ABRIR_CHAMADO":
        print(f"✅ SUCESSO: Ação = {acao} (não abre chamado)")
        return True
    else:
        print("❌ FALHOU: Ainda está abrindo chamados")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Testa a IA sem abertura de chamados")
    parser.add_argument("--rapido", action="store_true", help="Executa apenas teste rápido")
    
    args = parser.parse_args()
    
    if args.rapido:
        teste_rapido()
    else:
        testar_ia_sem_chamados()