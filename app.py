# app.py
import streamlit as st
from datetime import datetime, timezone
import pytz
import requests

# API Keys
ODDS_API_KEY = '416c30d26f73d0e2e25d670500f292f3'
SPORTSDATA_API_KEY = '498c3d8e413947fb99e9cea360011eb2'

SPORT = 'baseball_mlb'
REGION = 'us'
MARKET = 'h2h'

TEAM_NAME_MAP = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH"
}

def fetch_odds():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds/'
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': REGION,
        'markets': MARKET,
        'oddsFormat': 'american'
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def format_date_for_sportsdata(date_obj):
    return date_obj.strftime("%Y-%b-%d").upper()

def fetch_starting_lineups(date_obj):
    date_str = format_date_for_sportsdata(date_obj)
    url = f"https://api.sportsdata.io/v3/mlb/projections/json/StartingLineupsByDate/{date_str}"
    params = {'key': SPORTSDATA_API_KEY}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def fetch_player_era_dict():
    url = "https://api.sportsdata.io/v3/mlb/stats/json/PlayerSeasonStats/2025"
    headers = {'Ocp-Apim-Subscription-Key': SPORTSDATA_API_KEY}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    player_stats = response.json()
    return {player["PlayerID"]: player.get("EarnedRunAverage") for player in player_stats}

def fetch_team_records():
    url = "https://api.sportsdata.io/v3/mlb/scores/json/Standings/2025"
    headers = {'Ocp-Apim-Subscription-Key': SPORTSDATA_API_KEY}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    standings = response.json()
    return {
        team["Key"]: f"{team['Wins']}-{team['Losses']}"
        for team in standings
    }

def get_probable_pitchers(starting_lineups, team_abbr):
    for lineup in starting_lineups:
        if lineup.get('HomeTeam') == team_abbr:
            return lineup.get('HomeStartingPitcher')
        elif lineup.get('AwayTeam') == team_abbr:
            return lineup.get('AwayStartingPitcher')
    return None

def compare_and_format_era(era1, era2, pitcher_name):
    # Streamlit uses Markdown for formatting
    if era1 is None:
        return f"{pitcher_name} (ERA: N/A)"
    if era2 is None:
        return f"**{pitcher_name} (ERA: {era1:.2f})**"

    diff = abs(era1 - era2)
    if era1 < era2:
        if diff >= 2.0:
            return f"**<span style='color:green'>{pitcher_name} (ERA: {era1:.2f})</span>**"
        elif diff >= 1.0:
            return f"**<span style='color:orange'>{pitcher_name} (ERA: {era1:.2f})</span>**"
        else:
            return f"**{pitcher_name} (ERA: {era1:.2f})**"
    else:
        return f"{pitcher_name} (ERA: {era1:.2f})"

def odds_message(era_pitcher, era_opponent, pitcher_team_wins, opponent_team_wins, odds):
    if era_pitcher is not None and era_opponent is not None:
        era_diff = era_opponent - era_pitcher  # positive if pitcher better (lower ERA)
        wins_diff = pitcher_team_wins - opponent_team_wins

        if era_diff > 1.0 and wins_diff > 5:
            if odds < 0:
                return " (potential lock)"
            elif odds > 0:
                return " (potential upset)"
    return ""

def get_wins(record):
    try:
        return int(record.split('-')[0])
    except Exception:
        return 0

def main():
    st.title("MLB Odds & Probable Pitchers Dashboard")
    st.markdown("Data sourced from The Odds API and SportsDataIO")

    try:
        odds_data = fetch_odds()
        era_dict = fetch_player_era_dict()
        team_records = fetch_team_records()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return

    now = datetime.now(timezone.utc)
    local_tz = pytz.timezone('America/New_York')

    future_games = []
    for game in odds_data:
        start_str = game.get('commence_time')
        if not start_str:
            continue
        start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if start_time > now:
            local_time = start_time.astimezone(local_tz)
            future_games.append((local_time.date(), game))

    games_by_date = {}
    for game_date, game in future_games:
        games_by_date.setdefault(game_date, []).append(game)

    next_two_dates = sorted(games_by_date.keys())[:2]

    for game_date in next_two_dates:
        st.header(f"Odds for {game_date.strftime('%A, %b %d, %Y')}")

        try:
            starting_lineups = fetch_starting_lineups(game_date)
        except requests.HTTPError as e:
            st.warning(f"Failed to fetch starting lineups for {game_date}: {e}")
            starting_lineups = []

        for game in games_by_date[game_date]:
            home_team_name = game.get('home_team')
            away_team_name = game.get('away_team')

            if home_team_name and away_team_name:
                home_abbr = TEAM_NAME_MAP.get(home_team_name, home_team_name)
                away_abbr = TEAM_NAME_MAP.get(away_team_name, away_team_name)
                home_record = team_records.get(home_abbr, "N/A")
                away_record = team_records.get(away_abbr, "N/A")
                teams_str = f"{away_team_name} [{away_record}, A] vs {home_team_name} [{home_record}, H]"
                st.subheader(teams_str)
            else:
                st.subheader("Unknown teams")

            commence_time = game.get('commence_time')
            if commence_time:
                utc_time = datetime.strptime(commence_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                local_time = utc_time.astimezone(local_tz)
                friendly_time = local_time.strftime("%A, %b %d, %Y at %-I:%M %p %Z")
            else:
                friendly_time = "Unknown time"

            st.caption(f"Start time: {friendly_time}")

            era1 = era2 = None  # default None in case missing data

            if home_team_name and away_team_name:
                pitcher1 = get_probable_pitchers(starting_lineups, away_abbr)
                pitcher2 = get_probable_pitchers(starting_lineups, home_abbr)

                if pitcher1 and pitcher2:
                    era1 = era_dict.get(pitcher1.get('PlayerID'))
                    era2 = era_dict.get(pitcher2.get('PlayerID'))

                    p1_name = f"{pitcher1.get('FirstName', away_abbr)} {pitcher1.get('LastName', '')} [{away_abbr}, A]"
                    p2_name = f"{pitcher2.get('FirstName', home_abbr)} {pitcher2.get('LastName', '')} [{home_abbr}, H]"

                    st.markdown("**Probable Pitchers:**")
                    st.markdown(f"- {compare_and_format_era(era1, era2, p1_name)}", unsafe_allow_html=True)
                    st.markdown(f"- {compare_and_format_era(era2, era1, p2_name)}", unsafe_allow_html=True)
                else:
                    st.text("Probable pitchers info not found.")
            else:
                st.text("Could not identify teams properly for pitchers info.")

            bookmaker = game.get('bookmakers', [])
            if bookmaker:
                bookmaker = bookmaker[0]
                st.markdown(f"**Bookmaker:** {bookmaker.get('title', 'Unknown')}")

                home_wins = get_wins(home_record)
                away_wins = get_wins(away_record)

                for market in bookmaker.get('markets', []):
                    for outcome in market.get('outcomes', []):
                        team_name = outcome.get('name', 'Unknown')
                        price = outcome.get('price', 'N/A')

                        team_abbr = TEAM_NAME_MAP.get(team_name, team_name)

                        if team_abbr == away_abbr:
                            era_pitcher = era1
                            era_opponent = era2
                            pitcher_wins = away_wins
                            opponent_wins = home_wins
                        elif team_abbr == home_abbr:
                            era_pitcher = era2
                            era_opponent = era1
                            pitcher_wins = home_wins
                            opponent_wins = away_wins
                        else:
                            era_pitcher = era_opponent = pitcher_wins = opponent_wins = None

                        msg = odds_message(era_pitcher, era_opponent, pitcher_wins, opponent_wins, price)

                        if isinstance(price, (int, float)):
                            color = "🟢" if price < 0 else "🟡"
                            st.markdown(f"{color} **{team_name}**: {price} {msg}")
                        else:
                            st.text(f"{team_name}: {price}")
            else:
                st.text("No bookmaker odds available.")

            st.markdown("---")

if __name__ == "__main__":
    main()
