# Avaliação dos modelos — CogniFlow AI (plano 03, Etapa 7)

Este documento registra a avaliação do tutor de aula com os modelos reais, executados localmente pelo Ollama: o mapa mental gerado por map-reduce e o tira-dúvidas por RAG. Ele justifica duas decisões de configuração:

- **LLM padrão:** `qwen2.5:3b` (no lugar do `llama3.2:3b`).
- **Limiar do tutor (`TUTOR_MIN_SIMILARITY`):** `0.47`.

A avaliação também encontrou cinco defeitos que os testes com LLM falso não detectavam. Todos foram corrigidos antes da rodada final (ver [Achados](#achados-e-correções)).

## Resumo — rodada final

| Métrica | `llama3.2:3b` | `qwen2.5:3b` |
|---|---|---|
| Mapas gerados (de 3 documentos) | 3 | 3 |
| Recall de entidades — PDF de fotossíntese | 0,75 | **1,00** (igual nas 3 repetições extras) |
| Rótulos sustentados pelos trechos citados (média) | 0,67 | **0,78** |
| Erros estruturais nos mapas | 0 | 0 |
| Tutor — perguntas respondíveis corretas (de 10) | 9 | **10** |
| Tutor — perguntas fora do material recusadas (de 5) | 5 | 5 |
| JSON válido na 1ª tentativa — organização dos eixos | 0,67 | **1,00** |
| JSON válido na 1ª tentativa — todas as tarefas | 0,91 | 0,91 |
| Aderência ao perfil de acessibilidade — mapa | 0,92 | **0,97** |
| Aderência ao perfil de acessibilidade — tutor | 0,91 | **1,00** |
| Tempo médio para gerar um mapa | 125 s | **93 s** |
| Tempo de uma resposta do tutor (mediana / p90) | 30 s / 43 s | **22 s / 42 s** |

O `qwen2.5:3b` venceu ou empatou em todas as métricas de qualidade e é mais rápido. Ele organizou os eixos sem nenhuma correção e cobriu todos os conceitos de referência da aula de fotossíntese em 4 de 4 execuções. Por isso passou a ser o modelo padrão.

O erro do `llama3.2:3b` no tutor foi citar a página errada em "Qual gás é liberado na fotossíntese?". Ele também escreveu "oxigénio", com a grafia de Portugal.

## Como a avaliação foi feita

- **Execução:** `cd backend && ./.venv/bin/python -m evaluation --models llama3.2:3b qwen2.5:3b --academic 2`, em 05/11/2026. O resultado bruto da rodada final está em `backend/evaluation/results/evaluation-20261105-232648.json`. As rodadas anteriores às correções estão em `backend/evaluation/results/superseded/`.
- **Ambiente:** CPU com 12 núcleos, sem GPU, 15 GB de RAM livres; Ollama em Docker. O banco é um PostgreSQL + pgvector descartável (Testcontainers); o banco local não é usado.
- **Embeddings:** `bge-m3` (1024 dimensões), iguais para os dois modelos.
- **Mapa mental:** o PDF `fotossintese-texto-selecionavel.pdf` (3 páginas) e 2 apostilas sintéticas da suíte acadêmica (biologia celular e termodinâmica, em inglês). Para cada documento: ingestão, extração por seção, deduplicação, organização e validação do grafo. O mapa da fotossíntese foi gerado mais 3 vezes com o `qwen2.5:3b` para medir a estabilidade.
- **Tutor:** 15 perguntas sobre o PDF de fotossíntese (`backend/evaluation/datasets.py`):
  - 10 que o material responde, cada uma com a página esperada e palavras-chave da resposta;
  - 5 que ele não responde. Uma delas é do mesmo assunto ("Quem descobriu a fotossíntese?") e as outras quatro são de outros assuntos.
- **Critério de acerto do tutor:**
  - para pergunta respondível, o tutor precisa responder, citar a página certa e trazer na resposta uma das palavras-chave;
  - para pergunta fora do material, precisa responder *"Não encontrei isso no material da aula."*

### Métricas

- **JSON válido na 1ª tentativa:** fração das chamadas estruturadas aceitas sem correção (schema e regras semânticas, como trechos citados existentes).
- **Recall de entidades:** fração das entidades de referência presentes nos rótulos e resumos do mapa, sem diferenciar singular/plural nem acentos.
- **Rótulos sustentados pelos trechos citados:** fração dos conceitos e exemplos cujas palavras do rótulo aparecem nos trechos que o nó cita. É uma verificação simples contra conceitos inventados.
- **Aderência ao perfil de acessibilidade:** fração dos textos gerados (resumos e respostas) que passam em três verificações heurísticas:
  - todas as frases com até 20 palavras;
  - nenhuma pergunta retórica;
  - nenhuma de uma lista de expressões figuradas comuns ("fábrica da célula", "coração do processo").

  É uma aproximação, não uma avaliação clínica.

## Limiar do tutor

As similaridades (cosseno, `bge-m3`) entre a pergunta e o trecho mais parecido do material se dividem em três grupos:

| Grupo | Similaridade |
|---|---|
| Perguntas respondíveis | 0,625 a 0,751 |
| Fora do material, mesmo assunto ("Quem descobriu a fotossíntese?") | 0,568 |
| Fora do material, outros assuntos | 0,300 a 0,433 |

Nenhum limiar separa a pergunta "Quem descobriu…" das respondíveis com folga: quem precisa recusá-la é o modelo, e os dois modelos recusaram nas três rodadas. O papel do limiar é só **evitar chamar o LLM para perguntas claramente fora do assunto**, e ele nunca deve bloquear uma pergunta válida, porque isso é pior para o aluno do que uma chamada a mais.

Regra adotada: o limiar fica 0,15 abaixo da pergunta respondível menos parecida, ou seja 0,625 − 0,15 = 0,475, arredondado para **0,47**. Com esse valor:

- as 4 perguntas de outros assuntos são recusadas sem chamar o LLM;
- todas as respondíveis passam;
- o acerto não muda em relação a usar só o modelo: 15/15 no `qwen2.5:3b` e 14/15 no `llama3.2:3b`.

## Achados e correções

Cada defeito abaixo foi encontrado por uma rodada com os modelos reais, corrigido e coberto por um teste rápido de regressão. A ordem é a cronológica.

| # | Achado | Efeito | Correção |
|---|---|---|---|
| 1 | A simplificação do JSON Schema removia todas as chaves `title`, inclusive o campo `title` dos eixos | **100% dos mapas falhavam**, nos dois modelos | Só as anotações (`title` com valor texto) são removidas (`structured_output.py`) |
| 2 | A calibração desempatava pela maior distância e escolhia "sem limiar" | Limiar inútil | Regra da margem de segurança (acima) |
| 3 | A seção BIBLIOGRAFIA era agrupada com a última seção e virava conceitos ("YouTube", "Fontes de informação") | Mapas com conteúdo que não é de estudo | Seções de referências ficam fora do mapa; o tutor ainda pode citá-las (`units.py`) |
| 4 | O recall não reconhecia "Cloroplasto" como "Cloroplastos" | Métrica subestimava os mapas | Comparação sem diferenciar singular/plural e acentos (`evaluation_metrics.py`) |
| 5 | Na organização, o modelo descartava conceitos centrais (Cloroplasto, Clorofila, Glicose) e mantinha periféricos | Recall de 0,50 a 0,75 com o `qwen2.5:3b` | Os conceitos deixados de fora são encaixados no eixo mais parecido (similaridade `bge-m3`), até 5 por eixo (`pipeline.py`) |
| 6 | Exigir que o modelo cumprisse todas as regras da organização — todos os conceitos, nenhum repetido, de 3 a 5 eixos — falhava | A 3B não acerta tudo ao mesmo tempo; cada correção quebra outra regra; até 3/3 mapas falhavam | Conceito repetido fica no primeiro eixo; eixo vazio é removido; documentos curtos aceitam menos eixos (`min(3, conceitos ÷ 2)`). Continuam rejeitados: identificador inexistente, título igual a um conceito e mais de 5 eixos |

O princípio do plano 03 se manteve em todas as correções: **a IA gera o conteúdo e o código garante a forma**. Nenhuma correção gera rótulos ou resumos; elas só filtram a entrada (achado 3) ou reorganizam a saída do modelo com critérios fixos (achados 5 e 6).

### Outras observações

- **Exemplo do prompt copiado nas citações:** os modelos às vezes citam o "Trecho 4" do exemplo do prompt do tutor quando esse trecho não foi recuperado. A validação detecta e a correção resolve (2 correções por modelo na rodada final).
- **Fórmulas confundidas com títulos:** no chunking, uma linha que começa com número (`3 CO₂ + 6 H₂O → …`) é reconhecida como título de seção. O mapa não é afetado, mas o título aparece estranho nas citações.
- **Repetições que a deduplicação não une:** "Glicose" e "Glucose" (em inglês) podem aparecer juntos, porque a similaridade entre eles fica abaixo de 0,85.
- **Latência em CPU:** um mapa leva 1,5 a 3 minutos para um PDF de 3 páginas, e uma resposta do tutor de 20 a 45 s. Rodadas anteriores tiveram picos de até 5 minutos numa resposta isolada, provavelmente pela troca dos modelos na memória.

## Limitações

- **Amostra pequena:** 15 perguntas e 3 documentos. Os números indicam tendência e não têm valor estatístico. Um modelo de 3B não é determinístico; para limitar esse efeito, o mapa da fotossíntese foi repetido 4 vezes.
- **Recall injusto nas apostilas em inglês:** as apostilas sintéticas estão em inglês e o prompt pede rótulos em português ("Mitocôndria" × "Mitochondria"). O recall delas não mede a qualidade.
- **Heurísticas de acessibilidade:** não substituem a avaliação com estudantes com TDAH e TEA.
- **Linha de base anterior não comparável:** o recall de 100% do plano 02 foi medido com o gerador heurístico (sem LLM) sobre apostilas no formato `Conceito: explicação`, e não é comparável com estes números.

## Próximos passos recomendados

1. **Exemplo do prompt do tutor:** usar um número de trecho que nunca é recuperado no exemplo, para eliminar as citações copiadas.
2. **Detecção de títulos no chunking:** não considerar título uma linha com fórmula química ou setas.
3. **Deduplicação entre idiomas:** comparar também a forma normalizada dos rótulos ("glicose"/"glucose") ou pedir rótulos sempre em português do Brasil.
4. **Conjunto de avaliação maior e em português:** mais aulas reais e mais perguntas, incluindo perguntas de continuação (com histórico) e sobre conceitos do mapa.
5. **Latência:** testar com GPU e considerar *streaming* da resposta do tutor, para reduzir a espera percebida.

## Como reproduzir

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama pull llama3.2:3b
cd backend
./.venv/bin/python -m evaluation --models llama3.2:3b qwen2.5:3b --academic 2   # comparação (~45 min em CPU)
./.venv/bin/pytest -m llm tests/test_llm_quality.py                            # limites mínimos com o modelo padrão
```
