# Problema de Quota da API Google Gemini

## O que aconteceu?
Você excedeu a cota gratuita da API do Google Gemini para embeddings. O erro indica:
- **Quota exceeded for metric**: `generativelanguage.googleapis.com/embed_content_free_tier_requests`
- **Limite**: 0 (cota diária esgotada)

## Soluções Implementadas
✅ **Sistema de Busca Textual**: Quando embeddings não estão disponíveis, o sistema agora usa busca por texto simples nos documentos carregados.

✅ **Modo Fallback Inteligente**: Mantém funcionalidade mesmo sem acesso aos embeddings.

## Opções para Resolver
1. **Aguardar Reset Diário**: A cota gratuita renova automaticamente a cada 24h
2. **Upgrade para Plano Pago**: Considere um plano pago da Google AI para usar sem limitações
3. **API Key Alternativa**: Use uma API key diferente se disponível

## Funcionamento Atual
- ✅ Sistema continua operacional
- ✅ Busca textual nos documentos carregados
- ✅ Respostas baseadas no conteúdo dos PDFs e Markdown
- ⚠️ Menor precisão comparado ao sistema de embeddings

## Para Monitorar
- Verifique se a cota renovou no próximo dia
- Monitore uso da API em: https://ai.google.dev/gemini-api/docs/rate-limits