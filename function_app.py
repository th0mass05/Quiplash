import azure.functions as func
import datetime
import json
import logging
import uuid
import requests
import os
from shared_code.database import player_container
from shared_code.database import prompt_container
import time

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

CONTENT_SAFETY_MAX_ATTEMPTS = 6
CONTENT_SAFETY_MAX_WAIT_SECONDS = 10

def analyse_text_with_retry(session: requests.Session, endpoint: str, key: str, text: str) -> dict:
    """
        Due to usage limits , the burst of 5 calls can return an error. 

        So if azure returns 429, we will now wait and try again up to 6 times, according to azure's retry header
    """
    for attempt in range(CONTENT_SAFETY_MAX_ATTEMPTS):
        response = session.post(
            f"{endpoint}/contentsafety/text:analyze",
            params={"api-version": "2024-09-01"},
            headers={
                "Ocp-Apim-Subscription-Key": key,
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
                "outputType": "FourSeverityLevels"
            },
            timeout=20
        )
 
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()
 
        if attempt == CONTENT_SAFETY_MAX_ATTEMPTS - 1:
            break
 
        # azure usually says how long to wait in the retry-After header
        # if it doesn't, back off exponentially
        try:
            wait = float(response.headers.get("Retry-After"))
        except (TypeError, ValueError):
            wait = 2 ** attempt
        wait = min(max(wait, 1), CONTENT_SAFETY_MAX_WAIT_SECONDS)
 
        logging.warning("Content Safety rate limited (429); retrying in %s seconds", wait)
        time.sleep(wait)
 
    response.raise_for_status()

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

    try:
        data = req.get_json()
    except ValueError:
        return json_response(False, "Invalid request", 400)

    if not isinstance(data, dict):
        return json_response(False, "Invalid request", 400)

    username = data.get("username")
    add_to_games_played = data.get("add_to_games_played")
    add_to_score = data.get("add_to_score")

    if not isinstance(username, str) or type(add_to_games_played) is not int or type(add_to_score) is not int:
        return json_response(False, "Invalid request", 400)

    if add_to_games_played < 0 or add_to_score < 0:
        return json_response(False, "Invalid scores.", 200)
    
    try:
        username_query = """
                        SELECT *
                        FROM c
                        WHERE STRINGEQUALS(c.username, @username, true)
                        """
        username_parameters = [{"name": "@username", "value": username}]
    
            
    
        username_matches = list(player_container.query_items(query=username_query, parameters=username_parameters, enable_cross_partition_query=True))
    
        if not username_matches:
            return json_response(False, "Player does not exist.", 200)

        player = username_matches[0]

        # Increment the data but accounting for potential simultaneous updates by using atomic increments
        player_container.patch_item(
            item=player["id"],
            partition_key=player["id"],
            patch_operations=[
                {"op": "incr",
                 "path": "/games_played",
                 "value": add_to_games_played},
                 {"op": "incr",
                  "path": "/total_score",
                  "value": add_to_score}
            ]
        )


        return json_response(True, "OK", 200)

        
        
        
    except Exception:
        logging.exception("Player update failed")
        return json_response(False, "Server error", 500)


@app.route(route="prompt/create", methods=["POST"])
def create_prompt(req: func.HttpRequest) -> func.HttpResponse:

    try:
        data = req.get_json()
    except ValueError:
        return json_response(False, "Invalid request", 400)

    if not isinstance(data, dict):
            return json_response(False, "Invalid request", 400)

    username = data.get("username")
    text = data.get("text")
    tags = data.get("tags")

    if not isinstance(username, str) or not isinstance(text, str) or not isinstance(tags, list):
        return json_response(False, "Invalid request", 400)

    if not all(isinstance(tag, str) for tag in tags):
        return json_response(False, "Invalid request", 400)

    if not 20 <= len(text) <= 100:
        return json_response(False, "Prompt less than 20 characters or more than 100 characters.", 200)

    if len(tags) < 1:
        return json_response(False, "There must be at least one tag.", 200)

    for i in tags:
        if not 2 <= len(i) <= 10:
            return json_response(False, "Tag less than 2 characters or more than 10 characters.", 200)

    try:
        username_query = """
                        SELECT *
                        FROM c
                        WHERE STRINGEQUALS(c.username, @username, true)
                        """
        username_parameters = [{"name": "@username", "value": username}]

        username_matches = list(player_container.query_items(query=username_query, parameters=username_parameters, enable_cross_partition_query=True))
            
        if not username_matches:
            return json_response(False, "Player not found.", 404)


        # remove duplicate tags, insensitive to case
        cleaned_tags=[]

        marker = set()

        for l in tags:
            ll = l.lower()
            if ll not in marker:
                marker.add(ll)
                cleaned_tags.append(l)
                
        

        # read the configuraiton
        endpoint = os.environ["TranslationEndpoint"].rstrip("/")
        headers = {
            "Ocp-Apim-Subscription-Key": os.environ["TranslationKey"],
            "Ocp-Apim-Subscription-Region": os.environ["TranslationLocation"],
            "Content-Type": "application/json"}

        body = [{"Text": text}]

        # detect language
        response = requests.post(
            f"{endpoint}/detect",
            params={"api-version": "3.0"},
            headers=headers,
            json=body,
            timeout=20
        )

        response.raise_for_status()
        detection = response.json()[0]

        language = detection["language"]
        confidence = detection["score"]

        supported_languages = ["en", "cy", "es", "ta", "zh-Hans", "ar"]

        # reject languages not supported or not known
        if language not in supported_languages:
            return json_response(False, "Unsupported language.", 200)

        if confidence < 0.2:
            return json_response(False, "Unsupported language.", 200)

        new_languages = []

        for j in supported_languages:
            if j != language:
                new_languages.append(j)
        
        response = requests.post(
            f"{endpoint}/translate",
            params={
                "api-version": "3.0",
                "from": language,
                "to": new_languages
            },
            headers=headers,
            json=body,
            timeout=20
        )

        response.raise_for_status()
        translations = response.json()[0]["translations"]

        texts = [{"language": language, "text": text}]

        for k in translations:
            lang = k["to"]
            t = k["text"]

            texts.append({"language": lang, "text":t})

        prompt = {
            "id": str(uuid.uuid4()),
            "username": username_matches[0]["username"],
            "texts": texts,
            "tags": cleaned_tags

        }

        prompt_container.create_item(body=prompt)

        return json_response(True, "OK", 200)

    except Exception:
        logging.exception("Prompt creation failed")
        return json_response(False, "Server error", 500)

@app.route(route="prompt/moderate", methods=["POST"])
def moderate_prompts(req: func.HttpRequest) -> func.HttpResponse:

    try:
        data = req.get_json()
    except ValueError:
        return json_response(False, "Invalid request", 400)
    
    if not isinstance(data, dict):
        return json_response(False, "Invalid request", 400)

    prompt_ids = data.get("prompt-ids")

    if not isinstance(prompt_ids, list):
        return json_response(False, "Invalid request", 400)
    
    if not all(isinstance(id, str) for id in prompt_ids):
        return json_response(False, "Invalid request", 400)


    try:

        prompt_query = """
                            SELECT c.id, c.texts
                            FROM c
                            WHERE c.id = @id
                        """
        results = []
     

        # eead the configuration once, not once per prompt (fixing usage error)
        endpoint = os.environ["ContentSafetyEndpoint"].rstrip("/")
        key = os.environ["ContentSafetyKey"]

        # re use the same connection
        with requests.Session() as session:
            for id in prompt_ids:
                parameters = [{"name": "@id", "value": id}]
                prompt_matches = list(prompt_container.query_items(query=prompt_query, parameters=parameters, enable_cross_partition_query=True))
                        
                if not prompt_matches:
                    continue

                else:
                    current_prompt = prompt_matches[0]

                    current_text = None
                    for text in current_prompt["texts"]:
                        if text["language"] == "en":
                            current_text = text["text"]
                            break

                    if current_text is None:
                        raise ValueError("Stored prompt has no English text")

                    

                    
                    analysis = analyse_text_with_retry(session, endpoint, key, current_text)
                    summed = 0
                    for category in analysis["categoriesAnalysis"]:
                        summed += category["severity"]
                    average_severity = summed / 4
                    outcome = average_severity > 2

                    results.append({"prompt-id": id, "outcome": outcome, "average_severity": average_severity})

        
        return func.HttpResponse(
            json.dumps({"success": results}),
            status_code=200,
            mimetype="application/json"
        )

    except Exception:
        logging.exception("Prompt moderation failed")
        return json_response(False, "Server error", 500)

                


@app.route(route="prompt/delete", methods=["POST"])
def delete_prompts(req: func.HttpRequest) -> func.HttpResponse:

    try:
        data = req.get_json()
    except ValueError:
        return json_response(False, "Invalid request", 400)
    
    if not isinstance(data, dict):
        return json_response(False, "Invalid request", 400)
    
    username = data.get("username")
    
    if not isinstance(username, str):
        return json_response(False, "Invalid request", 400)

    try:
        username_query = """
                            SELECT c.username
                            FROM c
                            WHERE STRINGEQUALS(c.username, @username, true)
                        """

        username_parameters = [{"name": "@username", "value": username}]
        
        
        
        username_matches = list(player_container.query_items(query=username_query, parameters=username_parameters, enable_cross_partition_query=True))
        
        if not username_matches:
            return json_response(False, "Player not found so cannot be deleted", 404)
        stored_username = username_matches[0]["username"]
        prompt_query = """
                            SELECT c.username, c.id
                            FROM c
                            WHERE STRINGEQUALS(c.username, @username, true)
                        """

        parameters = [{"name": "@username", "value": stored_username}]
        prompt_matches = list(prompt_container.query_items(query=prompt_query, parameters=parameters, enable_cross_partition_query=True))
        count = 0                         
        for prompt in prompt_matches:
            prompt_container.delete_item(item=prompt["id"], partition_key=prompt["username"])
            count += 1

        return json_response(True, f"{count} prompts deleted", 200)
        
    except Exception:
        logging.exception("Prompt deletion failed")
        return json_response(False, "Server error", 500)
        
    



@app.route(route="utils/get", methods=["POST"])
def get_prompts(req: func.HttpRequest) -> func.HttpResponse:

    try:
        data = req.get_json()
    except ValueError:
        return json_response(False, "Invalid request", 400)
    
    if not isinstance(data, dict):
        return json_response(False, "Invalid request", 400)
    
    players = data.get("players")

    tag_list = data.get("tag_list")
    
    if not isinstance(players, list) or not isinstance(tag_list, list):
        return json_response(False, "Invalid request", 400)

    if not all(isinstance(tag, str) for tag in tag_list):
        return json_response(False, "Invalid request", 400)

    if not all(isinstance(player, str) for player in players):
        return json_response(False, "Invalid request", 400)
    
    try:
        username_query = """
                            SELECT c.username
                            FROM c
                            WHERE STRINGEQUALS(c.username, @username, true)
                        """
    
        

        stored_usernames = []

        for user in players:
            username_parameters = [{"name": "@username", "value": user}]
            username_matches = list(player_container.query_items(query=username_query, parameters=username_parameters, enable_cross_partition_query=True))
            if username_matches:
                stored_username = username_matches[0]["username"]
                if stored_username not in stored_usernames:
                    stored_usernames.append(username_matches[0]["username"])
        
    
    
        
        results = []
        requested_tags = {tag.casefold() for tag in tag_list}
        for stored_user in stored_usernames:
            prompt_query = """
                                SELECT c.username, c.id, c.tags, c.texts
                                FROM c
                                WHERE STRINGEQUALS(c.username, @username, true)
                            """
        
            parameters = [{"name": "@username", "value": stored_user}]
            prompt_matches = list(prompt_container.query_items(query=prompt_query, parameters=parameters, enable_cross_partition_query=True))
            
            for prompt in prompt_matches:
                tag_matches = any(tag.casefold() in requested_tags for tag in prompt["tags"])
                if tag_matches:
                    results.append(prompt)

        return func.HttpResponse(
            json.dumps(results),
            status_code= 200,
            mimetype="application/json"
            )

    except Exception:
        logging.exception("Prompt filtering failed")
        return json_response(False, "Server error", 500)