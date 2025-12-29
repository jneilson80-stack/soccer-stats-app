import streamlit as st
import pandas as pd
import io
import json
import random
from datetime import datetime

# ----------------------------------------
# Core session_state initialization
# ----------------------------------------

def ensure_session_state():
    if "stats" not in st.session_state:
        st.session_state.stats = []

    if "lineup" not in st.session_state:
        st.session_state.lineup = []

    if "lineup_select" not in st.session_state:
        st.session_state.lineup_select = []

    if "last_selected_player" not in st.session_state:
        st.session_state.last_selected_player = "Reset selection (use new name field)"

    if "last_new_name_input" not in st.session_state:
        st.session_state.last_new_name_input = ""

    if "add_merge_selector" not in st.session_state:
        st.session_state.add_merge_selector = "Reset selection (use new name field)"

    if "add_new_name_input" not in st.session_state:
        st.session_state.add_new_name_input = ""

    if "fasttap_player" not in st.session_state:
        st.session_state.fasttap_player = None

    if "last_play" not in st.session_state:
        st.session_state.last_play = None


def get_player_by_name(name: str):
    for p in st.session_state.stats:
        if p["Player"] == name:
            return p
    return None


def ensure_player_fields(player: dict):
    defaults = {
        "Goals": 0,
        "Assists": 0,
        "Shots": 0,
        "Saves": 0,
        "Goals_Allowed": 0,
    }
    for k, v in defaults.items():
        if k not in player:
            player[k] = v


def merge_or_add_player(stats_list, entry):
    existing = get_player_by_name(entry["Player"])
    if existing is None:
        ensure_player_fields(entry)
        stats_list.append(entry)
        return "added"
    else:
        ensure_player_fields(existing)
        ensure_player_fields(entry)
        existing["Goals"] += entry["Goals"]
        existing["Assists"] += entry["Assists"]
        existing["Shots"] += entry["Shots"]
        existing["Saves"] += entry["Saves"]
        existing["Goals_Allowed"] += entry["Goals_Allowed"]
        return "merged"


def record_fast_tap(player_name: str, field: str, delta: int):
    """
    Fast Tap logic:
    - Every Goal is also a Shot on Target.
    - Other fields only touch their own stat.
    """
    player = get_player_by_name(player_name)
    if player is None:
        player = {
            "Player": player_name,
            "Goals": 0,
            "Assists": 0,
            "Shots": 0,
            "Saves": 0,
            "Goals_Allowed": 0,
        }
        st.session_state.stats.append(player)

    ensure_player_fields(player)

    # Apply main stat change
    player[field] = max(0, player[field] + delta)

    # If a goal is recorded, also increment Shots on Target
    if field == "Goals" and delta > 0:
        player["Shots"] = max(0, player["Shots"] + delta)

    st.session_state.last_play = {
        "player": player_name,
        "field": field,
        "delta": delta,
    }


def undo_last_play():
    lp = st.session_state.last_play
    if not lp:
        st.warning("No action to undo.")
        return

    player = get_player_by_name(lp["player"])
    if player is None:
        st.session_state.last_play = None
        return

    ensure_player_fields(player)

    # If last play was a goal, we also undo the associated shot
    if lp["field"] == "Goals" and lp["delta"] > 0:
        player["Goals"] = max(0, player["Goals"] - lp["delta"])
        player["Shots"] = max(0, player["Shots"] - lp["delta"])
    else:
        player[lp["field"]] = max(0, player[lp["field"]] - lp["delta"])

    st.session_state.last_play = None
    st.success("Last action undone.")


def build_stats_dataframe():
    rows = []
    for p in st.session_state.stats:
        ensure_player_fields(p)
        rows.append({
            "Player": p["Player"],
            "G": p["Goals"],
            "A": p["Assists"],
            "Sh": p["Shots"],
            "S": p["Saves"],
            "C": p["Goals_Allowed"],
        })
    if not rows:
        return pd.DataFrame(columns=["Player", "G", "A", "Sh", "S", "C"])
    return pd.DataFrame(rows)


# ----------------------------------------
# App setup
# ----------------------------------------

st.set_page_config(
    page_title="Unified Soccer Stats & Fast Tap",
    layout="centered",
)

ensure_session_state()

st.title("⚽ Unified Soccer Stats & Fast Tap")

DEFAULT_PLAYERS = ["Theo", "Kekoa"]

tab_lineup, tab_add_merge, tab_game, tab_export, tab_faq = st.tabs(
    [
        "Lineup Setup",
        "Add / Merge Players",
        "Fast Tap Game Mode",
        "Export Summary File",
        "FAQ / Formulas",
    ]
)

# ----------------------------------------
# TAB 1 — Lineup Setup
# ----------------------------------------
with tab_lineup:
    st.header("📋 Lineup Setup")

    added_players = [p["Player"] for p in st.session_state.stats]
    all_players = sorted(set(DEFAULT_PLAYERS + added_players))

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("💾 Save Lineup"):
            st.session_state.lineup = st.session_state.lineup_select
            st.success("Lineup saved successfully.")

    with col2:
        st.multiselect(
            "Select players for the lineup (alphabetical):",
            options=all_players,
            key="lineup_select"
        )

    st.write("Current lineup (alphabetical):")
    st.write(", ".join(sorted(st.session_state.lineup)) or "No players yet.")

# ----------------------------------------
# TAB 2 — Add / Merge Players
# ----------------------------------------
with tab_add_merge:
    st.header("➕ Add or Merge Player Stats")

    lineup_names = st.session_state.lineup
    existing_names = [p["Player"] for p in st.session_state.stats]
    combined_names = sorted(set(lineup_names + existing_names))

    name_options = ["Reset selection (use new name field)"] + combined_names

    last_selected_dropdown = st.session_state.add_merge_selector

    # Clear new-name field when switching to an existing player
    if last_selected_dropdown != "Reset selection (use new name field)":
        st.session_state.add_new_name_input = ""

    new_name_input = st.text_input(
        "New player name (if adding someone new):",
        key="add_new_name_input",
    )

    selected_option = st.selectbox(
        "Choose an existing player or reset:",
        options=name_options,
        key="add_merge_selector",
    )

    reset_needed = False

    if selected_option != st.session_state.last_selected_player:
        reset_needed = True

    if selected_option == "Reset selection (use new name field)":
        if new_name_input.strip() != st.session_state.last_new_name_input.strip():
            reset_needed = True

    if reset_needed:
        reset_keys = ["soc_g", "soc_a", "soc_sh", "soc_s", "soc_c"]
        for k in reset_keys:
            if k in st.session_state:
                st.session_state[k] = 0

        st.session_state.last_selected_player = selected_option
        st.session_state.last_new_name_input = new_name_input

    if selected_option == "Reset selection (use new name field)":
        name = st.session_state.add_new_name_input.strip()
    else:
        name = selected_option.strip()

    st.subheader("Player Stats")

    g = st.number_input("Goals (G)", min_value=0, step=1, key="soc_g")
    a = st.number_input("Assists (A)", min_value=0, step=1, key="soc_a")
    sh = st.number_input("Shots on Target (Sh)", min_value=0, step=1, key="soc_sh")
    s_saves = st.number_input("Saves (S)", min_value=0, step=1, key="soc_s")
    c_allowed = st.number_input("Goals Allowed (C)", min_value=0, step=1, key="soc_c")

    if st.button("➕ Add / Merge Player Stats"):
        if selected_option == "Reset selection (use new name field)":
            raw_new_name = new_name_input
            if raw_new_name != raw_new_name.strip():
                st.error("Please enter first name only (no trailing spaces).")
                st.stop()

        if not name:
            st.error("Please select a player or enter a new player name.")
        else:
            is_new = get_player_by_name(name) is None

            total_stats = g + a + sh + s_saves + c_allowed
            if is_new and total_stats == 0:
                st.error("Please enter stats for a new player.")
            elif g > sh:
                st.error("Goals (G) cannot exceed Shots on Target (Sh).")
            else:
                entry = {
                    "Player": name,
                    "Goals": g,
                    "Assists": a,
                    "Shots": sh,
                    "Saves": s_saves,
                    "Goals_Allowed": c_allowed,
                }
                result = merge_or_add_player(st.session_state.stats, entry)

                if name not in st.session_state.lineup:
                    st.session_state.lineup.append(name)
                    st.session_state.lineup = sorted(st.session_state.lineup)

                if result == "added":
                    st.success(f"Added stats for {name}.")
                else:
                    st.success(f"Merged stats for {name}.")

    if st.session_state.stats:
        st.subheader("📊 Current Player Stats")
        df = build_stats_dataframe()
        st.table(df)

# ----------------------------------------
# TAB 3 — Fast Tap Game Mode
# ----------------------------------------
with tab_game:
    st.header("⚡ Fast Tap Game Mode")

    if not st.session_state.lineup:
        st.warning("No players in lineup. Add players in the Lineup Setup tab first.")
    else:
        fasttap_player = st.selectbox(
            "Select player to track in Fast Tap:",
            options=st.session_state.lineup,
            key="fasttap_player",
        )

        if fasttap_player:
            st.write(f"Recording stats for: **{fasttap_player}**")

            col1, col2, col3 = st.columns(3)
            col4, col5, col6 = st.columns(3)

            with col1:
                if st.button("⚽ Goal (G)"):
                    record_fast_tap(fasttap_player, "Goals", 1)
            with col2:
                if st.button("🎯 Assist (A)"):
                    record_fast_tap(fasttap_player, "Assists", 1)
            with col3:
                if st.button("🎯 Shot on Target (Sh)"):
                    record_fast_tap(fasttap_player, "Shots", 1)

            with col4:
                if st.button("🧤 Save (S)"):
                    record_fast_tap(fasttap_player, "Saves", 1)
            with col5:
                if st.button("❌ Goal Allowed (C)"):
                    record_fast_tap(fasttap_player, "Goals_Allowed", 1)
            with col6:
                if st.button("↩️ Undo Last Action"):
                    undo_last_play()

            p = get_player_by_name(fasttap_player)
            if p:
                ensure_player_fields(p)
                st.subheader("Current Stats for Selected Player")
                st.write(
                    f"G: {p['Goals']} | A: {p['Assists']} | "
                    f"Sh: {p['Shots']} | S: {p['Saves']} | C: {p['Goals_Allowed']}"
                )

# ----------------------------------------
# TAB 4 — Export Summary File + Season Save/Load
# ----------------------------------------
with tab_export:
    st.header("📤 Export Summary & Season Save/Load")

    df = build_stats_dataframe()

    if not df.empty:
        st.subheader("Preview")
        st.table(df)

        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="💾 Download CSV",
            data=csv_data,
            file_name="soccer_stats_summary.csv",
            mime="text/csv",
        )

        buffer = io.StringIO()
        buffer.write("Soccer Stats Summary\n\n")
        for _, row in df.iterrows():
            buffer.write(
                f"{row['Player']}: G={row['G']}, A={row['A']}, "
                f"Sh={row['Sh']}, S={row['S']}, C={row['C']}\n"
            )
        txt_data = buffer.getvalue().encode("utf-8")

        st.download_button(
            label="📝 Download TXT Summary",
            data=txt_data,
            file_name="soccer_stats_summary.txt",
            mime="text/plain",
        )

        st.subheader("💾 Season Save")

        season_data = {
            "stats": st.session_state.stats,
            "lineup": st.session_state.lineup,
            "lineup_select": st.session_state.lineup_select,
            "last_play": st.session_state.last_play,
        }

        season_json = json.dumps(season_data, indent=4)
        season_filename = (
            f"season_soccer_{random.randint(1, 1_000_000)}_"
            f"{datetime.now().strftime('%m-%d-%y')}.json"
        )

        st.download_button(
            label="💾 Download Season JSON",
            data=season_json,
            file_name=season_filename,
            mime="application/json"
        )

    else:
        st.warning("No stats available to export yet. Play a game or add stats first.")

    st.subheader("📁 Season Load")

    uploaded_season = st.file_uploader("📂 Load Season JSON", type=["json"])

    if uploaded_season is not None:
        try:
            loaded = json.load(uploaded_season)

            if "stats" not in loaded:
                st.error("Invalid season file. Missing required 'stats' field.")
            else:
                stats = loaded.get("stats", [])

                # Restore lineup if present; otherwise rebuild from stats
                lineup_from_file = loaded.get("lineup", [])
                if not lineup_from_file:
                    lineup_from_file = sorted(
                        {p.get("Player", "") for p in stats if p.get("Player")}
                    )

                st.session_state.stats = stats
                st.session_state.lineup = lineup_from_file
                st.session_state.last_play = loaded.get("last_play", None)

                st.success("Season loaded — stats and lineup restored. Check Lineup tab to confirm players.")

        except Exception as e:
            st.error(f"Error loading season file: {e}")

# ----------------------------------------
# TAB 5 — FAQ / Formulas
# ----------------------------------------
with tab_faq:
    st.header("❓ FAQ / Formulas")

    st.markdown(
        """
### What does each stat mean?

- **Goals (G):** Number of goals scored by the player.
- **Assists (A):** Number of times the player assisted a goal.
- **Shots on Target (Sh):** Shots that were on target (including goals).
- **Saves (S):** Saves made by the player (typically goalkeeper).
- **Goals Allowed (C):** Goals conceded while the player is in goal.

### How does Add / Merge work?

- If you enter stats for a **new player name**, a new record is created.
- If you enter stats for an **existing player**, the stats are **added** on top of existing totals.
- Switching the selected player or typing a different new name will reset the input fields to zero to prevent accidental carryover.

### How does Fast Tap Game Mode work?

- Choose a player from the lineup.
- Tap the appropriate buttons:
  - **Goal (G), Assist (A), Shot on Target (Sh)** for offensive actions.
  - **Save (S), Goal Allowed (C)** for goalkeeper actions.
- Each tap increments the corresponding stat by 1.
- Use **Undo Last Action** to reverse the last tap.

### How does exporting work?

- The **Export Summary File** tab lets you:
  - Download a **CSV** file for spreadsheets.
  - Download a **TXT** summary for quick sharing or notes.
- You can also **save or load a full season** using the Season Save/Load options.
"""
    )