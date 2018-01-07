#!/usr/bin/env python

from setuptools import setup, find_packages

install_requires = [
    'bintrees==2.0.7',
    'requests==2.13.0',
    'six==1.10.0',
    'websocket-client==0.40.0',
]

tests_require = [
    'pytest',
]

setup(
    name='gdax-trader',
    version='1.0.0',
    author='Tiger Huang',
    author_email='3wood.tiger@gmail.com',
    packages=find_packages(),
    install_requires=install_requires,
    tests_require=tests_require,
)
