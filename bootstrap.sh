#!/bin/sh

virtualenv env
env/bin/pip install -e .
env/bin/pip install -r devrequirements.txt
env/bin/py.test
