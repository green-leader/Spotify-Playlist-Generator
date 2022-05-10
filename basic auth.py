# from azure.identity import DefaultAzureCredential
# from azure.keyvault.secrets import SecretClient

# default_credential = DefaultAzureCredential()
# client = SecretClient(vault_url="https://keyvault0822.vault.azure.net/", credential=default_credential)
# # var = client.get_secret("SpotipyTokenCache")

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
vault_url="https://keyvault0822.vault.azure.net/"
# Create a SecretClient using default Azure credentials
credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url, credential)
secret_client.get_secret("SpotipyTokenCache")