"""Job status component for Streamlit."""

import streamlit as st

from src.database.models import Job


def render_job_status(jobs: list[Job]) -> None:
    """Render job status list.

    Args:
        jobs: List of jobs to display
    """
    if not jobs:
        return

    st.subheader("Jobs")

    for job in jobs:
        status_color = {
            "pending": "orange",
            "running": "blue",
            "completed": "green",
            "failed": "red",
            "cancelled": "gray",
        }.get(job.status, "gray")

        with st.expander(f":{status_color}[{job.status.upper()}] {job.job_type} - {job.id[:8]}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Type:** {job.job_type}")
                st.write(f"**Status:** {job.status}")

            with col2:
                if job.started_at:
                    st.write(f"**Started:** {job.started_at.strftime('%H:%M:%S')}")
                if job.completed_at:
                    st.write(f"**Completed:** {job.completed_at.strftime('%H:%M:%S')}")

            st.write("**Command:**")
            st.code(job.command, language="bash")

            if job.output:
                st.write("**Output:**")
                st.text(job.output[:1000])
                if len(job.output) > 1000:
                    st.info("Output truncated...")

            if job.error:
                st.error(f"Error: {job.error}")

            # Cancel button for running jobs
            if job.status in ("pending", "running"):
                if st.button("Cancel", key=f"cancel_{job.id}"):
                    st.session_state.cancel_job_id = job.id
                    st.rerun()


def render_job_progress(job: Job) -> None:
    """Render progress indicator for a running job.

    Args:
        job: Job to show progress for
    """
    if job.status == "running":
        st.info(f"Running: {job.job_type}")
        st.progress(0.5, text="Processing...")
    elif job.status == "pending":
        st.warning(f"Pending: {job.job_type}")
    elif job.status == "completed":
        st.success(f"Completed: {job.job_type}")
    elif job.status == "failed":
        st.error(f"Failed: {job.job_type}")
        if job.error:
            st.text(job.error)
