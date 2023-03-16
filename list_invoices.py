#!/usr/bin/env python

from os import environ
from pymongo import MongoClient
from fortnoxclient import Client

"""  Prints out a csv row of the invoice """
def print_invoice(invoice_from_db, invoice):
    order_status = invoice_from_db.get("OrderStatus")
    if (order_status == "completed") and (invoice.get("Credit")):
        order_status = "needs manual verification of refund"

    invoice_nr = invoice.get("DocumentNumber")
    booked = invoice.get("Booked")
    order_id = invoice_from_db["YourOrderNumber"]
    payment_method = invoice_from_db.get("PaymentMethod")

    total_currency = invoice.get("Total")
    currency_rate = invoice.get("CurrencyRate")

    credit_invoice_reference = invoice.get("CreditInvoiceReference")
    if credit_invoice_reference is None:
        credit_invoice_reference = 0

    total_sek = float(total_currency) * float(currency_rate)
    currency = invoice.get("Currency")

    invoice_date = invoice.get("InvoiceDate")
    if (order_status == "completed") and (credit_invoice_reference > 0):
        order_status = "needs manual verification of refund"

    print(
        str(order_id)
        + ","
        + str(invoice_nr)
        + ","
        + str(payment_method)
        + ","
        + str(order_status)
        + ","
        + str(booked)
        + ","
        + str(total_sek)
        + ","
        + str(total_currency)
        + ","
        + str(currency)
        + ","
        + str(currency_rate)
        + ","
        + str(invoice_date)
        + ","
        + str(credit_invoice_reference)
    )

"""
Lists all invoices for hard-coded year, month or day
"""
def main():
    connection_string = environ["DB_CONNECTION_STRING"]
    db_client = MongoClient(connection_string)
    invoices_collection = db_client.findus.invoices
    api = Client(connection_string)

    print(
        "orderId,invoiceNr,paymentMethod,orderStatus," +
        "booked,totalSek,totalCurrency,currency," +
        "currencyRate,invoiceDate,creditInvoiceReference"
    )

    include_year = 2023
    include_month = 1

    for page in range(1, 30):
        for invoice in api.invoices(
            None, params=dict(limit=100, page=page, sortorder="descending")
        )["Invoices"]:
            if invoice:
                invoice_date = invoice.get("InvoiceDate")
                year, month, _date = [int(x) for x in invoice_date.split("-")]
                if year == include_year and month == include_month:
                    invoice_from_db = invoices_collection.find_one(
                        {"DocumentNumber": int(invoice.get("DocumentNumber"))}
                    )
                    if invoice_from_db is not None:
                        print_invoice(invoice_from_db, invoice)


if __name__ == "__main__":
    main()
