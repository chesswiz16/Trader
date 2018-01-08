import unittest
import uuid

from trader.base_trader import Trader
from trader.base_trader import OrderPlacementFailure


class AuthenticatedClientMock(object):
    # noinspection PyMethodMayBeStatic
    def mock_trade(self, side, price, size):
        """Mock failures if quantity > 100"""
        if size > 100:
            return {
                'message': 'mock failure',
            }
        else:
            return {
                'id': str(uuid.uuid4()),
                'price': str(price),
                'size': str(size),
                'side': side,
            }

    def buy(self, **kwargs):
        return self.mock_trade('buy', kwargs['price'], kwargs['size'])

    def sell(self, **kwargs):
        return self.mock_trade('sell', kwargs['price'], kwargs['size'])


class TestTrader(unittest.TestCase):
    def setUp(self):
        self.trader = Trader(AuthenticatedClientMock(), 'BTC-USD', 0.5)

    def test_increment(self):
        self.trader.buy_limit_ptc(50, 100.3)
        expected = {
            'side': 'buy',
            'size': '50',
            'price': '100.5',
        }
        self.assertIn(expected, [{'side': x['side'], 'size': x['size'], 'price': x['price']} for x in
                                 self.trader.orders.values()])
        self.trader.quote_increment = 0.01
        self.trader.buy_limit_ptc(50, 100.03)
        expected = {
            'side': 'buy',
            'size': '50',
            'price': '100.03',
        }
        self.assertIn(expected, [{'side': x['side'], 'size': x['size'], 'price': x['price']} for x in
                                 self.trader.orders.values()])

    def test_good_order(self):
        self.trader.buy_limit_ptc(10, 100)
        self.assertTrue(len(self.trader.orders) == 1)
        self.trader.buy_limit_ptc(10, 200)
        self.assertTrue(len(self.trader.orders) == 2)
        self.trader.sell_limit_ptc(10, 200)
        self.assertTrue(len(self.trader.orders) == 3)

    def test_bad_order(self):
        self.assertRaises(OrderPlacementFailure, self.trader.buy_limit_ptc, 200, 10)
        self.assertRaises(OrderPlacementFailure, self.trader.sell_limit_ptc, 200, 10)


if __name__ == '__main__':
    unittest.main()
