"""Approval dialog component for code execution."""

import streamlit as st


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


def render_plan_approval(plan: dict) -> bool | None:
    """Render approval dialog for an agent plan.

    Args:
        plan: Plan dictionary with steps

    Returns:
        True if approved, False if rejected, None if pending
    """
    plan_key = f"plan_approval_{hash(str(plan))}"

    if plan_key in st.session_state:
        return st.session_state[plan_key]

    st.info("**Agent Plan**")

    steps = plan.get("steps", [])
    st.write(f"The agent proposes the following plan with {len(steps)} steps:")

    for i, step in enumerate(steps, 1):
        step_type = step.get("type", "unknown")
        description = step.get("description", "No description")
        requires_approval = step.get("requires_approval", False)

        approval_badge = " ⚠️ (requires approval)" if requires_approval else ""
        st.write(f"{i}. **{step_type}**: {description}{approval_badge}")

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
