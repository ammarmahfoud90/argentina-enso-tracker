"""Render compatibility entry point for the maintained scientific dashboard.

The former Streamlit analysis read legacy uncorrected correlation caches.
Expose the maintained static dashboard instead of a conflicting analysis.
"""
import streamlit as st
import streamlit.components.v1 as components

SITE_URL = "https://ammarmahfoud90.github.io/argentina-enso-tracker/"
st.set_page_config(page_title="Argentina ENSO Tracker", layout="wide")
st.link_button("Abrir Argentina ENSO Tracker", SITE_URL)
components.iframe(SITE_URL, height=1400, scrolling=True)
