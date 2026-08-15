import os
import io
import streamlit as st
import pandas as pd
from network_1d import adjust_1d_network

# --- Page Configuration ---
st.set_page_config(page_title="GEOADJUST - 1D Network Adjustment", layout="wide", page_icon="🌐")

st.title("🌐 GEOADJUST: 1D Vertical Network Adjustment")
st.write("Upload your leveling network file (.csv or .xlsx), validate the column format, compute least-squares adjustment, and export results.")

# --- Sidebar Inputs ---
st.sidebar.header("1. Fixed Datum Constraint")
bm_name = st.sidebar.text_input("Benchmark Station Name (Fixed)", value="BMFAB")
bm_height = st.sidebar.number_input("Benchmark Height (m)", value=100.0, format="%.4f")

st.sidebar.markdown("---")
st.sidebar.header("2. Output Directory Settings")
# Allow user to specify a local server/system directory path for saving results directly
default_dir = os.path.join(os.path.expanduser("~"), "GEOADJUST_Outputs")
output_dir = st.sidebar.text_input("Local Save Directory Path:", value=default_dir)
auto_save = st.sidebar.checkbox("Auto-save results to directory upon successful adjustment", value=True)

# --- Expected Schema Guidance ---
with st.expander("ℹ️ Click to view Required Column Format & Upload Instructions", expanded=False):
    st.markdown("""
    Your uploaded Excel (`.xlsx`) or CSV (`.csv`) file should follow this standard 1D differential leveling format:
    
    | Column Index | Recommended Header Name | Type | Description | Required? |
    |---|---|---|---|---|
    | **Col 1** | `From_Point` | String | Origin Station / Benchmark ID | **Yes** |
    | **Col 2** | `To_Point` | String | Target Station / Benchmark ID | **Yes** |
    | **Col 3** | `dH_m` | Float | Observed height difference ($m$) | **Yes** |
    | **Col 4** | `Dist_km` | Float | Sight distance / Line length ($km$) | Optional (default = 1.0) |
    | **Col 5** | `StdDev_mm` | Float | A-priori standard deviation ($mm$) | Optional (default = 1.0) |
    
    *Note: If your file does not contain headers, GEOADJUST will automatically assign these columns by position.*
    """)

# --- File Upload Section ---
st.subheader("📂 1. Upload Observation File")
uploaded_file = st.file_uploader("Choose a file (.xlsx or .csv)", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        # Check if header exists by sampling first row
        if uploaded_file.name.endswith('.csv'):
            df_preview = pd.read_csv(uploaded_file, nrows=2)
            has_header = st.checkbox("File includes a header row", value=True)
            uploaded_file.seek(0)
            if has_header:
                df_input = pd.read_csv(uploaded_file)
            else:
                df_input = pd.read_csv(uploaded_file, header=None)
        else:
            df_preview = pd.read_excel(uploaded_file, nrows=2)
            has_header = st.checkbox("File includes a header row", value=True)
            if has_header:
                df_input = pd.read_excel(uploaded_file)
            else:
                df_input = pd.read_excel(uploaded_file, header=None)

        # Standardize column names if no headers present or mismatched
        expected_cols = ["From_Point", "To_Point", "dH_m", "Dist_km", "StdDev_mm"]
        if not has_header or len(df_input.columns) < 3:
            # Map by index position
            col_mapping = {i: expected_cols[i] for i in range(min(len(df_input.columns), 5))}
            df_input = df_input.rename(columns=col_mapping)

        st.subheader("📋 Input Data Preview & Verification")
        st.dataframe(df_input.head(10), use_container_width=True)

        # Basic Format Validation
        if len(df_input.columns) < 3:
            st.error("❌ Invalid format: The input file must contain at least 3 columns (From_Point, To_Point, dH_m).")
        else:
            st.success("✅ File format verified successfully! Ready for adjustment.")

            # --- Execution Section ---
            if st.button("🚀 Run 1D Least Squares Adjustment", type="primary"):
                with st.spinner("Processing network adjustment..."):
                    # Compute Least Squares Adjustment
                    results = adjust_1d_network(df_input, bm_name, bm_height)

                    st.session_state['results'] = results
                    st.success("🎉 Adjustment Completed Successfully!")

            # --- Results & Export Section ---
            if 'results' in st.session_state:
                results = st.session_state['results']

                # Metrics Overview
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Reference Variance (σ₀²)", f"{results['sigma0_sq']:.6f}")
                col_m2.metric("Degrees of Freedom (DoF)", results['dof'])
                if 'chi_square' in results:
                    col_m3.metric("Chi-Square Test", results['chi_square'])

                # Data Tables
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📍 Adjusted Station Heights")
                    st.dataframe(results['stations'], use_container_width=True)

                with col2:
                    st.subheader("📏 Observation Residuals")
                    st.dataframe(results['residuals'], use_container_width=True)

                # --- Save to Custom Local Directory Action ---
                st.markdown("---")
                st.subheader("💾 Export & Save Output Files")

                # Handle Local Save Directory Logic
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    excel_path = os.path.join(output_dir, "1D_Adjustment_Results.xlsx")
                    csv_path = os.path.join(output_dir, "1D_Adjustment_Results.csv")

                    # Auto-save logic
                    if auto_save or st.button("📁 Save Output Files to Target Directory"):
                        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                            results['stations'].to_excel(writer, sheet_name='Adjusted Heights', index=False)
                            results['residuals'].to_excel(writer, sheet_name='Residuals', index=False)
                        
                        combined_df = pd.concat([results['stations'], results['residuals']], axis=1)
                        combined_df.to_csv(csv_path, index=False)
                        st.info(f"💾 Files successfully saved locally to: `{output_dir}`")

                # --- Browser Download Section ---
                st.write(" Or download directly via browser:")
                export_format = st.radio("Select Export Format:", ["Excel (.xlsx)", "CSV (.csv)"], horizontal=True)

                if export_format == "Excel (.xlsx)":
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        results['stations'].to_excel(writer, sheet_name='Adjusted Heights', index=False)
                        results['residuals'].to_excel(writer, sheet_name='Residuals', index=False)
                    
                    st.download_button(
                        label="📥 Download Excel Report (.xlsx)",
                        data=buffer.getvalue(),
                        file_name="1D_Adjustment_Results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                else:
                    combined_df = pd.concat([results['stations'], results['residuals']], axis=1)
                    csv_data = combined_df.to_csv(index=False).encode('utf-8')

                    st.download_button(
                        label="📥 Download CSV Report (.csv)",
                        data=csv_data,
                        file_name="1D_Adjustment_Results.csv",
                        mime="text/csv"
                    )

    except Exception as e:
        st.error(f"Error processing file or running adjustment: {e}")
