#!/bin/bash

retry() {
    local -r cmd="python3 start_cost_basis.py config/prod.json"
    local -i attempt_num=1

    until $cmd
    do
        echo "Attempt $attempt_num failed! Trying again in $attempt_num seconds..."
        sleep $(( attempt_num++ ))
    done
}

retry
