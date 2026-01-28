from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = ConfigDict(
        extra='ignore',  # Allow extra fields from .env
        env_file='.env'
    )
    
    database_url: str
    redis_url: str
    secret_key: str
    webhook_url: str = "http://localhost:3001/webhook"  # Webhook endpoint for notifications
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

settings = Settings()


