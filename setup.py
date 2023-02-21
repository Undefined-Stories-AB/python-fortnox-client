#!/usr/bin/env python
from setuptools import setup

setup(name='fortnox-client',
      version='0.1',
      description='Internal Utility Client for Fortnox API',
      url='http://github.com/Undefined-Stories-AB/python-fortnox-client',
      author='Joaqim Planstedt',
      author_email='git@joaqim.xyz',
      license='MIT',
      packages=['fortnoxclient'],
      python_requires="~=3.10.9",
      install_requires=[
        "pymongo==4.3.3",
        "fire==0.4.0",
        "requests==2.26.0",
        "python-dotenv==0.19.1",
        "ratelimit==2.2.1"
      ],
      zip_safe=False
      )
