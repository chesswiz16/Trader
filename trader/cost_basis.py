import json
import logging

from trader.base_trader import AccountBalanceFailure
from trader.base_trader import OrderPlacementFailure
from trader.base_trader import Trader

module_logger = logging.getLogger(__name__)


class CostBasis(Trader):
    def __init__(self, client, product_id, order_depth, wallet_fraction):
        """CostBasis trader. Places a sell at +1% of current cost basis for entire base currency balance
        and a buy which if filled would move current cost basis by -1%.
        :param client: AuthenticatedClient which has been initialized to be able to query wallet balance
        and place orders.
        :param product_id: ETH-USD, BTC-USD, etc.
        :param order_depth: Number of sequential buy orders algo is allowed to execute.
        :param wallet_fraction: Percentage of quote currency (USD) wallet balance algo is allowed to
        use per order. This is intentionally decaying as more buy orders are placed.
        """
        Trader.__init__(self, client, product_id)
        self.max_order_depth = order_depth
        self.wallet_fraction = wallet_fraction

        # TODO: Need to figure out how to recover on unexpected error
        self.current_order_depth = 0
        self.quote_currency_paid = 0.0

    def on_start(self):
        """Check outstanding orders, if we don't have 2, then place seeding orders
        """
        if len(self.orders) == 0:
            try:
                Trader.seed_wallet(self, self.wallet_fraction * self.get_balance(self.quote_currency))
            except (OrderPlacementFailure, AccountBalanceFailure):
                module_logger.warning('Failed to seed wallet, canceling all open orders')
                self.cancel_all()
        # TODO: Need to figure out how to recover on unexpected error


if __name__ == '__main__':
    from gdax.authenticated_client import AuthenticatedClient

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    with open('../config/sandbox.json') as config:
        data = json.load(config)

    auth_client = AuthenticatedClient(
        data['auth']['key'],
        data['auth']['secret'],
        data['auth']['phrase'],
        api_url=data['endpoints']['rest'],
    )

    trader = CostBasis(auth_client, 'BTC-USD', data['cost_basis']['order_depth'], data['cost_basis']['wallet_fraction'])
    trader.on_start()
