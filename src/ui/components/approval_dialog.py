"""Approval dialog component for code execution and plan approval."""

import streamlit as st

from src.agent.events import Plan, PlanStep
from src.tools import TOOL_REGISTRY, get_tools_requiring_approval


def render_approval_dialog(
    title: str,
    code: str,
    language: str = "python",
    description: str | None = None,
) -> bool | None:
    """Render an approval dialog for code execution.

    Args:
        title: Dialog title
        code: Code to be executed
        language: Programming language
        description: Optional description of what the code does

    Returns:
        True if approved, False if rejected, None if pending
    """
    approval_key = f"approval_{hash(code)}"

    if approval_key in st.session_state:
        return st.session_state[approval_key]

    st.warning(f"**{title}**")

    if description:
        st.write(description)

    st.write("The agent wants to execute the following code:")
    st.code(code, language=language)

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("Approve", type="primary", key=f"approve_{approval_key}"):
            st.session_state[approval_key] = True
            st.rerun()

    with col2:
        if st.button("Reject", key=f"reject_{approval_key}"):
            st.session_state[approval_key] = False
            st.rerun()

    return None


def clear_approval(code: str) -> None:
    """Clear an approval decision.

    Args:
        code: Code that was approved/rejected
    """
    approval_key = f"approval_{hash(code)}"
    if approval_key in st.session_state:
        del st.session_state[approval_key]


def render_plan_approval(plan: Plan | dict) -> bool | None:
    """Render approval dialog for an agent plan.

    Args:
        plan: Plan object or dictionary with steps

    Returns:
        True if approved, False if rejected, None if pending
    """
    # Handle both Plan objects and dicts
    if isinstance(plan, Plan):
        plan_dict = {
            "goal": plan.goal,
            "steps": [
                {
                    "step_number": s.step_number,
                    "description": s.description,
                    "tool_name": s.tool_name,
                    "requires_approval": s.requires_approval,
                }
                for s in plan.steps
            ],
            "reasoning": plan.reasoning,
        }
    else:
        plan_dict = plan

    plan_key = f"plan_approval_{hash(str(plan_dict))}"

    if plan_key in st.session_state:
        return st.session_state[plan_key]

    # Get tools requiring approval
    approval_tools = set(get_tools_requiring_approval())

    st.info("**Agent Plan**")

    # Show plan goal
    goal = plan_dict.get("goal", "Execute task")
    st.write(f"**Goal:** {goal}")

    # Show reasoning if available
    reasoning = plan_dict.get("reasoning")
    if reasoning:
        with st.expander("View agent reasoning"):
            st.write(reasoning)

    steps = plan_dict.get("steps", [])
    st.write(f"**Proposed steps ({len(steps)} total):**")

    # Display steps with approval indicators
    for step in steps:
        step_num = step.get("step_number", "?")
        description = step.get("description", "No description")
        tool_name = step.get("tool_name")
        requires_approval = step.get("requires_approval", False)

        # Check if tool requires approval
        tool_needs_approval = tool_name and tool_name in approval_tools
        needs_approval = requires_approval or tool_needs_approval

        # Format step display
        tool_badge = f" `{tool_name}`" if tool_name else ""
        approval_badge = " ⚠️" if needs_approval else ""

        st.write(f"{step_num}. {description}{tool_badge}{approval_badge}")

    # Show legend
    st.caption("⚠️ = Step requires approval before execution")

    # Warning about code execution
    has_execution = any(
        step.get("tool_name") in ["bash_executor", "python_executor"]
        for step in steps
    )
    if has_execution:
        st.warning(
            "This plan includes code execution steps. "
            "Please review carefully before approving."
        )

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("Approve Plan", type="primary", key=f"approve_{plan_key}"):
            st.session_state[plan_key] = True
            st.rerun()

    with col2:
        if st.button("Reject Plan", key=f"reject_{plan_key}"):
            st.session_state[plan_key] = False
            st.rerun()

    return None


def render_step_approval(step: PlanStep | dict) -> bool | None:
    """Render approval dialog for a single plan step.

    Args:
        step: PlanStep object or dictionary

    Returns:
        True if approved, False if rejected, None if pending
    """
    # Handle both PlanStep objects and dicts
    if isinstance(step, PlanStep):
        step_dict = {
            "step_number": step.step_number,
            "description": step.description,
            "tool_name": step.tool_name,
            "tool_input": step.tool_input,
        }
    else:
        step_dict = step

    step_key = f"step_approval_{hash(str(step_dict))}"

    if step_key in st.session_state:
        return st.session_state[step_key]

    step_num = step_dict.get("step_number", "?")
    description = step_dict.get("description", "No description")
    tool_name = step_dict.get("tool_name", "unknown")
    tool_input = step_dict.get("tool_input", {})

    st.warning(f"**Step {step_num}: Approval Required**")
    st.write(f"**Action:** {description}")
    st.write(f"**Tool:** `{tool_name}`")

    # Show tool-specific details
    if tool_name == "python_executor" and "code" in tool_input:
        st.write("**Code to execute:**")
        st.code(tool_input["code"], language="python")
    elif tool_name == "bash_executor" and "command" in tool_input:
        st.write("**Command to execute:**")
        st.code(tool_input["command"], language="bash")
    elif tool_input:
        with st.expander("View tool parameters"):
            st.json(tool_input)

    # Get tool description
    if tool_name in TOOL_REGISTRY:
        tool_desc = TOOL_REGISTRY[tool_name]["description"]
        st.caption(f"*{tool_desc}*")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("Approve Step", type="primary", key=f"approve_{step_key}"):
            st.session_state[step_key] = True
            st.rerun()

    with col2:
        if st.button("Skip Step", key=f"skip_{step_key}"):
            st.session_state[step_key] = False
            st.rerun()

    return None


def clear_plan_approval(plan: Plan | dict) -> None:
    """Clear approval state for a plan.

    Args:
        plan: Plan to clear approval for
    """
    if isinstance(plan, Plan):
        plan_dict = {
            "goal": plan.goal,
            "steps": [{"step_number": s.step_number} for s in plan.steps],
        }
    else:
        plan_dict = plan

    plan_key = f"plan_approval_{hash(str(plan_dict))}"
    if plan_key in st.session_state:
        del st.session_state[plan_key]


def get_pending_approvals() -> list[str]:
    """Get list of pending approval keys in session state.

    Returns:
        List of approval keys that are pending (None value)
    """
    pending = []
    for key in st.session_state:
        if key.startswith(("approval_", "plan_approval_", "step_approval_")):
            if st.session_state[key] is None:
                pending.append(key)
    return pending


def clear_all_approvals() -> None:
    """Clear all approval states from session."""
    keys_to_remove = [
        key
        for key in st.session_state
        if key.startswith(("approval_", "plan_approval_", "step_approval_"))
    ]
    for key in keys_to_remove:
        del st.session_state[key]
