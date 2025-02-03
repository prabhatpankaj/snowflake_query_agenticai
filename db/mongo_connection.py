import logging
from pymongo import MongoClient
from decouple import config
from langgraph.checkpoint.mongodb import MongoDBSaver

logging.basicConfig(level=logging.INFO)


def initialize_mongo_client():
    mongodb_uri = config("MONGODB_URI", default="mongodb://admin:admin123@localhost:27017")
    if not mongodb_uri:
        raise ValueError("MongoDB URI is missing in environment variables.")
    try:
        return MongoClient(mongodb_uri)
    except Exception as e:
        logging.error(f"Error initializing MongoDB client: {e}")
        raise

def get_database_from_client(client):
    database_name = config("DATABASE_NAME", default="workflow-agenticai")
    if not database_name:
        raise ValueError("Database name is missing in environment variables.")
    try:
        return client[database_name]
    except Exception as e:
        logging.error(f"Error retrieving database: {e}")
        raise

def get_checkpointer():
    try:
        client = initialize_mongo_client()
        database = get_database_from_client(client)
        return MongoDBSaver(database)
    except Exception as e:
        logging.error(f"Error creating checkpointer: {e}")
        raise
