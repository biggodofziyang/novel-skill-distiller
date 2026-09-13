"""Streamlit application entry point."""

import streamlit as st

from core.constants import LAYOUT, PAGE_ICON, PAGE_TITLE
from ui.workbench_full import render


def configure_page() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT,
        initial_sidebar_state="expanded",
    )


def main() -> None:
    configure_page()
    render()


if __name__ == "__main__":
    main()