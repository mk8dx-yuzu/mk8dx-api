import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import hmac
import hashlib
load_dotenv()

client = MongoClient(f"mongodb://{os.getenv('MONGODB_HOST')}:27017/")
db = client["lounge"]
collection = db["players"]

API_SECRET = os.getenv("API_SECRET")

app = Flask(__name__)

cors = CORS(app, origins="*")

def verify_hmac(data: str, signature: str):
  hashed = hmac.new(API_SECRET.encode('utf-8'), data.encode(), digestmod=hashlib.sha256).hexdigest()
  return hashed == signature

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

    if not verify_hmac(str(data), signature):
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
