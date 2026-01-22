"""Document update tool for agent to add content to the running document.

This tool allows the agent to add analysis results, visualizations, and findings
to the running document panel for user review.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.database.connection import get_database
from src.services.document_service import DocumentService
from src.tools.base import BaseAgentTool, ToolResult


class DocumentBlockInput(BaseModel):
    """Input schema for document block operations."""

    action: Literal["add_text", "add_code", "add_image", "add_table", "add_latex", "add_heading", "clear", "summary"] = Field(
        description="Action to perform on the document"
    )

    # Common parameters
    position: int | None = Field(
        default=None,
        description="Position to insert the block (defaults to end)"
    )

    # Text block parameters
    text: str | None = Field(
        default=None,
        description="Text content for text or heading blocks (supports markdown)"
    )

    # Heading parameters
    level: int | None = Field(
        default=2,
        description="Heading level (1-6) for add_heading action"
    )

    # LaTeX parameters
    latex: str | None = Field(
        default=None,
        description="LaTeX content for math equations (without $$ delimiters)"
    )

    # Code block parameters
    code: str | None = Field(
        default=None,
        description="Source code content"
    )
    language: str | None = Field(
        default="python",
        description="Programming language for syntax highlighting"
    )
    output: str | None = Field(
        default=None,
        description="Code execution output"
    )

    # Image parameters
    image_path: str | None = Field(
        default=None,
        description="Path to image file (relative to project or absolute)"
    )
    caption: str | None = Field(
        default=None,
        description="Caption for image or table"
    )

    # Table parameters
    table_data: list[dict[str, Any]] | None = Field(
        default=None,
        description="Table data as list of dictionaries (each dict is a row)"
    )


class DocumentTool(BaseAgentTool):
    """Tool for adding content to the running document.

    The document is a panel that accumulates analysis results, code snippets,
    visualizations, and findings. Use this tool to share results with the user.

    Supported actions:
    - add_text: Add markdown text
    - add_code: Add code with optional output
    - add_image: Add an image from a file
    - add_table: Add a data table
    - add_latex: Add mathematical equations
    - add_heading: Add a section heading
    - clear: Clear all document content
    - summary: Get document summary
    """

    name: str = "document"
    description: str = """Add content to the running document panel.

Use this tool to share analysis results, findings, and visualizations with the user.
The document accumulates content and displays it in a formatted panel.

Actions:
- add_text: Add markdown-formatted text (findings, explanations)
- add_code: Add code snippets with optional execution output
- add_image: Add visualizations and charts (provide image path)
- add_table: Add data tables (provide list of dicts)
- add_latex: Add mathematical equations
- add_heading: Add section headings
- clear: Clear the document
- summary: Get document statistics

Example usage:
1. Add a finding: action="add_text", text="## Key Findings\n- The dataset has 1000 rows..."
2. Add code: action="add_code", code="df.describe()", language="python", output="..."
3. Add image: action="add_image", image_path="images/plot.png", caption="Distribution"
4. Add table: action="add_table", table_data=[{"col1": "a", "col2": 1}, ...], caption="Summary"
5. Add equation: action="add_latex", latex="R^2 = 1 - \\frac{SS_{res}}{SS_{tot}}"
"""

    args_schema: type[BaseModel] = DocumentBlockInput
    _document_service: DocumentService | None = None

    def _get_document_service(self) -> DocumentService:
        """Get or create document service instance."""
        if self._document_service is None:
            if self.project_id is None:
                raise ValueError("Project ID is required for document operations")
            self._document_service = DocumentService(
                db=get_database(),
                project_id=self.project_id,
                project_path=self.project_path,
            )
        return self._document_service

    def _run(
        self,
        action: str,
        position: int | None = None,
        text: str | None = None,
        level: int | None = 2,
        latex: str | None = None,
        code: str | None = None,
        language: str | None = "python",
        output: str | None = None,
        image_path: str | None = None,
        caption: str | None = None,
        table_data: list[dict[str, Any]] | None = None,
    ) -> str:
        """Execute document action.

        Returns:
            String result message
        """
        try:
            doc_service = self._get_document_service()

            if action == "add_text":
                if not text:
                    return str(ToolResult(
                        success=False,
                        output="",
                        error="Text content is required for add_text action"
                    ))
                block = doc_service.add_text(text=text, position=position)
                return str(ToolResult(
                    success=True,
                    output=f"Added text block at position {block.position}",
                    data={"block_id": block.id, "position": block.position}
                ))

            elif action == "add_code":
                if not code:
                    return str(ToolResult(
                        success=False,
                        output="",
                        error="Code content is required for add_code action"
                    ))
                block = doc_service.add_code(
                    code=code,
                    language=language or "python",
                    output=output,
                    position=position
                )
                return str(ToolResult(
                    success=True,
                    output=f"Added {language} code block at position {block.position}",
                    data={"block_id": block.id, "position": block.position}
                ))

            elif action == "add_image":
                if not image_path:
                    return str(ToolResult(
                        success=False,
                        output="",
                        error="Image path is required for add_image action"
                    ))
                block = doc_service.add_image(
                    image_path=image_path,
                    caption=caption,
                    position=position
                )
                return str(ToolResult(
                    success=True,
                    output=f"Added image block at position {block.position}",
                    data={"block_id": block.id, "position": block.position, "path": image_path}
                ))

            elif action == "add_table":
                if not table_data:
                    return str(ToolResult(
                        success=False,
                        output="",
                        error="Table data is required for add_table action"
                    ))
                block = doc_service.add_table(
                    data=table_data,
                    caption=caption,
                    position=position
                )
                return str(ToolResult(
                    success=True,
                    output=f"Added table with {len(table_data)} rows at position {block.position}",
                    data={"block_id": block.id, "position": block.position, "rows": len(table_data)}
                ))

            elif action == "add_latex":
                if not latex:
                    return str(ToolResult(
                        success=False,
                        output="",
                        error="LaTeX content is required for add_latex action"
                    ))
                block = doc_service.add_latex(latex=latex, position=position)
                return str(ToolResult(
                    success=True,
                    output=f"Added LaTeX block at position {block.position}",
                    data={"block_id": block.id, "position": block.position}
                ))

            elif action == "add_heading":
                if not text:
                    return str(ToolResult(
                        success=False,
                        output="",
                        error="Text content is required for add_heading action"
                    ))
                block = doc_service.add_heading(text=text, level=level or 2, position=position)
                return str(ToolResult(
                    success=True,
                    output=f"Added heading at position {block.position}",
                    data={"block_id": block.id, "position": block.position}
                ))

            elif action == "clear":
                count = doc_service.clear()
                return str(ToolResult(
                    success=True,
                    output=f"Cleared {count} blocks from the document",
                    data={"cleared_count": count}
                ))

            elif action == "summary":
                summary = doc_service.get_summary()
                output_lines = [
                    f"Document has {summary['total_blocks']} blocks:",
                    f"  - Text: {summary['by_type']['text']}",
                    f"  - Code: {summary['by_type']['code']}",
                    f"  - Images: {summary['by_type']['image']}",
                    f"  - Tables: {summary['by_type']['table']}",
                    f"  - LaTeX: {summary['by_type']['latex']}",
                ]
                return str(ToolResult(
                    success=True,
                    output="\n".join(output_lines),
                    data=summary
                ))

            else:
                return str(ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown action: {action}"
                ))

        except Exception as e:
            self.logger.error(f"Document tool error: {e}")
            return str(ToolResult(
                success=False,
                output="",
                error=str(e)
            ))

    async def _arun(
        self,
        action: str,
        position: int | None = None,
        text: str | None = None,
        level: int | None = 2,
        latex: str | None = None,
        code: str | None = None,
        language: str | None = "python",
        output: str | None = None,
        image_path: str | None = None,
        caption: str | None = None,
        table_data: list[dict[str, Any]] | None = None,
    ) -> str:
        """Async execution - delegates to sync implementation."""
        return self._run(
            action=action,
            position=position,
            text=text,
            level=level,
            latex=latex,
            code=code,
            language=language,
            output=output,
            image_path=image_path,
            caption=caption,
            table_data=table_data,
        )
