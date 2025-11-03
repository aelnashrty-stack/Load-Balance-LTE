#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="LTE Sector Balance Tool", layout="wide")

st.title("📶 LTE Sector Balance Checker")

# --- Sidebar Threshold Controls ---
st.sidebar.header("⚙️ Threshold Settings")
prb_threshold = st.sidebar.number_input(
    "PRB Utilization Difference Threshold (%)", min_value=1, max_value=100, value=30
)
thp_ratio_threshold = st.sidebar.number_input(
    "User THP Ratio Threshold", min_value=1.0, max_value=5.0, value=1.3
)
traffic_ratio_threshold = st.sidebar.number_input(
    "Traffic Ratio Threshold", min_value=1.0, max_value=5.0, value=1.3
)

# --- File Upload ---
uploaded_file = st.file_uploader("📂 Upload your LTE Excel file", type=["xlsx"])

if uploaded_file is not None:
    # --- Load and Clean Data ---
    df = pd.read_excel(uploaded_file)
    df = df.dropna()

    # Extract Sector & Band
    df['Sector'] = df['LNCEL name'].astype(str).str[-1]
    df['Band'] = df['LNCEL name'].astype(str).str[-2]

    # Drop unused columns
    df = df.drop(columns=['Period start time'], errors='ignore')

    # Convert KPI columns to numeric
    exclude_cols = ['LNCEL name', 'Band', 'Sector', 'LNBTS name']
    for col in df.columns:
        if col not in exclude_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # --- Group by Cell & Average ---
    avg_df = df.groupby(['LNCEL name', 'Band', 'Sector', 'LNBTS name'], as_index=False).mean()

    # --- Detect Violations ---
    violation_results = []
    for (lnbts, sector), group in avg_df.groupby(['LNBTS name', 'Sector']):
        entry = {'LNBTS name': lnbts, 'Sector': sector}

        # PRB Violation
        prb_max = group['E-UTRAN Avg PRB usage per TTI DL'].max()
        prb_min = group['E-UTRAN Avg PRB usage per TTI DL'].min()
        entry['PRB Violation'] = (prb_max - prb_min) > prb_threshold

        # User THP Violation
        thp_sum = group['E-UTRAN avg IP sched thp DL, QCI9'].sum()
        if thp_sum > 0:
            thp_norm = group['E-UTRAN avg IP sched thp DL, QCI9'] / thp_sum
            thp_ratio = thp_norm.max() / thp_norm.min()
            entry['User THP Violation'] = thp_ratio > thp_ratio_threshold
        else:
            entry['User THP Violation'] = False

        # Traffic Violation
        traffic_sum = group['PDCP SDU Volume, DL'].sum()
        if traffic_sum > 0:
            traffic_norm = group['PDCP SDU Volume, DL'] / traffic_sum
            traffic_ratio = traffic_norm.max() / traffic_norm.min()
            entry['Traffic Violation'] = traffic_ratio > traffic_ratio_threshold
        else:
            entry['Traffic Violation'] = False

        violation_results.append(entry)

    violation_df = pd.DataFrame(violation_results)

    # --- Merge Results ---
    avg_df_with_violations = avg_df.merge(violation_df, on=['LNBTS name', 'Sector'], how='left')

    # --- Calculate Summary Stats ---
    total_sectors = len(avg_df_with_violations[['LNBTS name', 'Sector']].drop_duplicates())
    criteria = ['PRB Violation', 'User THP Violation', 'Traffic Violation']
    stats = []
    for c in criteria:
        violated = avg_df_with_violations[c].sum()
        percent = (violated / total_sectors) * 100 if total_sectors > 0 else 0
        stats.append({
            'Criteria': c,
            'Violated Sectors': int(violated),
            'Total Sectors': total_sectors,
            '% Unbalanced': round(percent, 1)
        })
    stats_df = pd.DataFrame(stats)

    # --- Display Outputs ---
    st.subheader("📊 Detailed Results (first 50 rows)")
    st.dataframe(avg_df_with_violations.head(50))

    st.subheader("📈 Violation Statistics Summary")
    st.dataframe(stats_df)

    st.bar_chart(stats_df.set_index('Criteria')['% Unbalanced'])

    # --- Export to Excel (2 sheets) ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        avg_df_with_violations.to_excel(writer, sheet_name='Detailed Results', index=False)
        stats_df.to_excel(writer, sheet_name='Violation Summary', index=False)

    st.download_button(
        label="💾 Download Results as Excel (with Stats)",
        data=output.getvalue(),
        file_name="sector_balance_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👆 Please upload your LTE Excel file to start the analysis.")

