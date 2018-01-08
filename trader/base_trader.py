import logging

module_logger = logging.getLogger(__name__)


class Trader(object):
    def __init__(self, client, product_id):
        self.client = client
        self.product_id = product_id
        # Query for product and find status/increment
        products = self.client.get_products()
        product = [x for x in products if x['status'] == 'online' and x['id'] == product_id]
        if len(product) != 1:
            module_logger.error('Product {} invalid from products {}'.format(product_id, json.dumps(products, indent=4,
                                                                                                    sort_keys=True)))
            raise ProductDefinitionFailure(product_id + ' not active for trading')
        self.quote_increment = product[0]['quote_increment']
        # Query for current open orders
        orders = self.client.get_orders()[0]
        self.orders = dict(zip([x['id'] for x in orders], orders))
        module_logger.info(
            'Started trader on {} with increment {} and {} open orders'.format(product_id, self.quote_increment,
                                                                               len(self.orders)))

    # on_start
    # on_fill
    # Check account balance before order

    def buy_limit_ptc(self, size, price):
        """Post only limit buy"""
        result = self.client.buy(type='limit',
                                 product_id=self.product_id,
                                 price=self.to_increment(price),
                                 size=size,
                                 post_only=True)
        if 'message' in result:
            module_logger.exception('Error placing buy order, message from api: {}'.format(result['message']))
            raise OrderPlacementFailure(result['message'])
        else:
            self.orders[result['id']] = result
        module_logger.info('Placed buy order for {} {} @ {}'.format(size, self.product_id, price))

    def sell_limit_ptc(self, size, price):
        """Post only limit sell"""
        result = self.client.sell(type='limit',
                                  product_id=self.product_id,
                                  price=self.to_increment(price),
                                  size=size,
                                  post_only=True)
        if 'message' in result:
            module_logger.exception('Error placing sell order, message from api: {}'.format(result['message']))
            raise OrderPlacementFailure(result['message'])
        else:
            self.orders[result['id']] = result
            module_logger.info('Placed sell order for {} {} @ {}'.format(size, self.product_id, price))

    def to_increment(self, price):
        diff = price - round(price)
        increments = round(diff / self.quote_increment)
        return round(price) + (increments * self.quote_increment)


class OrderPlacementFailure(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


class ProductDefinitionFailure(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


if __name__ == '__main__':
    import json
    from gdax.authenticated_client import AuthenticatedClient

    with open('../config/sandbox.json') as config:
        data = json.load(config)

    auth_client = AuthenticatedClient(data["auth"]["key"],
                                      data["auth"]["secret"],
                                      data["auth"]["phrase"],
                                      api_url=data["endpoints"]["rest"])
    t = Trader(auth_client, 'BTC-USD')
    # t.buy_limit_ptc(1, 100.001)
    res = auth_client.get_products()
    print(json.dumps(res, indent=4, sort_keys=True))
    res = auth_client.get_orders()
    print(json.dumps(res, indent=4, sort_keys=True))
