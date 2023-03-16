#!/usr/bin/env python
"""
Utility script to fetch specified Invoice from Fortnox using local 'fortnoxclient' module
"""
import os
import json
import argparse
from fortnoxclient import Client

# use argparse to accept a numerical id of invoice to fetch

def main():
    parser = argparse.ArgumentParser(description='Fetch invoice')
    parser.add_argument('-i', '--invoice', type=int, required=True, help='Invoice ID')

    # get invoice id from parser
    args = parser.parse_args()

    api = Client(os.environ['DB_CONNECTION_STRING'])

    print(json.dumps(api.invoices(invoice_number=args.invoice), indent=4, sort_keys=False))


if __name__ == '__main__':
    main()