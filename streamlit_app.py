import streamlit as st
from pathlib import Path
import pandas as pd

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
        st.error(f"Missing file: {path}")
        st.stop()
    return pd.read_csv(path)

def show_image_if_exists(path: Path, caption: str = ""):
    if path.exists():
        st.image(str(path), use_container_width=True, caption=caption)
    else:
        st.info(f"Missing image: {path.name}")

# Load data
sim = load_csv(DATA / "sim_results.csv")
test = load_csv(DATA / "thermal_chamber_test.csv")
comparison = load_csv(OUT / "comparison_stats.csv")
matched = load_csv(OUT / "matched_operating_points.csv")
recommendations = load_csv(OUT / "next_best_tests_filtered_pretty.csv")
config_residuals = load_csv(OUT / "config_residuals.csv")
sensor_key_residuals = load_csv(OUT / "sensor_key_residuals.csv")
location_residuals = load_csv(OUT / "location_residuals.csv")
feasibility = load_csv(OUT / "feasibility_summary.csv")

configs = sorted(comparison["config"].tolist())

# Sidebar controls
selected_cfg = st.sidebar.selectbox("Select config", configs)
top_n = st.sidebar.slider("Top recommendations to show", 1, max(1, len(recommendations)), min(6, len(recommendations)))

# KPI row
row = comparison[comparison["config"] == selected_cfg].iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("Sim mean", f"{row['sim_mean']:.1f} °C")
c2.metric("Test mean", f"{row['test_mean']:.1f} °C")
c3.metric("Gap", f"{row['gap']:.1f} °C")

tabs = st.tabs(["Overview", "Reconciliation", "Next best tests"])

with tabs[0]:
    st.subheader("Overview")
    st.write("Simulation points:", len(sim))
    st.write("Test points:", len(test))
    st.write("Matched operating points:", len(matched))

    st.markdown("### Config-level comparison")
    st.dataframe(comparison, use_container_width=True)

    show_image_if_exists(OUT / "04_config_level.png", "Config-level sim vs test")
    show_image_if_exists(OUT / "06_gap.png", "Simulation vs test gap")

with tabs[1]:
    st.subheader("Reconciliation layer")
    st.write("This section shows the bias correction layer and sensor diagnostics.")

    st.markdown("### Config residuals")
    st.dataframe(config_residuals, use_container_width=True)

    st.markdown("### Sensor key residuals")
    st.dataframe(sensor_key_residuals.head(10), use_container_width=True)

    st.markdown("### Location residuals")
    st.dataframe(location_residuals, use_container_width=True)

    show_image_if_exists(OUT / "07_physics_aware_alignment.png", "Physics-aware operating-point alignment")
    show_image_if_exists(OUT / "08_residual_vs_power.png", "Residual vs power")
    show_image_if_exists(OUT / "09_mean_residual_by_config.png", "Mean residual by config")
    show_image_if_exists(OUT / "10_mean_residual_by_sensor_key.png", "Mean residual by sensor key")
    show_image_if_exists(OUT / "11_mean_residual_by_location_code.png", "Mean residual by location code")
    show_image_if_exists(OUT / "14_before_after_error_hist.png", "Before vs after reconciliation")
    show_image_if_exists(OUT / "16_interval_width_by_config.png", "Prediction interval width by config")

with tabs[2]:
    st.subheader("Next best tests")
    st.write(
        "Recommendations are constrained to the operating envelope observed in the chamber tests, "
        "with only minor extrapolation."
    )

    st.markdown("### Feasibility summary")
    st.dataframe(feasibility, use_container_width=True)

    st.markdown("### Top recommendations")
    rec_view = recommendations.head(top_n).copy()
    st.dataframe(rec_view, use_container_width=True)

    show_image_if_exists(OUT / "18_filtered_recommended_points_operating_space.png", "Filtered next-best-test recommendations")
    show_image_if_exists(OUT / "19_next_best_test_ranking_filtered.png", "Ranking of top recommendations")

st.divider()
st.caption("Powered by Streamlit Community Cloud")