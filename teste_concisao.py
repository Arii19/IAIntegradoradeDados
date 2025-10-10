#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de concisão - verifica se as respostas estão mais curtas e diretas
"""

def testar_concisao():
    """Testa se as respostas estão mais concisas"""
    
    try:
        from main import processar_pergunta
        
        perguntas_teste = [
            "qual a finalidade da INT.INT_APLICINSUMOAGRIC",
            "Como solicitar férias?",
            "Qual a política de reembolso?",
            "Como funciona o trabalho remoto?"
        ]
        
        print("🎯 TESTE DE CONCISÃO DAS RESPOSTAS")
        print("=" * 50)
        
        for pergunta in perguntas_teste:
            print(f"\n📝 PERGUNTA: {pergunta}")
            print("-" * 40)
            
            resultado = processar_pergunta(pergunta)
            resposta = resultado.get("resposta", "")
            palavras = len(resposta.split())
            linhas = len(resposta.split('\n'))
            
            print(f"📊 ESTATÍSTICAS:")
            print(f"   • Palavras: {palavras}")
            print(f"   • Linhas: {linhas}")
            print(f"   • Caracteres: {len(resposta)}")
            
            # Avaliar concisão
            if palavras <= 100:
                print("   ✅ CONCISA (≤100 palavras)")
            elif palavras <= 200:
                print("   ⚠️ MODERADA (100-200 palavras)")
            else:
                print("   ❌ MUITO LONGA (>200 palavras)")
            
            print(f"\n💬 RESPOSTA:")
            print(f"   {resposta[:150]}{'...' if len(resposta) > 150 else ''}")
            
        print("\n" + "=" * 50)
        print("🎯 OBJETIVO: Respostas entre 50-100 palavras")
        print("✅ Respostas concisas são mais eficazes!")
        
    except ImportError:
        print("❌ Erro: Não foi possível importar o sistema")
        print("💡 Instale as dependências primeiro")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

if __name__ == "__main__":
    testar_concisao()