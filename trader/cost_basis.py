import json
import logging
import math

from trader.base_trader import AccountBalanceFailure
from trader.base_trader import AlgoStateException
from trader.base_trader import OrderPlacementFailure
from trader.base_trader import Trader

module_logger = logging.getLogger(__name__)


class CostBasisTrader(Trader):
    def __init__(self, product_id, order_depth, wallet_fraction,
                 delta=0.01, auth_client=None, api_key='', secret_key='',
                 pass_phrase='', api_url='', ws_url=''):

        """CostBasis trader. Places a sell at +1% of current cost basis for entire base currency balance
        and a buy which if filled would move current cost basis by delta.
        :param product_id: ETH-USD, BTC-USD, etc.
        :param order_depth: Number of sequential buy orders algo is allowed to execute.
        :param wallet_fraction: Percentage of quote currency (USD) starting wallet balance algo is allowed to use.
        :param delta: Percentage above and below cost basis to place orders.
        use per order.
        """
        Trader.__init__(self,
                        product_id,
                        delta=delta,
                        auth_client=auth_client,
                        api_key=api_key,
                        secret_key=secret_key,
                        pass_phrase=pass_phrase,
                        api_url=api_url,
                        ws_url=ws_url,
                        )

        self.max_order_depth = order_depth
        self.current_order_depth = 0
        # Running total of how much we've bought and how much we've paid for it, updated on order fills
        self.quote_currency_paid = 0.0
        self.base_currency_bought = 0.0
        self.wallet_fraction = wallet_fraction

    def get_order_size(self):
        return self.get_balance(self.quote_currency) * self.wallet_fraction

    def on_start(self):
        """Check outstanding orders, if we don't have 2, then place seeding orders
        [
            {
                "id": "d0c5340b-6d6c-49d9-b567-48c4bfca13d2",
                "price": "0.10000000",
                "size": "0.01000000",
                "product_id": "BTC-USD",
                "side": "buy",
                "stp": "dc",
                "type": "limit",
                "time_in_force": "GTC",
                "post_only": false,
                "created_at": "2016-12-08T20:02:28.53864Z",
                "fill_fees": "0.0000000000000000",
                "filled_size": "0.00000000",
                "executed_value": "0.0000000000000000",
                "status": "open",
                "settled": false
            },
            {
                "id": "8b99b139-58f2-4ab2-8e7a-c11c846e3022",
                "price": "1.00000000",
                "size": "1.00000000",
                "product_id": "BTC-USD",
                "side": "buy",
                "stp": "dc",
                "type": "limit",
                "time_in_force": "GTC",
                "post_only": false,
                "created_at": "2016-12-08T20:01:19.038644Z",
                "fill_fees": "0.0000000000000000",
                "filled_size": "0.00000000",
                "executed_value": "0.0000000000000000",
                "status": "open",
                "settled": false
            }
        ]
        """
        self.current_order_depth = 0
        self.quote_currency_paid = 0.0
        self.base_currency_bought = 0.0
        orders = self.client.get_orders()[0]
        try:
            stop_orders = [x for x in orders if x.get('type', '') == 'stop']
            limit_orders = [x for x in orders if x.get('type', '') == 'limit']
            if len(orders) == 0:
                Trader.seed_wallet(self, self.get_order_size())
            # With two open orders, we either failed right after seeding or in the middle of the algo
            elif len(orders) == 2:
                if len(stop_orders) == 1 and len(limit_orders) == 1:
                    module_logger.info('Recovered with seeding orders')
                elif len(limit_orders) == 2:
                    # Work out what cost basis was from the sell (current sell was 1% above cost basis)
                    sell_orders = [x for x in limit_orders if x.get('side', '') == 'sell']
                    self.reset_from_sell(sell_orders)
                else:
                    raise AlgoStateException('Unexpected order state:{}'.format(orders))
            elif len(orders) == 1:
                sell_orders = [x for x in limit_orders if x.get('side', '') == 'sell']
                buy_orders = [x for x in limit_orders if x.get('side', '') == 'buy']
                if len(sell_orders) == 1:
                    self.reset_from_sell(sell_orders)
                elif len(buy_orders) == 1:
                    # If we only have the buy, cancel it and reseed
                    module_logger.info('Found one open buy order, canceling and reseeding')
                    self.cancel_all()
                    Trader.seed_wallet(self, self.get_order_size())
                else:
                    raise AlgoStateException('Unexpected order state:{}'.format(orders))
            else:
                raise AlgoStateException('Unexpected order state:{}'.format(orders))
        except (OrderPlacementFailure, AccountBalanceFailure) as e:
            module_logger.error('BAILING. Failed to seed wallet, canceling all open orders')
            self.cancel_all()
            raise e
        except AlgoStateException:
            module_logger.warning('Unexpected order state: {}, canceling all and seeding'.format(
                json.dumps(orders, indent=4, sort_keys=True)))
            self.cancel_all()
            Trader.seed_wallet(self, self.get_order_size())

    def reset_from_sell(self, sell_order):
        if len(sell_order) != 1:
            raise AlgoStateException(
                'Unexpected order state:{}'.format(sell_order))
        sell_order = sell_order[0]
        cost_basis = float(sell_order['price']) / (1 + self.delta)
        self.base_currency_bought = float(sell_order['size'])
        self.quote_currency_paid = self.base_currency_bought * cost_basis
        # Guess at the order depth. If my math was better I'm sure we could be more accurate
        self.current_order_depth = math.floor(self.quote_currency_paid / self.get_order_size())
        module_logger.info(
            'Recovered with cost basis: {} ccy bought: {} price paid: {} order depth: {}'.format(
                cost_basis, self.base_currency_bought, self.quote_currency_paid, self.current_order_depth
            ))

    def place_next_orders(self, settled_order):
        """Meat of the logic, place new orders as described in __init__.
        Passed the last filled AND settled order message
        {
            "created_at": "2018-01-17T09:12:05.048469Z",
            "done_at": "2018-01-17T09:32:16.946Z",
            "done_reason": "filled",
            "executed_value": "19.7832704147000000",
            "fill_fees": "0.0000000000000000",
            "filled_size": "0.02039113",
            "id": "ddc06c65-cf94-4f9b-ac7a-1d2e4fdf8164",
            "post_only": true,
            "price": "970.19000000",
            "product_id": "ETH-USD",
            "settled": true,
            "side": "buy",
            "size": "0.02039113",
            "status": "done",
            "stp": "dc",
            "time_in_force": "GTC",
            "type": "limit"
        }
        """
        # Full order fill, cancel other open orders
        self.cancel_all()
        if settled_order['side'] == 'sell':
            # We've fully sold the stack, close current orders and reset at market
            self.on_start()
        else:
            # We've bought some, what's our order depth and cost basis?
            self.current_order_depth += 1
            price = float(settled_order['price'])
            filled_size = float(settled_order['filled_size'])
            self.quote_currency_paid += price * filled_size
            self.base_currency_bought += filled_size
            cost_basis = self.quote_currency_paid / self.base_currency_bought
            module_logger.info(
                'Order Depth: {}, Cost Basis: {} ({}/{}), targeting {}/{}'.format(
                    self.current_order_depth,
                    cost_basis,
                    self.quote_currency_paid,
                    self.base_currency_bought,
                    cost_basis * (1 + self.delta),
                    cost_basis * (1 - self.delta),
                )
            )
            # Place sell at delta above current cost basis
            self.sell_limit_ptc(self.base_currency_bought, cost_basis * (1 + self.delta))
            if self.current_order_depth > self.max_order_depth:
                module_logger.warning('At max order depth, not doing anything (leaving sell out)')
            else:
                # Place buy at price and size to move cost basis down by delta
                next_cost_basis = cost_basis * (1 - self.delta)
                target_base_quantity = (self.quote_currency_paid + self.get_order_size()) / next_cost_basis
                next_size = target_base_quantity - self.base_currency_bought
                self.buy_limit_ptc(next_size, self.get_order_size() / next_size)


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    with open('../config/sandbox.json') as config:
        data = json.load(config)

    trader = CostBasisTrader(
        'BTC-USD',
        data['cost_basis']['order_depth'],
        data['cost_basis']['wallet_fraction'],
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
