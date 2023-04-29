import requests
import json
from bs4 import BeautifulSoup
import re
import codecs
import pandas as pd
import os
import csv
import nest_asyncio
nest_asyncio.apply()

import asyncio
import json
import pandas as pd
import aiohttp
import asyncio

from understat import Understat

def get_team_data(data):

    teams_stats = pd.DataFrame(columns=['id', 'team', 'xG', 'xGA', 'npxG', 'npxGA', 'ppda', 'ppda_allowed', 'deep',
       'deep_allowed', 'scored', 'missed', 'xpts', 'wins', 'draws', 'loses',
       'pts', 'npxGD'])

    for i in range(0,len(data)):

        for j in range(0,len(data[i]["history"])):
            
            history = data[i]["history"][j]
            history["ppda"] = history["ppda"]["att"]/history["ppda"]["def"]
            history["ppda_allowed"] = history["ppda_allowed"]["att"]/history["ppda_allowed"]["def"]

        temp = pd.DataFrame({"id": [data[i]["id"]],"team":[data[i]["title"]]})
        history = pd.DataFrame(data[i]["history"])
        history = history.drop(["result","date","h_a"],axis=1)
        join = history.mean().to_frame().T
        temp = pd.concat([temp,join], axis=1)
        teams_stats = pd.concat([teams_stats,temp])

    teams_stats = teams_stats.reset_index(drop=True, inplace=False)
    
def get_data(url):
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Response was code " + str(response.status_code))
    html = response.text
    parsed_html = BeautifulSoup(html, 'html.parser')
    scripts = parsed_html.findAll('script')
    filtered_scripts = []
    for script in scripts:
        if len(script.contents) > 0:
            filtered_scripts += [script]
    return scripts

def get_epl_data():
    scripts = get_data("https://understat.com/league/EPL/2022")
    teamData = {}
    playerData = {}
    for script in scripts:
        for c in script.contents:
            split_data = c.split('=')
            data = split_data[0].strip()
            if data == 'var teamsData':
                content = re.findall(r'JSON\.parse\(\'(.*)\'\)',split_data[1])
                decoded_content = codecs.escape_decode(content[0], "hex")[0].decode('utf-8')
                teamData = json.loads(decoded_content)
            elif data == 'var playersData':
                content = re.findall(r'JSON\.parse\(\'(.*)\'\)',split_data[1])
                decoded_content = codecs.escape_decode(content[0], "hex")[0].decode('utf-8')
                playerData = json.loads(decoded_content)
    return teamData, playerData

def get_player_data(id):
    scripts = get_data("https://understat.com/player/" + str(id))
    groupsData = {}
    matchesData = {}
    shotsData = {}
    for script in scripts:
        for c in script.contents:
            split_data = c.split('=')
            data = split_data[0].strip()
            if data == 'var matchesData':
                content = re.findall(r'JSON\.parse\(\'(.*)\'\)',split_data[1])
                decoded_content = codecs.escape_decode(content[0], "hex")[0].decode('utf-8')
                matchesData = json.loads(decoded_content)
            elif data == 'var shotsData':
                content = re.findall(r'JSON\.parse\(\'(.*)\'\)',split_data[1])
                decoded_content = codecs.escape_decode(content[0], "hex")[0].decode('utf-8')
                shotsData = json.loads(decoded_content)
            elif data == 'var groupsData':
                content = re.findall(r'JSON\.parse\(\'(.*)\'\)',split_data[1])
                decoded_content = codecs.escape_decode(content[0], "hex")[0].decode('utf-8')
                groupsData = json.loads(decoded_content)
    return matchesData, shotsData, groupsData

def parse_epl_data():
    teamData,playerData = get_epl_data()

    player_frame = {"id":[],"Player":[],"goals":[],"shots":[],"xG":[],"xA":[],"assists":[]
                 ,"key_passes":[],"npg":[],"npxG":[],"xGChain":[],"xGBuildup":[]}
    columns = ["goals","shots","xG","xA","assists","key_passes","npg","npxG","xGChain","xGBuildup"]

    for d in playerData:
        player = pd.DataFrame(get_player_data(d["id"])[0][:5]).drop(columns = ["time","position","h_team","a_team",
                                                        "h_goals","a_goals","date","roster_id","id","season"])
        player = player.apply(pd.to_numeric).sum()
        for column in columns:
            player_frame[column].append(player[column])

        player_frame["id"].append(d["id"])
        player_frame["Player"].append(d["player_name"])
            
    player_frame = pd.DataFrame(player_frame)
    
    return player_frame

class PlayerID:
    def __init__(self, us_id, fpl_id, us_name, fpl_name):
        self.us_id = str(us_id)
        self.fpl_id = str(fpl_id)
        self.us_name = us_name
        self.fpl_name = fpl_name
        
