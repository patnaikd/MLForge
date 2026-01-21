"""Chat panel component for Streamlit."""

import streamlit as st

from src.database.models import Conversation


def render_chat_panel(conversation: Conversation | None = None) -> None:
    """Render the chat panel.

    Args:
        conversation: Current conversation or None
    """
    st.subheader("Chat")

    # Initialize chat history in session state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Load messages from conversation if provided
    if conversation and conversation.messages:
        st.session_state.chat_messages = conversation.messages

    # Display chat messages
    for message in st.session_state.chat_messages:
        role = message.get("role", "user")
        content = message.get("content", "")

        with st.chat_message(role):
            st.markdown(content)

    # Chat input
    if prompt := st.chat_input("Ask the agent..."):
        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt,
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        # Placeholder for agent response (will be implemented in Phase 2)
        with st.chat_message("assistant"):
            st.info("Agent integration coming in Phase 2")

        # Store that we have a pending message
        st.session_state.pending_message = prompt


def render_chat_history(conversations: list[Conversation]) -> Conversation | None:
    """Render conversation history selector.

    Args:
        conversations: List of conversations

    Returns:
        Selected conversation or None
    """
    if not conversations:
        st.info("No previous conversations")
        return None

    st.subheader("Conversation History")

    for conv in conversations:
        message_count = len(conv.messages)
        preview = ""
        if conv.messages:
            first_msg = conv.messages[0]
            preview = first_msg.get("content", "")[:50] + "..."

        with st.expander(f"{conv.created_at.strftime('%Y-%m-%d %H:%M')} ({message_count} messages)"):
            st.write(f"User: {conv.user_name}")
            if preview:
                st.write(f"Preview: {preview}")
            if st.button("Resume", key=f"resume_{conv.id}"):
                return conv

    return None
