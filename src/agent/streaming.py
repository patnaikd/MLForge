"""Streaming handler for agent events."""

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from src.agent.events import (
    EventType,
    StreamEvent,
    error_event,
    llm_response_event,
    llm_token_event,
    tool_completed_event,
    tool_output_event,
    tool_started_event,
)


class StreamingHandler(AsyncCallbackHandler):
    """Async callback handler for streaming agent events.

    Captures LangChain events and converts them to StreamEvents
    that can be consumed by the UI layer.
    """

    def __init__(self) -> None:
        """Initialize the streaming handler."""
        super().__init__()
        self._event_queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        self._token_buffer: str = ""
        self._current_tool: str | None = None
        self._listeners: list[Callable[[StreamEvent], None]] = []

    def add_listener(self, listener: Callable[[StreamEvent], None]) -> None:
        """Add an event listener.

        Args:
            listener: Callback function for events
        """
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[StreamEvent], None]) -> None:
        """Remove an event listener.

        Args:
            listener: Callback function to remove
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _emit_event(self, event: StreamEvent) -> None:
        """Emit an event to queue and listeners.

        Args:
            event: Event to emit
        """
        await self._event_queue.put(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass  # Don't let listener errors break the stream

    async def get_event(self, timeout: float = 30.0) -> StreamEvent | None:
        """Get the next event from the queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Next event or None if timeout
        """
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def events(self) -> AsyncGenerator[StreamEvent, None]:
        """Async generator for streaming events.

        Yields:
            StreamEvent objects as they occur
        """
        while True:
            event = await self.get_event()
            if event is None:
                break
            yield event
            if event.event_type == EventType.ERROR:
                break
            if event.event_type == EventType.EXECUTION_COMPLETED:
                break

    def clear_queue(self) -> None:
        """Clear the event queue."""
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    # LangChain callback methods

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts generating."""
        self._token_buffer = ""

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called for each new token from the LLM.

        Args:
            token: The new token
        """
        self._token_buffer += token
        await self._emit_event(llm_token_event(token))

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM finishes generating.

        Args:
            response: The LLM response
        """
        if self._token_buffer:
            await self._emit_event(llm_response_event(self._token_buffer))
            self._token_buffer = ""

    async def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when LLM encounters an error.

        Args:
            error: The error that occurred
        """
        await self._emit_event(error_event(str(error)))

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Called when a tool starts executing.

        Args:
            serialized: Tool metadata
            input_str: Tool input
        """
        tool_name = serialized.get("name", "unknown")
        self._current_tool = tool_name

        # Parse input as dict if possible
        tool_input = {"input": input_str}
        try:
            import json

            if input_str.startswith("{"):
                tool_input = json.loads(input_str)
        except (json.JSONDecodeError, ValueError):
            pass

        await self._emit_event(tool_started_event(tool_name, tool_input))

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called when a tool finishes executing.

        Args:
            output: Tool output
        """
        tool_name = self._current_tool or "unknown"
        await self._emit_event(tool_completed_event(tool_name, output))
        self._current_tool = None

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when a tool encounters an error.

        Args:
            error: The error that occurred
        """
        tool_name = self._current_tool or "unknown"
        await self._emit_event(
            error_event(f"Tool '{tool_name}' error: {error}")
        )
        self._current_tool = None

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when a chain starts."""
        pass  # Can be extended for chain-level events

    async def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
        """Called when a chain ends."""
        pass  # Can be extended for chain-level events

    async def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when a chain encounters an error."""
        await self._emit_event(error_event(f"Chain error: {error}"))


class EventAggregator:
    """Aggregates and manages streaming events."""

    def __init__(self) -> None:
        """Initialize the event aggregator."""
        self._events: list[StreamEvent] = []
        self._handlers: list[StreamingHandler] = []

    def create_handler(self) -> StreamingHandler:
        """Create a new streaming handler.

        Returns:
            New StreamingHandler instance
        """
        handler = StreamingHandler()
        handler.add_listener(self._on_event)
        self._handlers.append(handler)
        return handler

    def _on_event(self, event: StreamEvent) -> None:
        """Handle incoming events.

        Args:
            event: The event that occurred
        """
        self._events.append(event)

    @property
    def events(self) -> list[StreamEvent]:
        """Get all collected events."""
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()

    def get_events_by_type(self, event_type: EventType) -> list[StreamEvent]:
        """Get events of a specific type.

        Args:
            event_type: Type of events to retrieve

        Returns:
            List of matching events
        """
        return [e for e in self._events if e.event_type == event_type]

    def get_tool_events(self) -> list[StreamEvent]:
        """Get all tool-related events.

        Returns:
            List of tool events
        """
        tool_types = {
            EventType.TOOL_STARTED,
            EventType.TOOL_OUTPUT,
            EventType.TOOL_COMPLETED,
        }
        return [e for e in self._events if e.event_type in tool_types]


async def emit_tool_output(
    handler: StreamingHandler,
    tool_name: str,
    output: str,
    chunk_size: int = 100,
) -> None:
    """Emit tool output in chunks for streaming display.

    Args:
        handler: Streaming handler
        tool_name: Name of the tool
        output: Full output to stream
        chunk_size: Size of each chunk
    """
    for i in range(0, len(output), chunk_size):
        chunk = output[i : i + chunk_size]
        await handler._emit_event(tool_output_event(tool_name, chunk))
        await asyncio.sleep(0.01)  # Small delay for smoother streaming
