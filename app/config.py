import os

class BaseConfig:
    JSON_SORT_KEYS = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*")
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")
    OTP_SEND_LIMIT_PER_IP = os.getenv("OTP_SEND_LIMIT_PER_IP", "5 per 15 minutes")
    OTP_SEND_LIMIT_PER_PHONE = os.getenv("OTP_SEND_LIMIT_PER_PHONE", "3 per 15 minutes")
    LOGIN_LIMIT_PER_IP = os.getenv("LOGIN_LIMIT_PER_IP", "10 per 30 minutes")
    ORDER_LIMIT_PER_IP = os.getenv("ORDER_LIMIT_PER_IP", "20 per hour")
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-jwt-key")
    ACCESS_TOKEN_LIFETIME_MIN = int(os.getenv("ACCESS_TOKEN_LIFETIME_MIN", 15))
    REFRESH_TOKEN_LIFETIME_DAYS = int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", 30))

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///dev.db")

class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-key"
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    @staticmethod
    def validate():
        missing = []
        if not os.getenv("SECRET_KEY"):
            missing.append("SECRET_KEY")
        if not os.getenv("DATABASE_URL"):
            missing.append("DATABASE_URL")
        if missing:
            raise RuntimeError(
                f"Missing required env vars in production: {', '.join(missing)}"
            )

def get_config_class():
    env = os.getenv("APP_ENV", "development").lower()
    if env == "production":
        ProductionConfig.validate()
        return ProductionConfig
    if env == "testing":
        return TestingConfig
    return DevelopmentConfig
