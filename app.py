import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="IDL Stats", layout="centered")
st.title("IDL Stats")

# --- Load all CSV data ---
data_folder = "data"
all_data = []

def detect_data_type(df):
    """Determine if the CSV is a Competition or League file."""
    has_division = "Division" in df.columns and df["Division"].notna().any()
    has_date = "Date" in df.columns and df["Date"].notna().any()
    if has_division and not has_date:
        return "League"
    else:
        return "Competition"

for file in os.listdir(data_folder):
    if file.endswith(".csv"):
        df = pd.read_csv(os.path.join(data_folder, file))
        df["OriginalDate"] = df.get("Date", "")
        df["DataType"] = detect_data_type(df)
        all_data.append(df)

if not all_data:
    st.warning("No CSV files found in the data folder.")
    st.stop()

full_df = pd.concat(all_data, ignore_index=True)

# --- Ensure Season is integer for league data ---
if "Season" in full_df.columns:
    # Convert valid numeric values, turn invalid/missing to <NA>, then nullable Int64
    full_df["Season"] = pd.to_numeric(full_df["Season"], errors="coerce").astype("Int64")

# --- Parse Date Column ---
full_df["ParsedDate"] = pd.NaT
if "OriginalDate" in full_df.columns:
    date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %m %Y"]
    for fmt in date_formats:
        mask_unparsed = full_df["ParsedDate"].isna()
        if mask_unparsed.any():
            full_df.loc[mask_unparsed, "ParsedDate"] = pd.to_datetime(
                full_df.loc[mask_unparsed, "OriginalDate"],
                format=fmt,
                errors="coerce"
            )
full_df["Date_str"] = full_df["ParsedDate"].dt.strftime("%d-%b-%Y")
full_df.loc[full_df["Date_str"].isna(), "Date_str"] = full_df["OriginalDate"].astype(str)

# --- Identify throw columns dynamically ---
throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]
for c in throw_cols:
    full_df[c] = pd.to_numeric(full_df[c], errors="coerce")

if "Player" not in full_df.columns or not throw_cols:
    st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
    st.stop()

# --- Sidebar navigation ---
data_mode = st.sidebar.radio("📁 Select Competition Type", ["🏆 Grand Prix", "🏅 League"])
page = st.sidebar.radio("📊 Select Stat", ["🎯 180s", "🎣 Checkouts", "👇 Lowest Legs"])

# --- Filter dataset based on selection ---
if data_mode == "🏆 Grand Prix":
    active_df = full_df[full_df["DataType"] == "Competition"].copy()
    active_df["Venue"] = active_df["Venue"].astype(str)
    active_df["Competition"] = active_df["Venue"] + " - " + active_df["Date_str"]

    options_df = (
        active_df[["Competition", "ParsedDate"]]
        .drop_duplicates()
        .sort_values("ParsedDate", ascending=False, na_position="last")
        .reset_index(drop=True)
    )
    selected_label = st.selectbox("Select a competition", options_df["Competition"].tolist())
    filtered_df = active_df[active_df["Competition"] == selected_label].copy()

else:
    active_df = full_df[full_df["DataType"] == "League"].copy()
    active_df["Division"] = active_df["Division"].astype(str)
    active_df["Season"] = active_df["Season"].astype(str)
    active_df["LeagueLabel"] = active_df["Division"] + " - " + active_df["Season"]

    options_df = (
        active_df[["LeagueLabel", "Division", "Season"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    selected_label = st.selectbox("Select a league/season", options_df["LeagueLabel"].tolist())
    filtered_df = active_df[active_df["LeagueLabel"] == selected_label].copy()

# --- 180s Stats Page ---
if page == "🎯 180s":
    # --- Calculate 180s, 140+, 100+ ---
    filtered_df["180s"] = filtered_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
    )
    filtered_df["140_179"] = filtered_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and 140 <= score <= 179), axis=1
    )
    filtered_df["100_139"] = filtered_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and 100 <= score <= 139), axis=1
    )

    # --- Top 5 stats for selected dropdown ---
    player_stats = filtered_df.groupby("Player")[["180s", "140_179", "100_139"]].sum().reset_index()
    player_stats.rename(columns={"140_179": "140+", "100_139": "100+"}, inplace=True)
    total_180s = int(player_stats["180s"].sum()) if not player_stats.empty else 0
    player_stats = player_stats.sort_values(by=["180s", "140+", "100+"], ascending=[False, False, False])
    top5_stats = player_stats.head(5).reset_index(drop=True)

    st.subheader(f"Total 180s - {total_180s}")
    st.dataframe(top5_stats, hide_index=True)

    # --- Most 180s player for whole season (ignores dropdown) ---
    overall_df = active_df.copy()
    overall_df["180s"] = overall_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
    )
    season_180s = overall_df.groupby("Player")["180s"].sum().reset_index()
    if not season_180s.empty:
        max_180_row = season_180s.loc[season_180s["180s"].idxmax()]
        st.markdown("---")
        st.subheader(f"**Most 180s**")
        st.markdown(f"{int(max_180_row['180s'])} — {max_180_row['Player']}")

    # --- Top 5 most 180s in a single competition ---
    st.markdown("---")
    if data_mode == "🏅 League":
        # For leagues, group by Player + Division + Season
        comp_group = overall_df.groupby(["Player","Division","Season"])["180s"].sum().reset_index()
        comp_group = comp_group.sort_values("180s", ascending=False).head(5).reset_index(drop=True)
    else:
        # For competitions, group by Player + Venue + Date
        comp_group = overall_df.groupby(["Player","Venue","Date_str"])["180s"].sum().reset_index()
        comp_group = comp_group.sort_values(["180s"], ascending=False).head(5).reset_index(drop=True)
        comp_group.rename(columns={"Date_str":"Date"}, inplace=True)
    
    # Reorder columns to put 180s second
    if data_mode == "🏅 League":
        comp_group = comp_group[["180s", "Player", "Division", "Season"]]
        table_title = "**Most 180s in a League Season**"
    else:
        comp_group = comp_group[["180s", "Player", "Venue", "Date"]]
        table_title = "**Most 180s in a Grand Prix**" 

    st.subheader(table_title)
    st.dataframe(comp_group, hide_index=True)

# --- Checkout Stats Page ---
elif page == "🎣 Checkouts":
    winners_df = filtered_df[filtered_df["Result"].str.upper() == "WON"].copy()
    if winners_df.empty:
        st.info("No winning legs found — cannot calculate checkouts.")
        st.stop()

    winners_df["Checkout"] = winners_df[throw_cols].apply(
        lambda row: row[pd.notna(row) & (row > 0)].iloc[-1] if any(pd.notna(row) & (row > 0)) else None,
        axis=1
    )
    winners_df = winners_df.dropna(subset=["Checkout"])
    winners_df["Checkout"] = pd.to_numeric(winners_df["Checkout"], errors="coerce")

    # --- Top 5 for selection (no venue/date needed) ---
    top5_checkouts = winners_df[["Player","Checkout"]]
    top5_checkouts = top5_checkouts.sort_values("Checkout", ascending=False).head(5).reset_index(drop=True)
    st.subheader(f"Highest Checkouts")
    st.dataframe(top5_checkouts, hide_index=True)

    # --- 170 Checkout Club (whole season, ignores dropdown) ---
    st.markdown("---")
    st.markdown("## 🎣 The Big Fish")
    
    # Use active_df to get all data for the season/all competitions
    winners_all = active_df[active_df["Result"].str.upper() == "WON"].copy()
    winners_all["Checkout"] = winners_all[throw_cols].apply(
        lambda row: row[pd.notna(row) & (row > 0)].iloc[-1] if any(pd.notna(row) & (row > 0)) else None,
        axis=1
    )
    winners_all = winners_all.dropna(subset=["Checkout"])
    winners_all["Checkout"] = pd.to_numeric(winners_all["Checkout"], errors="coerce")
    
    max_170_df = winners_all[winners_all["Checkout"] == 170].copy()

    if data_mode == "🏅 League":
        max_170_df = max_170_df[["Player","Division","Season"]].drop_duplicates()
        max_170_df = max_170_df.sort_values(by="Season", ascending=False).reset_index(drop=True)
    else:
        max_170_df = max_170_df[["Player","Venue","Date_str","ParsedDate"]].drop_duplicates()
        max_170_df = max_170_df.sort_values("ParsedDate", ascending=False, na_position="last").reset_index(drop=True)
        max_170_df = max_170_df[["Player","Venue","Date_str"]]
        max_170_df.rename(columns={"Date_str":"Date"}, inplace=True)
    if not max_170_df.empty:
        st.dataframe(max_170_df, hide_index=True)
    else:
        st.info("No 170 checkouts recorded.")

# --- Lowest Legs Page ---
elif page == "👇 Lowest Legs":
    winners_df = filtered_df[filtered_df["Result"].str.upper() == "WON"].copy()
    winners_overall = active_df[active_df["Result"].str.upper() == "WON"].copy()  # overall

    # --- Top table: Lowest legs per player for selected dropdown ---
    if winners_df.empty:
        st.info("No winning legs found for this selection.")
    else:
        # Ensure Total Darts numeric
        winners_df["Total Darts"] = pd.to_numeric(winners_df["Total Darts"], errors="coerce")
        winners_df["LastScore"] = winners_df[throw_cols].apply(
            lambda row: row[pd.notna(row) & (row>0)].iloc[-1] if any(pd.notna(row) & (row>0)) else None,
            axis=1
        )

        # Get the lowest leg per player for this selection
        lowest_per_player = winners_df.sort_values(["Total Darts", "LastScore"], ascending=[True, False])
        lowest_per_player = lowest_per_player.groupby("Player").first().reset_index()
        lowest_per_player = lowest_per_player.sort_values(["Total Darts", "LastScore"], ascending=[True, False])
        top5_lowest = lowest_per_player[["Player","Total Darts","LastScore"]].head(5).reset_index(drop=True)
        top5_lowest.rename(columns={"Total Darts":"Darts Thrown","LastScore":"Checkout"}, inplace=True)

        st.subheader(f"Lowest Legs — {selected_label}")
        st.dataframe(top5_lowest, hide_index=True)

    # --- Bottom table: Overall lowest legs across all data (with venue/date) ---
    st.markdown("---")
    st.subheader("**Lowest Legs Overall**")

    if winners_overall.empty:
        st.info("No winning legs found overall.")
    else:
        winners_overall["Total Darts"] = pd.to_numeric(winners_overall["Total Darts"], errors="coerce")
        winners_overall["LastScore"] = winners_overall[throw_cols].apply(
            lambda row: row[pd.notna(row) & (row>0)].iloc[-1] if any(pd.notna(row) & (row>0)) else None,
            axis=1
        )

        all_lowest = winners_overall.sort_values(["Total Darts","LastScore"], ascending=[True,False])
        
        if data_mode == "🏅 League":
            top5_overall = all_lowest[["Player","Total Darts","LastScore","Division","Season"]].head(5).reset_index(drop=True)
            top5_overall.rename(columns={"Total Darts":"Darts Thrown","LastScore":"Checkout"}, inplace=True)
            ll_table_title = "**Lowest Leg in a League Season**"
        else:
            top5_overall = all_lowest[["Player","Total Darts","LastScore","Venue","Date_str"]].head(5).reset_index(drop=True)
            top5_overall.rename(columns={"Total Darts":"Darts Thrown","LastScore":"Checkout","Date_str":"Date"}, inplace=True)
            ll_table_title = "**Lowest Leg in a Grand Prix**"

        st.dataframe(top5_overall, hide_index=True)
        st.subheader(ll_table_title)