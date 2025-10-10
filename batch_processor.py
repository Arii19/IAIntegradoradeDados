"""
Sistema de Batch Processing para processamento em larga escala de documentos
Implementa processamento em lotes otimizado para milhares de documentos
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import json
import os
from threading import Lock
import queue
import threading

from main import processar_pergunta, get_llm, retriever
from langchain_core.messages import HumanMessage

# Configuração de logging específica para batch processing
batch_logger = logging.getLogger("batch_processor")
batch_logger.setLevel(logging.INFO)

@dataclass
class BatchItem:
    """Item individual para processamento em lote"""
    id: str
    content: str
    metadata: Dict[str, Any]
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class BatchResult:
    """Resultado do processamento de um item"""
    item_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    processing_time: float = 0.0
    timestamp: str = ""

class BatchProcessor:
    """Processador em lotes otimizado para grande volume de documentos"""
    
    def __init__(self, 
                 batch_size: int = 50,
                 max_workers: int = 4,
                 rate_limit: float = 1.0,  # Requisições por segundo
                 enable_caching: bool = True):
        """
        Inicializa o processador em lotes
        
        Args:
            batch_size: Tamanho do lote para processamento
            max_workers: Número máximo de threads
            rate_limit: Limite de requisições por segundo
            enable_caching: Habilitar cache de resultados
        """
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.rate_limit = rate_limit
        self.enable_caching = enable_caching
        
        # Cache e controle de estado
        self.cache = {} if enable_caching else None
        self.cache_lock = Lock()
        
        # Controle de rate limiting
        self.last_request_time = 0
        self.rate_lock = Lock()
        
        # Estatísticas
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'cache_hits': 0,
            'total_time': 0.0,
            'start_time': None
        }
        
        # Fila de processamento
        self.processing_queue = queue.Queue()
        self.results_queue = queue.Queue()
        
        batch_logger.info(f"BatchProcessor inicializado: batch_size={batch_size}, workers={max_workers}")

    def _apply_rate_limit(self):
        """Aplica rate limiting para evitar sobrecarga da API"""
        if self.rate_limit <= 0:
            return
            
        with self.rate_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            min_interval = 1.0 / self.rate_limit
            
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()

    def _get_cache_key(self, content: str) -> str:
        """Gera chave única para cache baseada no conteúdo"""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()

    def _check_cache(self, content: str) -> Optional[Any]:
        """Verifica se resultado está em cache"""
        if not self.enable_caching:
            return None
            
        cache_key = self._get_cache_key(content)
        with self.cache_lock:
            if cache_key in self.cache:
                self.stats['cache_hits'] += 1
                batch_logger.debug(f"Cache hit para item: {cache_key[:8]}...")
                return self.cache[cache_key]
        return None

    def _store_cache(self, content: str, result: Any):
        """Armazena resultado no cache"""
        if not self.enable_caching:
            return
            
        cache_key = self._get_cache_key(content)
        with self.cache_lock:
            self.cache[cache_key] = result

    def _process_single_item(self, item: BatchItem) -> BatchResult:
        """Processa um único item"""
        start_time = time.time()
        
        try:
            # Verificar cache primeiro
            cached_result = self._check_cache(item.content)
            if cached_result is not None:
                return BatchResult(
                    item_id=item.id,
                    success=True,
                    result=cached_result,
                    processing_time=time.time() - start_time,
                    timestamp=datetime.now().isoformat()
                )
            
            # Aplicar rate limiting
            self._apply_rate_limit()
            
            # Processar item usando o sistema principal
            result = processar_pergunta(item.content)
            
            # Armazenar no cache
            self._store_cache(item.content, result)
            
            return BatchResult(
                item_id=item.id,
                success=True,
                result=result,
                processing_time=time.time() - start_time,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            batch_logger.error(f"Erro ao processar item {item.id}: {str(e)}")
            return BatchResult(
                item_id=item.id,
                success=False,
                result=None,
                error=str(e),
                processing_time=time.time() - start_time,
                timestamp=datetime.now().isoformat()
            )

    def _process_batch_worker(self, batch: List[BatchItem]) -> List[BatchResult]:
        """Worker que processa um lote de itens"""
        results = []
        
        for item in batch:
            result = self._process_single_item(item)
            results.append(result)
            
            # Atualizar estatísticas
            self.stats['total_processed'] += 1
            if result.success:
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1
                
            batch_logger.debug(f"Processado item {item.id}: {'✓' if result.success else '✗'}")
        
        return results

    def process_large_document(self, 
                             document_path: str, 
                             chunk_size: int = 1000,
                             processing_function: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Processa um documento grande dividindo em chunks
        
        Args:
            document_path: Caminho para o documento
            chunk_size: Tamanho de cada chunk em caracteres
            processing_function: Função customizada de processamento
        """
        
        batch_logger.info(f"Iniciando processamento de documento grande: {document_path}")
        
        # Ler documento
        document_path = Path(document_path)
        if not document_path.exists():
            raise FileNotFoundError(f"Documento não encontrado: {document_path}")
        
        with open(document_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Dividir em chunks
        chunks = []
        total_chars = len(content)
        
        for i in range(0, total_chars, chunk_size):
            chunk_text = content[i:i + chunk_size]
            chunk_id = f"chunk_{i//chunk_size + 1}"
            
            chunks.append(BatchItem(
                id=chunk_id,
                content=chunk_text,
                metadata={
                    'source_file': str(document_path),
                    'chunk_start': i,
                    'chunk_end': min(i + chunk_size, total_chars),
                    'chunk_number': i//chunk_size + 1,
                    'total_chunks': (total_chars + chunk_size - 1) // chunk_size
                }
            ))
        
        batch_logger.info(f"Documento dividido em {len(chunks)} chunks de ~{chunk_size} caracteres")
        
        # Processar chunks em lotes
        results = self.process_batch(chunks, processing_function)
        
        # Compilar resultado final
        return {
            'document_path': str(document_path),
            'total_chunks': len(chunks),
            'total_characters': total_chars,
            'chunk_size': chunk_size,
            'results': results,
            'summary': self.get_processing_summary()
        }

    def process_batch(self, 
                     items: List[BatchItem], 
                     processing_function: Optional[Callable] = None) -> List[BatchResult]:
        """
        Processa uma lista de itens em lotes
        
        Args:
            items: Lista de itens para processar
            processing_function: Função customizada de processamento
        """
        
        self.stats['start_time'] = datetime.now()
        batch_logger.info(f"Iniciando processamento em lotes: {len(items)} itens")
        
        # Dividir em lotes
        batches = [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
        batch_logger.info(f"Criados {len(batches)} lotes de até {self.batch_size} itens")
        
        all_results = []
        
        # Processar lotes em paralelo
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submeter todos os lotes
            future_to_batch = {
                executor.submit(self._process_batch_worker, batch): i 
                for i, batch in enumerate(batches)
            }
            
            # Coletar resultados conforme completam
            for future in as_completed(future_to_batch):
                batch_num = future_to_batch[future]
                try:
                    batch_results = future.result()
                    all_results.extend(batch_results)
                    
                    batch_logger.info(f"Lote {batch_num + 1}/{len(batches)} concluído "
                                    f"({len(batch_results)} itens)")
                    
                except Exception as e:
                    batch_logger.error(f"Erro no lote {batch_num}: {str(e)}")
        
        self.stats['total_time'] = (datetime.now() - self.stats['start_time']).total_seconds()
        batch_logger.info(f"Processamento concluído: {len(all_results)} resultados")
        
        return all_results

    def process_directory(self, 
                         directory_path: str, 
                         file_pattern: str = "*.txt",
                         max_files: Optional[int] = None) -> Dict[str, Any]:
        """
        Processa todos os arquivos de um diretório
        
        Args:
            directory_path: Caminho do diretório
            file_pattern: Padrão de arquivos para processar
            max_files: Número máximo de arquivos (None = todos)
        """
        
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory}")
        
        # Encontrar arquivos
        files = list(directory.glob(file_pattern))
        if max_files:
            files = files[:max_files]
        
        batch_logger.info(f"Encontrados {len(files)} arquivos para processar")
        
        # Criar itens de lote
        items = []
        for i, file_path in enumerate(files):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                items.append(BatchItem(
                    id=f"file_{i+1}_{file_path.name}",
                    content=content,
                    metadata={
                        'source_file': str(file_path),
                        'file_size': file_path.stat().st_size,
                        'file_number': i + 1,
                        'total_files': len(files)
                    }
                ))
            except Exception as e:
                batch_logger.error(f"Erro ao ler arquivo {file_path}: {str(e)}")
        
        # Processar arquivos
        results = self.process_batch(items)
        
        return {
            'directory_path': str(directory),
            'file_pattern': file_pattern,
            'files_found': len(files),
            'files_processed': len(items),
            'results': results,
            'summary': self.get_processing_summary()
        }

    def get_processing_summary(self) -> Dict[str, Any]:
        """Retorna resumo das estatísticas de processamento"""
        return {
            'total_processed': self.stats['total_processed'],
            'successful': self.stats['successful'],
            'failed': self.stats['failed'],
            'success_rate': (self.stats['successful'] / max(self.stats['total_processed'], 1)) * 100,
            'cache_hits': self.stats['cache_hits'],
            'cache_hit_rate': (self.stats['cache_hits'] / max(self.stats['total_processed'], 1)) * 100,
            'total_time': self.stats['total_time'],
            'avg_time_per_item': self.stats['total_time'] / max(self.stats['total_processed'], 1),
            'items_per_second': self.stats['total_processed'] / max(self.stats['total_time'], 0.001)
        }

    def save_results(self, results: List[BatchResult], output_path: str):
        """Salva resultados em arquivo JSON"""
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': self.get_processing_summary(),
            'results': [
                {
                    'item_id': r.item_id,
                    'success': r.success,
                    'result': r.result,
                    'error': r.error,
                    'processing_time': r.processing_time,
                    'timestamp': r.timestamp
                }
                for r in results
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        batch_logger.info(f"Resultados salvos em: {output_path}")


# Exemplo de uso e demonstração
def demonstrar_batch_processing():
    """Demonstra o uso do sistema de batch processing"""
    
    # Criar processador
    processor = BatchProcessor(
        batch_size=10,
        max_workers=3,
        rate_limit=2.0,  # 2 requisições por segundo
        enable_caching=True
    )
    
    # Exemplo 1: Processar lista de perguntas
    perguntas_exemplo = [
        "O que é a procedure SP_AT_INT_APLICINSUMOAGRIC?",
        "Como funciona a normalização de dados?",
        "Qual é a origem dos dados no sistema?",
        "Explique o processo de ETL",
        "O que são regras de negócio?",
        "Como consultar a tabela INT_APLICINSUMOAGRIC?",
        "Qual é a função da procedure de normalização?",
        "Explique o fluxo de dados agrícolas",
        "Como funciona a integração de sistemas?",
        "O que é consolidação de dados?"
    ]
    
    # Criar itens de lote
    items = [
        BatchItem(
            id=f"pergunta_{i+1}",
            content=pergunta,
            metadata={'tipo': 'pergunta_tecnica', 'indice': i}
        )
        for i, pergunta in enumerate(perguntas_exemplo)
    ]
    
    print("🔄 Iniciando demonstração de Batch Processing...")
    print(f"📊 Processando {len(items)} itens em lotes de {processor.batch_size}")
    
    # Processar
    results = processor.process_batch(items)
    
    # Mostrar resultados
    print("\n📈 Resumo do Processamento:")
    summary = processor.get_processing_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Salvar resultados
    output_file = "batch_results.json"
    processor.save_results(results, output_file)
    
    print(f"\n💾 Resultados salvos em: {output_file}")
    
    return results


# Função para processar documento grande (exemplo com 1000 iterações)
def processar_documento_grande_exemplo():
    """Exemplo de processamento de documento grande com iterações"""
    
    # Criar documento de exemplo com conteúdo repetitivo
    print("📝 Criando documento de exemplo com 1000 iterações...")
    
    conteudo_base = """
    A procedure SP_AT_INT_APLICINSUMOAGRIC normaliza dados de aplicação de insumos agrícolas.
    Esta procedure processa informações da tabela temporária TEMP_DES_APLICINSUMOAGRIC.
    O objetivo é garantir a qualidade e consistência dos dados para integração.
    """
    
    # Gerar documento grande
    documento_exemplo = "documento_grande_exemplo.txt"
    with open(documento_exemplo, 'w', encoding='utf-8') as f:
        for i in range(1000):
            f.write(f"\n--- Iteração {i+1} ---\n")
            f.write(conteudo_base)
            f.write(f"\nID da iteração: {i+1}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
    
    print(f"✅ Documento criado: {documento_exemplo}")
    
    # Criar processador otimizado para documento grande
    processor = BatchProcessor(
        batch_size=20,  # Lotes maiores para eficiência
        max_workers=4,
        rate_limit=3.0,
        enable_caching=True
    )
    
    # Processar documento
    print("🔄 Processando documento grande...")
    resultado = processor.process_large_document(
        document_path=documento_exemplo,
        chunk_size=500  # Chunks de 500 caracteres
    )
    
    print("\n📊 Resultado do processamento:")
    print(f"  Chunks processados: {resultado['total_chunks']}")
    print(f"  Caracteres totais: {resultado['total_characters']}")
    
    # Mostrar resumo
    summary = resultado['summary']
    print("\n📈 Estatísticas:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Limpar arquivo de exemplo
    try:
        os.remove(documento_exemplo)
        print(f"\n🗑️ Arquivo temporário removido: {documento_exemplo}")
    except:
        pass
    
    return resultado


if __name__ == "__main__":
    print("🚀 Sistema de Batch Processing para Documentos")
    print("=" * 50)
    
    # Demonstrar funcionalidades
    demonstrar_batch_processing()
    
    print("\n" + "=" * 50)
    print("📄 Teste com Documento Grande (1000 iterações)")
    print("=" * 50)
    
    processar_documento_grande_exemplo()
    
    print("\n✅ Demonstração concluída!")