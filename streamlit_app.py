import streamlit as st
import pandas as pd
import os
import shutil
from datetime import datetime
from langchain_community.chat_models import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
try:
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:
    from langchain.prompts import ChatPromptTemplate
    from langchain_core.prompts import MessagesPlaceholder

from google.cloud import storage
from google.oauth2.service_account import Credentials

from models import MODEL_CONFIGS
from utils.utils import response_generator

st.set_page_config(
    page_title="Beer Game Assistant (OM)",
    page_icon=None,
    layout="centered",
    initial_sidebar_state="expanded",
)

MODEL_SELECTED = "gpt-5-mini"

st.title("Beer Game Assistant")
st.write(
    "..."
)

openai_api_key = st.secrets["OPENAI_API_KEY"]
llm = ChatOpenAI(model=MODEL_SELECTED, api_key=openai_api_key)

# Initializing GCP credentials and bucket details
credentials_dict = {
    "type": st.secrets.gcs["type"],
    "project_id": st.secrets.gcs.get("project_id"),
    "client_id": st.secrets.gcs["client_id"],
    "client_email": st.secrets.gcs["client_email"],
    "private_key": st.secrets.gcs["private_key"],
    "private_key_id": st.secrets.gcs["private_key_id"],
    # Required by google-auth; default value works for standard service accounts.
    "token_uri": st.secrets.gcs.get("token_uri", "https://oauth2.googleapis.com/token"),
}
credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")

try:
    credentials = Credentials.from_service_account_info(credentials_dict)
    client = storage.Client(credentials=credentials, project="beer-game-488600")
    bucket = client.get_bucket("beergame1")
except Exception as exc:
    st.error(f"GCP setup failed: {exc}")
    st.stop()

mode_label_to_config = {
    "Qualitative Coach": "BeerGameQualitative",
    "Quantitative Coach": "BeerGameQuantitative",
}

selected_mode_label = st.sidebar.radio(
    "Assistant Mode",
    list(mode_label_to_config.keys()),
    help="Switch between conceptual guidance and step-by-step calculations.",
)
selected_mode = mode_label_to_config[selected_mode_label]
system_prompt = MODEL_CONFIGS[selected_mode]["prompt"]
user_pid = st.sidebar.text_input("Study ID / Team ID")
autosave_enabled = st.sidebar.checkbox("Autosave to GCP", value=True)

# --- Player Role (Beer Game position) ---
ROLE_OPTIONS = ["Retailer", "Wholesaler", "Distributor", "Factory"]

selected_role = st.sidebar.selectbox(
    "Your Role (Beer Game)",
    ROLE_OPTIONS,
    index=0,
    help="Used to tailor advice (what you observe/control differs by role).",
)

if "player_role_by_mode" not in st.session_state:
    st.session_state["player_role_by_mode"] = {
        "BeerGameQualitative": selected_role,
        "BeerGameQuantitative": selected_role,
    }

# keep per-mode role (so switching modes can keep its own role if you want)
st.session_state["player_role_by_mode"][selected_mode] = selected_role

if "start_time_by_mode" not in st.session_state:
    now = datetime.now()
    st.session_state["start_time_by_mode"] = {
        "BeerGameQualitative": now,
        "BeerGameQuantitative": now,
    }

if "messages_by_mode" not in st.session_state:
    st.session_state["messages_by_mode"] = {
        "BeerGameQualitative": [
            {
                "role": "assistant",
                "content": (
                    "I am your Beer Game coach. Share your round context or decisions, and I will help "
                    "you reason about delays, backlog, and the bullwhip effect."
                ),
            }
        ],
        "BeerGameQuantitative": [
            {
                "role": "assistant",
                "content": (
                    "I am your Beer Game coach. Send the numbers you have, and I will walk through the "
                    "formulas and calculations step by step."
                ),
            }
        ],
    }

messages = st.session_state["messages_by_mode"][selected_mode]


def save_conversation_to_gcp(messages_to_save, mode_key, pid, player_role):
    if not pid:
        return None, "missing_pid"
    try:
        end_time = datetime.now()
        start_time = st.session_state["start_time_by_mode"][mode_key]
        duration = end_time - start_time

        chat_history_df = pd.DataFrame(messages_to_save)
        metadata_rows = pd.DataFrame(
            [
                {"role": "Mode", "content": mode_key},
                {"role": "Player Role", "content": player_role},
                {"role": "Start Time", "content": start_time},
                {"role": "End Time", "content": end_time},
                {"role": "Duration", "content": duration},
            ]
        )
        chat_history_df = pd.concat([chat_history_df, metadata_rows], ignore_index=True)

        created_files_path = f"conv_history_P{pid}"
        os.makedirs(created_files_path, exist_ok=True)
        timestamp = end_time.strftime("%Y%m%d_%H%M%S")
        mode_suffix = "qualitative" if mode_key == "BeerGameQualitative" else "quantitative"
        file_name = f"beergame_{mode_suffix}_P{pid}_{timestamp}.csv"
        local_path = os.path.join(created_files_path, file_name)

        chat_history_df.to_csv(local_path, index=False)
        blob = bucket.blob(file_name)
        blob.upload_from_filename(local_path)
        shutil.rmtree(created_files_path, ignore_errors=True)
        return file_name, None
    except Exception as exc:
        return None, str(exc)

if st.sidebar.button("Clear Current Mode Chat"):
    if selected_mode == "BeerGameQualitative":
        st.session_state["messages_by_mode"][selected_mode] = [
            {
                "role": "assistant",
                "content": (
                    "I am your Beer Game qualitative coach. Share your round context or decisions, and I will help "
                    "you reason about delays, backlog, and the bullwhip effect."
                ),
            }
        ]
    else:
        st.session_state["messages_by_mode"][selected_mode] = [
            {
                "role": "assistant",
                "content": (
                    "I am your Beer Game quantitative coach. Send the numbers you have, and I will walk through the "
                    "formulas and calculations step by step."
                ),
            }
        ]
    messages = st.session_state["messages_by_mode"][selected_mode]
    st.session_state["start_time_by_mode"][selected_mode] = datetime.now()

if st.sidebar.button("Save Conversation to GCP"):
    player_role = st.session_state["player_role_by_mode"][selected_mode]
    saved_file, save_error = save_conversation_to_gcp(messages, selected_mode, user_pid, player_role)
    
    if save_error == "missing_pid":
        st.sidebar.error("Enter Study ID / Team ID first.")
    elif save_error:
        st.sidebar.error(f"Save failed: {save_error}")
    else:
        st.sidebar.success(f"Saved to GCP bucket as {saved_file}")

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_input := st.chat_input("Ask a Beer Game question..."):
    messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    history_messages = []
    for msg in messages[:-1]:
        if msg["role"] == "user":
            history_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            history_messages.append(AIMessage(content=msg["content"]))

    prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt + "\n\nUser's Beer Game role: {player_role}\n"
                  "Tailor the guidance to this role's information/constraints."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)

player_role = st.session_state["player_role_by_mode"][selected_mode]

chain = prompt_template | llm
llm_response = chain.invoke(
    {"history": history_messages, "input": user_input, "player_role": player_role}
)
assistant_text = llm_response.content

    with st.chat_message("assistant"):
        st.write_stream(response_generator(response=assistant_text))

    messages.append({"role": "assistant", "content": assistant_text})

    if autosave_enabled:
        player_role = st.session_state["player_role_by_mode"][selected_mode]
        saved_file, save_error = save_conversation_to_gcp(messages, selected_mode, user_pid, player_role)
        if save_error == "missing_pid":
            st.sidebar.warning("Autosave is on. Enter Study ID / Team ID to enable uploads.")
        elif save_error:
            st.sidebar.error(f"Autosave failed: {save_error}")
        else:
            st.sidebar.caption(f"Autosaved: {saved_file}")
