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

def json_response(result: bool, msg: str, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(body=json.dumps({"result": result, "msg": msg}), status_code = status_code, mimetype="application/json")

@app.route(route="player/register", methods=["POST"])
def register_player(req: func.HttpRequest) -> func.HttpResponse:

    # Get data
    try:
        data = req.get_json()
    except ValueError:
        return json_response(False, "Invalid request", 400)

    # Ensure data contains an object
    if not isinstance(data, dict):
        return json_response(False, "Invalid request", 400)

    username = data.get("username")
    password = data.get("password")

    


    if not isinstance(username, str):
        return json_response(False, "Invalid request", 400)
    if not isinstance(password, str):
        return json_response(False, "Invalid request", 400)

    if not 5 <= len(username) <= 12:
        return json_response(False, "Username less than 5 characters or more than 12 characters.", 200)

    if not 8 <= len(password) <= 12:
            return json_response(False, "Password less than 8 characters or more than 12 characters.", 200)

    

    try:
        username_query = """
                                SELECT c.id
                                FROM c
                                WHERE STRINGEQUALS(c.username, @username, true)
                                """
        username_parameters = [{"name": "@username", "value": username}]
            
        username_matches = list(player_container.query_items(query=username_query, parameters=username_parameters, enable_cross_partition_query=True))

        if username_matches:
                return json_response(False, "Username already exists.", 200)
        username_id = str(uuid.uuid4())
        player = {
            "id": username_id,
            "username": username,
            "password": password,
            "games_played": 0,
            "total_score": 0
        }
    
        player_container.create_item(body=player)
        return json_response(True, "OK")
    except Exception:
        logging.exception("Player registration failed")
        return json_response(False, "Server error", 500)


@app.route(route="player/login", methods=["POST"])
def login_player(req: func.HttpRequest) -> func.HttpResponse:

    # Get data
    try:
        data = req.get_json()
    except ValueError:
        return json_response(False, "Invalid request", 400)

    # make sure it is dictionary
    if not isinstance(data, dict):
        return json_response(False, "Invalid request", 400)

    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        return json_response(False, "Invalid request", 400)

    try:
        username_query = """
                            SELECT c.password
                            FROM c
                            WHERE STRINGEQUALS(c.username, @username, true)
                        """
        username_parameters = [{"name": "@username", "value": username}]

        

        username_matches = list(player_container.query_items(query=username_query, parameters=username_parameters, enable_cross_partition_query=True))

        if not username_matches:
            return json_response(False, "Username or password incorrect.", 200)

        if username_matches[0]["password"] == password:
            return json_response(True, "OK", 200)
        else:
            return json_response(False, "Username or password incorrect.", 200)
    except Exception:
        logging.exception("Player login failed")
        return json_response(False, "Server error", 500)



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