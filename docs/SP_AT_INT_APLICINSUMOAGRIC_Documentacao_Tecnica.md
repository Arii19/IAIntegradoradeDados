# SP_AT_INT_APLICINSUMOAGRIC - Documentação Técnica Completa

## Visão Geral da Procedure

**Nome:** `int.SP_AT_INT_APLICINSUMOAGRIC`  
**Tipo:** Stored Procedure SQL Server (T-SQL)  
**Função:** Normalização e consolidação de dados de aplicações de insumos agrícolas  
**Processo ETL:** Fase Transform/Load

---

## A. Objetivo da Procedure

A procedure `int.SP_AT_INT_APLICINSUMOAGRIC` é responsável por **normalizar** os dados relacionados a aplicações de insumos agrícolas.

**Normalização de Banco de Dados:** Processo de design que organiza os dados em tabelas para:
- Minimizar redundância
- Eliminar dependências inconsistentes  
- Evitar anomalias (problemas de inserção, exclusão e atualização de dados)

---

## B. Origem dos Dados

### Fontes Primárias:
- **ERP (Enterprise Resource Planning):** Sistema integrado que gerencia processos empresariais (finanças, vendas, compras, estoque, RH)
- **Ferramentas de controle agrícola:** Sistemas específicos da usina de cana-de-açúcar

### Características das Fontes:
- Dados **não normalizados**
- Múltiplas origens possíveis
- Dependente da infraestrutura do cliente

---

## C. Base de Conhecimento e Regras Pré-definidas

### Procedure Predecessor: `int.SP_DES_INT_APLICINSUMOAGRIC`
- Aplica **regras de negócio padronizadas** independente do cliente
- Gera tabela temporária: `INT.TEMP_DES_APLICINSUMOAGRIC`
- Fornece base de conhecimento geral (sem particularidades por cliente)

---

## D. Processamento e Transformação

### Fluxo Principal:
```
INT.TEMP_DES_APLICINSUMOAGRIC → SP_AT_INT_APLICINSUMOAGRIC → INT.INT_APLICINSUMOAGRIC
```

### Objetivo Final:
- Dados **limpos, consistentes e normalizados**
- Regras de negócio específicas por cliente aplicadas
- Preparação para integração com tabelas finais

---

## Passo a Passo Detalhado

### 1. Recriação da Tabela
```sql
-- Se existe, apaga a tabela
DROP TABLE IF EXISTS INT.INT_APLICINSUMOAGRIC

-- Recria usando SELECT INTO
SELECT * INTO INT.INT_APLICINSUMOAGRIC 
FROM INT.TEMP_DES_APLICINSUMOAGRIC
```

### 2. Fontes de Dados
- **Principal:** `INT.TEMP_DES_APLICINSUMOAGRIC`
- **Complementar:** `dbo.TBLF_TRANSFERE_FAZENDAS` (mapeamento empresa origem → destino)

### 3. Identificação da Usina
```sql
-- Campo SE_USINA
SE_USINA = 'INTEGRADO:' + COALESCE(empresa_destino, empresa_original)
```

### 4. Tratamento de Insumos Sazonais (RES.90 / RES.60)

#### Insumos Específicos: `3502950` e `3504995` (herbicidas residuais)

| Período | Sufixo | Meses |
|---------|--------|-------|
| **RES.90** | Set-Out | Setembro a Outubro |
| **RES.60** | Nov-Ago | Novembro a Agosto |

```sql
-- Exemplo de implementação
CASE 
    WHEN CD_INSUMO IN (3502950, 3504995) 
         AND MONTH(DATAAPLICFINAL) IN (9,10) 
    THEN DESCRICAOINSUMO + '.RES.90'
    
    WHEN CD_INSUMO IN (3502950, 3504995) 
         AND MONTH(DATAAPLICFINAL) IN (11,12,1,2,3,4,5,6,7,8) 
    THEN DESCRICAOINSUMO + '.RES.60'
    
    ELSE DESCRICAOINSUMO
END
```

#### Exemplo Prático:
```
DATAFINAL    CD_INSUMO    DESCRICAOINSUMO
2025-09-15   3502950      HERBICIDA.RES.90
2025-12-10   3504995      HERBICIDA.RES.60  
2025-05-20   1234567      HERBICIDA
```

### 5. Tratamento de Campos Nulos

#### Campos Principais:
- `SE_INSUMO`, `DESCRICAOINSUMO`, `SIGLAINSUMO`, `ABREVIACAOINSUMO`, `GRUPOINSUMO`

#### Campos de Unidade:
- `UNIDADEINSUMO`, `UNIDADEDOSAGEM`

#### Valores Padrão por Tipo:
```sql
-- Adubação
IF ISNULL(campo) THEN 'ADUBACAO', 'KG'

-- Torta de filtro  
IF ISNULL(campo) THEN 'TORTAFILTRO', 'KG'
```

### 6. Tratamento de Quantidade e Dosagem
```sql
-- Evitar zeros
QUANTIDADE = CASE WHEN QUANTIDADE = 0 THEN 1 ELSE QUANTIDADE END
DOSAGEM = CASE WHEN DOSAGEM = 0 THEN 1 ELSE DOSAGEM END
```

### 7. Tipos de Operações Agrícolas

| Tipo | Critério | Tratamento | Unidade |
|------|----------|------------|---------|
| **Aplicação Geral** | `TABELA = 'APT_INS_HE'` | Herbicidas/defensivos | - |
| **Adubação** | `CD_OPERACAO` in lista_adubacao | `ADUBACAO` | `KG` |
| **Cotesia** | Lista específica | `COTESIA` | `KG` |
| **Torta de Filtro** | Lista específica | `TORTAFILTRO` | `KG` |
| **Vinhaça** | Lista específica | `VINHACA` | `KG` |

### 8. Chave Única e Relacionamentos

#### Chave Primária:
- `SE_APLICINSUMOAGRIC` (às vezes concatenado com `SEQ`)

#### Relacionamento:
- **1:N** entre `SE_APLICINSUMOAGRIC` e `SE_TALHAO`
- Um aplicação pode ter múltiplos talhões
- Combinação `SE_APLICINSUMOAGRIC` + `SE_TALHAO` deve ser única

### 9. Controle de Datas e Safra

#### Campo Principal: `DATAFINAL`
- Determina regras **RES.90 / RES.60**
- Controle de safra via relacionamento com `SE_TALHAO`
- Validação: `DATAFINAL` entre período início/fim safra do talhão

### 10. Resultado Final

#### Tabela: `INT.INT_APLICINSUMOAGRIC`
**Características:**
- ✅ Dados limpos e padronizados
- ✅ Sem nulos ou zeros problemáticos  
- ✅ Insumos sazonais corretos (RES.60/RES.90)
- ✅ Operações unificadas em modelo único
- ✅ Pronta para fase **Load** do ETL

---

## Glossário Técnico

| Termo | Definição |
|-------|-----------|
| **ETL** | Extract, Transform, Load - Processo de integração de dados |
| **Normalização** | Organização de dados para eliminar redundância |
| **ERP** | Sistema integrado de gestão empresarial |
| **T-SQL** | Linguagem SQL do SQL Server |
| **Procedure** | Conjunto de comandos SQL armazenados |
| **RES.60/RES.90** | Sufixos sazonais para herbicidas residuais |
| **1:N** | Relacionamento um-para-muitos |

---

## Arquitetura de Dados

```
[ERP/Sistema Agrícola] 
        ↓
[SP_DES_INT_APLICINSUMOAGRIC] 
        ↓
[TEMP_DES_APLICINSUMOAGRIC]
        ↓  
[SP_AT_INT_APLICINSUMOAGRIC] ← [TBLF_TRANSFERE_FAZENDAS]
        ↓
[INT_APLICINSUMOAGRIC]
        ↓
[Tabelas Finais para Software]
```

---

## Casos de Uso Comuns

### 1. Consulta de Aplicações por Período
```sql
SELECT * FROM INT.INT_APLICINSUMOAGRIC 
WHERE DATAFINAL BETWEEN '2025-09-01' AND '2025-10-31'
```

### 2. Filtro por Tipo de Insumo
```sql
SELECT * FROM INT.INT_APLICINSUMOAGRIC 
WHERE DESCRICAOINSUMO LIKE '%.RES.90%'
```

### 3. Análise por Usina
```sql
SELECT SE_USINA, COUNT(*) as total_aplicacoes
FROM INT.INT_APLICINSUMOAGRIC 
GROUP BY SE_USINA
```

---

*Documentação técnica gerada para otimizar compreensão por sistemas de IA e desenvolvedores.*