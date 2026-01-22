"""Document management service for running document panel.

This service manages the document blocks that accumulate analysis results.
It provides methods to add different content types (text, code, images, tables, LaTeX)
and persists them to the database for later retrieval.
"""

from pathlib import Path
from typing import Any, Literal

import pandas as pd

from src.database.connection import Database
from src.database.models import DocumentBlock
from src.utils.logging import get_logger

logger = get_logger(__name__)

BlockType = Literal["text", "code", "image", "table", "latex"]


class DocumentService:
    """Service for managing the running document with analysis results.

    The document is a collection of content blocks (text, code, images, tables, LaTeX)
    that are displayed in a sequential panel in the UI.
    """

    def __init__(self, db: Database, project_id: str, project_path: Path | None = None):
        """Initialize document service.

        Args:
            db: Database instance
            project_id: Project ID for document storage
            project_path: Path to project folder (for image paths)
        """
        self.db = db
        self.project_id = project_id
        self.project_path = project_path
        self._blocks: list[DocumentBlock] | None = None

    @property
    def blocks(self) -> list[DocumentBlock]:
        """Get all document blocks (lazy loaded).

        Returns:
            List of document blocks ordered by position
        """
        if self._blocks is None:
            self._blocks = self.db.list_document_blocks(self.project_id)
        return self._blocks

    def _get_next_position(self) -> int:
        """Get the next position for a new block.

        Returns:
            Next position number
        """
        if not self.blocks:
            return 0
        return max(block.position for block in self.blocks) + 1

    def _add_block(
        self,
        block_type: BlockType,
        content: dict[str, Any],
        position: int | None = None,
    ) -> DocumentBlock:
        """Add a block to the document.

        Args:
            block_type: Type of content block
            content: Block content as dictionary
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        if position is None:
            position = self._get_next_position()

        block = DocumentBlock(
            project_id=self.project_id,
            block_type=block_type,
            content=content,
            position=position,
        )

        # Persist to database
        created_block = self.db.create_document_block(block)

        # Update cache
        if self._blocks is not None:
            self._blocks.append(created_block)
            self._blocks.sort(key=lambda b: b.position)

        logger.info(f"Added {block_type} block at position {position}")
        return created_block

    def add_text(
        self,
        text: str,
        position: int | None = None,
    ) -> DocumentBlock:
        """Add a text block to the document.

        Text blocks support markdown formatting.

        Args:
            text: Text content (supports markdown)
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        return self._add_block(
            block_type="text",
            content={"text": text},
            position=position,
        )

    def add_latex(
        self,
        latex: str,
        position: int | None = None,
    ) -> DocumentBlock:
        """Add a LaTeX block to the document.

        LaTeX blocks are rendered as mathematical equations.

        Args:
            latex: LaTeX content (without $$ delimiters)
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        return self._add_block(
            block_type="latex",
            content={"latex": latex},
            position=position,
        )

    def add_code(
        self,
        code: str,
        language: str = "python",
        output: str | None = None,
        position: int | None = None,
    ) -> DocumentBlock:
        """Add a code block to the document.

        Code blocks include syntax highlighting and optional output.

        Args:
            code: Source code
            language: Programming language for highlighting
            output: Optional execution output
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        return self._add_block(
            block_type="code",
            content={
                "code": code,
                "language": language,
                "output": output,
            },
            position=position,
        )

    def add_image(
        self,
        image_path: str | Path,
        caption: str | None = None,
        position: int | None = None,
    ) -> DocumentBlock:
        """Add an image block to the document.

        Image paths can be absolute or relative to project folder.

        Args:
            image_path: Path to image file
            caption: Optional image caption
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        # Store relative path if within project
        path_str = str(image_path)
        if self.project_path is not None:
            try:
                path_obj = Path(image_path)
                if path_obj.is_absolute():
                    # Resolve both paths to handle symlinks and .. properly
                    resolved_path = path_obj.resolve()
                    resolved_project = self.project_path.resolve()
                    path_str = str(resolved_path.relative_to(resolved_project))
            except ValueError:
                # Path is not relative to project, keep absolute
                pass

        return self._add_block(
            block_type="image",
            content={
                "path": path_str,
                "caption": caption,
            },
            position=position,
        )

    def add_table(
        self,
        data: pd.DataFrame | list[dict[str, Any]] | dict[str, list[Any]],
        caption: str | None = None,
        position: int | None = None,
    ) -> DocumentBlock:
        """Add a table block to the document.

        Tables can be created from DataFrames, list of dicts, or dict of lists.

        Args:
            data: Table data (DataFrame, list of dicts, or dict of lists)
            caption: Optional table caption
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        # Convert to list of dicts for JSON storage
        if isinstance(data, pd.DataFrame):
            table_data = data.to_dict(orient="records")
        elif isinstance(data, dict):
            # Dict of lists -> list of dicts
            df = pd.DataFrame(data)
            table_data = df.to_dict(orient="records")
        else:
            # Assume list of dicts
            table_data = data

        return self._add_block(
            block_type="table",
            content={
                "data": table_data,
                "caption": caption,
            },
            position=position,
        )

    def add_heading(
        self,
        text: str,
        level: int = 2,
        position: int | None = None,
    ) -> DocumentBlock:
        """Add a heading block to the document.

        Headings are markdown text with # prefix.

        Args:
            text: Heading text
            level: Heading level (1-6)
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        prefix = "#" * min(max(level, 1), 6)
        return self.add_text(f"{prefix} {text}", position=position)

    def add_divider(self, position: int | None = None) -> DocumentBlock:
        """Add a horizontal divider to the document.

        Args:
            position: Optional position (defaults to end)

        Returns:
            Created document block
        """
        return self.add_text("---", position=position)

    def clear(self) -> int:
        """Clear all document blocks.

        Returns:
            Number of blocks deleted
        """
        count = self.db.delete_document_blocks(self.project_id)
        self._blocks = []
        logger.info(f"Cleared {count} document blocks")
        return count

    def get_block(self, block_id: str) -> DocumentBlock | None:
        """Get a specific block by ID.

        Args:
            block_id: Block ID

        Returns:
            Document block or None if not found
        """
        for block in self.blocks:
            if block.id == block_id:
                return block
        return None

    def get_blocks_by_type(self, block_type: BlockType) -> list[DocumentBlock]:
        """Get all blocks of a specific type.

        Args:
            block_type: Type of blocks to retrieve

        Returns:
            List of matching blocks
        """
        return [b for b in self.blocks if b.block_type == block_type]

    def reload(self) -> list[DocumentBlock]:
        """Reload blocks from database.

        Returns:
            Updated list of blocks
        """
        self._blocks = None
        return self.blocks

    def to_markdown(self) -> str:
        """Export document as markdown.

        Returns:
            Markdown string representation
        """
        lines = []

        for block in self.blocks:
            content = block.content

            if block.block_type == "text":
                lines.append(content.get("text", ""))
                lines.append("")

            elif block.block_type == "latex":
                lines.append(f"$${content.get('latex', '')}$$")
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

    def export_to_file(self, output_path: Path | str) -> Path:
        """Export document to a markdown file.

        Args:
            output_path: Path for output file

        Returns:
            Path to created file
        """
        output_path = Path(output_path)
        markdown = self.to_markdown()
        output_path.write_text(markdown)
        logger.info(f"Exported document to {output_path}")
        return output_path

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics about the document.

        Returns:
            Dictionary with document statistics
        """
        blocks = self.blocks
        return {
            "total_blocks": len(blocks),
            "by_type": {
                "text": len(self.get_blocks_by_type("text")),
                "code": len(self.get_blocks_by_type("code")),
                "image": len(self.get_blocks_by_type("image")),
                "table": len(self.get_blocks_by_type("table")),
                "latex": len(self.get_blocks_by_type("latex")),
            },
        }
