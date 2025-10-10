#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para converter PDF para Markdown
Otimizado para documentação técnica
"""

import os
from pathlib import Path

def converter_com_pymupdf():
    """Converte usando PyMuPDF4LLM (recomendado)"""
    try:
        import pymupdf4llm
        
        pdf_path = "docs/INT.SP_AT_INT_APLICINSUMOAGRIC.pdf"
        output_path = "docs/INT.SP_AT_INT_APLICINSUMOAGRIC_convertido.md"
        
        print("🔄 Convertendo PDF para Markdown com pymupdf4llm...")
        
        # Conversão otimizada para LLMs
        md_text = pymupdf4llm.to_markdown(pdf_path)
        
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(md_text)
        
        print(f"✅ Conversão concluída: {output_path}")
        return True
        
    except ImportError:
        print("❌ pymupdf4llm não instalada. Instale com: pip install pymupdf4llm")
        return False
    except Exception as e:
        print(f"❌ Erro na conversão: {e}")
        return False

def converter_com_pymupdf_basico():
    """Fallback usando PyMuPDF básico"""
    try:
        import fitz  # PyMuPDF
        
        pdf_path = "docs/INT.SP_AT_INT_APLICINSUMOAGRIC.pdf"
        output_path = "docs/INT.SP_AT_INT_APLICINSUMOAGRIC_basico.md"
        
        print("🔄 Convertendo PDF para Markdown com PyMuPDF...")
        
        doc = fitz.open(pdf_path)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            text += f"## Página {page_num + 1}\n\n{page_text}\n\n---\n\n"
        
        doc.close()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"✅ Conversão concluída: {output_path}")
        return True
        
    except ImportError:
        print("❌ PyMuPDF não instalada. Instale com: pip install PyMuPDF")
        return False
    except Exception as e:
        print(f"❌ Erro na conversão: {e}")
        return False

def converter_com_pdfplumber():
    """Alternativa usando pdfplumber"""
    try:
        import pdfplumber
        
        pdf_path = "docs/INT.SP_AT_INT_APLICINSUMOAGRIC.pdf"
        output_path = "docs/INT.SP_AT_INT_APLICINSUMOAGRIC_pdfplumber.md"
        
        print("🔄 Convertendo PDF para Markdown com pdfplumber...")
        
        text = "# Documentação Convertida\n\n"
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"## Página {i + 1}\n\n{page_text}\n\n---\n\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"✅ Conversão concluída: {output_path}")
        return True
        
    except ImportError:
        print("❌ pdfplumber não instalada. Instale com: pip install pdfplumber")
        return False
    except Exception as e:
        print(f"❌ Erro na conversão: {e}")
        return False

def instalar_dependencias():
    """Instala as dependências necessárias"""
    import subprocess
    import sys
    
    bibliotecas = [
        "pymupdf4llm",  # Primeira opção
        "PyMuPDF",      # Fallback 1
        "pdfplumber"    # Fallback 2
    ]
    
    print("📦 Instalando dependências...")
    
    for lib in bibliotecas:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
            print(f"✅ {lib} instalada com sucesso")
        except subprocess.CalledProcessError:
            print(f"❌ Erro ao instalar {lib}")

def main():
    """Função principal"""
    print("🔄 CONVERSOR PDF → MARKDOWN")
    print("=" * 40)
    
    # Verificar se o PDF existe
    pdf_path = Path("docs/INT.SP_AT_INT_APLICINSUMOAGRIC.pdf")
    if not pdf_path.exists():
        print(f"❌ PDF não encontrado: {pdf_path}")
        return
    
    print(f"📄 PDF encontrado: {pdf_path}")
    print()
    
    # Tentar conversões em ordem de preferência
    metodos = [
        ("PyMuPDF4LLM (Recomendado)", converter_com_pymupdf),
        ("PyMuPDF Básico", converter_com_pymupdf_basico),
        ("PDFPlumber", converter_com_pdfplumber)
    ]
    
    for nome, funcao in metodos:
        print(f"🔧 Tentando: {nome}")
        if funcao():
            print(f"🎉 Sucesso com {nome}!")
            break
        print()
    else:
        print("❌ Nenhum método funcionou. Instale as dependências:")
        print("pip install pymupdf4llm PyMuPDF pdfplumber")

if __name__ == "__main__":
    main()