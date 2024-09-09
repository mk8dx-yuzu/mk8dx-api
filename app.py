import os
import subprocess
import hmac
import json

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from pymongo import MongoClient
import hashlib
load_dotenv()

client = MongoClient(f"{os.getenv('MONGODB_HOST')}")
db = client["lounge"]
collection = db["players"]

API_SECRET = os.getenv("API_SECRET")
PASS_SECRET = os.getenv("PASS_SECRET")

app = Flask(__name__)

cors = CORS(app, origins="*")

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["5 per minute"],
)

@app.errorhandler(RateLimitExceeded)
def ratelimit_exceeded(error):
    return jsonify({'error': 'Too Many Requests'}), 429

def verify_api(data: str, signature: str):
  hashed = hmac.new(API_SECRET.encode('utf-8'), data.encode(), digestmod=hashlib.sha256).hexdigest()
  return hashed == signature

def verify_pass(data: str, signature: str):
  hashed = hmac.new(API_SECRET.encode('utf-8'), data.encode(), digestmod=hashlib.sha256).hexdigest()
  return hashed == signature

@app.post("/api/passwd")
def passwd():
    incoming_signature = request.headers.get('Signature-256')
    calculated_signature = f"{hmac.new(key=PASS_SECRET.encode(), msg=request.data, digestmod=hashlib.sha256).hexdigest()}"
    
    json_data = json.loads(request.data.decode().replace("'", '"'))

    if hmac.compare_digest(incoming_signature, calculated_signature):
        with open('persistent/password.txt', 'w+') as file:
            file.write(f"{json_data['password']}")
            file.close()

        return jsonify({'message': 'Cool!'}), 200
    return jsonify({'error': "nope"}), 400

@app.get("/api/leaderboard")
def get_data():
    data = list(collection.find({}, {"_id": 0}))
    return data

@app.post("/api/update")
def update_mmr():
    signature: str = request.headers.get('X-HMAC-Signature')
    data: list = request.json
    
    if not data or not signature:
        return jsonify({'error': 'Missing data or signature'}), 400

    if not verify_api(str(data), signature):
        return jsonify({'error': 'Invalid signature'}), 403
    
    for item in data:
        name: str = item[0]
        mmr: int = item[1]
        
        if type(name) != str or type(mmr) != int:
            return jsonify({'error': 'Invalid Data Format'}), 400 
        
        current_mmr: int = collection.find_one({"name": name})['mmr']

        collection.update_one({"name": name}, {"$set": {"mmr": mmr}})
        collection.update_one({"name": name}, {"$push": {"history": mmr - current_mmr}})
        collection.update_one({"name": name}, {"$inc": {"wins" if mmr > current_mmr else "losses": 1}})

    return jsonify({'message': 'Data submitted successfully'}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0")
