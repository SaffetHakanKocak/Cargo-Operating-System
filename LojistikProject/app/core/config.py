import json
import os
from typing import Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json")

class Settings:
    PROJECT_NAME: str = "Yazlab3 Logistics"
    PROJECT_VERSION: str = "1.0.0"
    
    JWT_SECRET: str
    JWT_ALGORITHM: str
    DATABASE_URL: str

    def __init__(self):
        # Load config.json
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                config_data = json.load(f)
            
            db_config = config_data.get("database", {})
            user = db_config.get("user", "root")
            password = db_config.get("password", "")
            host = db_config.get("host", "localhost")
            port = db_config.get("port", 3306)
            name = db_config.get("name", "yazlab3_logistics")
            
            # Construct MySQL Connection String
            self.DATABASE_URL = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{name}"
            
            self.JWT_SECRET = config_data.get("jwt_secret", "supersecret")
            self.JWT_ALGORITHM = config_data.get("jwt_algorithm", "HS256")
        else:
            # Fallback
            self.DATABASE_URL = "sqlite:///./yazlab3.db"
            self.JWT_SECRET = "fallback_secret"
            self.JWT_ALGORITHM = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

settings = Settings()
