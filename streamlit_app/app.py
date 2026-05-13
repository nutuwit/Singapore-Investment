import streamlit as st
import pandas as pd
import numpy as np
import os

# ----------------------------------
# CONFIG
# ----------------------------------
st.set_page_config(
    page_title="Economic Visualization Catalog",
    layout="wide"
)

DATA_DIR = "Singapore-Investment/data/processed"

# ----------------------------------
# PLACEHOLDER DATA
# ----------------------------------
def placeholder_series():
    dates = pd.date_range(start="2019-01-01", periods=60, freq="M")
    return pd.DataFrame({
        "date": dates,
        "value": np.random.randn(len(dates)).cumsum()
    })

# ----------------------------------
# LOAD DATA (PIPELINE)
# ----------------------------------
@st.cache_data
def load_data():
    data = {}

    if not os.path.exists(DATA_DIR):
        return data

    for file in os.listdir(DATA_DIR):
        if file.endswith(".csv"):
            name = file.replace(".csv", "").lower()
            path = os.path.join(DATA_DIR, file)

            try:
                df = pd.read_csv(path)
                df.columns = [c.lower() for c in df.columns]

                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")

                data[name] = df

            except:
                pass

    return data


datasets = load_data()

# ----------------------------------
# VISUALIZATION MODULES
# ----------------------------------

def viz_real_interest_rate():
    title = "Real Interest Rate (SORA - Inflation)"

    try:
        df_rate = datasets.get("interest_rate")
        df_cpi = datasets.get("cpi")

        if df_rate is None or df_cpi is None:
            raise Exception("Missing data")

        df = pd.merge(df_rate, df_cpi, on="date")
        df["real_rate"] = df["value_x"] - df["value_y"]

    except:
        df = placeholder_series()
        df["real_rate"] = df["value"]

    return title, df, "real_rate"


def viz_neer_trend():
    title = "NEER Trend"

    try:
        df = datasets.get("neer")

        if df is None:
            raise Exception("Missing data")

    except:
        df = placeholder_series()

    return title, df, "value"


def viz_gdp_growth():
    title = "GDP Growth"

    try:
        df = datasets.get("gdp")

        if df is None:
            raise Exception("Missing data")

    except:
        df = placeholder_series()

    return title, df, "value"


def viz_corruption_index():
    title = "Corruption Perception Index"

    df = placeholder_series()  # likely external source later

    return title, df, "value"


# ----------------------------------
# VISUALIZATION REGISTRY
# ----------------------------------

visualizations = {
    "Economic Indicators": [
        viz_real_interest_rate,
        viz_neer_trend,
        viz_gdp_growth
    ],
    "Governance Indicators": [
        viz_corruption_index
    ]
}

# ----------------------------------
# SIDEBAR SEARCH
# ----------------------------------
st.sidebar.title("🔎 Search")

search_query = st.sidebar.text_input("Search visualization")

# ----------------------------------
# TITLE
# ----------------------------------
st.title("📊 Economic Visualization Catalog")

st.markdown("""
Each card represents a **predefined economic visualization**.

Not raw data → but interpreted analytical outputs.
""")

# ----------------------------------
# CARD RENDER FUNCTION
# ----------------------------------

def render_card(viz_func):
    title, df, y_col = viz_func()

    # Search filter
    if search_query:
        if search_query.lower() not in title.lower():
            return

    st.markdown(f"## {title}")

    col1, col2 = st.columns([2, 1])

    # -------------------------
    # VISUALIZATION
    # -------------------------
    with col1:
        st.markdown("### 📊 Visualization")

        try:
            st.line_chart(df.set_index("date")[y_col])
        except:
            st.line_chart(placeholder_series().set_index("date")["value"])

        # TODO:
        # Replace with:
        # - plotly
        # - multi-line comparison
        # - annotations

    # -------------------------
    # INTERPRETATION
    # -------------------------
    with col2:
        st.markdown("### 🧠 Interpretation")

        st.markdown(f"""
        **What is this?**
        - {title}

        **Why it matters**
        - Placeholder explanation

        **How to interpret**
        - Placeholder logic

        **TODO**
        - Add real macroeconomic interpretation
        """)

    st.markdown("---")


# ----------------------------------
# RENDER ALL
# ----------------------------------

for section, viz_list in visualizations.items():

    st.header(section)

    for viz in viz_list:
        render_card(viz)