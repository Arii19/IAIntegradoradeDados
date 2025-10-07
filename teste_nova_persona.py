#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste da nova persona: Integrador de dados conciso
"""

def testar_nova_persona():
    """Testa se a IA está usando a nova persona corretamente"""
    
    try:
        from main import processar_pergunta
        
        # Pergunta específica que teve problema
        pergunta_teste = "qual a finalidade da INT.INT_APLICINSUMOAGRIC"
        
        print("🎯 TESTE DA NOVA PERSONA: INTEGRADOR DE DADOS")
        print("=" * 60)
        print(f"📝 PERGUNTA: {pergunta_teste}")
        print("-" * 60)
        
        resultado = processar_pergunta(pergunta_teste)
        resposta = resultado.get("resposta", "")
        confianca = resultado.get("confianca_geral", 0)
        
        # Análise da resposta
        palavras = len(resposta.split())
        linhas = resposta.split('\n')
        tem_introducao_ruim = any(palavra in resposta.lower()[:100] 
                                 for palavra in ['olá', 'como especialista', 'posso te ajudar'])
        
        print("📊 ANÁLISE DA RESPOSTA:")
        print(f"   • Palavras: {palavras}")
        print(f"   • Linhas: {len(linhas)}")
        print(f"   • Confiança: {confianca:.1%}")
        
        # Verificações
        print("\n🔍 VERIFICAÇÕES:")
        
        # 1. Tamanho ideal
        if palavras <= 50:
            print("   ✅ TAMANHO: Ideal (≤50 palavras)")
        elif palavras <= 80:
            print("   ✅ TAMANHO: Bom (≤80 palavras)")
        elif palavras <= 150:
            print("   ⚠️ TAMANHO: Aceitável (≤150 palavras)")
        else:
            print("   ❌ TAMANHO: Muito longo (>150 palavras)")
        
        # 2. Sem introdução ruim
        if not tem_introducao_ruim:
            print("   ✅ INTRODUÇÃO: Sem saudações desnecessárias")
        else:
            print("   ❌ INTRODUÇÃO: Ainda tem saudações ('Olá', 'Como especialista')")
        
        # 3. Linguagem técnica
        if "procedure" in resposta.lower() or "dados" in resposta.lower():
            print("   ✅ LINGUAGEM: Técnica apropriada")
        else:
            print("   ⚠️ LINGUAGEM: Poderia ser mais técnica")
        
        print(f"\n💬 RESPOSTA COMPLETA:")
        print("-" * 40)
        print(resposta)
        print("-" * 40)
        
        # Avaliar qualidade geral
        score = 0
        if palavras <= 80: score += 1
        if not tem_introducao_ruim: score += 1
        if "dados" in resposta.lower(): score += 1
        
        print(f"\n🎯 SCORE FINAL: {score}/3")
        if score == 3:
            print("🎉 EXCELENTE: Nova persona funcionando perfeitamente!")
        elif score == 2:
            print("✅ BOM: Quase lá, pequenos ajustes necessários")
        else:
            print("⚠️ PRECISA MELHORAR: Ajustes necessários")
        
        return score >= 2
        
    except ImportError:
        print("❌ Erro: Não foi possível importar o sistema")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

if __name__ == "__main__":
    testar_nova_persona()