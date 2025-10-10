import streamlit as st
import pandas as pd
import os

st.title("Darts League Stats Viewer")

# Load all CSVs from the data folder
data_folder = "data"
all_data = []

for file in os.listdir(data_folder):
    if file.endswith(".csv"):
        df = pd.read_csv(os.path.join(data_folder, file))
        df["Competition"] = file.replace(".csv", "")
        all_data.append(df)

# Combine all data
if all_data:
    full_df = pd.concat(all_data, ignore_index=True)
    st.write("Combined Data", full_df)

    # Filter by player
    players = st.multiselect("Select players", full_df["Player"].unique())
    filtered_df = full_df[full_df["Player"].isin(players)] if players else full_df

    st.write("Filtered Stats", filtered_df.describe())

    if st.checkbox("Show raw data"):
        st.write(filtered_df)
else:
    st.warning("No CSV files found in the data folder.")