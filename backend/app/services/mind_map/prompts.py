"""Prompts for the map-reduce mind map, in Portuguese (the language of the material).

Small (3B) models follow instructions better in the language of the content and with
short concrete examples. Etapa 5 reorganizes these blocks into accessibility profiles.
"""

from collections.abc import Sequence

from app.services.mind_map.units import MapUnit

GROUNDING_RULES = """REGRAS DE FIDELIDADE AO MATERIAL:
- Use SOMENTE informações escritas no material fornecido.
- NUNCA invente fatos, conceitos, exemplos, datas ou siglas que não estejam no material.
- Ignore metadados: nomes de autores, títulos de professor (Prof., Dr.), números de página, URLs e listas de bibliografia."""

NEURODIVERGENT_RULES = """REGRAS DE ACESSIBILIDADE (alunos com TDAH e TEA):
- Linguagem literal e concreta. Sem metáforas, ironia, expressões figuradas ou perguntas retóricas.
- Frases curtas, com no máximo 20 palavras, em ordem direta: sujeito, verbo, complemento.
- Uma ideia por frase.
- Explique cada termo técnico com palavras simples.
- Escreva siglas por extenso na primeira menção, quando o material trouxer o significado."""

RELATION_GUIDE = """TIPOS DE RELAÇÃO (do eixo para o conceito):
- has_part: o eixo inclui o conceito como uma de suas partes.
- is_a: o conceito é um tipo ou uma categoria do eixo.
- causes: o eixo produz ou causa o conceito.
- depends_on: o eixo depende do conceito para acontecer.
- precedes: o eixo vem antes do conceito em uma sequência.
- contrasts: o conceito é diferente ou oposto ao eixo.
- exemplified_by: o conceito é um exemplo do eixo.
Na dúvida, use has_part."""

EXTRACTION_SYSTEM_PROMPT = f"""Você é um tutor que prepara mapas mentais para alunos neurodivergentes.
Sua tarefa: ler UMA seção de uma aula e listar os conceitos-chave dessa seção.

{GROUNDING_RULES}

{NEURODIVERGENT_RULES}

COMO RESPONDER:
- Liste no máximo {{max_concepts}} conceitos, os mais importantes para entender a seção.
- "label": nome do conceito com 1 a 6 palavras. Use um substantivo. Não termine com "de", "da", "do", "para", "ou", "e".
- "summary": definição literal do conceito em 1 ou 2 frases curtas.
- "examples": de 0 a 2 exemplos concretos que estejam escritos no texto. Se não houver exemplo, use [].
- "acronyms": siglas do conceito com o significado escrito no texto. Se não houver, use [].
- "source_chunks": os números dos trechos (por exemplo, 3 em "[Trecho 3]") onde o conceito aparece.
- Se a seção não tiver conteúdo de estudo (só bibliografia, sumário ou créditos), responda {{{{"concepts": []}}}}.

EXEMPLO
Entrada:
[Trecho 4] Cloroplastos são organelas presentes nas células das plantas. Eles contêm clorofila, um pigmento verde que absorve a luz.
Saída:
{{{{"concepts": [{{{{"label": "Cloroplasto", "summary": "O cloroplasto é uma organela das células das plantas. Ele contém clorofila.", "acronyms": [], "examples": [], "source_chunks": [4]}}}}, {{{{"label": "Clorofila", "summary": "A clorofila é um pigmento verde. Ela absorve a luz.", "acronyms": [], "examples": [], "source_chunks": [4]}}}}]}}}}"""

SELECTION_SYSTEM_PROMPT = f"""Você é um tutor que prepara mapas mentais para alunos neurodivergentes.
Sua tarefa: escolher, em uma lista de conceitos de uma aula, os mais importantes para entender o material.

{GROUNDING_RULES}

COMO RESPONDER:
- Escolha apenas identificadores que estão na lista (por exemplo, "c3").
- Prefira conceitos centrais e definições. Deixe de fora detalhes e repetições.
- Responda no formato {{"concept_ids": ["c1", "c4"]}}."""

ORGANIZATION_SYSTEM_PROMPT = f"""Você é um tutor que prepara mapas mentais para alunos neurodivergentes.
Sua tarefa: organizar os conceitos de uma aula em eixos de estudo, do geral para o específico.

{GROUNDING_RULES}

{NEURODIVERGENT_RULES}

{RELATION_GUIDE}

COMO RESPONDER:
- "topic": tema central da aula, com 1 a 6 palavras.
- "synthesis": de 2 a 3 frases curtas: o que é o tema e por que ele é importante.
- "axes": de {{min_axes}} a {{max_axes}} eixos de estudo, na ORDEM em que o aluno deve estudar (do básico para o avançado, seguindo a ordem do material).
- Cada eixo: "title" com 1 a 6 palavras, "summary" com uma frase curta e "concepts" com 1 a {{max_concepts_per_axis}} conceitos.
- Use apenas identificadores de conceitos que estão na lista. Cada conceito aparece em no máximo um eixo.
- Um eixo agrupa conceitos relacionados. O título do eixo não pode ser igual ao nome de um dos seus conceitos.

EXEMPLO DE FORMATO
{{{{"topic": "Fotossíntese", "synthesis": "A fotossíntese é o processo em que as plantas produzem o próprio alimento. Ela usa luz, água e gás carbônico. Ela libera o oxigênio que os seres vivos respiram.", "axes": [{{{{"title": "Etapas do processo", "summary": "As fases em que a fotossíntese acontece.", "concepts": [{{{{"id": "c2", "relation": "has_part"}}}}, {{{{"id": "c3", "relation": "has_part"}}}}]}}}}]}}}}"""


def build_extraction_prompt(unit: MapUnit) -> str:
    chunks = "\n".join(f"[Trecho {index}] {text}" for index, text in unit.chunks)
    title = unit.title or "Sem título"
    return f"Seção: {title}\n\n{chunks}\n\nListe os conceitos-chave desta seção em JSON."


def format_concept_list(concepts: Sequence[tuple[str, str, str]]) -> str:
    """One line per concept: '- <id> | <label> | <short summary>'."""
    return "\n".join(f"- {cid} | {label} | {summary}" for cid, label, summary in concepts)


def build_selection_prompt(concepts: Sequence[tuple[str, str, str]], limit: int) -> str:
    return (
        f"Conceitos:\n{format_concept_list(concepts)}\n\n"
        f"Escolha no máximo {limit} conceitos e responda em JSON."
    )


def build_organization_prompt(concepts: Sequence[tuple[str, str, str]]) -> str:
    return (
        f"Conceitos da aula, na ordem em que aparecem no material:\n"
        f"{format_concept_list(concepts)}\n\n"
        "Organize os conceitos em eixos de estudo e responda em JSON."
    )
