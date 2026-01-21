"""Document panel component for Streamlit."""

from pathlib import Path

import streamlit as st

from src.database.models import DocumentBlock


def render_document_panel(blocks: list[DocumentBlock], project_path: Path | None = None) -> None:
    """Render the document panel with all content blocks.

    Args:
        blocks: List of document blocks to render
        project_path: Path to project folder for resolving image paths
    """
    st.subheader("Document")

    if not blocks:
        st.info("No content yet. The agent will add analysis results here.")
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
        st.markdown(content.get("text", ""))

    elif block.block_type == "latex":
        st.latex(content.get("latex", ""))

    elif block.block_type == "code":
        code = content.get("code", "")
        language = content.get("language", "python")
        output = content.get("output")

        st.code(code, language=language)

        if output:
            with st.expander("Output"):
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
            st.image(str(full_path), caption=caption)
        else:
            st.warning(f"Image not found: {image_path}")

    elif block.block_type == "table":
        import pandas as pd

        data = content.get("data")
        caption = content.get("caption")

        if data:
            df = pd.DataFrame(data)
            if caption:
                st.write(caption)
            st.dataframe(df)

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
