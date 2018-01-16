import uuid


class AuthenticatedClientMock(object):
    # noinspection PyMethodMayBeStatic
    def mock_trade(self, side, price, size, order_type, post_only):
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
                'type': order_type,
                'post_only': post_only,
            }

    # noinspection PyMethodMayBeStatic
    def get_products(self):
        return [
            {
                'status': 'online',
                'id': 'BTC-USD',
                'quote_increment': '0.5',
                'base_currency': 'BTC',
                'quote_currency': 'USD',
                'base_min_size': '0.5',
                'base_max_size': '10000',
            },
            {
                'status': 'online',
                'id': 'ETH-USD',
                'quote_increment': '0.01',
                'base_currency': 'ETH',
                'quote_currency': 'USD',
                'base_min_size': '0.01',
                'base_max_size': '100000',
            },
            {
                'status': 'offline',
                'id': 'ETH-EUR',
                'quote_increment': '0.1',
                'base_currency': 'ETH',
                'quote_currency': 'EUR',
                'base_min_size': '0.01',
                'base_max_size': '100000',
            }
        ]

    # noinspection PyMethodMayBeStatic
    def get_orders(self):
        return [[]]

    def buy(self, **kwargs):
        return self.mock_trade('buy', kwargs['price'], kwargs['size'], kwargs['type'], kwargs.get('post_only', False))

    def sell(self, **kwargs):
        return self.mock_trade('sell', kwargs['price'], kwargs['size'], kwargs['type'], kwargs.get('post_only', False))

    # noinspection PyMethodMayBeStatic
    def get_accounts(self):
        return [
            {
                'currency': 'BTC',
                'available': '100000.001',
            },
            {
                'currency': 'USD',
                'available': '100000.001',
            },
            {
                'currency': 'ETH',
                'available': '100000.001',
            },
        ]

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def get_product_ticker(self, product_id):
        return {
            'price': '100'
        }
