from src.graph_store import (
    format_graph_context,
    load_chunks_for_retrieval,
    load_graph_for_retrieval,
    subgraph_for_query,
)
from src.llm import chat_text
from src.storage import score_chunks

SYSTEM = """You are a GraphRAG personal knowledge assistant.
Answer using only the provided graph facts and document snippets.
Give personalized recommendations for projects, learning, fashion, or shopping when relevant.
For every recommendation, cite evidence (source file name or relationship).
If the graph has no information, say so and ask the user to upload data.
"""


def answer_query(person: str, question: str) -> str:
    graph = load_graph_for_retrieval(person)
    subgraph = subgraph_for_query(graph, question)
    all_chunks, chunk_source = load_chunks_for_retrieval(person)
    chunks = score_chunks(question, all_chunks)
    snippet_text = "\n\n".join(
        f"[{chunk['source']}] {chunk['text']}" for chunk in chunks
    ) or "No document snippets."
    graph_source = graph.get("source", "json")
    prompt = f"""Person: {person}
Graph source: {graph_source}
Snippet source: {chunk_source}

Knowledge graph:
{format_graph_context(subgraph)}

Document snippets:
{snippet_text}

User question: {question}
"""
    return chat_text(prompt, system=SYSTEM, temperature=0.3)
