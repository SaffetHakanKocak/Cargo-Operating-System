import mysql.connector
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

def create_db():
    if not os.path.exists(CONFIG_PATH):
        print("config.json not found")
        return

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    
    db_conf = config["database"]
    
    try:
        cnx = mysql.connector.connect(
            user=db_conf["user"],
            password=db_conf["password"],
            host=db_conf["host"],
            port=db_conf["port"]
        )
        cursor = cnx.cursor()
        
        db_name = db_conf["name"]
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            print(f"Database '{db_name}' created or already exists.")
        except mysql.connector.Error as err:
            print(f"Failed creating database: {err}")
        
        cursor.close()
        cnx.close()
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")

if __name__ == "__main__":
    create_db()
