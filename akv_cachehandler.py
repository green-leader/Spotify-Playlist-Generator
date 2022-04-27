"""
Provide spotipy cache handling with Azure Key Vault as the backend for secrets
"""
import logging
import json
import sys
import os
import spotipy
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import EnvironmentCredential
from azure.keyvault.secrets import SecretClient


class AzureKeyVaultCacheHandler(spotipy.cache_handler.CacheHandler):
    """
    Store and retrieve the token info inside of Azure Key Vault
    """

    def __init__(self, tokencachename="SpotipyTokenCache"):
        self.tokencachename = tokencachename
        vault_url = os.environ["VAULT_URL"]
        self.credential = EnvironmentCredential()
        self.client = SecretClient(vault_url=vault_url, credential=self.credential)

    def get_cached_token(self):
        token_info = None
        try:
            token_info_string = self.client.get_secret(self.tokencachename).value
            token_info = json.loads(token_info_string)
        except ResourceNotFoundError as err:
            logging.error("Resource Not Found for read: %s", (err))
            sys.exit(1)

        return token_info

    def save_token_to_cache(self, token_info):
        try:
            self.client.set_secret(
                self.tokencachename,
                json.dumps(token_info),
            )
        except ResourceNotFoundError as err:
            logging.error("Resource Not Found for write: %s", (err))
            sys.exit(1)
