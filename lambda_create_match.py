import os
import json
import uuid
import time
import boto3
from botocore.exceptions import ClientError

BUCKET = os.environ.get('BUCKET_NAME')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

if not BUCKET:
    raise RuntimeError("BUCKET_NAME env var is required")

s3 = boto3.client('s3', region_name=AWS_REGION)

def _now_ts():
    return int(time.time())

def s3_key_for_match(match_id):
    clean_id = match_id
    if not clean_id.startswith("match-"):
        clean_id = "match-" + clean_id
    return f"matches/{clean_id}.json"

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
    except Exception:
        return {"statusCode":400, "body": json.dumps({"error":"invalid json"})}

    raw_name = body.get('name')
    raw_teamA = body.get('teamA')
    raw_teamB = body.get('teamB')

    teamA = (raw_teamA.strip() if raw_teamA and str(raw_teamA).strip() else "Time A")
    teamB = (raw_teamB.strip() if raw_teamB and str(raw_teamB).strip() else "Time B")
    name = (raw_name.strip() if raw_name and str(raw_name).strip() else None)

    if not name:
        name = f"{teamA} x {teamB}"

    try:
        sets = int(body.get('sets', 3))
        max_points = int(body.get('maxPoints', 25))
        time_limit = body.get('timeLimit')
    except Exception:
        return {"statusCode":400, "body": json.dumps({"error":"invalid numeric fields"})}

    if sets < 1 or max_points < 1:
        return {"statusCode":400, "body": json.dumps({"error":"sets and maxPoints must be > 0"})}

    match_id = str(uuid.uuid4())[:8]
    created_at = _now_ts()

    match = {
        "id": f"match-{match_id}",
        "name": name,
        "teamA": teamA,
        "teamB": teamB,
        "setsTotal": sets,
        "maxPointsPerSet": max_points,
        "timeLimit": time_limit,
        "sets": [],
        "setsA": 0,
        "setsB": 0,
        "status": "andamento",
        "vencedor": None,
        "createdAt": created_at
    }

    key = s3_key_for_match(match["id"])
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(match, ensure_ascii=False, indent=2).encode('utf-8')
        )
    except ClientError as e:
        return {"statusCode":500, "body": json.dumps({"error":"s3 error", "detail": str(e)})}

    return {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"match": match})
    }