from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.config import GROQ_API_KEY, UPLOAD_DIR
from src.graph_store import load_graph, load_graph_for_retrieval, neo4j_enabled
from src.pipeline import build_graph_from_files
from src.rag import answer_query
from src.storage import person_slug

st.set_page_config(
    page_title="GraphRAG Personal Knowledge Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "person" not in st.session_state:
    st.session_state.person = ""
if "mode" not in st.session_state:
    st.session_state.mode = "Chat"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "build_log" not in st.session_state:
    st.session_state.build_log = None
if "auth_view" not in st.session_state:
    st.session_state.auth_view = "choose"
if "last_mode" not in st.session_state:
    st.session_state.last_mode = ""

if not st.session_state.person:
    st.session_state.mode = "Chat"
    st.session_state.last_mode = ""

LOGGED_IN = bool(st.session_state.person)

st.markdown(
    f"""
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Source+Sans+3:wght@400;600&display=swap");

      html, body, .stApp, [data-testid="stAppViewContainer"] {{
        background: #d7e4db !important;
        color: #14201a !important;
      }}
      [data-testid="stHeader"] {{ background: transparent; }}
      iframe[height="0"] {{ display: none !important; }}
      .block-container {{
        padding: {"0" if not LOGGED_IN else "1.4rem 2rem 2rem 2rem"};
        max-width: {"100%" if not LOGGED_IN else "880px"};
      }}
      h1, h2, h3 {{
        font-family: "Bricolage Grotesque", "Segoe UI", sans-serif !important;
        color: #102018 !important;
        letter-spacing: -0.03em;
      }}
      p, label, span, li, .stMarkdown, [data-testid="stMarkdownContainer"],
      [data-testid="stCaptionContainer"], [data-testid="stChatMessage"] p {{
        color: #14201a !important;
        font-family: "Source Sans 3", "Segoe UI", sans-serif;
      }}
      [data-testid="stSidebar"] {{
        background: #1f3d32 !important;
      }}
      [data-testid="stSidebar"] * {{
        color: #eef5f0 !important;
      }}
      [data-testid="stSidebar"] div.stButton > button {{
        background: #2d5a48;
        color: #eef5f0 !important;
        border: 1px solid #8fb5a3;
        min-height: 2.6rem;
      }}
      div.stButton > button {{
        font-family: "Bricolage Grotesque", "Segoe UI", sans-serif;
        font-weight: 700;
        border-radius: 8px;
        min-height: 2.9rem;
      }}
      div.stButton > button[kind="primary"],
      div.stFormSubmitButton > button {{
        background: #1b5e4a !important;
        color: #ffffff !important;
        border: 0 !important;
      }}
      div.stButton > button[kind="primary"] *,
      div.stFormSubmitButton > button * {{
        color: #ffffff !important;
      }}
      {"[data-testid='stSidebar'] { display: none; }" if not LOGGED_IN else ""}

      .stApp:has(.welcome-marker) [data-testid="stHorizontalBlock"] {{
        gap: 0 !important;
        align-items: stretch !important;
        min-height: 100vh;
      }}
      .stApp:has(.welcome-marker) [data-testid="stHorizontalBlock"] > div {{
        min-height: 100vh;
      }}
      .stApp:has(.welcome-marker) [data-testid="stHorizontalBlock"] > div:first-child {{
        background: #16352c;
        display: flex !important;
        flex-direction: column;
        justify-content: center !important;
        align-items: stretch !important;
        padding: 6vh 5vw !important;
      }}
      .stApp:has(.welcome-marker) [data-testid="stHorizontalBlock"] > div:first-child [data-testid="stVerticalBlock"] {{
        width: 100%;
        display: flex !important;
        flex-direction: column;
        justify-content: center !important;
        align-items: stretch !important;
        min-height: 88vh;
      }}
      .stApp:has(.welcome-marker) [data-testid="stHorizontalBlock"] > div:first-child [data-testid="stMarkdownContainer"] {{
        width: 100% !important;
        text-align: left;
      }}
      .stApp:has(.welcome-marker) [data-testid="stHorizontalBlock"] > div:last-child {{
        background: #d7e4db;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 5rem 4.2rem !important;
      }}
      .welcome-marker {{ display: none; }}
      .brand-title,
      p.brand-title,
      [data-testid="stMarkdownContainer"] p.brand-title {{
        font-family: "Bricolage Grotesque", "Segoe UI", sans-serif !important;
        font-size: clamp(3.8rem, 7.2vw, 9.5rem) !important;
        line-height: 0.9 !important;
        color: #f3f8f4 !important;
        margin: 0 !important;
        font-weight: 700 !important;
        text-align: left !important;
        width: 100% !important;
        max-width: none !important;
        letter-spacing: -0.045em !important;
      }}
      .auth-panel {{
        max-width: 380px;
        width: 100%;
      }}
      .panel-title {{
        font-family: "Bricolage Grotesque", "Segoe UI", sans-serif;
        font-size: 1.7rem;
        color: #102018 !important;
        margin: 0 0 0.35rem 0;
      }}
      .panel-copy {{
        font-family: "Source Sans 3", "Segoe UI", sans-serif;
        font-size: 1.05rem;
        color: #2a3b32 !important;
        margin: 0 0 0.9rem 0;
      }}
      .auth-block {{
        margin-bottom: 2.2rem;
      }}
      .chat-title,
      p.chat-title,
      [data-testid="stMarkdownContainer"] p.chat-title {{
        font-family: "Times New Roman", Times, serif !important;
        font-size: 2.15rem !important;
        color: #1b5e4a !important;
        margin: 0.4rem 0 1.4rem 0 !important;
        font-weight: 600 !important;
        text-align: center !important;
        width: 100% !important;
        letter-spacing: 0.01em;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


def collapse_sidebar() -> None:
    components.html(
        """
        <script>
        (function() {
          const doc = window.parent.document;
          function go() {
            const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            if (!sidebar) return;
            if (sidebar.getBoundingClientRect().width < 90) return;
            const selectors = [
              '[data-testid="stSidebarCollapseButton"]',
              'section[data-testid="stSidebar"] button[kind="header"]',
              'section[data-testid="stSidebar"] button[kind="headerNoPadding"]'
            ];
            for (const sel of selectors) {
              const el = doc.querySelector(sel);
              if (el) { el.click(); return; }
            }
            const buttons = sidebar.querySelectorAll('button');
            if (buttons.length) buttons[0].click();
          }
          go();
          setTimeout(go, 180);
          setTimeout(go, 450);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def sign_in(name: str, mode: str) -> None:
    person = name.strip()
    if st.session_state.person != person:
        st.session_state.messages = []
        st.session_state.build_log = None
    st.session_state.person = person
    st.session_state.mode = mode
    st.session_state.auth_view = "choose"
    st.session_state.last_mode = ""
    st.rerun()


def render_welcome() -> None:
    st.markdown('<div class="welcome-marker"></div>', unsafe_allow_html=True)
    left, right = st.columns([1.15, 1], gap="small")
    with left:
        st.markdown(
            """
            <p class="brand-title" style="
              font-size: clamp(3.8rem, 7.2vw, 9.5rem) !important;
              line-height: 0.9 !important;
              color: #f3f8f4 !important;
              margin: 0 !important;
              font-weight: 700 !important;
              width: 100% !important;
              max-width: none !important;
              letter-spacing: -0.045em !important;
            ">Personal<br>Knowledge<br>Assistant</p>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="auth-panel">', unsafe_allow_html=True)
        view = st.session_state.auth_view
        if view == "choose":
            st.markdown(
                """
                <div class="auth-block">
                  <p class="panel-title">Login</p>
                  <p class="panel-copy">Already have a knowledge graph? Sign in with your name.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Login", type="primary", use_container_width=True):
                st.session_state.auth_view = "login"
                st.rerun()
            st.markdown(
                """
                <div class="auth-block" style="margin-top:2.4rem;">
                  <p class="panel-title">New user</p>
                  <p class="panel-copy">First time here? Create your graph from images and documents.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("New user", use_container_width=True):
                st.session_state.auth_view = "new"
                st.rerun()
        elif view == "login":
            st.markdown(
                """
                <div class="auth-block">
                  <p class="panel-title">Login</p>
                  <p class="panel-copy">Enter the same name used when the graph was built.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="e.g. Anandhu")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    if not username.strip():
                        st.error("Enter a username.")
                    else:
                        sign_in(username, "Chat")
            if st.button("Back", use_container_width=True):
                st.session_state.auth_view = "choose"
                st.rerun()
        else:
            st.markdown(
                """
                <div class="auth-block">
                  <p class="panel-title">New user</p>
                  <p class="panel-copy">Choose a name for your knowledge graph, then extract your files.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("new_user_form"):
                username = st.text_input("Your name", placeholder="e.g. Anandhu")
                submitted = st.form_submit_button("Create graph", use_container_width=True)
                if submitted:
                    if not username.strip():
                        st.error("Enter your name.")
                    else:
                        sign_in(username, "Graph generator")
            if st.button("Back", use_container_width=True):
                st.session_state.auth_view = "choose"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"**{st.session_state.person}**")
        st.radio("Mode", ["Chat", "Graph generator"], key="mode")
        if st.button("Logout", use_container_width=True):
            st.session_state.person = ""
            st.session_state.messages = []
            st.session_state.auth_view = "choose"
            st.rerun()


def render_graph() -> None:
    st.header("Extract and build graph")
    st.caption(f"Files will be stored for {st.session_state.person}")

    images = st.file_uploader(
        "Wardrobe / clothing images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="image_uploads",
    )
    documents = st.file_uploader(
        "Documents (resume, notes, PDFs, text)",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        key="doc_uploads",
    )

    if st.button("Extract and build graph", type="primary", use_container_width=True):
        person = st.session_state.person
        if not GROQ_API_KEY:
            st.error("Add GROQ_API_KEY to a local .env file first.")
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
                    result = build_graph_from_files(person, saved)
                    st.session_state.build_log = result
                    st.session_state.messages = []
                    st.success(
                        f"Graph built: {result['nodes']} nodes, "
                        f"{result['relationships']} relationships."
                    )
                except Exception as exc:
                    st.exception(exc)

    log = st.session_state.build_log
    if log:
        st.subheader("Graph status")
        st.write(log["neo4j"])
        for line in log["summaries"]:
            st.write(f"- {line}")
        graph = load_graph(st.session_state.person)
        counts: dict[str, int] = {}
        for node in graph["nodes"]:
            counts[node["label"]] = counts.get(node["label"], 0) + 1
        st.write(
            f"{len(graph['nodes'])} nodes · {len(graph['relationships'])} relationships"
        )
        st.write(counts)
        with st.expander("All entities"):
            for label in sorted(counts):
                st.markdown(f"**{label}**")
                for node in graph["nodes"]:
                    if node["label"] == label:
                        st.write(f"- {node['properties'].get('name')}")

    st.caption(
        "Neo4j sync is "
        + ("on" if neo4j_enabled() else "off — using local JSON graph in data/graphs/")
    )


def render_chat() -> None:
    st.markdown('<p class="chat-title">Personal chat assistant</p>', unsafe_allow_html=True)
    person = st.session_state.person
    graph = load_graph_for_retrieval(person)
    if not graph["nodes"]:
        st.info("No knowledge graph yet for this username. Open the left panel and switch to Graph generator.")
        return

    source = graph.get("source", "json")
    st.caption(
        "Retrieving graph and document snippets from "
        + ("Neo4j" if source == "neo4j" and neo4j_enabled() else "local JSON")
        + "."
    )
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Type a question")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving graph context..."):
                try:
                    reply = answer_query(person, question)
                except Exception as exc:
                    reply = f"Could not answer that yet: {exc}"
                st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})


if not st.session_state.person:
    render_welcome()
else:
    render_sidebar()
    if st.session_state.mode == "Graph generator":
        st.session_state.last_mode = "Graph generator"
        render_graph()
    else:
        if st.session_state.last_mode != "Chat":
            collapse_sidebar()
        st.session_state.last_mode = "Chat"
        render_chat()
