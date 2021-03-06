#!/usr/bin/env python

import json
import sys

from gdax.authenticated_client import AuthenticatedClient

if __name__ == '__main__':

    if len(sys.argv) == 1:
        file = 'config/prod.json'
    else:
        file = sys.argv[1]

    with open(file) as config:
        data = json.load(config)

    auth_client = AuthenticatedClient(
        data['auth']['key'],
        data['auth']['secret'],
        data['auth']['phrase'],
        api_url=data['endpoints']['rest']
    )
    accounts = auth_client.get_accounts()
    total = 0.0
    for account in accounts:
        balance = float(account['balance'])
        if balance > 0:
            currency = account['currency']
            if currency != 'USD':
                product = '{}-USD'.format(currency)
                ask = float(auth_client.get_product_ticker(product)['ask'])
                print('{} balance: {:,} @ {}'.format(currency, balance, ask))
                balance = balance * ask
            else:
                print('USD balance: {:,}'.format(balance))
            total += balance
    print('Total sell balance: {:,.2f}'.format(total))
