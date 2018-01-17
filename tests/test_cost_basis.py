import logging
import unittest
from unittest.mock import Mock, MagicMock

from tests.authenticated_client_mock import AuthenticatedClientMock
from trader.cost_basis import CostBasisTrader

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class TestCostBasis(unittest.TestCase):
    def test_on_order_done(self):
        auth_client_mock = AuthenticatedClientMock()
        auth_client_mock.cancel_order = MagicMock(return_value={})
        auth_client_mock.cancel_all = Mock()
        auth_client_mock.get_product_ticker = MagicMock(return_value={
            'price': '100',
        })
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        trader.available_balance = {
            'ETH': 0.0,
            'USD': 10000,
        }
        trader.on_start()
        # Get limit order and mock it's been filled
        stop_order = [x for x in trader.orders.values() if x['type'] == 'stop'][0]
        limit_order = [x for x in trader.orders.values() if x['type'] == 'limit'][0]
        self.assertEqual(len(trader.orders), 2)
        available_balance = trader.get_balance('USD')
        self.assertEqual(available_balance, 8000)
        trader.on_order_fill({
            'maker_order_id': limit_order['id'],
            'taker_order_id': '',
            'type': 'match',
            'price': limit_order['price'],
            'side': 'buy',
            'size': limit_order['size'],
        })
        self.assertTrue(limit_order['id'] not in trader.orders)
        self.assertEqual(trader.current_order_depth, 1)
        self.assertEqual(trader.quote_currency_paid, 10 * 99.0)
        self.assertEqual(trader.base_currency_bought, 10)
        self.assertEqual(len(trader.orders), 2)
        expected = {
            'side': 'sell',
            'size': '10.0',
            'price': '99.99',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        expected = {
            'side': 'buy',
            'size': '9.2939496',
            'price': '96.94',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        self.assertAlmostEqual(
            trader.get_balance('USD'),
            available_balance +
            float(stop_order['size']) * float(stop_order['price']) -
            float(expected['size']) * float(expected['price']),
            places=2,
        )
        auth_client_mock.cancel_order.assert_called_with(stop_order['id'])

        # Get the buy order and mock that it's filled
        buy_order = [x for x in trader.orders.values() if x['side'] == 'buy'][0]
        sell_order = [x for x in trader.orders.values() if x['side'] == 'sell'][0]
        available_balance = trader.get_balance('USD')
        trader.on_order_fill({
            'maker_order_id': buy_order['id'],
            'taker_order_id': '',
            'type': 'match',
            'price': buy_order['price'],
            'side': 'buy',
            'size': buy_order['size'],
        })
        self.assertTrue(buy_order['id'] not in trader.orders)
        self.assertEqual(trader.current_order_depth, 2)
        self.assertEqual(trader.quote_currency_paid, 1890.9554742239998)
        self.assertEqual(trader.base_currency_bought, 19.2939496)
        self.assertEqual(len(trader.orders), 2)
        expected = {
            'side': 'sell',
            'size': '19.2939496',
            'price': '98.99',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        expected = {
            'side': 'buy',
            'size': '8.55234412',
            'price': '94.82',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        self.assertAlmostEqual(
            trader.get_balance('USD'),
            available_balance -
            float(expected['size']) * float(expected['price']),
            places=2,
        )
        auth_client_mock.cancel_order.assert_called_with(sell_order['id'])

        # 3 deep now, mock a partial fill
        buy_order = [x for x in trader.orders.values() if x['side'] == 'buy'][0]
        sell_order = [x for x in trader.orders.values() if x['side'] == 'sell'][0]
        available_balance = trader.get_balance('USD')
        trader.on_order_fill({
            'maker_order_id': buy_order['id'],
            'taker_order_id': '',
            'type': 'match',
            'price': buy_order['price'],
            'side': 'buy',
            'size': str(float(buy_order['size']) - 1),
        })
        self.assertEqual(trader.current_order_depth, 2)
        self.assertEqual(trader.quote_currency_paid, 1890.9554742239998)
        self.assertEqual(trader.base_currency_bought, 19.2939496)
        self.assertEqual(
            float(trader.orders[buy_order['id']]['size']) - float(trader.orders[buy_order['id']]['filled_size']), 1)
        trader.on_order_fill({
            'maker_order_id': buy_order['id'],
            'taker_order_id': '',
            'type': 'match',
            'price': buy_order['price'],
            'side': 'buy',
            'size': '1',
        })
        self.assertTrue(buy_order['id'] not in trader.orders)
        self.assertEqual(trader.current_order_depth, 3)
        self.assertEqual(trader.quote_currency_paid, 2701.8887436823998)
        self.assertEqual(trader.base_currency_bought, 27.84629372)
        self.assertEqual(len(trader.orders), 2)
        expected = {
            'side': 'sell',
            'size': '27.84629372',
            'price': '98.0',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        expected = {
            'side': 'buy',
            'size': '7.87885336',
            'price': '92.63',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        self.assertAlmostEqual(
            trader.get_balance('USD'),
            available_balance -
            float(expected['size']) * float(expected['price']),
            places=2,
        )
        auth_client_mock.cancel_order.assert_called_with(sell_order['id'])

        # 4 deep, sell should go out but no buy
        buy_order = [x for x in trader.orders.values() if x['side'] == 'buy'][0]
        sell_order = [x for x in trader.orders.values() if x['side'] == 'sell'][0]
        available_balance = trader.get_balance('USD')
        # Pretend we're taker this time
        trader.on_order_fill({
            'maker_order_id': '',
            'taker_order_id': buy_order['id'],
            'type': 'match',
            'price': buy_order['price'],
            'side': 'sell',
            'size': buy_order['size'],
        })
        self.assertTrue(buy_order['id'] not in trader.orders)
        self.assertEqual(trader.current_order_depth, 4)
        self.assertEqual(trader.quote_currency_paid, 3431.7069304191996)
        self.assertEqual(trader.base_currency_bought, 35.72514708)
        self.assertEqual(len(trader.orders), 1)
        expected = {
            'side': 'sell',
            'size': '35.72514708',
            'price': '97.02',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        self.assertAlmostEqual(trader.get_balance('USD'), available_balance)
        auth_client_mock.cancel_order.assert_called_with(sell_order['id'])

        # Sell comes in, should reset the cost basis to market
        sell_order = [x for x in trader.orders.values() if x['side'] == 'sell'][0]
        trader.on_order_fill({
            'maker_order_id': sell_order['id'],
            'taker_order_id': '',
            'type': 'match',
            'price': sell_order['price'],
            'side': 'sell',
            'size': sell_order['size'],
        })
        self.assertTrue(sell_order['id'] not in trader.orders)
        self.assertEqual(trader.current_order_depth, 0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(len(trader.orders), 2)
        expected = {
            'side': 'buy',
            'size': '10.03434',
            'price': '101.0',
            'type': 'stop',
            'post_only': False,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        expected = {
            'side': 'buy',
            'size': '10.03434',
            'price': '99.0',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in trader.orders.values()])
        wallet_value = trader.get_balance('USD')
        for order in trader.orders.values():
            wallet_value += float(order['size']) * float(order['price'])
        # Make sure we actually made money...
        self.assertGreater(wallet_value, 10000)

    def test_recovery(self):
        auth_client_mock = AuthenticatedClientMock()
        auth_client_mock.get_accounts = MagicMock(return_value=[
            {
                'currency': 'ETH',
                'available': '0',
            },
            {
                'currency': 'USD',
                'available': '10000',
            },
        ])
        auth_client_mock.cancel_order = MagicMock(return_value={})
        auth_client_mock.cancel_all = Mock()
        auth_client_mock.get_product_ticker = MagicMock(return_value={
            'price': '100',
        })
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        trader.on_start()
        self.assertTrue(len(trader.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)

        # Has seeding orders, assert orders are the same
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = {
            'id1': {
                'side': 'buy',
                'size': '20',
                'price': '101.0',
                'type': 'stop',
                'post_only': False,
            },
            'id2': {
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.orders = orders
        trader.on_start()
        self.assertTrue(len(trader.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)
        self.assertEqual(trader.orders, orders)

        # Has limit buy and sell, pick up where we were
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = {
            'id1': {
                'side': 'sell',
                'size': '20',
                'price': '101.0',
                'type': 'limit',
                'post_only': True,
            },
            'id2': {
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.orders = orders
        trader.on_start()
        self.assertTrue(len(trader.orders), 2)
        self.assertEqual(trader.base_currency_bought, 20)
        self.assertEqual(trader.quote_currency_paid, 20 * 100)
        self.assertEqual(trader.current_order_depth, 2)
        self.assertEqual(trader.orders, orders)

        # Has limit sell, pick up where we were
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = {
            'id1': {
                'side': 'sell',
                'size': '20',
                'price': '101.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.orders = orders
        trader.on_start()
        self.assertTrue(len(trader.orders), 2)
        self.assertEqual(trader.base_currency_bought, 20)
        self.assertEqual(trader.quote_currency_paid, 20 * 100)
        self.assertEqual(trader.current_order_depth, 2)
        self.assertEqual(trader.orders, orders)

        # Only has buy, reset
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = {
            'id2': {
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.orders = orders
        trader.on_start()
        self.assertTrue(len(trader.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)

        # Weird order state, resets status
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = {
            'id1': {
                'side': 'sell',
                'size': '20',
                'price': '101.0',
                'type': 'limit',
                'post_only': True,
            },
            'id2': {
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
            'id3': {
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.orders = orders
        self.assertTrue(len(trader.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)
