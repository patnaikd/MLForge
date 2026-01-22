"""Tests for document tool."""

from pathlib import Path

import pytest

from src.config.settings import Settings
from src.database.connection import Database
from src.database.models import Project
from src.services.project_service import ProjectService
from src.tools.document_tool import DocumentTool


@pytest.fixture
def test_project(test_db: Database, test_settings: Settings) -> Project:
    """Create a test project for document tool tests."""
    service = ProjectService(test_db, test_settings)
    return service.create_project(name="Doc Tool Test", created_by="testuser")


@pytest.fixture
def doc_tool(test_project: Project) -> DocumentTool:
    """Create a document tool for testing."""
    return DocumentTool(
        project_path=Path(test_project.folder_path),
        project_id=test_project.id,
        conversation_id=None,
    )


class TestDocumentTool:
    """Test cases for DocumentTool."""

    def test_add_text(self, doc_tool: DocumentTool):
        """Test adding text via the tool."""
        result = doc_tool._run(
            action="add_text",
            text="Hello from tool!",
        )

        assert "Added text block" in result
        assert "position 0" in result

    def test_add_text_missing_content(self, doc_tool: DocumentTool):
        """Test that add_text fails without text."""
        result = doc_tool._run(action="add_text")

        assert "Error" in result
        assert "required" in result.lower()

    def test_add_code(self, doc_tool: DocumentTool):
        """Test adding code via the tool."""
        result = doc_tool._run(
            action="add_code",
            code="print('Hello')",
            language="python",
            output="Hello",
        )

        assert "Added python code block" in result

    def test_add_code_missing_content(self, doc_tool: DocumentTool):
        """Test that add_code fails without code."""
        result = doc_tool._run(action="add_code", language="python")

        assert "Error" in result

    def test_add_image(self, doc_tool: DocumentTool):
        """Test adding image via the tool."""
        result = doc_tool._run(
            action="add_image",
            image_path="images/test.png",
            caption="Test image",
        )

        assert "Added image block" in result

    def test_add_image_missing_path(self, doc_tool: DocumentTool):
        """Test that add_image fails without path."""
        result = doc_tool._run(action="add_image", caption="No path")

        assert "Error" in result

    def test_add_table(self, doc_tool: DocumentTool):
        """Test adding table via the tool."""
        result = doc_tool._run(
            action="add_table",
            table_data=[{"col1": "a", "col2": 1}, {"col1": "b", "col2": 2}],
            caption="Test table",
        )

        assert "Added table with 2 rows" in result

    def test_add_table_missing_data(self, doc_tool: DocumentTool):
        """Test that add_table fails without data."""
        result = doc_tool._run(action="add_table", caption="No data")

        assert "Error" in result

    def test_add_latex(self, doc_tool: DocumentTool):
        """Test adding LaTeX via the tool."""
        result = doc_tool._run(
            action="add_latex",
            latex="E = mc^2",
        )

        assert "Added LaTeX block" in result

    def test_add_latex_missing_content(self, doc_tool: DocumentTool):
        """Test that add_latex fails without latex content."""
        result = doc_tool._run(action="add_latex")

        assert "Error" in result

    def test_add_heading(self, doc_tool: DocumentTool):
        """Test adding heading via the tool."""
        result = doc_tool._run(
            action="add_heading",
            text="Introduction",
            level=2,
        )

        assert "Added heading" in result

    def test_add_heading_missing_text(self, doc_tool: DocumentTool):
        """Test that add_heading fails without text."""
        result = doc_tool._run(action="add_heading", level=1)

        assert "Error" in result

    def test_clear(self, doc_tool: DocumentTool):
        """Test clearing document."""
        # Add some content first
        doc_tool._run(action="add_text", text="Block 1")
        doc_tool._run(action="add_text", text="Block 2")

        result = doc_tool._run(action="clear")

        assert "Cleared 2 blocks" in result

    def test_clear_empty_document(self, doc_tool: DocumentTool):
        """Test clearing empty document."""
        result = doc_tool._run(action="clear")

        assert "Cleared 0 blocks" in result

    def test_summary(self, doc_tool: DocumentTool):
        """Test getting document summary."""
        doc_tool._run(action="add_text", text="Text")
        doc_tool._run(action="add_code", code="code", language="python")
        doc_tool._run(action="add_latex", latex="x^2")

        result = doc_tool._run(action="summary")

        assert "3 blocks" in result
        assert "Text: 1" in result
        assert "Code: 1" in result
        assert "LaTeX: 1" in result

    def test_summary_empty(self, doc_tool: DocumentTool):
        """Test summary of empty document."""
        result = doc_tool._run(action="summary")

        assert "0 blocks" in result

    def test_unknown_action(self, doc_tool: DocumentTool):
        """Test that unknown actions fail gracefully."""
        result = doc_tool._run(action="unknown_action")

        assert "Error" in result
        assert "Unknown action" in result

    def test_position_parameter(self, doc_tool: DocumentTool):
        """Test adding blocks at specific positions."""
        doc_tool._run(action="add_text", text="First")
        doc_tool._run(action="add_text", text="Third")
        result = doc_tool._run(action="add_text", text="Second", position=1)

        assert "position 1" in result

    def test_tool_properties(self, doc_tool: DocumentTool):
        """Test tool name and description."""
        assert doc_tool.name == "document"
        assert "document" in doc_tool.description.lower()
        assert "add_text" in doc_tool.description


class TestDocumentToolAsync:
    """Test async execution of DocumentTool."""

    @pytest.mark.asyncio
    async def test_async_add_text(self, doc_tool: DocumentTool):
        """Test async text addition."""
        result = await doc_tool._arun(
            action="add_text",
            text="Async text",
        )

        assert "Added text block" in result

    @pytest.mark.asyncio
    async def test_async_summary(self, doc_tool: DocumentTool):
        """Test async summary."""
        await doc_tool._arun(action="add_text", text="Test")
        result = await doc_tool._arun(action="summary")

        assert "1 blocks" in result


class TestDocumentToolIntegration:
    """Integration tests for DocumentTool with document service."""

    def test_multiple_operations(self, doc_tool: DocumentTool):
        """Test a sequence of operations."""
        # Build a document
        doc_tool._run(action="add_heading", text="Analysis Report", level=1)
        doc_tool._run(action="add_text", text="This report analyzes the dataset.")
        doc_tool._run(
            action="add_code",
            code="df.describe()",
            language="python",
            output="count    1000.0\nmean     42.5",
        )
        doc_tool._run(action="add_image", image_path="images/histogram.png", caption="Distribution")
        doc_tool._run(
            action="add_table",
            table_data=[{"Metric": "Mean", "Value": 42.5}, {"Metric": "Std", "Value": 12.3}],
            caption="Summary Statistics",
        )
        doc_tool._run(action="add_latex", latex=r"\bar{x} = \frac{1}{n}\sum_{i=1}^n x_i")

        result = doc_tool._run(action="summary")

        assert "6 blocks" in result
        assert "Text: 2" in result  # heading + text
        assert "Code: 1" in result
        assert "Images: 1" in result
        assert "Tables: 1" in result
        assert "LaTeX: 1" in result

    def test_tool_without_project_id(self):
        """Test that tool fails gracefully without project_id."""
        tool = DocumentTool(
            project_path=None,
            project_id=None,
            conversation_id=None,
        )

        result = tool._run(action="add_text", text="Test")

        assert "Error" in result
