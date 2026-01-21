"""File explorer component for Streamlit."""

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from src.database.models import Project

# CSS to style buttons as links
LINK_BUTTON_CSS = """
<style>
.link-button {
    background: none;
    border: none;
    color: #1976d2;
    text-decoration: none;
    cursor: pointer;
    padding: 0;
    font-size: inherit;
}
.link-button:hover {
    text-decoration: underline;
}
div[data-testid="stHorizontalBlock"] > div > div > div > button {
    background: none !important;
    border: none !important;
    color: #1976d2 !important;
    padding: 0 !important;
    font-weight: normal !important;
    text-align: left !important;
}
div[data-testid="stHorizontalBlock"] > div > div > div > button:hover {
    text-decoration: underline;
    background: none !important;
}
</style>
"""


def render_file_explorer(project: Project, on_file_select: Callable | None = None) -> None:
    """Render a file explorer for a project.

    Args:
        project: Project instance
        on_file_select: Optional callback when a file is selected
    """
    project_path = Path(project.folder_path)

    if not project_path.exists():
        st.warning("Project folder not found")
        return

    st.subheader("Files")

    # Initialize session state for current path
    if "file_explorer_path" not in st.session_state:
        st.session_state.file_explorer_path = ""

    current_relative = st.session_state.file_explorer_path
    current_path = project_path / current_relative if current_relative else project_path

    # Breadcrumb navigation
    if current_relative:
        parts = Path(current_relative).parts

        # Build breadcrumb with columns for inline display
        cols = st.columns([1] + [0.3, 1] * len(parts))
        with cols[0]:
            if st.button("📂 root", key="breadcrumb_root", type="tertiary"):
                st.session_state.file_explorer_path = ""
                st.rerun()

        for i, part in enumerate(parts):
            with cols[1 + i * 2]:
                st.write("/")
            with cols[2 + i * 2]:
                if st.button(part, key=f"breadcrumb_{i}", type="tertiary"):
                    st.session_state.file_explorer_path = str(Path(*parts[: i + 1]))
                    st.rerun()
    else:
        st.write("📂 **root**")

    st.divider()

    # List directory contents
    try:
        items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError:
        st.error("Permission denied")
        return

    if not items:
        st.info("Empty folder")
        return

    # Display items
    for item in items:
        # File type icons
        if item.is_dir():
            icon = "📁"
        else:
            ext = item.suffix.lower()
            icons = {
                ".py": "🐍",
                ".csv": "📊",
                ".json": "📋",
                ".txt": "📝",
                ".md": "📄",
                ".png": "🖼️",
                ".jpg": "🖼️",
                ".jpeg": "🖼️",
                ".pdf": "📕",
                ".xlsx": "📗",
                ".parquet": "📦",
            }
            icon = icons.get(ext, "📄")

        size_str = f" ({_format_size(item.stat().st_size)})" if item.is_file() else ""

        if item.is_dir():
            if st.button(f"{icon} {item.name}", key=f"dir_{item.name}", type="tertiary"):
                new_path = current_relative + "/" + item.name if current_relative else item.name
                st.session_state.file_explorer_path = new_path
                st.rerun()
        else:
            if on_file_select:
                if st.button(f"{icon} {item.name}{size_str}", key=f"file_{item.name}", type="tertiary"):
                    on_file_select(item)
            else:
                st.write(f"{icon} {item.name}{size_str}")


def render_file_upload(project: Project, subfolder: str = "data") -> Path | None:
    """Render file upload widget.

    Args:
        project: Project instance
        subfolder: Target subfolder

    Returns:
        Path to uploaded file or None
    """
    project_path = Path(project.folder_path)
    target_dir = project_path / subfolder

    uploaded_file = st.file_uploader(
        f"Upload to {subfolder}/",
        key=f"file_upload_{subfolder}",
    )

    if uploaded_file is not None:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / uploaded_file.name

        with open(target_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        st.success(f"Uploaded: {uploaded_file.name}")
        return target_path

    return None


def _format_size(bytes_size: int) -> str:
    """Format file size for display.

    Args:
        bytes_size: Size in bytes

    Returns:
        Formatted string
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.0f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.0f} TB"
