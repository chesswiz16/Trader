#!/bin/bash

ps aux | grep "python3 start_cost_basis.py config/prod.json LTC-USD &" | grep -v grep > /dev/null
if [ $? != 0 ]
then
    echo "would start LTC"
    #python3 start_cost_basis.py config/prod.json ETH-USD &
fi

ps aux | grep "python3 balance_logger.py config/sandbox.json &" | grep -v grep > /dev/null
if [ $? != 0 ]
then
    python3 python3 balance_logger.py config/sandbox.json &
fi