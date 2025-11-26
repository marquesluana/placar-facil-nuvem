import os
import json
import boto3

BUCKET = os.environ.get('BUCKET_NAME')
s3 = boto3.client('s3')

def s3_key_for_match(match_id):
    clean_id = match_id
    if not clean_id.startswith("match-"):
        clean_id = "match-" + clean_id
    return f"matches/{clean_id}.json"

def lambda_handler(event, context):
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET, Prefix='matches/')

        matches = []
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                if not key.endswith('.json'):
                    continue

                try:
                    resp = s3.get_object(Bucket=BUCKET, Key=key)
                    match = json.loads(resp['Body'].read().decode('utf-8'))

                    matches.append({
                        "id": match["id"],
                        "name": match["name"],
                        "teamA": match["teamA"],
                        "teamB": match["teamB"],
                        "setsTotal": match["setsTotal"],
                        "maxPointsPerSet": match["maxPointsPerSet"],
                        "status": match["status"],
                        "vencedor": match.get("vencedor"),
                        "createdAt": match["createdAt"],
                        "setsA": match.get("setsA", 0),
                        "setsB": match.get("setsB", 0),
                        "sets": match.get("sets", []) 
                    })
                except Exception as e:
                    print(f"Erro lendo {key}: {e}")
                    continue

        matches.sort(key=lambda x: x["createdAt"], reverse=True)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"  
            },
            "body": json.dumps({"matches": matches}, ensure_ascii=False)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }