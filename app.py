# app.py — Render compatibility stub
#
# The Streamlit app was moved to legacy/app.py during the static-site
# refactor. Render's startCommand still references this root-level file.
# This stub runs the legacy app in the same Streamlit execution context.
#
# Streamlit executes this file as a script on every rerun, so exec() works:
# all st.* calls inside legacy/app.py are captured by the running session.

with open("legacy/app.py", encoding="utf-8") as _f:
    exec(_f.read())  # noqa: S102
