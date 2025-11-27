import os
import json
import boto3
from botocore.exceptions import ClientError

BUCKET = os.environ.get('BUCKET_NAME')
s3 = boto3.client('s3')

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }

def sets_needed_to_win(total_sets):
    """Calcula o número de sets necessários para vencer a partida."""
    if total_sets <= 0: return 1 
    return (total_sets // 2) + 1

def compute_sets_won(match):
    """Recalcula o placar de sets baseado nos sets marcados como finished."""
    a = 0
    b = 0
    for s in match.get('sets', []):
        if s.get('finished', False):
            if s.get('A', 0) > s.get('B', 0):
                a += 1
            elif s.get('B', 0) > s.get('A', 0):
                b += 1
    return a, b

def check_win_conditions(match):
    """Verifica se o set atual terminou e se a partida terminou."""
    max_points = match.get('maxPointsPerSet', 25)
    sets_total = match.get('setsTotal', 3)
    
    # 1. Checar se o set atual terminou
    current_set = None
    if match.get('sets'):
        for s in reversed(match['sets']):
            if not s.get('finished', False):
                current_set = s
                break
    
    # Se existe um set em andamento
    if current_set:
        score_A = current_set.get('A', 0)
        score_B = current_set.get('B', 0)
        
        if max_points > 0:
            if score_A >= max_points and score_A >= score_B + 2:
                current_set['finished'] = True
            elif score_B >= max_points and score_B >= score_A + 2:
                current_set['finished'] = True
                
    # 2. Recalcular placar de sets
    sets_won_A, sets_won_B = compute_sets_won(match)
    match['setsA'] = sets_won_A
    match['setsB'] = sets_won_B
    
    # 3. Checar vitória da Partida
    needed = sets_needed_to_win(sets_total)

    if sets_won_A >= needed:
        match['status'] = 'finalizado'
        match['vencedor'] = match.get('teamA')
    elif sets_won_B >= needed:
        match['status'] = 'finalizado'
        match['vencedor'] = match.get('teamB')
    
    return match

def lambda_handler(event, context):
    print("DEBUG Update:", json.dumps(event))
    if event.get('httpMethod') == 'OPTIONS':
        return response(200, {})

    path_params = event.get('pathParameters') or {}
    match_id = event.get('pathParameters', {}).get('matchId')
    if not match_id:
        return response(400, {"error": "missing id"})

    try:
        raw_body = event.get('body')
        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            body = event 
    except Exception:
        return response(400, {"error": "invalid json body"})

    action = body.get('action', 'point')
    
    clean_id = match_id if match_id.startswith("match-") else f"match-{match_id}"
    key = f"matches/{clean_id}.json"
    
    try:
        resp = s3.get_object(Bucket=BUCKET, Key=key)
        match = json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError:
        return response(404, {"error": "match not found"})

    if match.get('status') == 'finalizado':
        return response(400, {"error": "match is already finished"})
        
    if action == 'point':
        team = body.get('team')
        delta = int(body.get('delta', 1))
        
        if 'sets' not in match: match['sets'] = []
        
        current = None
        for s in match['sets']:
            if not s.get('finished'):
                current = s
                break
        
        if not current:
            current = {"set": len(match['sets'])+1, "A": 0, "B": 0, "finished": False}
            match['sets'].append(current)
            
        if team == 'A': current['A'] = max(0, current['A'] + delta)
        elif team == 'B': current['B'] = max(0, current['B'] + delta)
        
        match = check_win_conditions(match)
                
    elif action == 'finish':
        match = check_win_conditions(match) 
        match['status'] = 'finalizado'
        
        if match.get('setsA', 0) > match.get('setsB', 0):
            match['vencedor'] = match.get('teamA')
        elif match.get('setsB', 0) > match.get('setsA', 0): 
            match['vencedor'] = match.get('teamB')
        else:
            match['vencedor'] = None 


    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(match).encode('utf-8'))
    
    return response(200, {"match": match})