#!/usr/bin/env python
import json
import logging
import sys
from datetime import datetime, timedelta
from time import sleep

import dateutil.parser

from gdax.public_client import PublicClient
from regression.authenticated_client_regression import AuthenticatedClientRegression
from trader.cost_basis import CostBasisTrader

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
module_logger = logging.getLogger(__name__)


def get_rates(start, end):
    return client.get_product_historic_rates(
        product_id,
        start=start.isoformat() + 'Z',
        end=end.isoformat() + 'Z',
        granularity=60
    )


if __name__ == '__main__':
    time_delta = timedelta(minutes=300)
    if len(sys.argv) == 6:
        product_id = sys.argv[1]
        start_time = dateutil.parser.parse(sys.argv[2])
        end_time = dateutil.parser.parse(sys.argv[3])
        starting_balance = sys.argv[4]
        config_file = sys.argv[5]
    else:
        product_id = 'ETH-USD'
        start_time = datetime.utcnow() - timedelta(days=10)
        end_time = datetime.utcnow()
        starting_balance = 1000
        config_file = 'config/sandbox.json'

    with open(config_file) as config:
        data = json.load(config)

    client = PublicClient()
    # Seed with indicative rates
    last_rates = get_rates(start_time, start_time + timedelta(minutes=2))[-1]
    regression_client = AuthenticatedClientRegression(product_id, last_rates, starting_balance=starting_balance)
    trader = CostBasisTrader(
        product_id,
        data['cost_basis']['order_depth'],
        data['cost_basis']['wallet_fraction'],
        auth_client=regression_client,
    )
    # Place starting orders
    trader.on_start()

    # Let'er rip!
    current_time = start_time
    last_high = 0
    fees = 0
    total_trades = 0
    fee_trades = 0
    while current_time < end_time:
        next_time = current_time + time_delta
        module_logger.info('Running from {} to {}'.format(current_time, next_time))
        rates = get_rates(current_time, next_time)
        for candle in reversed(rates):
            # time, low, high, open, close, volume
            last_high = candle[2]
            order = regression_client.on_tick(candle[1], candle[2])
            if order:
                module_logger.info(
                    '{}: Low:{} High:{} Open:{} Close:{}'.format(
                        datetime.fromtimestamp(candle[0]), candle[1],
                        candle[2], candle[3], candle[4]
                    )
                )
                total_trades += 1
                if order['type'] == 'stop':
                    fee_trades += 1
                    fees += 0.003 * float(order['size']) * float(order['price'])
                trader.on_order_fill({
                    'maker_order_id': order['id'],
                    'taker_order_id': '',
                    'type': 'match',
                    'price': order['price'],
                    'side': order['side'],
                    'size': order['size'],
                })
                regression_client.last_rates = candle
        current_time = next_time
        sleep(1)

    # Cancel remaining to release held balances
    trader.cancel_all()

    # What do we have left?
    balances = trader.available_balance
    module_logger.info('Ending orders:{}'.format(json.dumps(trader.orders, indent=4, sort_keys=True)))
    module_logger.info('Ending balances:{}'.format(json.dumps(balances, indent=4, sort_keys=True)))
    total = 0
    for currency, balance in balances.items():
        if currency == 'USD':
            total += float(balance)
        else:
            total += float(balance) * last_high
    module_logger.info('Made a total of {} trades'.format(total_trades))
    module_logger.info('Incurred {:,.2f} on {} feed trades'.format(fees, fee_trades))
    module_logger.info('Total sell balance @ {}: {:,.2f}'.format(last_high, total - fees))
