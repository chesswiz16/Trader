import json
import logging
import math

from trader.base_trader import AccountBalanceFailure
from trader.base_trader import OrderPlacementFailure
from trader.base_trader import Trader

module_logger = logging.getLogger(__name__)


class CostBasisTrader(Trader):
    def __init__(self, product_id, order_depth, wallet_fraction, auth_client=None, api_key='', secret_key='',
                 pass_phrase='', api_url='', ws_url=''):

        """CostBasis trader. Places a sell at +1% of current cost basis for entire base currency balance
        and a buy which if filled would move current cost basis by -1%.
        :param auth_client: AuthenticatedClient which has been initialized to be able to query wallet balance
        and place orders.
        :param product_id: ETH-USD, BTC-USD, etc.
        :param order_depth: Number of sequential buy orders algo is allowed to execute.
        :param wallet_fraction: Percentage of quote currency (USD) wallet balance algo is allowed to
        use per order. This is intentionally decaying as more buy orders are placed.
        """
        Trader.__init__(self,
                        product_id,
                        auth_client=auth_client,
                        api_key=api_key,
                        secret_key=secret_key,
                        pass_phrase=pass_phrase,
                        api_url=api_url,
                        ws_url=ws_url,
                        )
        self.max_order_depth = order_depth
        self.wallet_fraction = wallet_fraction
        self.current_order_depth = 0
        # Running total of how much we've bought and how much we've paid for it, updated on order fills
        self.quote_currency_paid = 0.0
        self.base_currency_bought = 0.0

    def on_start(self):
        """Check outstanding orders, if we don't have 2, then place seeding orders
        """
        self.current_order_depth = 0
        self.quote_currency_paid = 0.0
        self.base_currency_bought = 0.0
        try:
            stop_orders = [x for x in self.orders.values() if x.get('type', '') == 'stop']
            limit_orders = [x for x in self.orders.values() if x.get('type', '') == 'limit']
            if len(self.orders) == 0:
                Trader.seed_wallet(self, self.wallet_fraction * self.get_balance(self.quote_currency))
            # With two open orders, we either failed right after seeding or in the middle of the algo
            elif len(self.orders) == 2:
                if len(stop_orders) == 1 and len(limit_orders) == 1:
                    module_logger.info('Recovered with seeding orders')
                elif len(limit_orders) == 2:
                    # Work out what cost basis was from the sell (current sell was 1% above cost basis)
                    sell_orders = [x for x in limit_orders if x.get('side', '') == 'sell']
                    self.reset_from_sell(sell_orders)
                else:
                    raise AlgoStateException('Unexpected order state:{}'.format(self.orders))
            elif len(self.orders) == 1:
                sell_orders = [x for x in limit_orders if x.get('side', '') == 'sell']
                buy_orders = [x for x in limit_orders if x.get('side', '') == 'buy']
                if len(sell_orders) == 1:
                    self.reset_from_sell(sell_orders)
                elif len(buy_orders) == 1:
                    # If we only have the buy, cancel it and reseed
                    module_logger.info('Found one open buy order, canceling and reseeding')
                    self.cancel_all()
                    Trader.seed_wallet(self, self.wallet_fraction * self.get_balance(self.quote_currency))
                else:
                    raise AlgoStateException('Unexpected order state:{}'.format(self.orders))
            else:
                raise AlgoStateException('Unexpected order state:{}'.format(self.orders))
        except (OrderPlacementFailure, AccountBalanceFailure) as e:
            module_logger.error('BAILING. Failed to seed wallet, canceling all open orders')
            self.cancel_all()
            raise e
        except AlgoStateException:
            module_logger.warning('Unexpected order state: {}, canceling all and seeding'.format(
                json.dumps(self.orders, indent=4, sort_keys=True)))
            self.cancel_all()
            Trader.seed_wallet(self, self.wallet_fraction * self.get_balance(self.quote_currency))

    def reset_from_sell(self, sell_order):
        if len(sell_order) != 1:
            raise AlgoStateException(
                'Unexpected order state:{}'.format(json.dumps(self.orders, indent=4, sort_keys=True)))
        sell_order = sell_order[0]
        cost_basis = float(sell_order['price']) / 1.01
        self.base_currency_bought = float(sell_order['size'])
        self.quote_currency_paid = self.base_currency_bought * cost_basis
        # Guess at the order depth. If my math was better I'm sure we could be more accurate
        self.current_order_depth = math.floor(
            self.quote_currency_paid / (self.available_balance[self.quote_currency] * self.wallet_fraction))
        module_logger.info(
            'Recovered with cost basis: {} ccy bought: {} price paid: {} order depth: {}'.format(
                cost_basis, self.base_currency_bought, self.quote_currency_paid, self.current_order_depth
            ))

    def on_order_fill(self, message):
        """Actual meat of the logic. On order fill, determine where to place new orders
        """
        checked_message = Trader.on_order_fill(self, message)
        if checked_message:
            side = checked_message['side']
            price = float(checked_message['price'])
            size = float(checked_message['size'])
            filled = float(checked_message['filled_size'])
            # Wait for partial order fills to be fully filled
            if size - filled <= 0.000000001:
                # Full order fill, cancel other open orders
                self.cancel_all()
                if side == 'sell':
                    # We've fully sold the stack, close current orders and reset at market
                    self.on_start()
                else:
                    # We've bought some, what's our order depth and cost basis?
                    self.current_order_depth += 1
                    self.quote_currency_paid += price * size
                    self.base_currency_bought += size
                    cost_basis = self.quote_currency_paid / self.base_currency_bought
                    module_logger.info(
                        'Order Depth: {}, Cost Basis: {} ({}/{}), targeting {}/{}'.format(
                            self.current_order_depth,
                            cost_basis,
                            self.quote_currency_paid,
                            self.base_currency_bought,
                            cost_basis * 1.01,
                            cost_basis * 0.99,
                        )
                    )
                    # Place sell at 1% above current cost basis
                    self.sell_limit_ptc(self.base_currency_bought, cost_basis * 1.01)
                    if self.current_order_depth > self.max_order_depth:
                        module_logger.warning('At max order depth, not doing anything (leaving sell out)')
                    else:
                        # Place buy at price and size to move cost basis down by 1%
                        next_cost_basis = cost_basis * 0.99
                        next_quote_size = self.wallet_fraction * self.get_balance(self.quote_currency)
                        target_base_quantity = (self.quote_currency_paid + next_quote_size) / next_cost_basis
                        next_size = target_base_quantity - self.base_currency_bought
                        self.buy_limit_ptc(next_size, next_quote_size / next_size)


class AlgoStateException(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


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
    trader.on_start()
