#!/usr/bin/env python
from setuptools import find_packages, Command


setup_params = dict(
    name='bugimporters',
    version=0.1,
    author='Various contributers to the OpenHatch project, Berry Phillips',
    author_email='all@openhatch.org, berryphillips@gmail.com',
    packages=find_packages(),
    description='Bug importers for the OpenHatch project',
    install_requires=[
        'gdata',
        'lxml',
        'pyopenssl',
        'unicodecsv',
        'feedparser',
        'twisted',
        'python-dateutil',
        'decorator',
        'scrapy>0.9',
        'argparse',
        'mock',
        'PyYAML',
        'importlib',
        'autoresponse>=0.2',
    ],
)


if __name__ == '__main__':
    from setuptools import setup
    setup(**setup_params)
