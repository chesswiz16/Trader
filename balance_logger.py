#!/usr/bin/env python

import json
import logging.config
import sys
from time import sleep

from gdax.authenticated_client import AuthenticatedClient

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s|%(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'standard',
            'filename': 'balances.log',
            'when': 'midnight',
            'interval': 1,
            'backupCount': 5
        },
    },
    'loggers': {
        '': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True
        },
    },
})
module_logger = logging.getLogger(__name__)

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
    running = True
    while running:
        try:
            total = 0.0
            for account in accounts:
                balance = float(account['balance'])
                if balance > 0:
                    currency = account['currency']
                    if currency != 'USD':
                        product = '{}-USD'.format(currency)
                        ask = float(auth_client.get_product_ticker(product)['ask'])
                        balance = balance * ask
                    total += balance
            module_logger.info('{:,.2f}'.format(total))
            sleep(300)
        except KeyboardInterrupt:
            running = False
