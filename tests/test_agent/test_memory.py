"""Tests for conversation memory."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.memory import ConversationMemory, MemoryManager


class TestConversationMemory:
    """Tests for ConversationMemory class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = MagicMock()
        conversation = MagicMock()
        conversation.messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        db.get_conversation.return_value = conversation
        return db

    @pytest.fixture
    def memory(self, mock_db):
        """Create a conversation memory instance."""
        return ConversationMemory(
            db=mock_db,
            conversation_id="test-conv-123",
        )

    def test_init_loads_from_db(self, memory, mock_db):
        """Memory loads existing messages from database on init."""
        mock_db.get_conversation.assert_called_once_with("test-conv-123")
        assert len(memory.messages) == 2

    def test_add_user_message(self, memory, mock_db):
        """Adding a user message works correctly."""
        memory.add_user_message("Test message")

        assert len(memory.messages) == 3
        assert isinstance(memory.messages[-1], HumanMessage)
        assert memory.messages[-1].content == "Test message"
        mock_db.update_conversation.assert_called()

    def test_add_ai_message(self, memory, mock_db):
        """Adding an AI message works correctly."""
        memory.add_ai_message("AI response")

        assert len(memory.messages) == 3
        assert isinstance(memory.messages[-1], AIMessage)
        assert memory.messages[-1].content == "AI response"

    def test_add_system_message(self, memory, mock_db):
        """Adding a system message works correctly."""
        memory.add_system_message("System instruction")

        assert len(memory.messages) == 3
        assert isinstance(memory.messages[-1], SystemMessage)
        assert memory.messages[-1].content == "System instruction"

    def test_clear_messages(self, memory, mock_db):
        """Clearing messages works correctly."""
        memory.clear()

        assert len(memory.messages) == 0
        mock_db.update_conversation.assert_called()

    def test_get_recent_messages(self, memory):
        """Getting recent messages returns correct count."""
        recent = memory.get_recent_messages(1)

        assert len(recent) == 1
        assert isinstance(recent[0], AIMessage)

    def test_max_messages_trimming(self, mock_db):
        """Memory trims old messages when max_messages is set."""
        memory = ConversationMemory(
            db=mock_db,
            conversation_id="test-conv-123",
            max_messages=3,
        )

        # Add messages to exceed limit
        memory.add_user_message("Message 1")
        memory.add_ai_message("Response 1")
        memory.add_user_message("Message 2")

        # Should only keep 3 most recent
        assert len(memory.messages) <= 3

    def test_messages_to_dict(self, memory):
        """Converting messages to dict format works."""
        result = ConversationMemory._messages_to_dict(memory.messages)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Hi there!"

    def test_dict_to_messages(self):
        """Converting dict to messages works."""
        data = [
            {"role": "user", "content": "Test"},
            {"role": "assistant", "content": "Response"},
            {"role": "system", "content": "Instruction"},
        ]

        messages = ConversationMemory._dict_to_messages(data)

        assert len(messages) == 3
        assert isinstance(messages[0], HumanMessage)
        assert isinstance(messages[1], AIMessage)
        assert isinstance(messages[2], SystemMessage)


class TestMemoryManager:
    """Tests for MemoryManager class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = MagicMock()
        conversation = MagicMock()
        conversation.messages = []
        db.get_conversation.return_value = conversation
        return db

    @pytest.fixture
    def manager(self, mock_db):
        """Create a memory manager instance."""
        return MemoryManager(mock_db)

    def test_get_memory_creates_new(self, manager, mock_db):
        """Getting memory for new conversation creates one."""
        memory = manager.get_memory("conv-1")

        assert memory is not None
        assert isinstance(memory, ConversationMemory)

    def test_get_memory_returns_cached(self, manager, mock_db):
        """Getting memory twice returns same instance."""
        memory1 = manager.get_memory("conv-1")
        memory2 = manager.get_memory("conv-1")

        assert memory1 is memory2

    def test_clear_memory(self, manager, mock_db):
        """Clearing memory removes it from cache."""
        memory = manager.get_memory("conv-1")
        manager.clear_memory("conv-1")

        # Getting again should create new instance
        memory2 = manager.get_memory("conv-1")
        assert memory is not memory2

    def test_refresh_memory(self, manager, mock_db):
        """Refreshing memory reloads from database."""
        memory = manager.get_memory("conv-1")
        memory.add_user_message("Test")

        # Reset mock to track refresh call
        mock_db.reset_mock()
        manager.refresh_memory("conv-1")

        mock_db.get_conversation.assert_called()
