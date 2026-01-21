"""Home page - Project list and creation."""

import streamlit as st

from src.config.settings import get_settings
from src.database.connection import get_database
from src.services.project_service import ProjectService
from src.services.storage_service import StorageService


def render_home_page() -> None:
    """Render the home page with project list."""
    st.title("MLForge")
    st.write("Agentic ML/Data Science Application")

    settings = get_settings()
    db = get_database()
    project_service = ProjectService(db, settings)
    storage_service = StorageService(settings)

    # User identification
    if "user_name" not in st.session_state:
        st.session_state.user_name = ""

    with st.sidebar:
        st.subheader("User")
        user_name = st.text_input(
            "Your name",
            value=st.session_state.user_name,
            placeholder="Enter your name",
        )
        if user_name:
            st.session_state.user_name = user_name

        st.divider()

        # Workspace stats
        st.subheader("Workspace")
        usage = storage_service.get_workspace_usage()
        st.write(f"**Total Usage:** {usage['total_formatted']}")

    # Create new project section
    st.subheader("Create New Project")

    if not st.session_state.user_name:
        st.warning("Please enter your name in the sidebar to create a project.")
    else:
        with st.form("new_project_form"):
            project_name = st.text_input(
                "Project Name",
                placeholder="My Analysis Project",
            )
            submitted = st.form_submit_button("Create Project")

            if submitted and project_name:
                try:
                    project = project_service.create_project(
                        name=project_name,
                        created_by=st.session_state.user_name,
                    )
                    st.success(f"Created project: {project.name}")
                    st.session_state.current_project_id = project.id
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # Project list
    st.divider()
    st.subheader("Projects")

    projects = project_service.list_projects()

    if not projects:
        st.info("No projects yet. Create one above!")
    else:
        for project in projects:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.write(f"**{project.name}**")
                    st.caption(
                        f"Created by {project.created_by} on {project.created_at.strftime('%Y-%m-%d %H:%M')}"
                    )

                with col2:
                    disk_usage = project_service.format_disk_usage(project.disk_usage_bytes)
                    st.caption(f"Size: {disk_usage}")

                with col3:
                    if st.button("Open", key=f"open_{project.id}"):
                        st.session_state.current_project_id = project.id
                        st.session_state.page = "workspace"
                        st.rerun()

                st.divider()


def main() -> None:
    """Entry point for home page."""
    render_home_page()


if __name__ == "__main__":
    main()
