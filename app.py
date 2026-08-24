from pathlib import Path

import streamlit as st

from src.config import GROQ_API_KEY, UPLOAD_DIR
from src.graph_store import load_graph, neo4j_enabled
from src.pipeline import build_graph_from_files
from src.rag import answer_query
from src.storage import person_slug

st.set_page_config(
    page_title="GraphRAG Personal Knowledge Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .stApp { background: linear-gradient(180deg, #f3efe6 0%, #e7ddd0 100%); }
      h1, h2, h3 { font-family: "Georgia", "Times New Roman", serif; }
      .block-container { padding-top: 1.4rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "build_log" not in st.session_state:
    st.session_state.build_log = None

st.title("Personal Knowledge Assistant")
st.caption("GraphRAG recommendations from documents, notes, and wardrobe images.")

left, right = st.columns(2, gap="large")

with left:
    st.header("Knowledge intake")
    person = st.text_input("Person name", placeholder="e.g. Aisha Khan")
    images = st.file_uploader(
        "Wardrobe / clothing images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )
    documents = st.file_uploader(
        "Documents (resume, notes, PDFs, text)",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )

    if st.button("Extract and build graph", type="primary", use_container_width=True):
        if not GROQ_API_KEY:
            st.error("Add GROQ_API_KEY to a local .env file first.")
        elif not person.strip():
            st.error("Enter the person's name before building the graph.")
        elif not images and not documents:
            st.error("Upload at least one image or document.")
        else:
            person_dir = UPLOAD_DIR / person_slug(person)
            person_dir.mkdir(parents=True, exist_ok=True)
            saved: list[Path] = []
            for file in list(images or []) + list(documents or []):
                dest = person_dir / file.name
                dest.write_bytes(file.getbuffer())
                saved.append(dest)
            with st.spinner("Extracting entities and building the knowledge graph..."):
                try:
                    result = build_graph_from_files(person.strip(), saved)
                    st.session_state.build_log = result
                    st.session_state.person = person.strip()
                    st.session_state.messages = []
                    st.success(
                        f"Graph built for {result['person']}: "
                        f"{result['nodes']} nodes, {result['relationships']} relationships."
                    )
                except Exception as exc:
                    st.exception(exc)

    log = st.session_state.build_log
    if log:
        st.subheader("Graph status")
        st.write(log["neo4j"])
        for line in log["summaries"]:
            st.write(f"- {line}")
        graph = load_graph(log["person"])
        with st.expander("Preview entities"):
            for node in graph["nodes"][:40]:
                st.write(f"{node['label']}: {node['properties'].get('name')}")

    st.caption(
        "Neo4j sync is "
        + ("on" if neo4j_enabled() else "off — using local JSON graph in data/graphs/")
    )

with right:
    st.header("Assistant")
    active_person = st.session_state.get("person") or person.strip()
    if not active_person:
        st.info("Build a graph on the left, then ask about skills, outfits, or learning paths.")
    else:
        st.caption(f"Chatting with the knowledge graph for {active_person}")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        question = st.chat_input("Ask about skills, projects, wardrobe, or recommendations")
        if question:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Retrieving graph context..."):
                    try:
                        reply = answer_query(active_person, question)
                    except Exception as exc:
                        reply = f"Could not answer that yet: {exc}"
                    st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
