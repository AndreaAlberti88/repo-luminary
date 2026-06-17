# ASSIGNMENT_DOCUMENTATION.md

## Project Summary

This take-home project focused on building a lightweight thermal decision-support prototype for a semiconductor power systems team preparing for a critical design review. The customer had three data sources:

1. simulation results,
2. physical chamber test data,
3. supplier-reported datasheet metrics.

The core problem was that simulation and test data did not match exactly, and the customer needed a practical way to:
- understand the simulation-to-test bias,
- estimate junction temperature at new operating points,
- quantify uncertainty,
- and prioritize the most informative remaining tests.

The final deliverable is a small, interpretable workflow rather than a black-box model. The emphasis was on transparency, reproducibility, and engineering usability.

---

## What I Built

I built a complete Phase 1 workflow consisting of:

- data loading and cleaning,
- unit normalization,
- configuration alignment between simulation and test,
- residual analysis,
- a physics-aware reconciliation layer,
- uncertainty estimation via bootstrap,
- a “next best tests” ranking method,
- and a Streamlit demo to make the results interactive and easy to explore.

The final Streamlit app shows:
- config-level comparison,
- reconciliation and residual diagnostics,
- sensor/location residual summaries,
- and recommended next tests constrained to the chamber-test envelope.

---

## Data Understanding and Key Assumptions

### 1. Simulation data
The simulation dataset was treated as a **broad design sweep**. Louis confirmed that simulation load cases were independently generated design points and were **not** paired one-to-one with physical chamber tests.

The simulation fields used most heavily were:
- `component_id`
- `power_dissipation_W`
- `T_junction_C`
- `T_case_C`
- `T_ambient_C`

Louis clarified that:
- `T_junction_C` is the **peak junction temperature**,
- `T_case_C` is the **case reference temperature**,
- `T_ambient_C` is the ambient boundary condition.

### 2. Test data
The chamber tests were treated as a **narrow validation subset** of the operating space. The most important fields were:
- `specimen_id`
- `ambient_temp_K`
- `case_temp_K`
- `hotspot_temp_K`
- `applied_power_W`
- `thermocouple_id`
- `location_code`

Louis clarified that:
- `hotspot_temp` is a direct thermocouple reading at the hottest location,
- `case_temp` is a direct reading at the case position,
- `ambient_temp` is the ambient reference.

### 3. Supplier data
The supplier datasheet data was used only as **context / guardrail information**. It was not used as a primary training target because the supplier values were high-level and not directly comparable to the internal simulation and chamber-test data.

---

## Data Cleaning and Normalization

### Kelvin to Celsius conversion
The chamber-test temperatures were provided in Kelvin, while the simulation temperatures were already in Celsius. For consistent comparison, all test temperatures were converted from Kelvin to Celsius using:

\[
^\circ C = K - 273.15
\]

This conversion was applied to:
- `hotspot_temp_K` → `hotspot_temp_C`
- `case_temp_K` → `case_temp_C`
- `ambient_temp_K` → `ambient_temp_C`

This was required so that simulation and test values were in the same units before any comparison or modeling.

### Configuration mapping
The two datasets used different naming conventions:
- simulation config names: `POWERMOD-A`, `POWERMOD-B`, `POWERMOD-C`, `POWERMOD-D`
- test specimen IDs: `PWM-A-xxx`, `PWM-B-xxx`, `PWM-C-xxx`, `PWM-D-xxx`

I mapped the test prefixes to the simulation config names so that the same family of design could be compared across datasets.

### Sensor identity issue
A small inconsistency existed in the test data:
- `thermocouple_id = TC_04` appeared with two different `location_code` values:
  - `CASE_TOP_CENTER`
  - `CASE_SIDE`

This means `thermocouple_id` alone is **not a unique sensor key**.  
To avoid ambiguity, I used:

\[
\text{sensor key} = \text{thermocouple_id} + \text{location_code}
\]

This is the correct way to interpret the sensor-level residuals.

---

## Configuration Coverage and Why Some Gaps Are More Reliable Than Others

The configurations had very different test coverage:

- **POWERMOD-A**: approximately 80 test rows
- **POWERMOD-B**: approximately 3 test rows
- **POWERMOD-C**: approximately 2 test rows
- **POWERMOD-D**: approximately 4 test rows

Simulation coverage was balanced across all four configs, with about 50 rows each.

Because of this imbalance:

- statistics for **POWERMOD-A** are relatively trustworthy,
- statistics for **B/C/D** are much less stable,
- and the apparent gap for B/C/D must be interpreted carefully.

With only 2–4 test points, the estimated mean, standard deviation, and gap for B/C/D are highly sensitive to individual points and outliers. In particular:
- a small sample can make a gap look much more stable or unstable than it really is,
- and a “near-zero” gap for a config with only two points is not strong evidence of true agreement.

This is why the analysis explicitly treats A as the strongest anchor configuration and treats B/C/D with much more caution.

---

## Initial Config-Level Gap Analysis

The first comparison was a simple config-level mean comparison between:
- mean simulation `T_junction_C`
- mean test `hotspot_temp_C`

This produced the following qualitative picture:
- **A** had a moderate positive gap,
- **B** had a negative gap,
- **C** had almost no gap but too few test points to trust it strongly,
- **D** had a very large gap.

The important conclusion was that the gap is **not constant across configurations**.  
That means a single global offset is not sufficient.

---

## Physics-Aware Matching: “Nearest Sim Point per Test within Same Config”

Because there is no one-to-one mapping between simulation load cases and chamber tests, I built a physics-aware alignment step.

For each chamber-test row:
1. I restricted the search to the same configuration.
2. I compared the test operating point to all simulation operating points in that same config.
3. I used distance in operating space defined by:
   - power difference,
   - ambient temperature difference.
4. I selected the nearest simulation point.

This produced the “nearest sim point per test” mapping.

### Why this was done
The purpose was not to claim the rows are identical.  
The purpose was to compare each physical test to the most similar simulation point available in the same config.

### How it was computed
For each test row:
- I standardized power and ambient within the config,
- computed the Euclidean distance to each simulation row,
- and selected the simulation row with minimum distance.

This gave a more physically meaningful comparison than simply comparing config averages.

---

## Reconciliation Layer

The reconciliation layer is the core modeling step.

### Goal
Predict the **residual** between test and matched simulation:

\[
\text{residual} = \text{test hotspot temperature} - \text{matched sim junction temperature}
\]

### Features used
The reconciliation model used:
- `config`
- `matched_sim_power_W`
- `matched_sim_ambient_C`

### Model type
I used a **ridge regression** model because it is:
- simple,
- stable,
- interpretable,
- and appropriate for a small dataset.

### Why ridge regression
Ridge regression is linear regression with L2 regularization. It helps avoid overly large coefficients and is especially useful when:
- sample size is limited,
- features are correlated,
- and the desired model should remain transparent.

### Why this model was chosen over a more complex one
I deliberately avoided a black-box model because:
- the dataset is small,
- the customer is skeptical of opaque AI,
- and the business need is decision support, not ML benchmark performance.

### What the reconciliation model does
Once trained, it predicts a corrected residual.  
The corrected junction temperature is then:

\[
\text{corrected junction temperature} = \text{matched sim junction temperature} + \text{predicted residual}
\]

This gives a calibrated prediction that is closer to the physical test data than the raw simulation output.

---

## Reconciliation Performance

The reconciliation model reduced the error substantially.

Key metrics after reconciliation were approximately:
- **Reconciliation MAE on residuals**: 4.31 °C
- **Reconciliation RMSE on residuals**: 4.92 °C
- **Reconciliation R² on residuals**: 0.711

This means the simple model captured a large fraction of the residual structure while remaining interpretable.

### Interpretation
The model does not eliminate all error, but it reduces the raw simulation-to-test mismatch dramatically and makes the correction usable for decision support.

---

## Sensor and Location Diagnostics

I also analyzed residuals by:
- configuration,
- thermocouple,
- sensor key (`thermocouple_id + location_code`),
- and location code.

This helped answer whether the mismatch was:
- mainly a system-level bias,
- or whether specific sensors were behaving oddly.

### Important observation
The `CASE_SIDE` location with `TC_04` showed a larger residual, but it appeared only once.  
Because of that, it is not statistically strong enough to conclude that `CASE_SIDE` is systematically different. It is best treated as a follow-up item, not as a firm engineering conclusion.

### Main conclusion from sensor analysis
The residuals were generally positive and clustered in a similar range. This suggests the mismatch is largely **system-level**, not dominated by a single defective sensor.

---

## Uncertainty Estimation

To communicate uncertainty, I used bootstrap resampling.

### Why
The customer explicitly wanted confidence intervals / uncertainty margins.  
Since the data is sparse, especially for B/C/D, uncertainty is critical.

### How it works
- resample the matched reconciliation data with replacement,
- refit the ridge model many times,
- generate a distribution of predictions for each candidate test point,
- compute prediction percentiles (10th, 50th, 90th).

This gives a simple uncertainty band around the corrected junction-temperature estimate.

---

## Next Best Tests

The next-best-test recommendation layer was designed to answer:

> Given a limited remaining test budget, which chamber runs add the most information?

### What it uses
The ranking combines:
- predicted corrected junction temperature,
- prediction uncertainty,
- distance from already-tested operating points,
- scarcity of test coverage per config.

### Why this matters
A good next test is not just a “hot” test.  
It should also be:
- informative,
- under-sampled,
- and within the feasible test envelope.

### Operating envelope constraint
Louis confirmed that recommendations should be constrained to the operating envelope already observed in the chamber tests, with only minor extrapolation if needed.

So the next-best-test ranking was filtered to points near the chamber-test domain rather than being allowed to explore the much broader simulation sweep.

### Resulting behavior
The recommendation layer prioritizes under-tested configurations, especially B and D, because:
- A is already relatively well covered,
- C has very few points but is not always as informative as B/D,
- and B/D need more validation before review.

---

## Why the Plot “Sim vs Test Aligned Configs” Is Useful but Limited

The “SIMULATION vs TEST (Aligned Configs)” plot is a useful high-level visual, but it does **not** imply exact row matching.

It is only telling us that:
- within each configuration, the simulation points and test points occupy different but related thermal spaces,
- and that a config-level comparison is meaningful, but not a strict point-by-point comparison.

This is why the physics-aware matching and reconciliation layer are needed.

---

## Why the Test-Gap Statistics Must Be Interpreted Carefully for Sparse Configs

For B, C, and D, the number of tests is extremely small.  
As a result:
- means are unstable,
- standard deviations are not robust,
- and apparent agreement or disagreement may be driven by one or two points.

This is why the report and demo emphasize:
- A as the strongest anchor,
- B/C/D as under-validated,
- and uncertainty as a first-class output.

---

## Streamlit Demo

The Streamlit app was built as a simple interactive front end for the analysis. It provides:
- overview metrics,
- config-level gap comparisons,
- reconciliation diagnostics,
- sensor/location residual summaries,
- and next-best-test recommendations.

The app is intentionally minimal and transparent. It does not try to hide the analysis behind a complex interface.

---

## AI Tools Used

I used ChatGPT to help with:
- scoping the analysis,
- cleaning and structuring the code,
- debugging notebook and Streamlit issues,
- drafting the reconciliation logic,
- designing the ranking logic,
- and writing supporting documentation.

I used Google Colab as the execution environment for analysis and prototype generation.  
I used Streamlit Community Cloud for deployment of the interactive demo.

---

## Tradeoffs Made

### 1. Simplicity over complexity
I chose a ridge regression reconciliation model instead of a more complex ML approach because the dataset is small and interpretability was more important than maximum predictive performance.

### 2. Physics-aware matching over naive row matching
Because the simulation and test rows are not one-to-one, I used nearest-neighbor matching in operating space instead of pretending there was a direct pairing.

### 3. Junction temperature as the main KPI
Louis confirmed that junction temperature is the primary KPI for phase 1, so the whole demo is centered on corrected junction-temperature prediction.

### 4. Test-enveloped recommendations instead of unconstrained exploration
The simulation sweep is intentionally broader than the test envelope. I therefore constrained the next-best-test ranking to the chamber-test operating envelope, with only minor extrapolation.

### 5. No joblib model loading in Streamlit
I avoided relying on a serialized scikit-learn pipeline inside Streamlit after environment/version incompatibility issues. The final demo is based on CSV outputs and precomputed artifacts, which is more robust for this take-home context.

---

## Limitations

- Test coverage is extremely sparse for B/C/D.
- No internal thermal margin threshold was provided.
- The sensor key `TC_04` / `CASE_SIDE` appears only once, so that outlier should be interpreted cautiously.
- The recommendation layer is constrained by the observed chamber-test envelope and does not represent full design-space optimization.
- The prototype is not a production MLOps system and does not include authentication or automated retraining.

---

## What I Would Do with One Additional Week

With one more week, I would:

1. Add a real thermal-margin threshold if the customer provides one.
2. Add a more formal leave-one-config-out validation.
3. Improve the recommendation layer with a stricter feasibility and risk framework.
4. Add authentication scaffolding for deployment.
5. Add a more polished report export for the design review board.
6. Improve the sensor-outlier analysis with more data, if available.
7. Refine the Streamlit UI with cleaner narrative framing for engineering stakeholders.

---

## Final Note

This prototype is intentionally lightweight and transparent.  
Its purpose is not to replace the customer’s engineering workflow, but to support a near-term design review by:
- reconciling simulation and test data,
- making uncertainty visible,
- and helping the team choose the next most informative tests.