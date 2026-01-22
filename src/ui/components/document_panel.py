"""Document panel component for Streamlit.

This module provides the UI components for rendering the running document panel
that displays analysis results from the agent. It supports text, code, images,
tables, and LaTeX blocks.
"""

from pathlib import Path
from typing import Any

import streamlit as st

from src.database.models import DocumentBlock


def render_document_panel(
    blocks: list[DocumentBlock],
    project_path: Path | None = None,
    title: str = "Document",
    show_controls: bool = False,
) -> None:
    """Render the document panel with all content blocks.

    Args:
        blocks: List of document blocks to render
        project_path: Path to project folder for resolving image paths
        title: Title for the document panel
        show_controls: Whether to show export/clear controls
    """
    # Header with optional controls
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(title)

    if show_controls and blocks:
        with col2:
            if st.button("📋 Export", key="doc_export", help="Export as Markdown"):
                markdown = _blocks_to_markdown(blocks)
                st.download_button(
                    label="Download Markdown",
                    data=markdown,
                    file_name="document.md",
                    mime="text/markdown",
                )

    if not blocks:
        st.info("No content yet. The agent will add analysis results here.")
        return

    # Render blocks in a container for consistent styling
    with st.container():
        for block in blocks:
            render_block(block, project_path)


def render_document_panel_streaming(
    container: st.delta_generator.DeltaGenerator,
    blocks: list[DocumentBlock],
    project_path: Path | None = None,
) -> None:
    """Render document panel for streaming updates.

    This version is optimized for real-time updates during agent execution.

    Args:
        container: Streamlit container for rendering
        blocks: List of document blocks to render
        project_path: Path to project folder
    """
    with container:
        if not blocks:
            st.info("Analysis results will appear here...")
            return

        for block in blocks:
            render_block(block, project_path)


def render_block(block: DocumentBlock, project_path: Path | None = None) -> None:
    """Render a single document block.

    Args:
        block: Document block to render
        project_path: Path to project folder
    """
    content = block.content

    if block.block_type == "text":
        text = content.get("text", "")
        st.markdown(text)

    elif block.block_type == "latex":
        latex = content.get("latex", "")
        # Handle both inline and block LaTeX
        if latex.strip():
            st.latex(latex)

    elif block.block_type == "code":
        code = content.get("code", "")
        language = content.get("language", "python")
        output = content.get("output")

        # Render code with syntax highlighting
        st.code(code, language=language, line_numbers=True)

        # Show output if present
        if output:
            with st.expander("Output", expanded=True):
                # Check if output looks like an error
                if "Error" in output or "Traceback" in output:
                    st.error(output)
                else:
                    st.text(output)

    elif block.block_type == "image":
        image_path = content.get("path", "")
        caption = content.get("caption")

        # Resolve relative path
        if project_path and not Path(image_path).is_absolute():
            full_path = project_path / image_path
        else:
            full_path = Path(image_path)

        if full_path.exists():
            st.image(str(full_path), caption=caption, use_container_width=True)
        else:
            st.warning(f"Image not found: {image_path}")

    elif block.block_type == "table":
        import pandas as pd

        data = content.get("data")
        caption = content.get("caption")

        if data:
            df = pd.DataFrame(data)
            if caption:
                st.caption(caption)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Empty table")

    else:
        st.warning(f"Unknown block type: {block.block_type}")


def create_text_block(project_id: str, text: str, position: int) -> DocumentBlock:
    """Create a text document block.

    Args:
        project_id: Project ID
        text: Text content (supports markdown)
        position: Block position

    Returns:
        DocumentBlock instance
    """
    return DocumentBlock(
        project_id=project_id,
        block_type="text",
        content={"text": text},
        position=position,
    )


def create_latex_block(project_id: str, latex: str, position: int) -> DocumentBlock:
    """Create a LaTeX document block.

    Args:
        project_id: Project ID
        latex: LaTeX content
        position: Block position

    Returns:
        DocumentBlock instance
    """
    return DocumentBlock(
        project_id=project_id,
        block_type="latex",
        content={"latex": latex},
        position=position,
    )


def create_code_block(
    project_id: str,
    code: str,
    position: int,
    language: str = "python",
    output: str | None = None,
) -> DocumentBlock:
    """Create a code document block.

    Args:
        project_id: Project ID
        code: Code content
        position: Block position
        language: Programming language
        output: Optional code output

    Returns:
        DocumentBlock instance
    """
    return DocumentBlock(
        project_id=project_id,
        block_type="code",
        content={"code": code, "language": language, "output": output},
        position=position,
    )


def create_image_block(
    project_id: str, image_path: str, position: int, caption: str | None = None
) -> DocumentBlock:
    """Create an image document block.

    Args:
        project_id: Project ID
        image_path: Path to image (relative to project)
        position: Block position
        caption: Optional image caption

    Returns:
        DocumentBlock instance
    """
    return DocumentBlock(
        project_id=project_id,
        block_type="image",
        content={"path": image_path, "caption": caption},
        position=position,
    )


def create_table_block(
    project_id: str, data: list[dict], position: int, caption: str | None = None
) -> DocumentBlock:
    """Create a table document block.

    Args:
        project_id: Project ID
        data: Table data as list of dicts
        position: Block position
        caption: Optional table caption

    Returns:
        DocumentBlock instance
    """
    return DocumentBlock(
        project_id=project_id,
        block_type="table",
        content={"data": data, "caption": caption},
        position=position,
    )


def _blocks_to_markdown(blocks: list[DocumentBlock]) -> str:
    """Convert document blocks to markdown string.

    Args:
        blocks: List of document blocks

    Returns:
        Markdown string
    """
    import pandas as pd

    lines = []

    for block in blocks:
        content = block.content

        if block.block_type == "text":
            lines.append(content.get("text", ""))
            lines.append("")

        elif block.block_type == "latex":
            latex = content.get("latex", "")
            lines.append(f"$${latex}$$")
            lines.append("")

        elif block.block_type == "code":
            language = content.get("language", "python")
            code = content.get("code", "")
            output = content.get("output")

            lines.append(f"```{language}")
            lines.append(code)
            lines.append("```")

            if output:
                lines.append("")
                lines.append("**Output:**")
                lines.append("```")
                lines.append(output)
                lines.append("```")
            lines.append("")

        elif block.block_type == "image":
            path = content.get("path", "")
            caption = content.get("caption", "")
            if caption:
                lines.append(f"![{caption}]({path})")
            else:
                lines.append(f"![]({path})")
            lines.append("")

        elif block.block_type == "table":
            data = content.get("data", [])
            caption = content.get("caption")

            if caption:
                lines.append(f"*{caption}*")
                lines.append("")

            if data:
                df = pd.DataFrame(data)
                lines.append(df.to_markdown(index=False))
            lines.append("")

    return "\n".join(lines)


def render_block_preview(block: DocumentBlock, max_lines: int = 5) -> str:
    """Get a text preview of a block for summaries.

    Args:
        block: Document block
        max_lines: Maximum lines to show

    Returns:
        Preview text
    """
    content = block.content

    if block.block_type == "text":
        text = content.get("text", "")
        lines = text.split("\n")[:max_lines]
        return "\n".join(lines)

    elif block.block_type == "latex":
        return f"[LaTeX: {content.get('latex', '')[:50]}...]"

    elif block.block_type == "code":
        language = content.get("language", "python")
        code = content.get("code", "")
        lines = code.split("\n")[:max_lines]
        return f"[{language} code: {len(code.split(chr(10)))} lines]"

    elif block.block_type == "image":
        caption = content.get("caption", "")
        path = content.get("path", "")
        return f"[Image: {caption or path}]"

    elif block.block_type == "table":
        import pandas as pd

        data = content.get("data", [])
        caption = content.get("caption", "Table")
        return f"[Table: {caption} - {len(data)} rows]"

    return f"[{block.block_type}]"
