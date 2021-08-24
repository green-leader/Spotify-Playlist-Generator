import logging
from  azure.core.exceptions import ResourceNotFoundError
import json
import sys
import os
import spotipy
from azure.identity import EnvironmentCredential
from azure.keyvault.secrets import SecretClient

class AzureKeyVaultCacheHandler(spotipy.cache_handler.CacheHandler):
    """
    Store and retrieve the token info inside of Azure Key Vault
    """
    def __init__(self, tokenCacheName="SpotipyTokenCache"):
        self.tokenCacheName = tokenCacheName
        VAULT_URL = os.environ["VAULT_URL"]
        self.credential = EnvironmentCredential()
        self.client = SecretClient(vault_url=VAULT_URL, credential=self.credential)

    def get_cached_token(self):
        token_info = None
        try:
            token_info_string = self.client.get_secret(self.tokenCacheName).value
            token_info = json.loads(token_info_string)
        except ResourceNotFoundError as err:
            logging.error("Couldn't read cache from vault")
            exit(1)

        return token_info
        
    
    def save_token_to_cache(self, token_info):
        try:
            self.client.set_secret(
                self.tokenCacheName,
                json.dumps(token_info),
            )
        except ResourceNotFoundError as err:
            logging.error("Couldn't write cache to vault")
            exit(1)
