import azure.functions as func
import datetime
import json
import logging

app = func.FunctionApp(
    http_auth_level=func.AuthLevel.FUNCTION
)

