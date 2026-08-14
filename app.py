import streamlit as st
import pandas as pd
import io
from network_1d import adjust_1d_network

st.set_page_config(page_title="GEOADJUST - 1D Network Adjustment", layout="wide")

st.title("🌐 GEOADJUST: 1D Network Adjustment")
st.write("Upload your leveling network file, configure constraints, and download the adjusted output.")

# --- Sidebar Inputs ---
st.sidebar.header("1. Input Parameters")
bm_name = st.sidebar.text_input("Benchmark Station Name", value="BMFAB")
bm_height = st.sidebar.number_input("Benchmark Height (m)", value=100.0, format="%.3f")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload Excel (.xlsx) or CSV file", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_input = pd.read_csv(uploaded_file, header=None)
        else:
            df_input = pd.read_excel(uploaded_file, header=None)

        st.subheader("📋 Input Data Preview")
        st.dataframe(df_input.head())

        if st.button("🚀 Run 1D Adjustment"):
            # Compute Adjustment
            results = adjust_1d_network(df_input, bm_name, bm_height)

            st.success("Adjustment Completed Successfully!")

            # Display Stats
            st.metric("Reference Variance (σ₀²)", f"{results['sigma0_sq']:.6f}")
            st.metric("Degrees of Freedom", results['dof'])

            # Display Results Tables
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📍 Adjusted Station Heights")
                st.dataframe(results['stations'])

            with col2:
                st.subheader("📏 Observation Residuals")
                st.dataframe(results['residuals'])

            # --- Export Section ---
            st.markdown("---")
            st.subheader("💾 Download Results")

            export_format = st.radio("Select Export Format:", ["Excel (.xlsx)", "CSV (.csv)"])

            if export_format == "Excel (.xlsx)":
                # Create an Excel buffer with multiple sheets
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    results['stations'].to_excel(writer, sheet_name='Adjusted Heights', index=False)
                    results['residuals'].to_excel(writer, sheet_name='Residuals', index=False)
                
                st.download_button(
                    label="📥 Download Excel Report",
                    data=buffer.getvalue(),
                    file_name="1D_Adjustment_Results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            else:
                # Combine data into single CSV download
                combined_df = pd.concat([results['stations'], results['residuals']], axis=1)
                csv_data = combined_df.to_csv(index=False).encode('utf-8')

                st.download_button(
                    label="📥 Download CSV Report",
                    data=csv_data,
                    file_name="1D_Adjustment_Results.csv",
                    mime="text/csv"
                )

    except Exception as e:
        st.error(f"Error processing file: {e}")
