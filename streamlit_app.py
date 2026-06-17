import streamlit as st
from pathlib import Path
import pandas as pd

st.set_page_config(
    page_title="Luminary Thermal Demo",
    page_icon="🔥",
    layout="wide",
)

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "outputs"

st.title("Luminary Thermal Reconciliation Demo")
st.caption("Simulation baseline + test reconciliation + next-best-test recommendations")

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.error(f"Missing file: {path.name}")
        st.stop()
    return pd.read_csv(path)

def show_image_if_exists(path: Path, caption: str = ""):
    if path.exists():
        st.image(str(path), use_container_width=True, caption=caption)
    else:
        st.info(f"Missing image: {path.name}")

def fmt(x, digits=1):
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return str(x)

# ---------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------
sim = load_csv(DATA / "sim_results.csv")
test = load_csv(DATA / "thermal_chamber_test.csv")
comparison = load_csv(OUT / "comparison_stats.csv")
matched = load_csv(OUT / "matched_operating_points.csv")
recommendations = load_csv(OUT / "next_best_tests_filtered_pretty.csv")
config_residuals = load_csv(OUT / "config_residuals.csv")
sensor_key_residuals = load_csv(OUT / "sensor_key_residuals.csv")
location_residuals = load_csv(OUT / "location_residuals.csv")
feasibility = load_csv(OUT / "feasibility_summary.csv")

# Optional outputs
candidate_scores = OUT / "candidate_pool_scored.csv"
if candidate_scores.exists():
    candidate_scores_df = pd.read_csv(candidate_scores)
else:
    candidate_scores_df = None

# ---------------------------------------------------------------------
# High-level summary
# ---------------------------------------------------------------------
comparison = comparison.sort_values("config").reset_index(drop=True)
avg_gap = comparison["gap"].mean()
avg_abs_gap = comparison["gap"].abs().mean()
total_sim = len(sim)
total_test = len(test)
n_configs = comparison["config"].nunique()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Configs", f"{n_configs}")
c2.metric("Simulation rows", f"{total_sim}")
c3.metric("Test rows", f"{total_test}")
c4.metric("Mean abs gap", f"{avg_abs_gap:.1f} °C")

st.markdown(
    """
    ### Executive takeaway
    - Config A is the anchor case; B/C/D remain under-validated.
    - Simulation and chamber test show a systematic mismatch, so a simple global offset is not enough.
    - The app reconciles simulation to test, makes uncertainty explicit, and ranks the next most informative tests within the observed chamber-test envelope.
    """
)

st.write(
    "This demo compares simulation and chamber test data, "
    "calibrates the simulation bias, and ranks the next tests "
    "within the operating envelope observed in the chamber data."
)

tabs = st.tabs(["Overview", "Reconciliation", "Next best tests", "Data"])

# ---------------------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------------------
with tabs[0]:
    st.subheader("Overview")

    st.markdown("### Config-level summary")
    st.dataframe(comparison, use_container_width=True)

    st.caption(
        "Mean abs gap is a high-level summary of the absolute difference between simulation and test means per config. "
        "Because B/C/D are sparse, interpret those rows cautiously."
    )

    st.markdown("### Gap by config")
    show_image_if_exists(OUT / "06_gap.png", "Simulation vs test gap by config")

    st.markdown("### Core comparison plots")
    cols = st.columns(2)
    with cols[0]:
        show_image_if_exists(OUT / "04_config_level.png", "Config-level sim vs test")
    with cols[1]:
        show_image_if_exists(OUT / "05_power_vs_temp.png", "Power vs temperature")

    st.markdown("### What this means")
    st.write(
        f"The average config gap is {avg_gap:.1f} °C and the mean absolute gap is {avg_abs_gap:.1f} °C. "
        "The bias is not constant across configs, so a simple offset is not enough; "
        "the reconciliation layer adds a physics-aware correction using power and ambient."
    )

# ---------------------------------------------------------------------
# RECONCILIATION
# ---------------------------------------------------------------------
with tabs[1]:
    st.subheader("Reconciliation layer")

    st.info(
        "Sensor-key analysis uses `thermocouple_id + location_code` because `thermocouple_id` alone is not unique. "
        "In particular, `TC_04` appears with two location codes (`CASE_TOP_CENTER` and `CASE_SIDE`), so it must not be treated as a single sensor."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("### Config residuals")
        st.dataframe(config_residuals, use_container_width=True)

    with right:
        st.markdown("### Location residuals")
        st.dataframe(location_residuals, use_container_width=True)

    st.markdown("### Sensor-key residuals")
    st.dataframe(sensor_key_residuals, use_container_width=True)

    st.markdown("### Physics-aware operating-point alignment")
    show_image_if_exists(OUT / "07_physics_aware_alignment.png", "Nearest sim point per test within same config")

    cols = st.columns(2)
    with cols[0]:
        show_image_if_exists(OUT / "08_residual_vs_power.png", "Residual vs power")
    with cols[1]:
        show_image_if_exists(OUT / "09_mean_residual_by_config.png", "Mean residual by config")

    cols = st.columns(2)
    with cols[0]:
        show_image_if_exists(OUT / "10_mean_residual_by_sensor_key.png", "Mean residual by sensor key")
    with cols[1]:
        show_image_if_exists(OUT / "11_mean_residual_by_location_code.png", "Mean residual by location code")

    cols = st.columns(2)
    with cols[0]:
        show_image_if_exists(OUT / "14_before_after_error_hist.png", "Before vs after reconciliation")
    with cols[1]:
        show_image_if_exists(OUT / "16_interval_width_by_config.png", "Prediction interval width by config")

    st.markdown("### A few matched operating points")
    show_cols = [
        "config",
        "sensor_key",
        "test_applied_power_W",
        "matched_sim_power_W",
        "test_ambient_temp_C",
        "matched_sim_ambient_C",
        "residual_C",
    ]
    st.dataframe(matched[show_cols].head(20), use_container_width=True)

    st.markdown("### Reconciliation interpretation")
    st.write(
        "The matching is done within each config using proximity in power and ambient. "
        "The residual captures the systematic gap between the matched simulation point "
        "and the physical measurement. The sensor-key tables help show whether the error "
        "is system-level or concentrated at specific measurement locations."
    )

# ---------------------------------------------------------------------
# NEXT BEST TESTS
# ---------------------------------------------------------------------
with tabs[2]:
    st.subheader("Next best tests")

    st.write(
        "Recommendations are constrained to the operating envelope observed in the chamber tests, "
        "with only minor extrapolation."
    )

    st.info(
        "How to read this: higher uncertainty, larger distance from already-tested operating points, "
        "and higher corrected junction temperature increase priority. The ranking is intentionally biased "
        "toward configs with sparse test coverage."
    )

    top_n = st.slider(
        "Top recommendations to show",
        min_value=1,
        max_value=max(1, len(recommendations)),
        value=min(10, len(recommendations)),
        step=1,
        key="top_n_slider",
    )

    st.markdown("### Feasibility summary")
    st.dataframe(feasibility, use_container_width=True)

    st.markdown("### Top recommendations")
    rec_view = recommendations.head(top_n).copy()
    st.dataframe(rec_view, use_container_width=True)

    cols = st.columns(2)
    with cols[0]:
        show_image_if_exists(
            OUT / "18_filtered_recommended_points_operating_space.png",
            "Filtered next-best-test recommendations",
        )
    with cols[1]:
        show_image_if_exists(
            OUT / "19_next_best_test_ranking_filtered.png",
            "Ranking of top recommendations",
        )

    st.markdown("### How to read the ranking")
    st.write(
        "Higher scores favor points with more uncertainty, more distance from already-tested conditions, "
        "and higher corrected junction temperature. The recommendation set is intentionally biased "
        "toward configs with sparse test coverage."
    )

    if candidate_scores_df is not None:
        st.markdown("### Candidate pool summary")
        st.dataframe(candidate_scores_df.head(20), use_container_width=True)

# ---------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------
with tabs[3]:
    st.subheader("Data")

    st.markdown("### Source datasets")
    c1, c2 = st.columns(2)
    with c1:
        st.write("Simulation rows:", len(sim))
        st.dataframe(sim.head(20), use_container_width=True)
    with c2:
        st.write("Test rows:", len(test))
        st.dataframe(test.head(20), use_container_width=True)

    st.markdown("### Output files available")
    outputs_list = sorted([p.name for p in OUT.iterdir() if p.is_file()])
    st.code("\n".join(outputs_list))

st.divider()
st.caption("Powered by Streamlit Community Cloud")
