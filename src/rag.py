from src.graph_store import format_graph_context, load_graph, subgraph_for_query
from src.llm import chat_text
from src.storage import load_chunks, score_chunks

SYSTEM = """You are a GraphRAG personal knowledge assistant.
Answer using only the provided graph facts and document snippets.
Give personalized recommendations for projects, learning, fashion, or shopping when relevant.
For every recommendation, cite evidence (source file name or relationship).
If the graph has no information, say so and ask the user to upload data.
"""


def answer_query(person: str, question: str) -> str:
    graph = load_graph(person)
    subgraph = subgraph_for_query(graph, question)
    chunks = score_chunks(question, load_chunks(person))
    snippet_text = "\n\n".join(
        f"[{chunk['source']}] {chunk['text']}" for chunk in chunks
    ) or "No document snippets."
    prompt = f"""Person: {person}

Knowledge graph:
{format_graph_context(subgraph)}

Document snippets:
{snippet_text}

User question: {question}
"""
    return chat_text(prompt, system=SYSTEM, temperature=0.3)
