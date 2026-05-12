import streamlit as st

st.set_page_config(
    page_title="LiveTranslate",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide sidebar entirely
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Route between pages
params = st.query_params
page = params.get("page", "home")

if page == "speaker":
    import speaker
    speaker.show()
elif page == "audience":
    import audience
    audience.show()
else:
    import home
    home.show()
