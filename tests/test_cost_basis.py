import logging
import unittest
from unittest.mock import Mock

from tests.authenticated_client_mock import AuthenticatedClientMock
from trader.cost_basis import CostBasis

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class TestCostBasis(unittest.TestCase):
    def test_on_order_done(self):
        auth_client_mock = AuthenticatedClientMock()
        auth_client_mock.cancel_order = Mock(side_effect=[''])
        auth_client_mock.cancel_all = Mock()
        trader = CostBasis('ETH-USD', 4, 0.1, auth_client=auth_client_mock)
        trader.available_balance = {
            'ETH': 0.0,
            'USD': 10000,
        }
        trader.orders = {
            'id1': {
                'side': 'buy',
                'size': '10',
                'price': '101.0',
                'type': 'stop',
                'post_only': False,
            },
            'id2': {
                'side': 'buy',
                'size': '10',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.on_order_done({
            'order_id': 'id1',
            'type': 'done',
            'price': '101.0',
            'side': 'buy',
            'reason': 'filled',
            'remaining_size': '0',
        })
        self.assertTrue('id1' not in trader.orders)
        self.assertEquals(trader.current_order_depth, 1)
        self.assertEquals(trader.quote_currency_paid, 10 * 101.0)
        self.assertEquals(trader.base_currency_bought, 10)
        self.assertEquals(len(trader.orders), 2)
        expected = {
            'side': 'sell',
            'size': '10.0',
            'price': '102.01',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        expected = {
            'side': 'buy',
            'size': '9.091909190919093',
            'price': '98.88',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        auth_client_mock.cancel_all.assert_called_once_with()
        auth_client_mock.cancel_order.assert_called_with('id2')

    # TODO More order depth
    # TODO Sell order
    # TODO Over max depth
