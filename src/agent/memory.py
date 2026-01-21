"""Conversation memory with SQLite persistence."""

from datetime import datetime
from typing import Any

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.database.connection import Database


class ConversationMemory(BaseChatMessageHistory):
    """Conversation memory with SQLite persistence.

    Implements LangChain's BaseChatMessageHistory for integration with
    LangChain agents while persisting to SQLite.
    """

    def __init__(
        self,
        db: Database,
        conversation_id: str,
        max_messages: int | None = None,
    ):
        """Initialize conversation memory.

        Args:
            db: Database instance for persistence
            conversation_id: ID of the conversation
            max_messages: Maximum messages to keep in memory (None = unlimited)
        """
        self.db = db
        self.conversation_id = conversation_id
        self.max_messages = max_messages
        self._messages: list[BaseMessage] = []
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Load messages from database."""
        conversation = self.db.get_conversation(self.conversation_id)
        if conversation and conversation.messages:
            self._messages = self._dict_to_messages(conversation.messages)

    def _save_to_db(self) -> None:
        """Save messages to database."""
        conversation = self.db.get_conversation(self.conversation_id)
        if conversation:
            conversation.messages = self._messages_to_dict(self._messages)
            conversation.updated_at = datetime.now()
            self.db.update_conversation(conversation)

    @property
    def messages(self) -> list[BaseMessage]:
        """Get all messages in memory."""
        return self._messages

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to memory and persist.

        Args:
            message: Message to add
        """
        self._messages.append(message)

        # Trim if max_messages is set
        if self.max_messages and len(self._messages) > self.max_messages:
            # Keep system messages and trim oldest non-system messages
            system_msgs = [m for m in self._messages if isinstance(m, SystemMessage)]
            other_msgs = [m for m in self._messages if not isinstance(m, SystemMessage)]
            keep_count = self.max_messages - len(system_msgs)
            if keep_count > 0:
                self._messages = system_msgs + other_msgs[-keep_count:]
            else:
                self._messages = system_msgs[-self.max_messages :]

        self._save_to_db()

    def add_user_message(self, content: str) -> None:
        """Add a user message.

        Args:
            content: Message content
        """
        self.add_message(HumanMessage(content=content))

    def add_ai_message(self, content: str) -> None:
        """Add an AI message.

        Args:
            content: Message content
        """
        self.add_message(AIMessage(content=content))

    def add_system_message(self, content: str) -> None:
        """Add a system message.

        Args:
            content: Message content
        """
        self.add_message(SystemMessage(content=content))

    def clear(self) -> None:
        """Clear all messages from memory and database."""
        self._messages = []
        self._save_to_db()

    def get_messages_for_llm(self, include_system: bool = True) -> list[BaseMessage]:
        """Get messages formatted for LLM input.

        Args:
            include_system: Whether to include system messages

        Returns:
            List of messages for LLM
        """
        if include_system:
            return self._messages.copy()
        return [m for m in self._messages if not isinstance(m, SystemMessage)]

    def get_recent_messages(self, count: int) -> list[BaseMessage]:
        """Get the most recent messages.

        Args:
            count: Number of messages to retrieve

        Returns:
            List of recent messages
        """
        return self._messages[-count:] if self._messages else []

    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation.

        Returns:
            Summary string
        """
        if not self._messages:
            return "No messages in conversation."

        user_count = sum(1 for m in self._messages if isinstance(m, HumanMessage))
        ai_count = sum(1 for m in self._messages if isinstance(m, AIMessage))

        return f"Conversation with {user_count} user messages and {ai_count} assistant messages."

    @staticmethod
    def _messages_to_dict(messages: list[BaseMessage]) -> list[dict[str, Any]]:
        """Convert LangChain messages to dictionary format.

        Args:
            messages: List of LangChain messages

        Returns:
            List of message dictionaries
        """
        result = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, SystemMessage):
                role = "system"
            else:
                role = "unknown"

            result.append({
                "role": role,
                "content": msg.content,
            })
        return result

    @staticmethod
    def _dict_to_messages(messages: list[dict[str, Any]]) -> list[BaseMessage]:
        """Convert dictionary format to LangChain messages.

        Args:
            messages: List of message dictionaries

        Returns:
            List of LangChain messages
        """
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
            elif role == "system":
                result.append(SystemMessage(content=content))
            else:
                # Default to human message for unknown roles
                result.append(HumanMessage(content=content))

        return result


class MemoryManager:
    """Manager for conversation memories across sessions."""

    def __init__(self, db: Database):
        """Initialize memory manager.

        Args:
            db: Database instance
        """
        self.db = db
        self._memories: dict[str, ConversationMemory] = {}

    def get_memory(
        self,
        conversation_id: str,
        max_messages: int | None = None,
    ) -> ConversationMemory:
        """Get or create memory for a conversation.

        Args:
            conversation_id: Conversation ID
            max_messages: Maximum messages to keep

        Returns:
            ConversationMemory instance
        """
        if conversation_id not in self._memories:
            self._memories[conversation_id] = ConversationMemory(
                db=self.db,
                conversation_id=conversation_id,
                max_messages=max_messages,
            )
        return self._memories[conversation_id]

    def clear_memory(self, conversation_id: str) -> None:
        """Clear memory for a conversation.

        Args:
            conversation_id: Conversation ID
        """
        if conversation_id in self._memories:
            self._memories[conversation_id].clear()
            del self._memories[conversation_id]

    def refresh_memory(self, conversation_id: str) -> None:
        """Refresh memory from database.

        Args:
            conversation_id: Conversation ID
        """
        if conversation_id in self._memories:
            self._memories[conversation_id]._load_from_db()
