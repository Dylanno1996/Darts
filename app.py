import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go

# --- Page Config ---
st.set_page_config(page_title="IDL Stats", layout="centered")
st.title("IDL Stats")

# --- Helper Functions ---
def detect_data_type(df):
    """Determine if the CSV is a Competition or League file."""
    has_division = "Division" in df.columns and df["Division"].notna().any()
    has_date = "Date" in df.columns and df["Date"].notna().any()
    
    if has_division and not has_date:
        return "League"
    else:
        return "Competition"

@st.cache_data(show_spinner="Loading and processing data...")
def load_and_process_data(data_folder):
    """
    Loads all CSVs, combines them, and performs heavy processing 
    (Date parsing, Numeric conversion) only once.
    """
    all_data = []
    
    # Check if folder exists
    if not os.path.exists(data_folder):
        return pd.DataFrame()

    for file in os.listdir(data_folder):
        if file.endswith(".csv"):
            file_path = os.path.join(data_folder, file)
            try:
                df = pd.read_csv(file_path)
                df["OriginalDate"] = df.get("Date", "")
                df["DataType"] = detect_data_type(df)
                all_data.append(df)
            except Exception as e:
                st.error(f"Error reading {file}: {e}")

    if not all_data:
        return pd.DataFrame()

    full_df = pd.concat(all_data, ignore_index=True)

    # 1. Process Season (League)
    if "Season" in full_df.columns:
        full_df["Season"] = pd.to_numeric(full_df["Season"], errors="coerce").astype("Int64")

    # 2. Parse Dates (Competition)
    full_df["ParsedDate"] = pd.NaT
    if "OriginalDate" in full_df.columns:
        date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %m %Y"]
        for fmt in date_formats:
            mask_unparsed = full_df["ParsedDate"].isna()
            if mask_unparsed.any():
                temp_parsed = pd.to_datetime(
                    full_df.loc[mask_unparsed, "OriginalDate"], 
                    format=fmt, 
                    errors="coerce"
                )
                full_df.loc[mask_unparsed, "ParsedDate"] = temp_parsed
    
    # Create a nice string format for display
    full_df["Date_str"] = full_df["ParsedDate"].dt.strftime("%d-%b-%Y")
    # Fill missing parsed dates with the original string
    full_df.loc[full_df["Date_str"].isna(), "Date_str"] = full_df["OriginalDate"].astype(str)

    # 3. Process Throw Columns
    throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]
    for c in throw_cols:
        full_df[c] = pd.to_numeric(full_df[c], errors="coerce")
        
    return full_df

# --- Load Data ---
data_folder = "data"
full_df = load_and_process_data(data_folder)

if full_df.empty:
    st.warning("No CSV files found in the data folder or folder is missing.")
    st.stop()

# Identify throw columns dynamically (needed for logic below)
throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]

if "Player" not in full_df.columns or not throw_cols:
    st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
    st.stop()

# --- Sidebar Navigation ---
data_mode = st.sidebar.radio("📁 Select Competition Type", ["🏆 Grand Prix", "🏅 League"])
page = st.sidebar.radio("📊 Select Stat", ["🎯 180s", "🎣 Checkouts", "👇 Lowest Legs"])

# --- Filter Dataset ---
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
    
    if options_df.empty:
        st.warning("No Grand Prix data found.")
        st.stop()
        
    selected_label = st.selectbox("Select a competition", options_df["Competition"].tolist())
    filtered_df = active_df[active_df["Competition"] == selected_label].copy()

else:
    # --- LEAGUE DATA PROCESSING (Cascading Dropdowns) ---
    active_df = full_df[full_df["DataType"] == "League"].copy()
    
    # Ensure columns are strings for smooth filtering
    active_df["Venue"] = active_df.get("Venue", pd.Series(dtype='str')).astype(str)
    active_df["Season"] = active_df["Season"].astype(str)
    active_df["Division"] = active_df["Division"].astype(str)

    # 1. Select Venue
    unique_venues = sorted(active_df["Venue"].unique())
    if not unique_venues:
        st.warning("No League venues found.")
        st.stop()
    selected_venue = st.selectbox("📍 Select League/Venue", unique_venues)
    
    venue_df = active_df[active_df["Venue"] == selected_venue]

    # 2. Select Season
    unique_seasons = venue_df["Season"].unique()
    try:
        unique_seasons = sorted(unique_seasons, key=lambda x: int(x), reverse=True)
    except ValueError:
        unique_seasons = sorted(unique_seasons, reverse=True)
    selected_season = st.selectbox("📅 Select Season", unique_seasons)

    season_df = venue_df[venue_df["Season"] == selected_season]

    # 3. Select Division
    unique_divisions = sorted(season_df["Division"].unique())
    selected_division = st.selectbox("🏆 Select Division", unique_divisions)

    # Final Filter
    filtered_df = season_df[season_df["Division"] == selected_division].copy()
    selected_label = f"{selected_venue} - S{selected_season} - {selected_division}"

# ==========================
# PAGE: 180s
# ==========================
if page == "🎯 180s":
    # --- Calculations ---
    filtered_df["180s"] = filtered_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
    )
    filtered_df["140_179"] = filtered_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and 140 <= score <= 179), axis=1
    )
    filtered_df["100_139"] = filtered_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and 100 <= score <= 139), axis=1
    )

    # --- Main Table (All Players) ---
    player_stats = filtered_df.groupby("Player")[["180s", "140_179", "100_139"]].sum().reset_index()
    player_stats.rename(columns={"140_179": "140+", "100_139": "100+"}, inplace=True)
    total_180s = int(player_stats["180s"].sum()) if not player_stats.empty else 0
    
    # Sort by 180s, then 140s, then 100s
    player_stats = player_stats.sort_values(by=["180s", "140+", "100+"], ascending=[False, False, False])
    
    st.subheader(f"Total 180s - {total_180s}")
    st.dataframe(player_stats, hide_index=True)

    # --- Bottom Chart Section ---
    overall_df = active_df.copy()
    overall_df["180s"] = overall_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
    )

    st.markdown("---")
    
    if data_mode == "🏅 League":
        # Group by Player/Venue/Division/Season
        comp_group = overall_df.groupby(["Player", "Venue", "Division", "Season"])["180s"].sum().reset_index()
        comp_group = comp_group.sort_values("180s", ascending=False).head(5).reset_index(drop=True)
        
        st.subheader("**Most 180s in a League Season**")
        
        # --- League Bar Chart ---
        if not comp_group.empty:
            chart_data = comp_group.copy()
            # Create Unique ID to prevent merging same player in different seasons if they appear in Top 5 twice
            chart_data['Unique_ID'] = chart_data['Player'] + '_' + chart_data['Season'].astype(str)
            # Reverse for horizontal bar order
            chart_data = chart_data.iloc[::-1].reset_index(drop=True)
            
            fig = go.Figure(go.Bar(
                x=chart_data["180s"],
                y=chart_data["Unique_ID"],
                orientation='h',
                text=chart_data["180s"],
                textposition='outside',
                hovertemplate='<b>%{customdata[0]}</b><br>' +
                              '180s: %{x}<br>' +
                              'Venue: %{customdata[1]}<br>' +
                              'Division: %{customdata[2]}<br>' +
                              'Season: %{customdata[3]}<extra></extra>',
                customdata=chart_data[["Player", "Venue", "Division", "Season"]].values,
                marker=dict(color='#1f77b4')
            ))
            fig.update_yaxes(ticktext=chart_data["Player"], tickvals=chart_data["Unique_ID"])
            fig.update_layout(
                xaxis_title="",
                xaxis=dict(showticklabels=False, showgrid=False),
                yaxis_title="",
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No 180s recorded in League data.")
        
    else:
        # Grand Prix Logic
        comp_group = overall_df.groupby(["Player", "Venue", "Date_str"])["180s"].sum().reset_index()
        comp_group = comp_group.sort_values(["180s"], ascending=False).head(5).reset_index(drop=True)
        comp_group.rename(columns={"Date_str": "Date"}, inplace=True)
        
        st.subheader("**Most 180s in a Grand Prix**")
        
        # --- GP Bar Chart ---
        if not comp_group.empty:
            chart_data = comp_group.copy()
            chart_data['Unique_ID'] = chart_data['Player'] + '_' + chart_data['Date']
            chart_data = chart_data.iloc[::-1].reset_index(drop=True)
            
            fig = go.Figure(go.Bar(
                x=chart_data["180s"],
                y=chart_data["Unique_ID"],
                orientation='h',
                text=chart_data["180s"],
                textposition='outside',
                hovertemplate='<b>%{customdata[0]}</b><br>' +
                              '180s: %{x}<br>' +
                              'Venue: %{customdata[1]}<br>' +
                              'Date: %{customdata[2]}<extra></extra>',
                customdata=chart_data[["Player", "Venue", "Date"]].values,
                marker=dict(color='#1f77b4')
            ))
            fig.update_yaxes(ticktext=chart_data["Player"], tickvals=chart_data["Unique_ID"])
            fig.update_layout(
                xaxis_title="",
                xaxis=dict(showticklabels=False, showgrid=False),
                yaxis_title="",
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
             st.info("No 180s recorded in Grand Prix data.")

# ==========================
# PAGE: Checkouts
# ==========================
elif page == "🎣 Checkouts":
    winners_df = filtered_df[filtered_df["Result"].str.upper() == "WON"].copy()
    
    if winners_df.empty:
        st.info("No winning legs found — cannot calculate checkouts.")
    else:
        # Calculate Checkouts
        winners_df["Checkout"] = winners_df[throw_cols].apply(
            lambda row: row[pd.notna(row) & (row > 0)].iloc[-1] if any(pd.notna(row) & (row > 0)) else None,
            axis=1
        )
        winners_df = winners_df.dropna(subset=["Checkout"])
        winners_df["Checkout"] = pd.to_numeric(winners_df["Checkout"], errors="coerce")

        # Define columns to keep
        cols_to_keep = ["Player", "Checkout"]
        
        # Check if URL exists in the CSV
        if "URL" in winners_df.columns:
            cols_to_keep.append("URL")

        top5_checkouts = winners_df[cols_to_keep]
        top5_checkouts = top5_checkouts.sort_values("Checkout", ascending=False).head(5).reset_index(drop=True)
        
        st.subheader(f"Highest Checkouts")

        # Configure the column if it exists
        column_config = {}
        if "URL" in top5_checkouts.columns:
            column_config["URL"] = st.column_config.LinkColumn(
                "Match Link", display_text="View Match"
            )

        st.dataframe(top5_checkouts, column_config=column_config, hide_index=True)

    # --- 170 Club ---
    st.markdown("---")
    st.markdown("## 🎣 The Big Fish")
    
    winners_all = active_df[active_df["Result"].str.upper() == "WON"].copy()
    winners_all["Checkout"] = winners_all[throw_cols].apply(
        lambda row: row[pd.notna(row) & (row > 0)].iloc[-1] if any(pd.notna(row) & (row > 0)) else None,
        axis=1
    )
    winners_all = winners_all.dropna(subset=["Checkout"])
    winners_all["Checkout"] = pd.to_numeric(winners_all["Checkout"], errors="coerce")
    
    max_170_df = winners_all[winners_all["Checkout"] == 170].copy()

    if data_mode == "🏅 League":
        # Keep URL here too if it exists
        cols_170 = ["Player", "Division", "Season"]
        if "URL" in max_170_df.columns:
            cols_170.append("URL")
            
        max_170_df = max_170_df[cols_170].drop_duplicates()
        max_170_df = max_170_df.sort_values(by="Season", ascending=False).reset_index(drop=True)
    else:
        max_170_df = max_170_df[["Player","Venue","Date_str","ParsedDate"]].drop_duplicates()
        max_170_df = max_170_df.sort_values("ParsedDate", ascending=False, na_position="last").reset_index(drop=True)
        max_170_df = max_170_df[["Player","Venue","Date_str"]]
        max_170_df.rename(columns={"Date_str":"Date"}, inplace=True)
    
    if not max_170_df.empty:
        # Config for 170 table
        cfg_170 = {}
        if "URL" in max_170_df.columns:
            cfg_170["URL"] = st.column_config.LinkColumn(
                "Match Link", display_text="View Match"
            )
        st.dataframe(max_170_df, column_config=cfg_170, hide_index=True)
    else:
        st.info("No 170 checkouts recorded.")

# ==========================
# PAGE: Lowest Legs
# ==========================
elif page == "👇 Lowest Legs":
    winners_df = filtered_df[filtered_df["Result"].str.upper() == "WON"].copy()
    winners_overall = active_df[active_df["Result"].str.upper() == "WON"].copy()

    # Helper to calculate stats
    def calculate_lowest_legs(df):
        if df.empty: return pd.DataFrame()
        df["Total Darts"] = pd.to_numeric(df["Total Darts"], errors="coerce")
        df["LastScore"] = df[throw_cols].apply(
            lambda row: row[pd.notna(row) & (row>0)].iloc[-1] if any(pd.notna(row) & (row>0)) else None,
            axis=1
        )
        return df

    # --- Selected Competition Lowest Legs ---
    if winners_df.empty:
        st.info("No winning legs found for this selection.")
    else:
        winners_df = calculate_lowest_legs(winners_df)
        
        # Lowest per player
        # Sort by best leg (Least darts, then highest checkout)
        lowest_per_player = winners_df.sort_values(["Total Darts", "LastScore"], ascending=[True, False])
        # Group to get unique players, taking their best leg
        lowest_per_player = lowest_per_player.groupby("Player", as_index=False).first()
        # Re-sort to order the table
        lowest_per_player = lowest_per_player.sort_values(["Total Darts", "LastScore"], ascending=[True, False])
        
        # Define Columns (No Checkout, Add URL)
        cols_to_keep = ["Player", "Total Darts"]
        if "URL" in lowest_per_player.columns:
            cols_to_keep.append("URL")

        top5_lowest = lowest_per_player[cols_to_keep].head(5).reset_index(drop=True)
        top5_lowest.rename(columns={"Total Darts":"Darts Thrown"}, inplace=True)

        st.subheader(f"Lowest Legs — {selected_label}")
        
        # Column Config for URL
        column_config = {}
        if "URL" in top5_lowest.columns:
            column_config["URL"] = st.column_config.LinkColumn(
                "Match Link", display_text="View Match"
            )
            
        st.dataframe(top5_lowest, column_config=column_config, hide_index=True)

    # --- Overall Lowest Legs ---
    st.markdown("---")
    if winners_overall.empty:
        st.info("No winning legs found overall.")
    else:
        winners_overall = calculate_lowest_legs(winners_overall)
        all_lowest = winners_overall.sort_values(["Total Darts","LastScore"], ascending=[True,False])
        
        # Select Columns (No Checkout, Add URL)
        if data_mode == "🏅 League":
            cols = ["Player","Total Darts","Division","Season"]
            ll_table_title = "**Lowest Leg in a League Season**"
        else:
            cols = ["Player","Total Darts","Venue","Date_str"]
            ll_table_title = "**Lowest Leg in a Grand Prix**"
            
        if "URL" in all_lowest.columns:
            cols.append("URL")

        top5_overall = all_lowest[cols].head(5).reset_index(drop=True)
        top5_overall.rename(columns={"Total Darts":"Darts Thrown", "Date_str":"Date"}, inplace=True)

        st.subheader(ll_table_title)
        
        # Column Config for URL
        column_config = {}
        if "URL" in top5_overall.columns:
            column_config["URL"] = st.column_config.LinkColumn(
                "Match Link", display_text="View Match"
            )
            
        st.dataframe(top5_overall, column_config=column_config, hide_index=True)