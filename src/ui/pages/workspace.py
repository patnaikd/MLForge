"""Workspace page - Main project workspace."""

from pathlib import Path

import streamlit as st

from src.agent import AgentEngine, create_agent_engine
from src.config.llm_providers import get_llm
from src.config.settings import get_settings
from src.database.connection import get_database
from src.services.project_service import ProjectService
from src.ui.components.chat_panel import render_chat_panel
from src.ui.components.document_panel import render_document_panel
from src.ui.components.file_explorer import render_file_explorer, render_file_upload


def get_agent_engine(project_path: Path) -> AgentEngine | None:
    """Get or create the agent engine for the current session.

    Args:
        project_path: Path to the project directory

    Returns:
        AgentEngine instance or None if initialization fails
    """
    # Check if we already have an engine in session state
    if "agent_engine" in st.session_state:
        return st.session_state.agent_engine

    try:
        settings = get_settings()
        db = get_database()

        # Initialize LLM
        llm = get_llm(settings)

        # Initialize tools (empty list for now, will be populated in Phase 3)
        tools = []

        # Create agent engine
        engine = create_agent_engine(
            llm=llm,
            tools=tools,
            db=db,
            project_path=project_path,
        )

        # Store in session state
        st.session_state.agent_engine = engine
        return engine

    except Exception as e:
        st.error(f"Failed to initialize agent engine: {str(e)}")
        return None


def render_workspace_page() -> None:
    """Render the workspace page."""
    settings = get_settings()
    db = get_database()
    project_service = ProjectService(db, settings)

    # Check if we have a project selected
    if "current_project_id" not in st.session_state:
        st.warning("No project selected. Please go back to home.")
        if st.button("Go to Home"):
            st.session_state.page = "home"
            st.rerun()
        return

    project = project_service.get_project(st.session_state.current_project_id)
    if not project:
        st.error("Project not found.")
        if st.button("Go to Home"):
            st.session_state.page = "home"
            st.rerun()
        return

    # Initialize agent engine
    project_path = Path(project.folder_path)
    agent_engine = get_agent_engine(project_path)

    # Page header
    st.title(project.name)

    # Display agent status if engine is available
    if agent_engine:
        agent_status = st.session_state.get("agent_state", "idle")
        if agent_status != "idle":
            st.info(f"Agent status: {agent_status}")

    # Sidebar with project info and file explorer
    with st.sidebar:
        st.subheader("Project Info")
        st.write(f"**Created by:** {project.created_by}")
        st.write(f"**Created:** {project.created_at.strftime('%Y-%m-%d %H:%M')}")

        disk_usage = project_service.calculate_disk_usage(project)
        st.write(f"**Size:** {project_service.format_disk_usage(disk_usage)}")

        # LLM Provider info
        st.write(f"**LLM:** {settings.llm_provider}")

        if st.button("Back to Projects"):
            # Clean up agent engine
            if "agent_engine" in st.session_state:
                del st.session_state.agent_engine
            st.session_state.page = "home"
            del st.session_state.current_project_id
            st.rerun()

        st.divider()

        # File upload
        st.subheader("Upload Data")
        uploaded = render_file_upload(project, "data")
        if uploaded:
            st.rerun()

        st.divider()

        # File explorer
        render_file_explorer(project)

    # Main content area with tabs
    tab1, tab2, tab3 = st.tabs(["Chat", "Document", "Settings"])

    with tab1:
        render_chat_tab(project, project_service, agent_engine)

    with tab2:
        render_document_tab(project)

    with tab3:
        render_settings_tab(project, project_service)


def render_chat_tab(
    project,
    project_service: ProjectService,
    agent_engine: AgentEngine | None,
) -> None:
    """Render the chat tab.

    Args:
        project: Current project
        project_service: Project service instance
        agent_engine: Agent engine for processing
    """
    # Get or create conversation
    if "current_conversation_id" not in st.session_state:
        # Check for existing conversations
        conversations = project_service.get_conversations(project)
        if conversations:
            # Use most recent
            st.session_state.current_conversation_id = conversations[0].id
            conversation = conversations[0]
        else:
            # Create new conversation
            user_name = st.session_state.get("user_name", "anonymous")
            conversation = project_service.create_conversation(project, user_name)
            st.session_state.current_conversation_id = conversation.id
    else:
        conversation = get_database().get_conversation(st.session_state.current_conversation_id)

    # Render conversation selector
    conversations = project_service.get_conversations(project)
    if len(conversations) > 1:
        selected_id = st.selectbox(
            "Conversation",
            options=[c.id for c in conversations],
            format_func=lambda x: next(
                c.created_at.strftime("%Y-%m-%d %H:%M") for c in conversations if c.id == x
            ),
            index=0,
        )
        if selected_id != st.session_state.current_conversation_id:
            st.session_state.current_conversation_id = selected_id
            st.session_state.chat_messages = []  # Clear messages for reload
            st.rerun()

    # New conversation button
    if st.button("New Conversation"):
        user_name = st.session_state.get("user_name", "anonymous")
        conversation = project_service.create_conversation(project, user_name)
        st.session_state.current_conversation_id = conversation.id
        st.session_state.chat_messages = []
        st.rerun()

    st.divider()

    # Render chat with agent engine
    render_chat_panel(conversation, agent_engine)


def render_document_tab(project) -> None:
    """Render the document tab.

    Args:
        project: Current project
    """
    db = get_database()
    blocks = db.list_document_blocks(project.id)
    project_path = Path(project.folder_path)

    render_document_panel(blocks, project_path)


def render_settings_tab(project, project_service: ProjectService) -> None:
    """Render the settings tab.

    Args:
        project: Current project
        project_service: Project service instance
    """
    settings = get_settings()

    st.subheader("Project Settings")

    # Project details
    with st.form("project_settings"):
        new_name = st.text_input("Project Name", value=project.name)
        save_clicked = st.form_submit_button("Save Changes")

        if save_clicked:
            project.name = new_name
            get_database().update_project(project)
            st.success("Settings saved!")
            st.rerun()

    st.divider()

    # LLM Configuration (read-only display)
    st.subheader("LLM Configuration")
    st.write(f"**Provider:** {settings.llm_provider}")
    if settings.llm_provider == "anthropic":
        st.write(f"**Model:** {settings.anthropic_model}")
    elif settings.llm_provider == "openai":
        st.write(f"**Model:** {settings.openai_model}")
    st.caption("To change LLM settings, update the .env file and restart the application.")

    st.divider()

    # Danger zone
    st.subheader("Danger Zone")
    st.warning("These actions cannot be undone!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Clear Document", type="secondary"):
            get_database().delete_document_blocks(project.id)
            st.success("Document cleared!")
            st.rerun()

    with col2:
        if st.button("Delete Project", type="primary"):
            st.session_state.confirm_delete = True

    if st.session_state.get("confirm_delete"):
        st.error("Are you sure you want to delete this project?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete"):
                # Clean up agent engine
                if "agent_engine" in st.session_state:
                    del st.session_state.agent_engine
                project_service.delete_project(project.id, delete_files=True)
                del st.session_state.current_project_id
                del st.session_state.confirm_delete
                st.session_state.page = "home"
                st.rerun()
        with col2:
            if st.button("Cancel"):
                del st.session_state.confirm_delete
                st.rerun()


def main() -> None:
    """Entry point for workspace page."""
    render_workspace_page()


if __name__ == "__main__":
    main()
