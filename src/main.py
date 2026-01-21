"""MLForge - Main Streamlit Application Entry Point."""

from pathlib import Path

import streamlit as st

from src.config.settings import get_settings
from src.database.connection import get_database
from src.utils.logging import setup_logging

# Configure page
st.set_page_config(
    page_title="MLForge",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_custom_css() -> None:
    """Load custom CSS styles."""
    css_path = Path(__file__).parent / "ui" / "styles" / "custom.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def init_app() -> None:
    """Initialize application."""
    # Setup logging
    setup_logging()

    # Ensure settings and database are initialized
    settings = get_settings()
    settings.ensure_workspace_exists()

    # Initialize database (creates tables if needed)
    get_database()

    # Load custom styles
    load_custom_css()


def main() -> None:
    """Main application entry point."""
    init_app()

    # Initialize page state
    if "page" not in st.session_state:
        st.session_state.page = "home"

    # Route to appropriate page
    if st.session_state.page == "home":
        from src.ui.pages.home import render_home_page

        render_home_page()
    elif st.session_state.page == "workspace":
        from src.ui.pages.workspace import render_workspace_page

        render_workspace_page()
    else:
        st.error(f"Unknown page: {st.session_state.page}")


if __name__ == "__main__":
    main()
