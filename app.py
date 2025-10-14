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
        # keep original Date column (string) for fallback
        df["OriginalDate"] = df.get("Date", "")
        all_data.append(df)

if all_data:
    full_df = pd.concat(all_data, ignore_index=True)

    # --- Normalize and clean date formats safely ---
    if "OriginalDate" in full_df.columns:
        # Try automatic parsing (assume day-first for ambiguous d/m)
        full_df["ParsedDate"] = pd.to_datetime(full_df["OriginalDate"], errors="coerce", dayfirst=True)

        # For any unparsed dates, try a second pass assuming month-first (e.g. MM-DD-YYYY)
        mask_unparsed = full_df["ParsedDate"].isna()
        if mask_unparsed.any():
            full_df.loc[mask_unparsed, "ParsedDate"] = pd.to_datetime(
                full_df.loc[mask_unparsed, "OriginalDate"], errors="coerce", dayfirst=False
            )

        # If still unparsed, try some common explicit formats
        mask_unparsed = full_df["ParsedDate"].isna()
        if mask_unparsed.any():
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
                try:
                    full_df.loc[mask_unparsed, "ParsedDate"] = pd.to_datetime(
                        full_df.loc[mask_unparsed, "OriginalDate"], format=fmt, errors="coerce"
                    )
                except Exception:
                    pass
                mask_unparsed = full_df["ParsedDate"].isna()
                if not mask_unparsed.any():
                    break

        # Create Date_str for display in dd-mm-yyyy; fallback to original string if parsing failed
        full_df["Date_str"] = full_df["ParsedDate"].dt.strftime("%d-%b-%Y")
        full_df.loc[full_df["Date_str"].isna(), "Date_str"] = full_df["OriginalDate"].astype(str)

    else:
        # if there was no Date column, create placeholders
        full_df["ParsedDate"] = pd.NaT
        full_df["Date_str"] = ""

    # Create unified Competition label (Venue - dd-mm-yyyy or Venue - original date if parsing failed)
    full_df["Venue"] = full_df["Venue"].astype(str)
    full_df["Competition"] = full_df["Venue"] + " - " + full_df["Date_str"]

    # --- Sort competitions by ParsedDate (newest first). Unparsed go to the bottom ---
    full_df = full_df.sort_values("ParsedDate", ascending=False, na_position="last")

    # Build unique competitions list (sorted newest → oldest)
    competitions_df = (
        full_df[["Competition", "ParsedDate"]]
        .drop_duplicates()
        .sort_values("ParsedDate", ascending=False, na_position="last")
        .reset_index(drop=True)
    )

    # Create dropdown for competition selection (one Selectbox only)
    selected_comp = st.selectbox("Select a competition", competitions_df["Competition"].tolist())

    # Identify throw columns dynamically and coerce to numeric (to avoid string comparisons)
    throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]
    # convert throw columns to numeric (non-numeric -> NaN)
    for c in throw_cols:
        full_df[c] = pd.to_numeric(full_df[c], errors="coerce")

    if "Player" in full_df.columns and throw_cols:
        # Calculate 180s for the full dataset (all competitions) — stored per row
        full_df["180s"] = full_df[throw_cols].apply(
            lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
        )

        # Group by competition and player to find total 180s per competition
        comp_180s = full_df.groupby(["Competition", "Player"])["180s"].sum().reset_index()

        # Find the single highest 180 total in any competition (guard for empty)
        if not comp_180s.empty:
            max_180_row = comp_180s.loc[comp_180s["180s"].idxmax()]
            max_180s = int(max_180_row["180s"])
            top_player = max_180_row["Player"]
            top_comp = max_180_row["Competition"]
            st.markdown(f"🏆 **Most 180s in a single competition:** {top_player} — {max_180s} ({top_comp})")

            # --- NEW: Find the player with the most 180s across the entire tournament ---
            total_180s_all = comp_180s.groupby("Player")["180s"].sum().reset_index()
            max_total_row = total_180s_all.loc[total_180s_all["180s"].idxmax()]
            top_total_player = max_total_row["Player"]
            top_total_180s = int(max_total_row["180s"])
            st.markdown(f"🎯 **Most 180s across all competitions:** {top_total_player} — {top_total_180s}")

            # --- NEW: Most 180s at a single tournament ---
            tournament_totals = comp_180s.groupby("Competition")["180s"].sum().reset_index()
            if not tournament_totals.empty:
                top_tournament_row = tournament_totals.loc[tournament_totals["180s"].idxmax()]
                top_tournament = top_tournament_row["Competition"]
                top_tournament_180s = int(top_tournament_row["180s"])
                st.markdown(f"📍 **Most 180s at a single tournament:** {top_tournament} - {top_tournament_180s} ")

        # Filter rows for the selected competition
        comp_df = full_df[full_df["Competition"] == selected_comp].copy()

        # Count 180s and 140-179 scores for each row/player within this competition
        comp_df["180s"] = comp_df[throw_cols].apply(
            lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
        )
        comp_df["140_179"] = comp_df[throw_cols].apply(
            lambda row: sum(1 for score in row if pd.notna(score) and 140 <= score <= 179), axis=1
        )
        comp_df["100_139"] = comp_df[throw_cols].apply(
            lambda row: sum(1 for score in row if pd.notna(score) and 100 <= score <= 139), axis=1
        )

        # Group by player and sum their counts
        player_stats = comp_df.groupby("Player")[["180s", "140_179", "100_139"]].sum().reset_index()

        # Rename columns for display
        player_stats.rename(columns={
            "140_179": "140+",
            "100_139": "100+"

        # Calculate total 180s across ALL players in this competition (before slicing to top 5)
        total_180s = int(player_stats["180s"].sum()) if not player_stats.empty else 0

        # Sort by 180s first, then 140-179, then 100-139 (desc)
        player_stats = player_stats.sort_values(by=["180s", "140_179", "100_139"], ascending=[False, False, False])

        # Keep top 5 for display
        top5_stats = player_stats.head(5).reset_index(drop=True)

        st.subheader(f"Total 180s - {total_180s}")

        # Display top 5 without conditional formatting
        st.dataframe(top5_stats, hide_index=True)

    else:
        st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
else:
    st.warning("No CSV files found in the data folder.")










