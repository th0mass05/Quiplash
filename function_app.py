import azure.functions as func
import datetime
import json
import logging
import uuid
from shared_code.database import player_container

app = func.FunctionApp(
    http_auth_level=func.AuthLevel.FUNCTION
)

def not_implemented() -> func.HttpResponse:
    return func.HttpResponse(
        '{"msg": "not implemented"}',
        status_code=200,
        mimetype="application/json"
    )


@app.route(route="player/register", methods=["POST"])
def register_player(req: func.HttpRequest) -> func.HttpResponse:
    return not_implemented()


@app.route(route="player/login", methods=["POST"])
def login_player(req: func.HttpRequest) -> func.HttpResponse:
    return not_implemented()


@app.route(route="player/update", methods=["PUT"])
def update_player(req: func.HttpRequest) -> func.HttpResponse:
    return not_implemented()


@app.route(route="prompt/create", methods=["POST"])
def create_prompt(req: func.HttpRequest) -> func.HttpResponse:
    return not_implemented()


@app.route(route="prompt/moderate", methods=["POST"])
def moderate_prompts(req: func.HttpRequest) -> func.HttpResponse:
    return not_implemented()


@app.route(route="prompt/delete", methods=["POST"])
def delete_prompts(req: func.HttpRequest) -> func.HttpResponse:
    return not_implemented()


@app.route(route="utils/get", methods=["POST"])
def get_prompts(req: func.HttpRequest) -> func.HttpResponse:
    return not_implemented()