import os
from azure.cosmos import CosmosClient


client = CosmosClient.from_connection_string(os.environ["AzureCosmosDBConnectionString"])

database = client.get_database_client(os.environ["DatabaseName"])

player_container = database.get_container_client(os.environ["PlayerContainerName"])

prompt_container = database.get_container_client(os.environ["PromptContainerName"])