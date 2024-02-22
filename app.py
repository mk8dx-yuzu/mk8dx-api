import os
from dotenv import load_dotenv
from flask import Flask, jsonify, Request
from flask_cors import CORS
from pymongo import MongoClient
load_dotenv()

client = MongoClient(f"mongodb://{os.getenv('MONGODB_HOST')}:27017/")
db = client["lounge"]
collection = db["players"]

app = Flask(__name__)

cors = CORS(app, origins="*")

@app.route("/api/leaderboard")
def get_data():
    data = list(collection.find({}, {"_id": 0}))
    print(data)
    return data

if __name__ == "__main__":
    app.run(host="0.0.0.0")
