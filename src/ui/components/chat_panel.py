"""Chat panel component for Streamlit."""

import asyncio

import streamlit as st

from src.agent import AgentEngine, AgentState, EventType, Plan, StreamEvent
from src.database.models import Conversation


def render_chat_panel(
    conversation: Conversation | None = None,
    agent_engine: AgentEngine | None = None,
) -> None:
    """Render the chat panel.

    Args:
        conversation: Current conversation or None
        agent_engine: Agent engine for processing messages
    """
    st.subheader("Chat")

    # Initialize chat history in session state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Initialize agent state
    if "agent_state" not in st.session_state:
        st.session_state.agent_state = AgentState.IDLE

    if "pending_plan" not in st.session_state:
        st.session_state.pending_plan = None

    # Load messages from conversation if provided
    if conversation and conversation.messages:
        st.session_state.chat_messages = conversation.messages

    # Display chat messages
    for message in st.session_state.chat_messages:
        role = message.get("role", "user")
        content = message.get("content", "")

        with st.chat_message(role):
            st.markdown(content)

    # Display pending plan for approval if any
    if st.session_state.pending_plan and st.session_state.agent_state == AgentState.AWAITING_APPROVAL:
        render_approval_dialog(st.session_state.pending_plan)

    # Chat input
    if prompt := st.chat_input("Ask the agent...", disabled=st.session_state.agent_state == AgentState.EXECUTING):
        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt,
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        # Process with agent if available
        if agent_engine and conversation:
            process_with_agent(prompt, conversation.id, agent_engine)
        else:
            # Placeholder for when agent is not available
            with st.chat_message("assistant"):
                st.info("Agent engine not initialized. Please check configuration.")


def process_with_agent(
    prompt: str,
    conversation_id: str,
    agent_engine: AgentEngine,
) -> None:
    """Process user input with the agent engine.

    Args:
        prompt: User's message
        conversation_id: Conversation ID
        agent_engine: Agent engine instance
    """
    st.session_state.agent_state = AgentState.PLANNING

    # Create placeholder for streaming response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        status_placeholder = st.empty()

        # Run agent and stream events
        response_text = ""
        current_status = "Planning..."

        async def run_agent():
            nonlocal response_text, current_status

            def approval_callback(plan: Plan) -> bool:
                # Store plan for UI approval
                st.session_state.pending_plan = plan
                st.session_state.agent_state = AgentState.AWAITING_APPROVAL
                # For now, auto-approve (will be enhanced with proper UI flow)
                return True

            async for event in agent_engine.run(
                user_input=prompt,
                conversation_id=conversation_id,
                approval_callback=approval_callback,
            ):
                # Update UI based on event type
                if event.event_type == EventType.MESSAGE:
                    message_content = event.data.get("content", "")
                    message_role = event.data.get("role", "assistant")

                    if message_content:
                        # System messages go to status, assistant messages to response
                        if message_role == "system":
                            status_placeholder.info(message_content)
                        else:
                            # Append assistant response (don't replace previous content)
                            if response_text:
                                response_text += "\n\n" + message_content
                            else:
                                response_text = message_content
                            response_placeholder.markdown(response_text)

                elif event.event_type == EventType.LLM_TOKEN:
                    response_text += event.data.get("token", "")
                    response_placeholder.markdown(response_text + "▌")

                elif event.event_type == EventType.PLAN_STARTED:
                    current_status = "Creating plan..."
                    status_placeholder.info(current_status)

                elif event.event_type == EventType.PLAN_COMPLETED:
                    current_status = "Plan created"
                    status_placeholder.success(current_status)

                elif event.event_type == EventType.EXECUTION_STARTED:
                    current_status = "Executing plan..."
                    status_placeholder.info(current_status)

                elif event.event_type == EventType.STEP_STARTED:
                    step_num = event.data.get("step_number", "?")
                    desc = event.data.get("description", "")
                    current_status = f"Step {step_num}: {desc}"
                    status_placeholder.info(current_status)

                elif event.event_type == EventType.TOOL_STARTED:
                    tool_name = event.data.get("tool_name", "")
                    current_status = f"Running tool: {tool_name}"
                    status_placeholder.info(current_status)

                elif event.event_type == EventType.TOOL_COMPLETED:
                    tool_name = event.data.get("tool_name", "")
                    current_status = f"Tool completed: {tool_name}"
                    status_placeholder.success(current_status)

                elif event.event_type == EventType.EXECUTION_COMPLETED:
                    current_status = "Completed"
                    status_placeholder.empty()

                elif event.event_type == EventType.ERROR:
                    error_msg = event.data.get("error", "Unknown error")
                    status_placeholder.error(f"Error: {error_msg}")

            return response_text

        # Run the async agent
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            final_response = loop.run_until_complete(run_agent())
            loop.close()

            # Clear status and show final response
            status_placeholder.empty()
            response_placeholder.markdown(final_response)

            # Add to chat history
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": final_response,
            })

        except Exception as e:
            status_placeholder.error(f"Error: {str(e)}")
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": f"I encountered an error: {str(e)}",
            })

        finally:
            st.session_state.agent_state = AgentState.IDLE
            st.session_state.pending_plan = None


def render_approval_dialog(plan: Plan) -> None:
    """Render the plan approval dialog.

    Args:
        plan: Plan awaiting approval
    """
    with st.expander("Plan Approval Required", expanded=True):
        st.markdown(f"**Goal:** {plan.goal}")
        st.markdown(f"**Reasoning:** {plan.reasoning}")

        st.markdown("**Steps:**")
        for step in plan.steps:
            approval_marker = "⚠️" if step.requires_approval else "✓"
            tool_info = f" (using {step.tool_name})" if step.tool_name else ""
            st.markdown(f"{approval_marker} {step.step_number}. {step.description}{tool_info}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve", type="primary", key="approve_plan"):
                st.session_state.plan_approved = True
                st.session_state.agent_state = AgentState.EXECUTING
                st.rerun()

        with col2:
            if st.button("Reject", key="reject_plan"):
                st.session_state.plan_approved = False
                st.session_state.agent_state = AgentState.IDLE
                st.session_state.pending_plan = None
                st.rerun()


def render_streaming_response(events: list[StreamEvent]) -> None:
    """Render a list of streaming events.

    Args:
        events: List of stream events to render
    """
    for event in events:
        if event.event_type == EventType.MESSAGE:
            st.markdown(event.data.get("content", ""))

        elif event.event_type == EventType.TOOL_STARTED:
            tool_name = event.data.get("tool_name", "unknown")
            st.info(f"🔧 Running: {tool_name}")

        elif event.event_type == EventType.TOOL_OUTPUT:
            output = event.data.get("output", "")
            st.code(output)

        elif event.event_type == EventType.TOOL_COMPLETED:
            tool_name = event.data.get("tool_name", "unknown")
            st.success(f"✓ Completed: {tool_name}")

        elif event.event_type == EventType.ERROR:
            error = event.data.get("error", "Unknown error")
            st.error(f"Error: {error}")


def render_chat_history(conversations: list[Conversation]) -> Conversation | None:
    """Render conversation history selector.

    Args:
        conversations: List of conversations

    Returns:
        Selected conversation or None
    """
    if not conversations:
        st.info("No previous conversations")
        return None

    st.subheader("Conversation History")

    for conv in conversations:
        message_count = len(conv.messages)
        preview = ""
        if conv.messages:
            first_msg = conv.messages[0]
            preview = first_msg.get("content", "")[:50] + "..."

        with st.expander(f"{conv.created_at.strftime('%Y-%m-%d %H:%M')} ({message_count} messages)"):
            st.write(f"User: {conv.user_name}")
            if preview:
                st.write(f"Preview: {preview}")
            if st.button("Resume", key=f"resume_{conv.id}"):
                return conv

    return None


def render_plan_display(plan: Plan) -> None:
    """Render a plan for display.

    Args:
        plan: Plan to display
    """
    st.markdown(f"### Plan: {plan.goal}")
    st.markdown(f"*{plan.reasoning}*")

    for step in plan.steps:
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }
        icon = status_icons.get(step.status, "⏳")
        tool_info = f" [{step.tool_name}]" if step.tool_name else ""

        st.markdown(f"{icon} **Step {step.step_number}:** {step.description}{tool_info}")
