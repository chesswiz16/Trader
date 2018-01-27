#!/usr/bin/env python
import json
import logging.config
import sys

from trader.cost_basis import CostBasisTrader

if __name__ == '__main__':
    if len(sys.argv) == 3:
        file = sys.argv[1]
        product_id = sys.argv[2]
    else:
        file = 'config/prod.json'
        product_id = 'ETH-USD'

    with open(file) as config:
        data = json.load(config)

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
                'filename': '/root/Trader/cost_basis_{}.log'.format(product_id),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 5
            },
            'file_debug': {
                'level': 'DEBUG',
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'formatter': 'standard',
                'filename': '/root/Trader/cost_basis_{}.log.debug'.format(product_id),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 5
            },
        },
        'loggers': {
            '': {
                'handlers': ['file', 'file_debug'],
                'level': 'INFO',
                'propagate': False
            },
        },
    })

    trader = CostBasisTrader(
        product_id,
        data['cost_basis']['order_depth'],
        data['cost_basis']['wallet_fraction'],
        delta=data['cost_basis']['delta'],
        api_key=data['auth']['key'],
        secret_key=data['auth']['secret'],
        pass_phrase=data['auth']['phrase'],
        api_url=data['endpoints']['rest'],
        ws_url=data['endpoints']['socket'],
    )
    try:
        trader.on_start()
        trader.connect()
        trader.run_forever()
    except KeyboardInterrupt:
        trader.close()
