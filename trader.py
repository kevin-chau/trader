import os
from coinbase.wallet.client import Client

api_key = os.environ['CB_KEY']
api_secret = os.environ['CB_SECRET']

client = Client(api_key, api_secret)

# currencies = client.get_currencies()
# print(currencies)

accounts = client.get_accounts()
# print(accounts)

# for wallet in accounts.data:
#     print(wallet['name'])
#     # # print(wallet)
#     # if wallet['name'] == 'ETH Wallet':
#     #     print(wallet)

eth_account = client.get_account('ETH')
print(eth_account)