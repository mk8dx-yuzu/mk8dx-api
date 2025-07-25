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
db = client["season-3-lounge"]
collection = db["players"]

db_season_3 = client["season-3-lounge"]
collection_season_3 = db["players"]
collection_mogis = db["mogis"]

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
    return jsonify({"error": "Too Many Requests"}), 429


def verify_api(data: str, signature: str):
    hashed = hmac.new(
        API_SECRET.encode("utf-8"), data.encode(), digestmod=hashlib.sha256
    ).hexdigest()
    return hashed == signature


def verify_pass(data: str, signature: str):
    hashed = hmac.new(
        API_SECRET.encode("utf-8"), data.encode(), digestmod=hashlib.sha256
    ).hexdigest()
    return hashed == signature


@app.post("/api/passwd")
def passwd():
    incoming_signature = request.headers.get("Signature-256")
    calculated_signature = f"{hmac.new(key=PASS_SECRET.encode(), msg=request.data, digestmod=hashlib.sha256).hexdigest()}"

    request_data: dict[str, str] = None

    try:
        request_data: dict[str, str] = json.loads(
            request.data.decode().replace("'", '"')
        )
        if not isinstance(request_data, dict):
            return jsonify({"error": "Bad request"}), 400
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON format"}), 400

    target_server: str | None = request_data.get("server", None)
    new_password: str | None = request_data.get("password", None)

    success_msg = {"message": "Cool!"}

    if hmac.compare_digest(incoming_signature, calculated_signature):
        # Legacy: Put the password in password.txt for #inmogi-password
        if not target_server:
            with open("persistent/password.txt", "w+", encoding="utf-8") as file:
                file.write(new_password)
                file.close()
        # Update the JSON configuration with the new password
        try:
            with open(
                "persistent/passwords.json", "r", encoding="utf-8"
            ) as passwords_file:
                passwords: dict[str, str] = json.load(passwords_file)

            print(passwords)
            print(target_server)

            if target_server and not target_server in passwords:
                success_msg["server"] = "invalid server"
            elif not target_server:
                success_msg["server"] = "no server provided, updated pass for eu main"
                target_server = (
                    "EU MAIN 🌍 | LOUNGE → Join Discord to play here! dsc.gg/yuzuonline"
                )
            if target_server:
                # Update password in config
                passwords[target_server] = new_password

                # Write updated config back to file
                with open(
                    "persistent/passwords.json", "w", encoding="utf-8"
                ) as passwords_file:
                    json.dump(passwords, passwords_file, indent=4, ensure_ascii=False)
                success_msg["message"] = "set server pass"
        except Exception as e:
            success_msg["error"] = f"Failed to read password file: {str(e)}"
            print(f"Error reading passwords.json: {e}")

        return jsonify(success_msg), 200
    return jsonify({"error": "nope"}), 400


@app.get("/api/passwd")
def get_passwd():
    incoming_signature = request.headers.get("Signature-256")
    calculated_signature = f"{hmac.new(key=PASS_SECRET.encode(), msg=request.data, digestmod=hashlib.sha256).hexdigest()}"

    if hmac.compare_digest(incoming_signature, calculated_signature):
        with open("persistent/passwords.json", "r", encoding="utf-8") as passwords_file:
            return jsonify(json.load(passwords_file)), 200
    return jsonify({"error": "nope"}), 400


@app.get("/api/")
def get_msg():
    return "Yuzu is a hybrid of mandarin orange and ichang papeda, with a tart and fragrant flavor. It is widely used in East Asian cuisine, especially in Japan, Korea, and China, where it is made into sauces, vinegars, teas, and sweets."


@app.get("/api/leaderboard")
def get_data():
    season = request.args.get("season", type=int) or 3

    db = client[f"season-{season}-lounge"]
    target_collection = db["players"]

    data = list(
        target_collection.find(
            {"name": {"$ne": "mrboost"}, "inactive": {"$ne": True}}, {"_id": 0}
        )
    )
    return data

@app.get("/api/mogis")
def get_mogi_data():
    season = request.args.get("season", type=int) or 3

    db = client[f"season-{season}-lounge"]
    target_collection = db["mogis"]

    data = list(
        target_collection.find(
            {}, {"_id": 0}
        )
    )
    return data


@app.post("/api/update")
def update_mmr():
    signature: str = request.headers.get("X-HMAC-Signature")
    data: list = request.json

    if not data or not signature:
        return jsonify({"error": "Missing data or signature"}), 400

    if not verify_api(str(data), signature):
        return jsonify({"error": "Invalid signature"}), 403

    for item in data:
        name: str = item[0]
        mmr: int = item[1]

        if type(name) != str or type(mmr) != int:
            return jsonify({"error": "Invalid Data Format"}), 400

        current_mmr: int = collection.find_one({"name": name})["mmr"]

        collection.update_one({"name": name}, {"$set": {"mmr": mmr}})
        collection.update_one({"name": name}, {"$push": {"history": mmr - current_mmr}})
        collection.update_one(
            {"name": name}, {"$inc": {"wins" if mmr > current_mmr else "losses": 1}}
        )

    return jsonify({"message": "Data submitted successfully"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0")
