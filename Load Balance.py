#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import streamlit as st
from io import BytesIO

st.set_page_config(page_title="LTE Sector & Band Imbalance Tool", layout="centered")

st.title("📊 LTE Sector & Band Imbalance Analyzer")
st.write("Upload your LTE KPI Excel file to automatically calculate inter-band and inter-sector imbalance violations.")

uploaded_file = st.file_uploader("📂 Upload LTE KPI Excel File", type=["xlsx", "xls"])

if uploaded_file:
    try:
        # Load Excel file
        df = pd.read_excel(uploaded_file)
        df = df.dropna()

        # Extract Sector and Band from LNCEL name
        df['Sector'] = df['LNCEL name'].astype(str).str[-1]
        df['Band'] = df['LNCEL name'].astype(str).str[-2]

        # Drop unnecessary column
        df = df.drop(columns=['Period start time'], errors='ignore')

        # Convert numeric columns
        exclude_cols = ['LNCEL name', 'Band', 'Sector', 'LNBTS name']
        for col in df.columns:
            if col not in exclude_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Average per cell
        avg_df = df.groupby(['LNCEL name', 'Band', 'Sector', 'LNBTS name'], as_index=False).mean()

        # Violation checks
        group_cols = ['LNBTS name', 'Sector']
        violation_results = []

        for (lnbts, sector), group in avg_df.groupby(group_cols):
            entry = {'LNBTS name': lnbts, 'Sector': sector}

            # PRB Violation
            prb_max = group['E-UTRAN Avg PRB usage per TTI DL'].max()
            prb_min = group['E-UTRAN Avg PRB usage per TTI DL'].min()
            entry['PRB Violation'] = (prb_max - prb_min) > 30

            # User THP Violation
            thp_sum = group['E-UTRAN avg IP sched thp DL, QCI9'].sum()
            if thp_sum > 0:
                thp_norm = group['E-UTRAN avg IP sched thp DL, QCI9'] / thp_sum
                entry['User THP Violation'] = (thp_norm.max() / thp_norm.min()) > 1.3
            else:
                entry['User THP Violation'] = False

            # Traffic Violation
            traffic_sum = group['PDCP SDU Volume, DL'].sum()
            if traffic_sum > 0:
                traffic_norm = group['PDCP SDU Volume, DL'] / traffic_sum
                entry['Traffic Violation'] = (traffic_norm.max() / traffic_norm.min()) > 1.3
            else:
                entry['Traffic Violation'] = False

            violation_results.append(entry)

        violation_df = pd.DataFrame(violation_results)
        result = avg_df.merge(violation_df, on=['LNBTS name', 'Sector'], how='left')

        st.success("✅ Processing complete!")
        st.dataframe(result.head(10))

        # Prepare download
        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        st.download_button(
            label="📥 Download Processed Excel",
            data=output,
            file_name="output_with_sector_band.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
else:
    st.info("👆 Please upload an Excel file to begin analysis.")

