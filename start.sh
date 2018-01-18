#!/bin/bash

python3 start_cost_basis.py config/prod.json ETH-USD &
python3 balance_logger.py config/prod.json &