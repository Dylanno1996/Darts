import streamlit as st
import pandas as pd
import os

st.title("IDL GP Stats")

data_folder = "data"
all_data = []

# Load all CSVs
for file in os.listdir(data_folder):
    if file.endswith(".csv"):
        df = pd.read_csv(os.path.join(data_folder, file))
        df["Competition"] = df["Venue"] + " - " + df["Date"]
        all_data.append(df)

if all_data:
    full_df = pd.concat(all_data, ignore_index=True)

    # Identify throw columns dynamically
    throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]

    if "Player" in full_df.columns and throw_cols:
        # Dropdown for competition selection
        competitions = full_df["Competition"].unique()
        selected_comp = st.selectbox("Select a competition", competitions)

        comp_df = full_df[full_df["Competition"] == selected_comp]

        # Count 180s and 140-179 scores for each player
        comp_df["180s"] = comp_df[throw_cols].apply(
            lambda row: sum(score == 180 for score in row if pd.notna(score)), axis=1
        )
        comp_df["140_179"] = comp_df[throw_cols].apply(
            lambda row: sum(140 <= score <= 179 for score in row if pd.notna(score)), axis=1
        )
        comp_df["100_139"] = comp_df[throw_cols].apply(
            lambda row: sum(100 <= score <= 139 for score in row if pd.notna(score)), axis=1
        )

        # Group by player
        player_stats = comp_df.groupby("Player")[["180s", "140_179", "100_139"]].sum().reset_index()

        # Sort by 180s first, then 140-179
        player_stats = player_stats.sort_values(by=["180s", "140_179", "100_139"], ascending=[False, False])

        # Total 180s in competition
        total_180s = player_stats["180s"].sum()

        st.subheader(f"Total 180s - {total_180s}")

        # Display table without index
        st.dataframe(player_stats, hide_index=True)
    else:
        st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
else:
    st.warning("No CSV files found in the data folder.")

