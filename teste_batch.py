"""
Teste rápido do sistema de Batch Processing
"""

import sys
import os

# Adicionar diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from batch_processor import BatchProcessor, BatchItem

def teste_rapido():
    """Teste rápido com 10 perguntas"""
    
    print("🧪 Teste Rápido do Batch Processing")
    print("=" * 40)
    
    # Perguntas de teste
    perguntas = [
        "O que é a procedure SP_AT_INT_APLICINSUMOAGRIC?",
        "Como funciona a normalização de dados?", 
        "Qual é a origem dos dados?",
        "Explique o processo ETL",
        "O que são regras de negócio?",
        "Como consultar tabelas?",
        "Explique integração de sistemas",
        "O que é consolidação de dados?",
        "Como funciona o SmartBreeder?",
        "Explique procedures SQL"
    ]
    
    # Criar processador
    processor = BatchProcessor(
        batch_size=3,
        max_workers=2,
        rate_limit=2.0,
        enable_caching=True
    )
    
    # Criar itens
    items = [
        BatchItem(id=f"teste_{i+1}", content=pergunta, metadata={})
        for i, pergunta in enumerate(perguntas)
    ]
    
    print(f"📝 Processando {len(items)} perguntas...")
    
    # Processar
    results = processor.process_batch(items)
    
    # Mostrar resultados
    print(f"\n📊 Resultados:")
    summary = processor.get_processing_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    # Mostrar amostra
    print(f"\n📋 Amostra (primeiros 3):")
    for result in results[:3]:
        status = "✅" if result.success else "❌"
        print(f"{status} {result.item_id}: {result.processing_time:.2f}s")
        
        if result.success and result.result:
            resposta = result.result.get('resposta', 'N/A')
            print(f"   {resposta[:80]}...")
        elif result.error:
            print(f"   Erro: {result.error}")
        print()
    
    return results

if __name__ == "__main__":
    try:
        results = teste_rapido()
        print("✅ Teste concluído com sucesso!")
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()