import streamlit as st
import requests

st.set_page_config(page_title="L'Assistant Méso-NH", layout="wide")

LLM_API_URL = "http://localhost:8000/v1/chat/completions"

def query_llm(prompt, history):
    messages = [
        {"role": "system", "content": "You are a helpful assistant specialized in MesoNH atmospheric model."}
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.7,
    }

    try:
        response = requests.post(LLM_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return "❌ Error: Could not connect to vLLM. Is the server running on localhost:8080?"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def main():
    st.title("Local LLM Assistant")
    st.caption("Connected to vLLM at localhost:8080")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask me anything about MesoNH or Namelists..."):
        with st.chat_message("user"):
            st.markdown(prompt)

        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = query_llm(prompt, st.session_state.messages[:-1])
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})

    with st.sidebar:
        st.header("Chat Settings")
        if st.button("Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.info(
            "**Pro Tip:** You can copy-paste your Namelist content here and ask the AI "
            "to suggest optimal parameters or explain specific blocks."
        )

if __name__ == "__main__":
    main()
