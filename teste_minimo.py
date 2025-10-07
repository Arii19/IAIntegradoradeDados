#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste mínimo para verificar se o sistema principal funciona
"""

def teste_import_main():
    """Testa se consegue importar e usar a função principal"""
    try:
        # Teste de import
        print("🔄 Testando import...")
        from main import processar_pergunta
        print("✅ Import bem-sucedido!")
        
        # Teste básico de funcionamento
        print("🔄 Testando função principal...")
        resultado = processar_pergunta("Como solicitar férias?")
        
        acao = resultado.get("acao_final", "ERRO")
        resposta = resultado.get("resposta", "")
        
        print(f"✅ Função executada!")
        print(f"📋 Ação: {acao}")
        print(f"💬 Resposta: {resposta[:100]}...")
        
        # Verificar se não está abrindo chamados
        if acao == "ABRIR_CHAMADO":
            print("❌ PROBLEMA: Ainda está abrindo chamados!")
            return False
        else:
            print("✅ CORRETO: Não abre chamados!")
            return True
            
    except ImportError as e:
        print(f"❌ ERRO DE IMPORT: {e}")
        print("💡 Instale as dependências: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")
        return False

if __name__ == "__main__":
    print("🧪 TESTE MÍNIMO DO SISTEMA")
    print("=" * 40)
    
    sucesso = teste_import_main()
    
    print("\n" + "=" * 40)
    if sucesso:
        print("🎉 SISTEMA FUNCIONANDO CORRETAMENTE!")
        print("✅ Streamlit deve funcionar agora")
    else:
        print("❌ SISTEMA COM PROBLEMAS")
        print("💡 Verifique as dependências e configurações")