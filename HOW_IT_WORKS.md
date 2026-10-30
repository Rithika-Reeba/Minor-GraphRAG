# How This Repository Works

This project is a **GraphRAG Personal Knowledge Assistant**. It turns a person's documents and wardrobe images into a knowledge graph, stores the graph **and document snippets in Neo4j** (JSON files are a local backup), then answers chat questions from Neo4j.

Run the app with:

```bash
streamlit run app.py
```

---

## End-to-end flow

```text
Welcome page
  Login  -------------> Chat (graph + snippets from Neo4j; JSON only if Neo4j is down)
  New user -----------> Graph generator (upload files -> extract -> build graph)
                              |
                              v
                    Groq vision (images)
                    PDF/text extract + Groq LLM (documents)
                              |
                              v
                    Neo4j (primary)
                      User --rels--> Skill / Clothing / Project / ...
                      User -[:HAS_CHUNK]-> Chunk {text, source, kind}
                    Local JSON backup
                      data/graphs/<name>.json
                      data/chunks/<name>.json
                              |
                              v
                    Chat prompt
                      1. Load 2-hop neighborhood from Neo4j
                      2. Load Chunk nodes from Neo4j, score by keyword
                      3. Send facts + snippets to Groq
                      4. Return an evidence-backed answer
```

Identity is the **login name**. Graphs, uploads, and chunks are all keyed by a slug of that name (`Anandhu` → `anandhu`).

---

## Repository layout

```text
Assistant/
├── app.py                      Streamlit UI (welcome, login, graph generator, chat)
├── HOW_IT_WORKS.md             This file
├── README.md                   Short setup and run guide
├── requirements.txt            Python dependencies
├── .env                        Local secrets (not committed)
├── .env.example                Template for .env
├── .gitignore
├── .streamlit/config.toml      Streamlit light theme
├── data/
│   ├── uploads/<name>/         Files uploaded in Graph generator
│   ├── graphs/<name>.json      Local knowledge graph
│   └── chunks/<name>.json      Text snippets from PDFs/images
└── src/
    ├── __init__.py
    ├── config.py               Paths and environment variables
    ├── llm.py                  Groq client and JSON parsing
    ├── extractor.py            LLM entity extraction from documents
    ├── pipeline.py             Ingest files and build the graph
    ├── graph_store.py          JSON graph + Neo4j sync/retrieval
    ├── storage.py              Person slugs and document chunks
    ├── rag.py                  Chat retrieval + LLM answer
    └── ingestion/
        ├── __init__.py
        ├── vision.py           Wardrobe image analysis
        └── documents.py        PDF text extract and chunking
```

---

## Runtime files and config

| File | Role |
|------|------|
| `app.py` | Only UI entry point. All extraction and chat go through `src/`. |
| `requirements.txt` | `streamlit`, `groq`, `pymupdf`, `python-dotenv`, `neo4j`, etc. |
| `.env` | `GROQ_API_KEY`, model names, Neo4j URI/user/password. |
| `.env.example` | Safe copy of the same keys with placeholders. |
| `.streamlit/config.toml` | Light theme: sage background, dark green primary, dark text. |
| `data/uploads/` | Saved copies of uploaded images and PDFs. |
| `data/graphs/` | Local backup of the entity graph (`nodes` + `relationships`). Chat does not use this when Neo4j is up. |
| `data/chunks/` | Local backup of text snippets. Migrated into Neo4j on extract (and on first chat if older graphs had JSON only). |

---

## `app.py` — Streamlit UI

Session state: `person`, `mode` (`Chat` or `Graph generator`), `messages`, `build_log`, `auth_view`, `last_mode`.

| Function | Use |
|----------|-----|
| `collapse_sidebar()` | On first entering Chat, injects JS so the left sidebar starts collapsed. |
| `sign_in(name, mode)` | Saves the username, sets Chat or Graph generator, clears old chat if the name changed, then reruns. |
| `render_welcome()` | Split home page: large title on the left; Login / New user on the right. Login asks for username then goes to Chat. New user asks for a name then goes to Graph generator. |
| `render_sidebar()` | After login: shows name, Chat / Graph generator radio, Logout (returns to welcome). |
| `render_graph()` | Upload images/PDFs, **Extract and build graph**, then show node counts and entity list. Uses the signed-in name. Calls `build_graph_from_files()`. |
| `render_chat()` | Title **Personal chat assistant**. Loads graph via `load_graph_for_retrieval()`. Each message calls `answer_query()`. Caption shows whether graph retrieval used Neo4j or JSON. |

---

## `src/config.py` — Settings

Loads `.env`, creates `data/uploads`, `data/graphs`, `data/chunks`.

| Name | Use |
|------|-----|
| `ROOT_DIR`, `DATA_DIR`, `UPLOAD_DIR`, `GRAPH_DIR`, `CHUNK_DIR` | Project and data paths. |
| `GROQ_API_KEY` | Groq authentication. |
| `GROQ_TEXT_MODEL` | Chat + document entity extraction. |
| `GROQ_VISION_MODEL` | Wardrobe image analysis (`qwen/qwen3.6-27b`). |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Neo4j Desktop connection. |

---

## `src/llm.py` — Groq helpers

| Function | Use |
|----------|-----|
| `groq_client()` | Builds a Groq client; raises if `GROQ_API_KEY` is missing. |
| `parse_json_object(text)` | Strips `<think>` blocks and markdown fences, then extracts a JSON object from an LLM reply. |
| `chat_text(prompt, system, temperature)` | Text completion with `GROQ_TEXT_MODEL`. Used for entity extraction and chat answers. |

---

## `src/ingestion/vision.py` — Image analysis

| Function | Use |
|----------|-----|
| `analyze_image(image_path)` | Encodes the image as base64, sends it to the Groq vision model, asks for clothing JSON (`type`, `color`, `style`, …). `reasoning_effort="none"` avoids Qwen thinking tokens breaking JSON. |

---

## `src/ingestion/documents.py` — PDFs and text

| Function | Use |
|----------|-----|
| `extract_pdf_text(pdf_path)` | Reads all pages with PyMuPDF (`fitz`) and concatenates text. |
| `chunk_text(text, size, overlap)` | Splits cleaned text into overlapping windows (~1200 chars, 150 overlap) for later retrieval. |

---

## `src/extractor.py` — Document entities

| Function | Use |
|----------|-----|
| `extract_document_entities(person, text)` | Sends resume/notes text to Groq and returns JSON: skills, projects, education, interests, goals, technologies. First 12,000 characters only. |

---

## `src/storage.py` — Names and chunks

| Function | Use |
|----------|-----|
| `person_slug(name)` | Lowercase file-safe id (`Anandhu` → `anandhu`). |
| `make_chunk(person, source, text, kind)` | One snippet dict (`id`, `source` file name, `kind` image/document, timestamp). |
| `save_chunks(person, chunks)` | Appends snippets to `data/chunks/<slug>.json` (backup). |
| `load_chunks(person)` | Reads the local JSON backup. Used during extract and if Neo4j has no chunks yet. |
| `score_chunks(query, chunks, limit)` | Keyword overlap rank on a chunk list (from Neo4j or JSON); returns top matches, or the last few if nothing matches. |

---

## `src/pipeline.py` — Build the graph

Called from Graph generator after upload.

| Function | Use |
|----------|-----|
| `_ensure_user(graph, person)` | Creates/merges the `User` node. |
| `ingest_image(person, image_path)` | Vision JSON → `ClothingItem`, `Color`, `Style` nodes and `OWNS` / `HAS_COLOR` / `HAS_STYLE` edges. Saves JSON backup, syncs entity graph and `Chunk` nodes to Neo4j. |
| `ingest_document(person, doc_path)` | PDF or text → entity JSON → `Skill`, `Project`, `Technology`, `Education`, `Interest`, `Goal` plus relationships (`HAS_SKILL`, `WORKED_ON`, `USES`, …). Chunks the raw text. Saves JSON backup, syncs graph + chunks to Neo4j. |
| `build_graph_from_files(person, file_paths)` | Routes `.png/.jpg/.webp` to images and `.pdf/.txt/.md` to documents, then syncs the full graph and all chunks to Neo4j. |

Graph node types produced here: `User`, `ClothingItem`, `Color`, `Style`, `Skill`, `Project`, `Technology`, `Education`, `Interest`, `Goal`, plus `Chunk` in Neo4j.

---

## `src/graph_store.py` — JSON backup and Neo4j (primary)

Local JSON is written on every extract as a backup. Chat loads **entities and snippets from Neo4j**. JSON is used only if Neo4j is down or empty.

| Function | Use |
|----------|-----|
| `empty_graph(person)` | Empty `{nodes, relationships}` template. |
| `graph_path(person)` | `data/graphs/<slug>.json`. |
| `load_graph(person)` | Read local JSON (used while building the graph). |
| `save_graph(graph)` | Write JSON after ingest (backup). |
| `_node_id(label, name)` | Stable id such as `Skill:python`. |
| `upsert_node(...)` | Add or update a node by id. |
| `add_rel(...)` | Add a relationship if it does not already exist. |
| `subgraph_for_query(graph, query)` | If ≤ 150 nodes, return the whole graph. Otherwise keep nodes whose text overlaps the question. |
| `format_graph_context(subgraph)` | Turns nodes/edges into a text block for the LLM, including `evidence` on relationships. |
| `neo4j_enabled()` | True when URI and a real password are set (not the placeholder). |
| `_neo4j_node_to_dict(node)` | Converts a Neo4j node to the same dict shape as JSON. Skips `Chunk` labels when assembling the entity subgraph. |
| `load_graph_from_neo4j(person)` | Cypher: find `User` by name/id, then 2 hops out. Returns `source: "neo4j"`. |
| `load_graph_for_retrieval(person)` | Neo4j first; if empty or error, local JSON with `source: "json"`. |
| `sync_to_neo4j(graph)` | `MERGE` every entity node and relationship into Neo4j after extract. |
| `sync_chunks_to_neo4j(person, chunks)` | `MERGE` each snippet as `(User)-[:HAS_CHUNK]->(Chunk {id, text, source, kind})`. |
| `load_chunks_from_neo4j(person)` | Cypher: all `Chunk` nodes linked to that user. |
| `load_chunks_for_retrieval(person)` | Neo4j chunks first. If none exist, copies local JSON chunks into Neo4j, then reads them. Falls back to JSON only if Neo4j is unavailable. |

Entity Cypher (simplified):

```cypher
MATCH (u:User)
WHERE toLower(u.name) = toLower($name) OR u.id = $uid
OPTIONAL MATCH (u)-[r1]->(a)
OPTIONAL MATCH (a)-[r2]->(b)
RETURN u, r1, a, r2, b
```

Snippet Cypher:

```cypher
MATCH (u:User)-[:HAS_CHUNK]->(c:Chunk)
WHERE toLower(u.name) = toLower($name) OR u.id = $uid
RETURN c.id, c.text, c.source, c.kind
```

The question text is **not** turned into Cypher. Neo4j loads that person's neighborhood and chunks; the LLM reads those facts.

---

## `src/rag.py` — Chat answers

| Function | Use |
|----------|-----|
| `answer_query(person, question)` | 1) `load_graph_for_retrieval` (Neo4j) 2) `subgraph_for_query` 3) `load_chunks_for_retrieval` (Neo4j `Chunk` nodes) 4) `score_chunks` 5) `chat_text` with graph + snippets + question. |

Both the knowledge graph and document snippets come from Neo4j when it is running.

---

## `src/ingestion/__init__.py`

Re-exports `analyze_image` so other modules can import it from the package.

---

## Typical user path

1. Open the welcome page. **Login** with the same name used to build the graph, or **New user** to extract files first.
2. Graph generator: upload `wardrobe.png` and a resume PDF → **Extract and build graph**.
3. That writes JSON backups under `data/`, then syncs the entity graph **and** `Chunk` nodes to Neo4j (`HAS_CHUNK`).
4. Chat: each prompt loads the 2-hop graph and document snippets from Neo4j, ranks snippets, then Groq answers. JSON is used only if Neo4j is down.

---

## Dependencies (what they are for)

| Package | Used for |
|---------|----------|
| `streamlit` | UI |
| `groq` | Vision, extraction, chat |
| `pymupdf` | PDF text |
| `python-dotenv` | `.env` |
| `neo4j` | Store and retrieve the entity graph and document chunks for chat |
| `pypdf` | Listed in requirements; PDF path in code uses PyMuPDF |
| `networkx` | Listed in requirements; graph logic is custom dicts, not NetworkX |
