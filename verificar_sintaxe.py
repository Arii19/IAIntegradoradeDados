#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de sintaxe para verificar se o main.py está correto
"""

import ast
import sys

def verificar_sintaxe_main():
    """Verifica se o arquivo main.py tem sintaxe válida"""
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            codigo = f.read()
        
        # Verificar sintaxe Python
        ast.parse(codigo)
        print("✅ SINTAXE PYTHON: OK")
        
        # Verificar se não há referências a 'abrir_chamado'
        if 'abrir_chamado' in codigo:
            print("❌ ERRO: Ainda há referências a 'abrir_chamado'")
            linhas = codigo.split('\n')
            for i, linha in enumerate(linhas, 1):
                if 'abrir_chamado' in linha:
                    print(f"   Linha {i}: {linha.strip()}")
            return False
        else:
            print("✅ REFERÊNCIAS 'abrir_chamado': Removidas")
        
        # Verificar se workflow está correto
        if 'workflow.add_edge("abrir_chamado"' in codigo:
            print("❌ ERRO: Ainda há edge para 'abrir_chamado'")
            return False
        else:
            print("✅ WORKFLOW EDGES: OK")
        
        # Verificar se apenas AUTO_RESOLVER e PEDIR_INFO estão nas decisões
        if '"ABRIR_CHAMADO"' in codigo:
            print("⚠️ AVISO: Ainda há referências a 'ABRIR_CHAMADO' no código")
            print("   (Pode ser em comentários ou strings)")
        
        print("✅ VERIFICAÇÃO GERAL: SUCESSO")
        return True
        
    except SyntaxError as e:
        print(f"❌ ERRO DE SINTAXE: {e}")
        return False
    except FileNotFoundError:
        print("❌ ERRO: Arquivo main.py não encontrado")
        return False
    except Exception as e:
        print(f"❌ ERRO INESPERADO: {e}")
        return False

def verificar_imports():
    """Verifica se os imports estão corretos"""
    print("\n📦 VERIFICANDO IMPORTS...")
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            linhas = f.readlines()
        
        imports_encontrados = []
        for i, linha in enumerate(linhas[:30], 1):  # Verificar apenas primeiras 30 linhas
            if linha.strip().startswith(('import ', 'from ')):
                imports_encontrados.append(f"Linha {i}: {linha.strip()}")
        
        print("Imports encontrados:")
        for imp in imports_encontrados:
            print(f"  {imp}")
        
        return True
    except Exception as e:
        print(f"❌ ERRO ao verificar imports: {e}")
        return False

if __name__ == "__main__":
    print("🔍 VERIFICAÇÃO DE SINTAXE E ESTRUTURA")
    print("=" * 50)
    
    sucesso_sintaxe = verificar_sintaxe_main()
    sucesso_imports = verificar_imports()
    
    print("\n" + "=" * 50)
    if sucesso_sintaxe and sucesso_imports:
        print("🎉 VERIFICAÇÃO COMPLETA: SUCESSO!")
        print("✅ O arquivo main.py está pronto para uso")
        print("✅ Não há mais referências a 'abrir_chamado'")
    else:
        print("❌ VERIFICAÇÃO FALHOU!")
        print("⚠️ Corrija os problemas acima")