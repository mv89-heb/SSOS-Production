from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flasgger import Swagger

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
cors = CORS()

# Swagger Configuration for OpenAPI 3.0
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs"
}

template = {
    "openapi": "3.0.3",
    "info": {
        "title": "SSOS API",
        "version": "1.0.0",
        "description": "Smart Supplier Order System API Documentation"
    },
    "components": {
        "securitySchemes": {
            "cookieAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "session"
            }
        }
    }
}

swagger = Swagger(config=swagger_config, template=template)
