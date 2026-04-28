# Desafio Técnico - Squad WhatsApp

## 🎯 Objetivo
Otimizar a inteligência de escolha de telefones para disparos de WhatsApp, mitigando o problema de multiplicidade de registros no Registro Municipal Integrado (RMI) da Prefeitura do Rio. O objetivo central é garantir maior taxa de entrega, eficiência de custos e otimização das janelas de comunicação com o cidadão.

## 📊 Principais Insights

### 1. Análise de Qualidade e Decaimento
Ao contrário da hipótese inicial de que dados mais antigos seriam menos confiáveis, a análise de decaimento revelou um cenário crítico:
* **Problema Sistêmico:** A taxa de telefones com qualidade "BAIXA" é superior a 93% em **todas** as faixas etárias de registro (de 0 a 30 anos).
* **Conclusão:** O problema não é o tempo de vida do dado, mas uma falha sistêmica na origem da coleta/validação. A estratégia de atualização de dados não deve ser focada apenas em "limpar dados antigos", mas em revisar o processo de entrada de novos dados no sistema.

### 2. Ranking de Confiabilidade
Desenvolvi um `indice_confiabilidade` ponderado, onde sistemas com maior penetração de telefones validados ("ALTA" qualidade) recebem maior peso. 
* **Metodologia:** O índice foi calculado como: `(ALTA * 1.0) + (MEDIA * 0.5) - (BAIXA * 0.5)`. 
* Isso penaliza sistemas que entregam massivamente números inválidos, priorizando fontes que comprovadamente convertem em entregas (`DELIVERED`).

## ⚙️ Metodologia do Algoritmo de Escolha
Para a seleção dos 2 melhores telefones por CPF, implementei um sistema de scoring vetorial:
1. **Origem (50% do score):** Baseado na confiabilidade histórica do sistema.
2. **Recência (30% do score):** Priorização de dados mais recentes para minimizar o *churn* de telefones.
3. **Aderência (20% do score):** Priorização de telefones com DDD compatível ao perfil de residência do cidadão, aumentando a probabilidade de contato bem-sucedido.

## 🚀 Proposta de Teste A/B
Para validar a nova estratégia, proponho um experimento controlado:
* **Hipótese:** O novo ranking de confiabilidade aumentará a taxa de *Delivered* em relação ao envio aleatório atual.
* **Grupo A (Controle):** Estratégia atual (envio aleatório).
* **Grupo B (Teste):** Seleção dos 2 melhores telefones baseada no score ponderado.
* **Métrica Primária:** Taxa de Entrega (Delivered Rate).
* **Métrica Secundária:** Redução de custo operacional (economia gerada ao evitar disparos em números inválidos).

## 🛠 Como reproduzir
1. Instale as dependências: `pip install -r requirements.txt`
2. Configure os caminhos dos arquivos `.parquet` no script `src/Pipeline.py`.
3. Execute: `python src/Pipeline.py`
