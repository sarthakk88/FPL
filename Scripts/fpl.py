import os
import pandas as pd
import requests
import json
import logging
from datetime import datetime, timezone
import json
import numpy as np

logger = logging.getLogger()

# Setting the threshold of logger to DEBUG
logger.setLevel(logging.INFO)

def get(url):
    response = requests.get(url)
    return json.loads(response.content)

def player_data(response):
    players = response['elements']
    return players

def team_data(response):
    teams = response['teams']
    return teams

def event_data(response):
    events = response['events']
    return events

def id_name(id):
    url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    response = get(url)
    players = response['elements']
    for i in players:
        if i['id'] == id:
            name = i['first_name'] + i['second_name']
            return name
            break
        else:
            logger.info("Player not present")

def players_stats(response, first_name, second_name):
    players = response['elements']
    for i in players:
        if i['first_name'] == first_name and i['second_name'] == second_name:
            player_id = i['id']
            break
        else:
            logger.info("Player not present")

    url = 'https://fantasy.premierleague.com/api/element-summary/' + \
       str(player_id) + '/' 
    response = get(url)
    fixtures = response['fixtures']
    history = response['history']
    history_past = response['history_past']

    return fixtures, history, history_past

def fpl_team_data(current_gw):
    my_team_url = 'https://fantasy.premierleague.com/api/entry/318718/event/' + \
    str(current_gw) + '/picks/'
    my_team = get(my_team_url)


    return my_team

def fixture_data(current_gw):
    return get('https://fantasy.premierleague.com/api/fixtures/?event='+str(current_gw))

def calc_in_weights(players):
    players['weight'] = 1
    players['weight'] += players['diff']/3
    players['weight'] += players['form'].astype("float")*10
    players['weight'] -= (100 - players['chance_of_playing_this_round'].astype("float"))*0.2
    players.loc[players['weight'] <0, 'weight'] =0

    return players.sample(1, weights=players.weight)


def calc_out_weight(players):
    players['weight'] = 100
    players['weight']-= players['diff']/3
    players['weight']-= players['form'].astype("float")*10
    players['weight']+= (100 - players['chance_of_playing_this_round'].astype("float"))*0.2
    players.loc[players['element_type'] ==1, 'weight'] -=10
    players.loc[players['weight'] <0, 'weight'] =0

    return players.sample(1, weights=players.weight)

def calc_starting_weight(players):
    players['weight'] = 1
    players['weight'] += players['diff']/2
    players['weight'] += players['form'].astype("float")*5
    players['weight'] -= (100 - players['chance_of_playing_this_round'].astype("float"))*0.2
    players.loc[players['weight'] <0, 'weight'] =0
    return players.sort_values('weight', ascending=False)

def team_stats(response):

    players_data = pd.DataFrame(player_data(response))
    events_data = pd.DataFrame(event_data(response))
    teams_data = pd.DataFrame(team_data(response))

    today = datetime.now(timezone.utc).timestamp()
    events_left = events_data[events_data.deadline_time_epoch>today]
    last_gw = events_left.iloc[0].id-1

    fixtures_data = pd.DataFrame(fixture_data(last_gw+1))
    my_fpl_team = fpl_team_data(last_gw)

    players_data.chance_of_playing_next_round = players_data.chance_of_playing_next_round.fillna(100.0)
    players_data.chance_of_playing_this_round = players_data.chance_of_playing_this_round.fillna(100.0)

    teams=dict(zip(teams_data.id, teams_data.name))

    players_data['team_name'] = players_data['team'].map(teams)
    fixtures_data['team_a_name'] = fixtures_data['team_a'].map(teams)
    fixtures_data['team_h_name'] = fixtures_data['team_h'].map(teams)
    home_strength=dict(zip(teams_data.id, teams_data.strength_overall_home))
    away_strength=dict(zip(teams_data.id, teams_data.strength_overall_away))
    fixtures_data['team_a_strength']=fixtures_data['team_a'].map(away_strength)
    fixtures_data['team_h_strength']=fixtures_data['team_h'].map(home_strength)

    try:
        fixtures_data=fixtures_data.drop(columns=['id'])
    except:
        print("Id not found")

    a_players = pd.merge(players_data, fixtures_data, how="inner", left_on=["team"], right_on=["team_a"])
    h_players = pd.merge(players_data, fixtures_data, how="inner", left_on=["team"], right_on=["team_h"])
    a_players['diff'] = a_players['team_a_strength'] - a_players['team_h_strength']
    h_players['diff'] = h_players['team_h_strength'] - h_players['team_a_strength']
    players_data = a_players.append(h_players)

    players = [x['element'] for x in my_fpl_team["picks"]]
    my_team = players_data.loc[players_data.id.isin(players)]
    potential_players = players_data.loc[~players_data.id.isin(players)]
    bank = my_fpl_team["entry_history"]['bank']


    my_team = my_team[['first_name','second_name','id','team_name','chance_of_playing_next_round','chance_of_playing_this_round','event_points','form',
   'news', 'form_rank','diff', 'now_cost', 'points_per_game', 'team_a_name','team_h_name', "element_type" ]]
    
    goalies = my_team.loc[my_team.element_type==1].drop(['element_type'], axis=1)
    defenders = my_team.loc[my_team.element_type==2].drop(['element_type'], axis=1)
    midfielders = my_team.loc[my_team.element_type==3].drop(['element_type'], axis=1)
    attackers = my_team.loc[my_team.element_type==4].drop(['element_type'], axis=1)

    return goalies,defenders,midfielders,attackers

def midfielders_stats(response,midfielders):
    midfielders["team_against"] = np.where(midfielders["team_a_name"] != midfielders["team_name"],midfielders["team_a_name"],midfielders["team_h_name"])
    midfielders["Home/Away"] = np.where(midfielders["team_a_name"] == midfielders["team_name"],"Away","Home")

    first_name = midfielders.first_name.tolist()
    temp_first_name = []
    second_name = midfielders.second_name.tolist()
    temp_second_name = []
    HorA = midfielders["Home/Away"].tolist()
    ids = midfielders.id.tolist()
    temp_ids = []

    xG = []
    xA = []
    xGC = []
    xPoints_HorA = []
    total_points_HorA = []
    bonus = []
    total_points = []
    goal_scored = []
    assists = []                                                                  
    clean_sheets = []                                                              
    goals_conceded = []
    xPoints = []
    minutes = []

    for i in range(0,len(first_name)):
        fixtures, history, history_past = players_stats(response, first_name[i], second_name[i])
        history = pd.DataFrame(history)

        if HorA[i] == "Home":
            HomeorAway = True
        else:
            HomeorAway = False 
        
        history_HorA = history[(history["was_home"] == HomeorAway) & (history["minutes"]>20)].tail(5)
        history = history[history["minutes"]>20].tail(5)

        convert_dict = {"expected_goals": float,"expected_assists": float, "expected_goal_involvements": float,"expected_goals_conceded": float}
        history = history.astype(convert_dict)
        history_HorA = history_HorA.astype(convert_dict)

        history["xPoints"] = history["expected_goals"]*5 + history["expected_assists"]*3 +  (history["minutes"]//60)*2 + np.maximum(0,1-history["expected_goals_conceded"]) + history["bonus"] - history["yellow_cards"] - 2*history["red_cards"] - 2*history["penalties_missed"] - 2*history["own_goals"]
        history = history.sum()
        history_HorA["xPoints"] = history_HorA["expected_goals"]*5 + history_HorA["expected_assists"]*3 +  (history_HorA["minutes"]//60)*2 + np.maximum(0,1-history_HorA["expected_goals_conceded"]) + history_HorA["bonus"] - history_HorA["yellow_cards"] - 2*history_HorA["red_cards"] - 2*history_HorA["penalties_missed"] - 2*history_HorA["own_goals"]
        history_HorA = history_HorA.sum()

        if (history["minutes"] > 90) & (history["xPoints"] > 10) & (history["total_points"] > 10):  

            minutes.append(history["minutes"])
            xG.append(history["expected_goals"])
            xA.append(history["expected_assists"])
            xGC.append(history["expected_goals_conceded"])
            xPoints_HorA.append(history_HorA["xPoints"])
            total_points_HorA.append(history_HorA["total_points"])
            bonus.append(history["bonus"])
            xPoints.append(history["xPoints"])
            total_points.append(history["total_points"])
            goal_scored.append(history["goals_scored"])
            assists.append(history["assists"])                                                                    
            clean_sheets.append(history["clean_sheets"])                                                                
            goals_conceded.append(history["goals_conceded"])
            temp_first_name.append(first_name[i])
            temp_second_name.append(second_name[i])
            temp_ids.append(ids[i])
             

    lst = {"first_name" :temp_first_name,
        "second_name": temp_second_name,
        "id": temp_ids,
        "minutes" : minutes,
        "xG" : xG,
        "xA" : xA,
        "xGC" : xGC,
        "total_points" : total_points,
        "xPoints" : xPoints,
        "total_points_Home/Away" : total_points_HorA,
        "xPoints_Home/Away" : xPoints_HorA,
        "goal_scored" : goal_scored,
        "assists" : assists,      
        "clean_sheets" : clean_sheets,                                                                 
        "goals_conceded" : goals_conceded,
        "bonus" : bonus}
    midfielders_stats = pd.DataFrame(lst)
    add_column = ["form","diff","team_against","Home/Away"]
    for column in add_column:
        midfielders = midfielders.loc[midfielders.id.isin(temp_ids)]
        lst = midfielders[column].tolist()
        midfielders_stats[column] = np.array(lst)

    return midfielders_stats

def attackers_stats(response,attackers):
    attackers["team_against"] = np.where(attackers["team_a_name"] != attackers["team_name"],attackers["team_a_name"],attackers["team_h_name"])
    attackers["Home/Away"] = np.where(attackers["team_a_name"] == attackers["team_name"],"Away","Home")

    first_name = attackers.first_name.tolist()
    temp_first_name = []
    second_name = attackers.second_name.tolist()
    temp_second_name = []
    HorA = attackers["Home/Away"].tolist()
    ids = attackers.id.tolist()
    temp_ids = []

    xG = []
    xA = []
    xPoints_HorA = []
    total_points_HorA = []
    bonus = []
    total_points = []
    goal_scored = []
    assists = []                                                                  
    xPoints = []
    minutes = []

    for i in range(0,len(first_name)):
        fixtures, history, history_past = players_stats(response, first_name[i], second_name[i])
        history = pd.DataFrame(history)

        if HorA[i] == "Home":
            HomeorAway = True
        else:
            HomeorAway = False 
        
        history_HorA = history[(history["was_home"] == HomeorAway) & (history["minutes"]>20)].tail(5)
        history = history[history["minutes"]>20].tail(5)

        convert_dict = {"expected_goals": float,"expected_assists": float, "expected_goal_involvements": float,"expected_goals_conceded": float}
        history = history.astype(convert_dict)
        history_HorA = history_HorA.astype(convert_dict)

        history["xPoints"] = history["expected_goals"]*4 + history["expected_assists"]*3 +  (history["minutes"]//60)*2 + history["bonus"] - history["yellow_cards"] - 2*history["red_cards"] -2*history["penalties_missed"] - 2*history["own_goals"]
        history = history.sum()
        history_HorA["xPoints"] = history_HorA["expected_goals"]*4 + history_HorA["expected_assists"]*3 +  (history_HorA["minutes"]//60)*2 + history_HorA["bonus"] - history_HorA["yellow_cards"] - 2*history_HorA["red_cards"] -2*history_HorA["penalties_missed"] - 2*history_HorA["own_goals"]
        history_HorA = history_HorA.sum()

        if (history["minutes"] > 90) & (history["xPoints"] > 10) & (history["total_points"] > 10):  

            minutes.append(history["minutes"])
            xG.append(history["expected_goals"])
            xA.append(history["expected_assists"])
            xPoints_HorA.append(history_HorA["xPoints"])
            total_points_HorA.append(history_HorA["total_points"])
            bonus.append(history["bonus"])
            xPoints.append(history["xPoints"])
            total_points.append(history["total_points"])
            goal_scored.append(history["goals_scored"])
            assists.append(history["assists"]) 
            temp_first_name.append(first_name[i])
            temp_second_name.append(second_name[i])
            temp_ids.append(ids[i]) 

    lst = {"first_name" :temp_first_name,
        "second_name": temp_second_name,
        "id": temp_ids,
        "minutes" : minutes,
        "xG" : xG,
        "xA" : xA,
        "total_points" : total_points,
        "xPoints" : xPoints,
        "total_points_Home/Away" : total_points_HorA,
        "xPoints_Home/Away" : xPoints_HorA,
        "goal_scored" : goal_scored,
        "assists" : assists,      
        "bonus" : bonus}
    attackers_stats = pd.DataFrame(lst)
    add_column = ["form","diff","team_against","Home/Away"]
    for column in add_column:
        attackers = attackers.loc[attackers.id.isin(temp_ids)]
        lst = attackers[column].tolist()
        attackers_stats[column] = np.array(lst)

    return attackers_stats

def goalies_stats(response,goalies):
    goalies["team_against"] = np.where(goalies["team_a_name"] != goalies["team_name"],goalies["team_a_name"],goalies["team_h_name"])
    goalies["Home/Away"] = np.where(goalies["team_a_name"] == goalies["team_name"],"Away","Home")

    first_name = goalies.first_name.tolist()
    temp_first_name = []
    second_name = goalies.second_name.tolist()
    temp_second_name = []
    HorA = goalies["Home/Away"].tolist()
    ids = goalies.id.tolist()
    temp_ids = []

    xGC = []
    xPoints_HorA = []
    total_points_HorA = []
    bonus = []
    total_points = []                                                                
    clean_sheets = []                                                              
    goals_conceded = []
    xPoints = []
    minutes = []
    saves =[]

    for i in range(0,len(first_name)):
        fixtures, history, history_past = players_stats(response, first_name[i], second_name[i])
        history = pd.DataFrame(history)

        if HorA[i] == "Home":
            HomeorAway = True
        else:
            HomeorAway = False 
        
        history_HorA = history[(history["was_home"] == HomeorAway) & (history["minutes"]>20)].tail(5)
        history = history[history["minutes"]>20].tail(5)

        convert_dict = {"expected_goals": float,"expected_assists": float, "expected_goal_involvements": float,"expected_goals_conceded": float}
        history = history.astype(convert_dict)
        history_HorA = history_HorA.astype(convert_dict)

        history["xPoints"] = history["expected_goals"]*6 + history["expected_assists"]*3 +  (history["minutes"]//60)*2 + np.maximum(0,1-history["expected_goals_conceded"])*4 + (history["saves"]//3) + history["bonus"] - history["yellow_cards"] - 2*history["red_cards"] - 2*history["penalties_missed"] - 2*history["own_goals"]
        history = history.sum()
        history_HorA["xPoints"] = history_HorA["expected_goals"]*6 + history_HorA["expected_assists"]*3 +  (history_HorA["minutes"]//60)*2 + np.maximum(0,1-history_HorA["expected_goals_conceded"])*4 + (history_HorA["saves"]//3) + history_HorA["bonus"] - history_HorA["yellow_cards"] - 2*history_HorA["red_cards"] - 2*history_HorA["penalties_missed"] - 2*history_HorA["own_goals"]
        history_HorA = history_HorA.sum()

        if (history["minutes"] > 90) & (history["xPoints"] > 10) & (history["total_points"] > 10):  

            minutes.append(history["minutes"])
            xGC.append(history["expected_goals_conceded"])
            xPoints_HorA.append(history_HorA["xPoints"])
            total_points_HorA.append(history_HorA["total_points"])
            bonus.append(history["bonus"])
            xPoints.append(history["xPoints"])
            total_points.append(history["total_points"])                                                                    
            clean_sheets.append(history["clean_sheets"])                                                                
            goals_conceded.append(history["goals_conceded"])
            saves.append(history["saves"])
            temp_first_name.append(first_name[i])
            temp_second_name.append(second_name[i])
            temp_ids.append(ids[i])
            
             

    lst = {"first_name" :temp_first_name,
        "second_name": temp_second_name,
        "id": temp_ids,
        "minutes" : minutes,
        "xGC" : xGC,
        "total_points" : total_points,
        "xPoints" : xPoints,
        "total_points_Home/Away" : total_points_HorA,
        "xPoints_Home/Away" : xPoints_HorA,     
        "clean_sheets" : clean_sheets,                                                                 
        "goals_conceded" : goals_conceded,
        "bonus" : bonus,
        "saves" : saves}
    goalies_stats = pd.DataFrame(lst)
    add_column = ["form","diff","team_against","Home/Away"]
    for column in add_column:
        goalies = goalies.loc[goalies.id.isin(temp_ids)]
        lst = goalies[column].tolist()
        goalies_stats[column] = np.array(lst)

    return goalies_stats

def defenders_stats(response,defenders):
    defenders["team_against"] = np.where(defenders["team_a_name"] != defenders["team_name"],defenders["team_a_name"],defenders["team_h_name"])
    defenders["Home/Away"] = np.where(defenders["team_a_name"] == defenders["team_name"],"Away","Home")

    first_name = defenders.first_name.tolist()
    temp_first_name = []
    second_name = defenders.second_name.tolist()
    temp_second_name = []
    HorA = defenders["Home/Away"].tolist()
    ids = defenders.id.tolist()
    temp_ids = []

    xG = []
    xA = []
    xGC = []
    xPoints_HorA = []
    total_points_HorA = []
    bonus = []
    total_points = []
    goal_scored = []
    assists = []                                                                  
    clean_sheets = []                                                              
    goals_conceded = []
    xPoints = []
    minutes = []

    for i in range(0,len(first_name)):
        fixtures, history, history_past = players_stats(response, first_name[i], second_name[i])
        history = pd.DataFrame(history)

        if HorA[i] == "Home":
            HomeorAway = True
        else:
            HomeorAway = False 
        
        history_HorA = history[(history["was_home"] == HomeorAway) & (history["minutes"]>20)].tail(5)
        history = history[history["minutes"]>20].tail(5)

        convert_dict = {"expected_goals": float,"expected_assists": float, "expected_goal_involvements": float,"expected_goals_conceded": float}
        history = history.astype(convert_dict)
        history_HorA = history_HorA.astype(convert_dict)

        history["xPoints"] = history["expected_goals"]*6 + history["expected_assists"]*3 +  (history["minutes"]//60)*2 + np.maximum(0,1-history["expected_goals_conceded"])*4 + history["bonus"] - history["yellow_cards"] - 2*history["red_cards"] - 2*history["penalties_missed"] - 2*history["own_goals"]
        history = history.sum()
        history_HorA["xPoints"] = history_HorA["expected_goals"]*6 + history_HorA["expected_assists"]*3 +  (history_HorA["minutes"]//60)*2 + np.maximum(0,1-history_HorA["expected_goals_conceded"])*4 + history_HorA["bonus"] - history_HorA["yellow_cards"] - 2*history_HorA["red_cards"] - 2*history_HorA["penalties_missed"] -- 2*history_HorA["own_goals"]
        history_HorA = history_HorA.sum()

        if (history["minutes"] > 90) & (history["xPoints"] > 10) & (history["total_points"] > 10):  

            minutes.append(history["minutes"])
            xG.append(history["expected_goals"])
            xA.append(history["expected_assists"])
            xGC.append(history["expected_goals_conceded"])
            xPoints_HorA.append(history_HorA["xPoints"])
            total_points_HorA.append(history_HorA["total_points"])
            bonus.append(history["bonus"])
            xPoints.append(history["xPoints"])
            total_points.append(history["total_points"])
            goal_scored.append(history["goals_scored"])
            assists.append(history["assists"])                                                                    
            clean_sheets.append(history["clean_sheets"])                                                                
            goals_conceded.append(history["goals_conceded"])
            temp_first_name.append(first_name[i])
            temp_second_name.append(second_name[i])
            temp_ids.append(ids[i])
             

    lst = {"first_name" :temp_first_name,
        "second_name": temp_second_name,
        "id": temp_ids,
        "minutes" : minutes,
        "xG" : xG,
        "xA" : xA,
        "xGC" : xGC,
        "total_points" : total_points,
        "xPoints" : xPoints,
        "total_points_Home/Away" : total_points_HorA,
        "xPoints_Home/Away" : xPoints_HorA,
        "goal_scored" : goal_scored,
        "assists" : assists,      
        "clean_sheets" : clean_sheets,                                                                 
        "goals_conceded" : goals_conceded,
        "bonus" : bonus}
    defenders_stats = pd.DataFrame(lst)
    add_column = ["form","diff","team_against","Home/Away"]
    for column in add_column:
        defenders = defenders.loc[defenders.id.isin(temp_ids)]
        lst = defenders[column].tolist()
        defenders_stats[column] = np.array(lst)

    return defenders_stats
def overall_player_stats(response):

    players_data = pd.DataFrame(player_data(response))
    events_data = pd.DataFrame(event_data(response))
    teams_data = pd.DataFrame(team_data(response))

    today = datetime.now(timezone.utc).timestamp()
    events_left = events_data[events_data.deadline_time_epoch>today]
    last_gw = events_left.iloc[0].id-1

    fixtures_data = pd.DataFrame(fixture_data(last_gw+1))
    my_fpl_team = fpl_team_data(last_gw)

    players_data.chance_of_playing_next_round = players_data.chance_of_playing_next_round.fillna(100.0)
    players_data.chance_of_playing_this_round = players_data.chance_of_playing_this_round.fillna(100.0)

    teams=dict(zip(teams_data.id, teams_data.name))

    players_data['team_name'] = players_data['team'].map(teams)
    fixtures_data['team_a_name'] = fixtures_data['team_a'].map(teams)
    fixtures_data['team_h_name'] = fixtures_data['team_h'].map(teams)
    home_strength=dict(zip(teams_data.id, teams_data.strength_overall_home))
    away_strength=dict(zip(teams_data.id, teams_data.strength_overall_away))
    fixtures_data['team_a_strength']=fixtures_data['team_a'].map(away_strength)
    fixtures_data['team_h_strength']=fixtures_data['team_h'].map(home_strength)

    try:
        fixtures_data=fixtures_data.drop(columns=['id'])
    except:
        print("Id not found")

    a_players = pd.merge(players_data, fixtures_data, how="inner", left_on=["team"], right_on=["team_a"])
    h_players = pd.merge(players_data, fixtures_data, how="inner", left_on=["team"], right_on=["team_h"])
    a_players['diff'] = a_players['team_a_strength'] - a_players['team_h_strength']
    h_players['diff'] = h_players['team_h_strength'] - h_players['team_a_strength']
    players_data = a_players.append(h_players)

    players_data = players_data[['first_name','second_name','id','team_name','chance_of_playing_next_round','chance_of_playing_this_round','event_points','form',
   'news', 'form_rank','diff', 'now_cost', 'points_per_game', 'team_a_name','team_h_name', "element_type" ]]
    
    goalies = players_data.loc[players_data.element_type==1].drop(['element_type'], axis=1)
    defenders = players_data.loc[players_data.element_type==2].drop(['element_type'], axis=1)
    midfielders = players_data.loc[players_data.element_type==3].drop(['element_type'], axis=1)
    attackers = players_data.loc[players_data.element_type==4].drop(['element_type'], axis=1)


    return goalies,defenders,midfielders,attackers