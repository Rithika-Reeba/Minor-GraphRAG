# GraphRAG Personal Knowledge Assistant

Streamlit app that turns resumes, notes, and wardrobe images into a personal knowledge graph, then answers questions with GraphRAG and evidence-backed recommendations.

## What it does

- Left pane: upload images and documents, enter a person name, click **Extract and build graph**
- Right pane: chatbot over that person's graph and document chunks
- Vision model (Groq) extracts clothing items from images
- PDF/text extraction plus an LLM builds skills, projects, interests, and goals
- Graph is stored as JSON under `data/graphs/` and optionally synced to Neo4j

## Setup

```bash
cd F:\Assistant
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put your Groq key in `.env` as `GROQ_API_KEY`.

Optional Neo4j: start Neo4j Desktop, then set `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`. If those are empty, the app still runs on the local graph files.

## Run

```bash
streamlit run app.py
```

## Suggested uploads

- Resume PDF
- Notes (`.txt` / `.md`)
- Wardrobe photos (`.png` / `.jpg`)
- Optional shopping list as a text file

The graph is keyed by the **person name** you enter, so different people get separate graphs.

## Example questions

- What skills do I have?
- Suggest a project based on my resume.
- What outfits can I make from my wardrobe?
- What should I learn next?
- Recommend a shopping item that fills a wardrobe gap.
