"""Workspace page - Main project workspace."""

from pathlib import Path

import streamlit as st

from src.config.settings import get_settings
from src.database.connection import get_database
from src.database.models import Conversation
from src.services.project_service import ProjectService
from src.ui.components.chat_panel import render_chat_panel
from src.ui.components.document_panel import render_document_panel
from src.ui.components.file_explorer import render_file_explorer, render_file_upload


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

    # Page header
    st.title(project.name)

    # Sidebar with project info and file explorer
    with st.sidebar:
        st.subheader("Project Info")
        st.write(f"**Created by:** {project.created_by}")
        st.write(f"**Created:** {project.created_at.strftime('%Y-%m-%d %H:%M')}")

        disk_usage = project_service.calculate_disk_usage(project)
        st.write(f"**Size:** {project_service.format_disk_usage(disk_usage)}")

        if st.button("Back to Projects"):
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
        render_chat_tab(project, project_service)

    with tab2:
        render_document_tab(project)

    with tab3:
        render_settings_tab(project, project_service)


def render_chat_tab(project, project_service: ProjectService) -> None:
    """Render the chat tab.

    Args:
        project: Current project
        project_service: Project service instance
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
            st.rerun()

    # New conversation button
    if st.button("New Conversation"):
        user_name = st.session_state.get("user_name", "anonymous")
        conversation = project_service.create_conversation(project, user_name)
        st.session_state.current_conversation_id = conversation.id
        st.session_state.chat_messages = []
        st.rerun()

    st.divider()

    # Render chat
    render_chat_panel(conversation)


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
