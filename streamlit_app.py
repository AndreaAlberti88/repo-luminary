import streamlit as st
from pathlib import Path
import pandas as pd
import joblib
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="Luminary Thermal Demo",
    page_icon="🔥",
    layout="wide"
)

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "outputs"

st.title("Luminary Thermal Reconciliation Demo")
st.caption("Simulation baseline + test reconciliation + next-best-test recommendations")

@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.error(f"Missing file: {path.name}")
        st.stop()
    return pd.read_csv(path)

@st.cache_resource
def load_model(path: Path):
    if not path.exists():
        st.error(f"Missing model: {path.name}")
        st.stop()
    return joblib.load(path)

# Load data
sim = load_csv(DATA / "sim_results.csv")
test = load_csv(DATA / "thermal_chamber_test.csv")
comparison = load_csv(OUT / "comparison_stats.csv")
matched = load_csv(OUT / "matched_operating_points.csv")
recommendations = load_csv(OUT / "next_best_tests_filtered_pretty.csv")
model = load_model(OUT / "reconciliation_model.joblib")

# Sidebar controls
configs = sorted(comparison["config"].tolist())
selected_cfg = st.sidebar.selectbox("Select config", configs)

max_rec = max(1, len(recommendations))
default_rec = min(6, max_rec)
top_n = st.sidebar.slider("Top recommendations to show", 1, max_rec, default_rec)

# Metrics
row = comparison[comparison["config"] == selected_cfg].iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("Sim mean", f"{row['sim_mean']:.1f} °C")
c2.metric("Test mean", f"{row['test_mean']:.1f} °C")
c3.metric("Gap", f"{row['gap']:.1f} °C")

tabs = st.tabs(["Overview", "Reconciliation", "Next best tests"])

with tabs[0]:
    st.subheader("Data overview")
    st.write("Simulation points:", len(sim))
    st.write("Test points:", len(test))
    st.write("Matched operating points:", len(matched))

    st.markdown("### Config-level comparison")
    st.dataframe(comparison, use_container_width=True)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(comparison["config"], comparison["gap"])
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xlabel("Config")
    ax.set_ylabel("Gap (°C)")
    ax.set_title("Simulation vs Test gap by config")
    st.pyplot(fig)

with tabs[1]:
    st.subheader("Reconciliation layer")
    st.write("The model corrects the simulation residual using config, matched sim power, and matched sim ambient.")

    st.dataframe(
        matched[[
            "config",
            "sensor_key",
            "test_applied_power_W",
            "matched_sim_power_W",
            "test_ambient_temp_C",
            "matched_sim_ambient_C",
            "residual_C"
        ]].head(20),
        use_container_width=True
    )

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(matched["residual_C"], matched["abs_residual_C"], alpha=0.5)
    ax.set_xlabel("Residual (°C)")
    ax.set_ylabel("Absolute residual (°C)")
    ax.set_title("Residual magnitude")
    st.pyplot(fig)

with tabs[2]:
    st.subheader("Recommended next tests")
    st.write(
        "Recommendations are constrained to the operating envelope observed in the chamber tests, "
        "with only minor extrapolation."
    )

    rec_view = recommendations.head(top_n).copy()
    st.dataframe(rec_view, use_container_width=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(range(len(rec_view)), rec_view["final_score"])
    ax.set_xticks(range(len(rec_view)))
    ax.set_xticklabels(
        [f"{i+1}-{cfg}" for i, cfg in enumerate(rec_view["config"])],
        rotation=45,
        ha="right"
    )
    ax.set_title("Top recommended tests")
    ax.set_ylabel("Score")
    st.pyplot(fig)

st.divider()
st.caption("Powered by Streamlit Community Cloud")