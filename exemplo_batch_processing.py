"""
Exemplo de uso do sistema de Batch Processing
Demonstra como processar milhares de documentos de forma eficiente
"""

from batch_processor import BatchProcessor, BatchItem, demonstrar_batch_processing, processar_documento_grande_exemplo
from main import processar_pergunta, get_cache_stats, limpar_cache
import time
import json
from datetime import datetime

def exemplo_batch_1000_perguntas():
    """Exemplo prático: processamento de 1000 perguntas em lotes"""
    
    print("🚀 Exemplo: Processamento de 1000 perguntas técnicas")
    print("=" * 60)
    
    # Perguntas base para gerar variações
    perguntas_base = [
        "O que é a procedure SP_AT_INT_APLICINSUMOAGRIC?",
        "Como funciona a normalização de dados agrícolas?",
        "Qual é a origem dos dados no sistema ERP?",
        "Explique o processo de ETL para insumos",
        "O que são regras de negócio na agricultura?",
        "Como consultar a tabela INT_APLICINSUMOAGRIC?",
        "Qual é a função da procedure de normalização?",
        "Explique o fluxo de dados no SmartBreeder",
        "Como funciona a integração de sistemas?",
        "O que é consolidação de dados agrícolas?"
    ]
    
    # Gerar 1000 perguntas com variações
    perguntas_1000 = []
    for i in range(1000):
        base_idx = i % len(perguntas_base)
        pergunta_variada = f"{perguntas_base[base_idx]} (Variação {i+1})"
        perguntas_1000.append(pergunta_variada)
    
    print(f"📝 Geradas {len(perguntas_1000)} perguntas para processamento")
    
    # Limpar cache para teste limpo
    limpar_cache()
    
    # Configurar processador otimizado
    processor = BatchProcessor(
        batch_size=50,      # Lotes de 50 para balancear memória e velocidade
        max_workers=6,      # 6 threads paralelas
        rate_limit=5.0,     # 5 req/sec para não sobrecarregar API
        enable_caching=True
    )
    
    # Criar itens de lote
    items = [
        BatchItem(
            id=f"pergunta_{i+1:04d}",
            content=pergunta,
            metadata={
                'tipo': 'pergunta_tecnica',
                'indice': i+1,
                'categoria': 'agricultura' if 'agric' in pergunta.lower() else 'dados',
                'prioridade': 1 if i < 100 else 2  # Primeiras 100 com prioridade alta
            },
            priority=1 if i < 100 else 2
        )
        for i, pergunta in enumerate(perguntas_1000)
    ]
    
    print(f"🔧 Configuração do processador:")
    print(f"   - Lotes de: {processor.batch_size} itens")
    print(f"   - Workers: {processor.max_workers}")
    print(f"   - Rate limit: {processor.rate_limit} req/sec")
    print(f"   - Cache: {'Habilitado' if processor.enable_caching else 'Desabilitado'}")
    
    # Medir tempo total
    inicio_total = time.time()
    
    print("\n🔄 Iniciando processamento em lotes...")
    results = processor.process_batch(items)
    
    tempo_total = time.time() - inicio_total
    
    # Resultados e estatísticas
    print("\n📊 RESULTADOS DO PROCESSAMENTO:")
    print("=" * 40)
    
    summary = processor.get_processing_summary()
    for key, value in summary.items():
        print(f"📈 {key}: {value}")
    
    # Estatísticas de cache
    print("\n💾 ESTATÍSTICAS DE CACHE:")
    cache_stats = get_cache_stats()
    for key, value in cache_stats.items():
        print(f"🗄️  {key}: {value}")
    
    # Análise de performance
    print(f"\n⚡ ANÁLISE DE PERFORMANCE:")
    print(f"⏱️  Tempo total: {tempo_total:.2f} segundos")
    print(f"📊 Itens/segundo: {len(items)/tempo_total:.2f}")
    print(f"🎯 Taxa de sucesso: {(summary['successful']/summary['total_processed'])*100:.1f}%")
    
    # Salvar resultados detalhados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"batch_1000_results_{timestamp}.json"
    processor.save_results(results, output_file)
    
    print(f"\n💾 Resultados salvos em: {output_file}")
    
    # Amostra de resultados
    print(f"\n📋 AMOSTRA DOS RESULTADOS (primeiros 3):")
    for i, result in enumerate(results[:3]):
        status = "✅" if result.success else "❌"
        print(f"{status} Item {result.item_id}: {result.processing_time:.3f}s")
        if result.success and result.result:
            resposta = result.result.get('resposta', 'N/A')
            print(f"   Resposta: {resposta[:100]}...")
        print()
    
    return results, summary

def exemplo_documento_estruturado():
    """Exemplo: processar documento estruturado grande"""
    
    print("\n📄 Exemplo: Documento Estruturado com Dados Técnicos")
    print("=" * 60)
    
    # Criar documento com estrutura técnica
    documento_tecnico = "documento_tecnico_estruturado.txt"
    
    with open(documento_tecnico, 'w', encoding='utf-8') as f:
        f.write("DOCUMENTAÇÃO TÉCNICA - SISTEMA DE INTEGRAÇÃO DE DADOS AGRÍCOLAS\n")
        f.write("=" * 80 + "\n\n")
        
        for i in range(200):  # 200 seções
            f.write(f"SEÇÃO {i+1:03d}: PROCEDURE SP_PROCESSO_{i+1:03d}\n")
            f.write("-" * 50 + "\n")
            f.write(f"Objetivo: Processar dados de insumos agrícolas tipo {i % 10 + 1}\n")
            f.write(f"Tabela origem: TEMP_INSUMO_{i+1:03d}\n")
            f.write(f"Tabela destino: INT_INSUMO_{i+1:03d}\n")
            f.write(f"Regras de negócio:\n")
            f.write(f"  - Validar campos obrigatórios\n")
            f.write(f"  - Normalizar códigos de fazenda\n")
            f.write(f"  - Calcular totais agregados\n")
            f.write(f"  - Aplicar regras de cliente específicas\n")
            f.write(f"Parâmetros de entrada:\n")
            f.write(f"  @DataInicio: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"  @DataFim: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"  @CodigoCliente: {i % 50 + 1}\n")
            f.write(f"Status: {'ATIVO' if i % 3 == 0 else 'TESTE'}\n")
            f.write(f"Última atualização: {datetime.now().isoformat()}\n\n")
    
    print(f"📝 Documento técnico criado: {documento_tecnico}")
    
    # Configurar processador para documento estruturado
    processor = BatchProcessor(
        batch_size=25,
        max_workers=4,
        rate_limit=3.0,
        enable_caching=True
    )
    
    # Processar documento
    resultado = processor.process_large_document(
        document_path=documento_tecnico,
        chunk_size=800  # Chunks maiores para preservar estrutura
    )
    
    print(f"\n📊 Processamento do documento:")
    print(f"📄 Chunks: {resultado['total_chunks']}")
    print(f"📊 Caracteres: {resultado['total_characters']:,}")
    print(f"⚙️  Tamanho do chunk: {resultado['chunk_size']}")
    
    summary = resultado['summary']
    print(f"\n📈 Estatísticas:")
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    # Limpar arquivo
    import os
    try:
        os.remove(documento_tecnico)
        print(f"\n🗑️ Arquivo temporário removido")
    except:
        pass
    
    return resultado

def benchmark_performance():
    """Benchmark de performance para diferentes configurações"""
    
    print("\n🏁 BENCHMARK DE PERFORMANCE")
    print("=" * 50)
    
    # Configurações para testar
    configs = [
        {"batch_size": 10, "workers": 2, "rate_limit": 2.0, "name": "Conservador"},
        {"batch_size": 25, "workers": 4, "rate_limit": 3.0, "name": "Balanceado"},
        {"batch_size": 50, "workers": 6, "rate_limit": 5.0, "name": "Agressivo"},
    ]
    
    # Perguntas de teste (100 para benchmark rápido)
    perguntas_teste = [
        f"Explique a procedure de integração número {i+1}"
        for i in range(100)
    ]
    
    resultados_benchmark = []
    
    for config in configs:
        print(f"\n🧪 Testando configuração: {config['name']}")
        print(f"   Batch: {config['batch_size']}, Workers: {config['workers']}, Rate: {config['rate_limit']}")
        
        # Limpar cache para teste justo
        limpar_cache()
        
        # Criar processador
        processor = BatchProcessor(
            batch_size=config['batch_size'],
            max_workers=config['workers'],
            rate_limit=config['rate_limit'],
            enable_caching=True
        )
        
        # Criar itens
        items = [
            BatchItem(id=f"test_{i}", content=pergunta, metadata={})
            for i, pergunta in enumerate(perguntas_teste)
        ]
        
        # Medir tempo
        inicio = time.time()
        results = processor.process_batch(items)
        tempo = time.time() - inicio
        
        summary = processor.get_processing_summary()
        
        resultado_config = {
            'configuracao': config['name'],
            'tempo_total': tempo,
            'itens_por_segundo': len(items) / tempo,
            'taxa_sucesso': (summary['successful'] / summary['total_processed']) * 100,
            'cache_hit_rate': get_cache_stats()['hit_rate_percent']
        }
        
        resultados_benchmark.append(resultado_config)
        
        print(f"   ⏱️  Tempo: {tempo:.2f}s")
        print(f"   📊 Items/sec: {resultado_config['itens_por_segundo']:.2f}")
        print(f"   🎯 Sucesso: {resultado_config['taxa_sucesso']:.1f}%")
    
    # Mostrar comparação
    print(f"\n🏆 COMPARAÇÃO DE PERFORMANCE:")
    print("-" * 60)
    for resultado in resultados_benchmark:
        print(f"{resultado['configuracao']:12} | "
              f"{resultado['tempo_total']:6.2f}s | "
              f"{resultado['itens_por_segundo']:6.2f}/s | "
              f"{resultado['taxa_sucesso']:5.1f}%")
    
    # Identificar melhor configuração
    melhor = max(resultados_benchmark, key=lambda x: x['itens_por_segundo'])
    print(f"\n🥇 Melhor configuração: {melhor['configuracao']} "
          f"({melhor['itens_por_segundo']:.2f} items/sec)")
    
    return resultados_benchmark

if __name__ == "__main__":
    print("🚀 SISTEMA DE BATCH PROCESSING - EXEMPLOS PRÁTICOS")
    print("=" * 70)
    
    # Exemplo 1: 1000 perguntas
    results_1000, summary_1000 = exemplo_batch_1000_perguntas()
    
    # Exemplo 2: Documento estruturado  
    resultado_doc = exemplo_documento_estruturado()
    
    # Exemplo 3: Benchmark
    benchmark_results = benchmark_performance()
    
    print("\n✅ TODOS OS EXEMPLOS CONCLUÍDOS!")
    print("🎯 O sistema está otimizado para processamento em larga escala")
    print("💡 Use as configurações do benchmark para ajustar performance")