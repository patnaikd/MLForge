"""Tests for document service."""

from pathlib import Path

import pandas as pd
import pytest

from src.config.settings import Settings
from src.database.connection import Database
from src.database.models import Project
from src.services.document_service import DocumentService
from src.services.project_service import ProjectService


@pytest.fixture
def test_project(test_db: Database, test_settings: Settings) -> Project:
    """Create a test project for document tests."""
    service = ProjectService(test_db, test_settings)
    return service.create_project(name="Doc Test Project", created_by="testuser")


@pytest.fixture
def doc_service(test_db: Database, test_project: Project) -> DocumentService:
    """Create a document service for testing."""
    # Use resolved path to ensure absolute path
    project_path = Path(test_project.folder_path).resolve()
    return DocumentService(
        db=test_db,
        project_id=test_project.id,
        project_path=project_path,
    )


class TestDocumentService:
    """Test cases for DocumentService."""

    def test_add_text(self, doc_service: DocumentService):
        """Test adding a text block."""
        block = doc_service.add_text("Hello, **world**!")

        assert block.block_type == "text"
        assert block.content["text"] == "Hello, **world**!"
        assert block.position == 0

    def test_add_multiple_blocks(self, doc_service: DocumentService):
        """Test adding multiple blocks with sequential positions."""
        doc_service.add_text("First block")
        doc_service.add_text("Second block")
        block3 = doc_service.add_text("Third block")

        assert block3.position == 2
        assert len(doc_service.blocks) == 3

    def test_add_text_at_position(self, doc_service: DocumentService):
        """Test adding text at a specific position."""
        doc_service.add_text("First")
        doc_service.add_text("Third")
        block = doc_service.add_text("Second", position=1)

        assert block.position == 1

    def test_add_latex(self, doc_service: DocumentService):
        """Test adding a LaTeX block."""
        block = doc_service.add_latex(r"E = mc^2")

        assert block.block_type == "latex"
        assert block.content["latex"] == r"E = mc^2"

    def test_add_code(self, doc_service: DocumentService):
        """Test adding a code block."""
        code = "print('Hello')"
        output = "Hello"
        block = doc_service.add_code(code=code, language="python", output=output)

        assert block.block_type == "code"
        assert block.content["code"] == code
        assert block.content["language"] == "python"
        assert block.content["output"] == output

    def test_add_code_without_output(self, doc_service: DocumentService):
        """Test adding a code block without output."""
        block = doc_service.add_code(code="x = 1 + 1", language="python")

        assert block.block_type == "code"
        assert block.content["output"] is None

    def test_add_image(self, doc_service: DocumentService):
        """Test adding an image block."""
        block = doc_service.add_image(
            image_path="images/plot.png",
            caption="Distribution plot",
        )

        assert block.block_type == "image"
        assert block.content["path"] == "images/plot.png"
        assert block.content["caption"] == "Distribution plot"

    def test_add_image_relative_path(self, doc_service: DocumentService, test_project: Project):
        """Test that absolute paths within project are converted to relative."""
        # Use resolved path to ensure absolute path matching doc_service
        project_path = Path(test_project.folder_path).resolve()
        abs_path = project_path / "images" / "chart.png"

        block = doc_service.add_image(image_path=abs_path)

        # Should be stored as relative path (relative to project)
        assert block.content["path"] == "images/chart.png"

    def test_add_image_outside_project(self, doc_service: DocumentService, tmp_path: Path):
        """Test that absolute paths outside project remain absolute."""
        outside_path = tmp_path / "outside" / "image.png"

        block = doc_service.add_image(image_path=outside_path)

        # Should remain as provided since it's outside project
        assert str(outside_path) in block.content["path"]

    def test_add_table_from_list(self, doc_service: DocumentService):
        """Test adding a table from list of dicts."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        block = doc_service.add_table(data=data, caption="User data")

        assert block.block_type == "table"
        assert len(block.content["data"]) == 2
        assert block.content["caption"] == "User data"

    def test_add_table_from_dataframe(self, doc_service: DocumentService):
        """Test adding a table from a pandas DataFrame."""
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [4, 5, 6],
        })
        block = doc_service.add_table(data=df)

        assert block.block_type == "table"
        assert len(block.content["data"]) == 3

    def test_add_table_from_dict_of_lists(self, doc_service: DocumentService):
        """Test adding a table from dict of lists."""
        data = {"col1": [1, 2], "col2": [3, 4]}
        block = doc_service.add_table(data=data)

        assert block.block_type == "table"
        assert len(block.content["data"]) == 2

    def test_add_heading(self, doc_service: DocumentService):
        """Test adding a heading block."""
        block = doc_service.add_heading("Introduction", level=2)

        assert block.block_type == "text"
        assert block.content["text"] == "## Introduction"

    def test_add_heading_levels(self, doc_service: DocumentService):
        """Test different heading levels."""
        h1 = doc_service.add_heading("H1", level=1)
        h3 = doc_service.add_heading("H3", level=3)
        h6 = doc_service.add_heading("H6", level=6)

        assert h1.content["text"] == "# H1"
        assert h3.content["text"] == "### H3"
        assert h6.content["text"] == "###### H6"

    def test_add_divider(self, doc_service: DocumentService):
        """Test adding a divider."""
        block = doc_service.add_divider()

        assert block.block_type == "text"
        assert block.content["text"] == "---"

    def test_clear(self, doc_service: DocumentService):
        """Test clearing all blocks."""
        doc_service.add_text("Block 1")
        doc_service.add_text("Block 2")
        doc_service.add_text("Block 3")

        assert len(doc_service.blocks) == 3

        count = doc_service.clear()

        assert count == 3
        assert len(doc_service.blocks) == 0

    def test_get_block(self, doc_service: DocumentService):
        """Test getting a specific block by ID."""
        block1 = doc_service.add_text("First")
        block2 = doc_service.add_text("Second")

        retrieved = doc_service.get_block(block1.id)

        assert retrieved is not None
        assert retrieved.id == block1.id
        assert retrieved.content["text"] == "First"

    def test_get_block_not_found(self, doc_service: DocumentService):
        """Test getting a non-existent block."""
        result = doc_service.get_block("nonexistent-id")
        assert result is None

    def test_get_blocks_by_type(self, doc_service: DocumentService):
        """Test filtering blocks by type."""
        doc_service.add_text("Text 1")
        doc_service.add_code("code", "python")
        doc_service.add_text("Text 2")
        doc_service.add_latex("x^2")

        text_blocks = doc_service.get_blocks_by_type("text")
        code_blocks = doc_service.get_blocks_by_type("code")

        assert len(text_blocks) == 2
        assert len(code_blocks) == 1

    def test_reload(self, doc_service: DocumentService):
        """Test reloading blocks from database."""
        doc_service.add_text("Before reload")

        # Modify internal cache
        doc_service._blocks = []

        # Reload should restore
        blocks = doc_service.reload()

        assert len(blocks) == 1
        assert blocks[0].content["text"] == "Before reload"

    def test_to_markdown(self, doc_service: DocumentService):
        """Test exporting document as markdown."""
        doc_service.add_heading("Title", level=1)
        doc_service.add_text("Some description.")
        doc_service.add_code("print('hi')", "python", "hi")
        doc_service.add_latex("E = mc^2")

        markdown = doc_service.to_markdown()

        assert "# Title" in markdown
        assert "Some description." in markdown
        assert "```python" in markdown
        assert "print('hi')" in markdown
        assert "$$E = mc^2$$" in markdown

    def test_export_to_file(self, doc_service: DocumentService, tmp_path: Path):
        """Test exporting document to a file."""
        doc_service.add_text("# Test Export")
        doc_service.add_text("Content here.")

        output_file = tmp_path / "output.md"
        result = doc_service.export_to_file(output_file)

        assert result == output_file
        assert output_file.exists()
        content = output_file.read_text()
        assert "# Test Export" in content

    def test_get_summary(self, doc_service: DocumentService):
        """Test getting document summary."""
        doc_service.add_text("Text")
        doc_service.add_code("code", "python")
        doc_service.add_image("img.png")
        doc_service.add_table([{"a": 1}])
        doc_service.add_latex("x")

        summary = doc_service.get_summary()

        assert summary["total_blocks"] == 5
        assert summary["by_type"]["text"] == 1
        assert summary["by_type"]["code"] == 1
        assert summary["by_type"]["image"] == 1
        assert summary["by_type"]["table"] == 1
        assert summary["by_type"]["latex"] == 1

    def test_persistence(self, test_db: Database, test_project: Project):
        """Test that blocks persist across service instances."""
        # Create first service and add blocks
        service1 = DocumentService(
            db=test_db,
            project_id=test_project.id,
        )
        service1.add_text("Persisted text")
        service1.add_code("persisted_code()", "python")

        # Create second service instance
        service2 = DocumentService(
            db=test_db,
            project_id=test_project.id,
        )

        # Should see the same blocks
        assert len(service2.blocks) == 2
        assert service2.blocks[0].content["text"] == "Persisted text"
        assert service2.blocks[1].content["code"] == "persisted_code()"

    def test_empty_document(self, doc_service: DocumentService):
        """Test operations on empty document."""
        assert len(doc_service.blocks) == 0
        assert doc_service.to_markdown() == ""

        summary = doc_service.get_summary()
        assert summary["total_blocks"] == 0

    def test_special_characters_in_text(self, doc_service: DocumentService):
        """Test handling of special characters in text."""
        text = "Special chars: <>&\"' `code` *bold* _italic_"
        block = doc_service.add_text(text)

        assert block.content["text"] == text

    def test_multiline_code(self, doc_service: DocumentService):
        """Test adding multiline code blocks."""
        code = """def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)"""

        block = doc_service.add_code(code, "python")

        assert block.content["code"] == code
        assert "\n" in block.content["code"]


class TestDocumentServiceEdgeCases:
    """Edge case tests for DocumentService."""

    def test_large_text_block(self, doc_service: DocumentService):
        """Test adding a very large text block."""
        large_text = "x" * 100000  # 100KB of text
        block = doc_service.add_text(large_text)

        assert len(block.content["text"]) == 100000

    def test_unicode_content(self, doc_service: DocumentService):
        """Test handling of unicode content."""
        unicode_text = "Hello \u4e16\u754c! \U0001f600 \u03b1\u03b2\u03b3"
        block = doc_service.add_text(unicode_text)

        assert block.content["text"] == unicode_text

    def test_empty_table(self, doc_service: DocumentService):
        """Test adding an empty table."""
        block = doc_service.add_table(data=[])

        assert block.block_type == "table"
        assert block.content["data"] == []

    def test_complex_latex(self, doc_service: DocumentService):
        """Test complex LaTeX formulas."""
        latex = r"\frac{\partial^2 f}{\partial x^2} + \frac{\partial^2 f}{\partial y^2} = 0"
        block = doc_service.add_latex(latex)

        assert block.content["latex"] == latex
