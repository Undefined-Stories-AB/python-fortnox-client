#!/usr/bin/env python
import base64
from typing import Dict
from datetime import datetime, timedelta
from urllib import parse
import json

from pymongo.uri_parser import parse_uri
from ratelimit import limits, sleep_and_retry
import fire
import requests
from pymongo import MongoClient

FORTNOX_API_URL = "https://api.fortnox.se/3/"
FORTNOX_TOKEN_ENDPOINT = "https://apps.fortnox.se/oauth-v1/token"
FORTNOX_TOKEN_EXPIRES_IN__SECONDS = 3600
FORTNOX_MAX_CALLS_PER_MINUTE = 240
ONE_MINUTE_IN_SECONDS = 60


class FortnoxPayload:
    """
    Class for holding Fortnox payload returned from API
    """

    def __init__(self, resource, payload: Dict, pluralize=False):
        self.resource = resource
        self.resource_name = resource.title()
        self.data = payload[self.resource_name]


class ResourceParams:
    """
    Class for holding resource parameters.
    """

    def __init__(self, limit=10, page=1, sortorder="ascending"):
        """
        Initialize the resource parameters with default limit 10, page 1, and sortorder "ascending".
        """
        if sortorder != "ascending" and sortorder != "descending":
            raise ValueError("Invalid param for 'ResourceParams': 'sortorder'")
        self.limit = limit
        self.page = page
        self.sortorder = sortorder


class Client:
    """
    Fortnox Client for fetching resources from Fortnox API.

    Methods:
        invoices(invoice_number=None, params: ResourceParams = None)
        invoicespayments(invoice_number=None, params: ResourceParams = None)
        vouchers(voucher_series, voucher_number=None, params: ResourceParams = None)
    """

    def __init__(
        self, db_connection_string, access_token=None, client_secret=None, request_timeout_in_seconds=60
    ):
        self.access_token = access_token
        self.client_secret = client_secret
        self.request_timeout = request_timeout_in_seconds

        if db_connection_string is None:
            raise ValueError("Required param 'db_connection_string' was not provided .")

        if not db_connection_string.strip():
            raise ValueError("Required param 'db_connection_string' is defined, but it is empty or whitespace only.")

        # Parse the MongoDB URI and remove the database name
        parsed_uri = parse_uri(db_connection_string)
        if parsed_uri['database'] != 'findus':
            raise ValueError(f"Invalid database in database connection string: {parsed_uri['database']}, expected: 'findus'")

        self.db_client = MongoClient(db_connection_string)

        # Check if the database connection is working
        if not self.db_client.server_info():
            raise ConnectionError("Could not connect to the MongoDB server.");

        self.database = self.db_client.get_database()

        # Check if the 'credentials' exists in the database
        if not 'credentials' in self.database.list_collection_names():
            raise ConnectionError("The 'credentials' collection could not be found in the database.")

    @sleep_and_retry
    @limits(calls=FORTNOX_MAX_CALLS_PER_MINUTE, period=ONE_MINUTE_IN_SECONDS)
    def __request(
        self,
        url,
        method,
        data=None,
        params=None,
        access_token=None,
        raise_exception=True,
    ):
        if access_token is None:
            access_token = self.__get_access_token()
        if params:
            url += f"?{parse.urlencode(params)}"
        response = requests.request(
            method,
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=self.request_timeout,
        )
        if raise_exception is True:
            status_code = response.status_code
            try:
                match method:
                    case "GET":
                        if status_code != 200:
                            response.raise_for_status()
                    case "POST":
                        if status_code != 201:
                            response.raise_for_status()
                    case "DELETE":
                        if status_code != 204:
                            response.raise_for_status()
            except Exception as exc:
                print(response.content)

                raise Exception(
                    f"Failed to {method} @ {url}, received unexpected status code: {status_code}"
                ) from exc

        return response

    def __fetch_resources(
        self, resource, resource_number=None, voucher_series=None, params=None
    ):
        voucher_identifier = None

        def xstr(str_or_null):
            return str_or_null or ""

        if resource == "vouchers":
            if not voucher_series[0].isalpha() or not voucher_series[0].isupper():
                raise ValueError("Invalid Series for voucher resource")
            voucher_identifier = f"{voucher_series}/{xstr(resource_number)}"
        url = (
            FORTNOX_API_URL + resource + f"/{xstr(resource_number)}"
            if not voucher_identifier
            else FORTNOX_API_URL + voucher_identifier
        )
        return self.__request(url, "GET", params=params).json()

    def __post_resources(
        self, resource, data, resource_number=None, voucher_series=None, params=None
    ):
        """
        :return: JSON Payload of the created resource(s)
        """
        voucher_identifier = None

        def xstr(str_or_null):
            return str_or_null or ""

        if resource == "vouchers":
            if not voucher_series[0].isalpha() or not voucher_series[0].isupper():
                raise ValueError("Invalid Series for voucher resource")
            voucher_identifier = f"{voucher_series}/{xstr(resource_number)}"
        url = (
            FORTNOX_API_URL + resource + f"/{xstr(resource_number)}"
            if not voucher_identifier
            else FORTNOX_API_URL + voucher_identifier
        )
        return self.__request(url, "POST",data=data, params=params).json()

    def __delete_resource(
        self, resource, resource_number
    ):
        """
        Delete a Fortnox document
        :returns: 204 - No Content ( Empty Body ) on success
                  and Fortnox Error object on failure
        """
        url = (
            FORTNOX_API_URL + resource + f"/{resource_number}"
        )
        return self.__request(url, "DELETE")


    # TODO: params: https://developer.fortnox.se/documentation/resources/financial-years/
    def financialyears(self, financialyear_id=None, params=None):
        """
        :return: JSON Payload containing requested financial year(s)
        :rtype: Dict
        """
        return self.__fetch_resources(
            "financialyears", resource_number=financialyear_id, params=params
        )


    def accounts(self, account_number=None, params=None):
        """
        :return: JSON Payload containing requested account(s)
        :rtype: Dict
        """
        return self.__fetch_resources(
            "accounts", resource_number=account_number, params=params
        )

    def create_article(self, article_number, description,):
        """
        Create and upload a new article.
        """
        article = dict(Article=(dict(ArticleNumber=article_number, Description=description)))
        return self.upload_article(article)


    def upload_article(self, article):
        """
        Upload a new article.
        """
        return self.__post_resources("articles", data=json.dumps(article))

    def upload_customer(self, customer):
        """
        Upload a new customer.
        """
        return self.__post_resources("customers", data=json.dumps(customer))

    def delete_customer(self, customer_number):
        """
        Delete a customer.
        """
        return self.__delete_resource("customers", resource_number=customer_number)

    def upload_invoice(self, invoice):
        """
        Upload a new invoice.
        """
        return self.__post_resources("invoices", data=json.dumps(invoice))

    def invoices(self, invoice_number=None, params=None):
        """
        Fetch invoices with given invoice number and resource parameters.

        :param invoice_number: (optional) the document number of the specific invoice to retrieve
        :type invoice_number: int
        :return: JSON Payload containing requested invoice(s)
        :rtype: Dict
        """
        return self.__fetch_resources(
            "invoices", resource_number=invoice_number, params=params
        )

    def bookkeep_invoice(self, invoice_number):
        """
        Bookkeep an invoice.
        """
        if not isinstance(invoice_number, int):
            raise ValueError
        return self.__request(
            f"{FORTNOX_API_URL}invoices/{invoice_number}/bookkeep", "PUT"
        )

    def invoicepayments(
        self, invoice_payment_number=None, params: ResourceParams = None
    ):
        """
        Fetch invoice payments with given invoice number and resource parameters.

        :param invoice_payment_number: (optional) the document number of the specific invoice to retrieve
        :type invoice_payment_number: int
        :return: JSON Payload containing requested invoice payment(s)
        :rtype: Dict
        """
        return self.__fetch_resources(
            "invoicepayments", resource_number=invoice_payment_number, params=params
        )

    def remove_invoice_payment(self, invoice_payment_number):

        if not isinstance(invoice_payment_number, int):
            raise ValueError
        return self.__request(
            f"{FORTNOX_API_URL}invoicepayments/{invoice_payment_number}", "DELETE"
        )

    def vouchers(
        self, voucher_series, voucher_number=None, params: ResourceParams = None
    ):
        """
        Fetch vouchers with given voucher series and number and resource parameters.

        :param voucher_number: (optional) the document number of the specific invoice to retrieve
        :param voucher_series: the voucher series to retrieve from, should be an uppercase letter.
        :type voucher_number: int
        :type voucher_series: str
        :return: JSON Payload containing requested voucher(s)
        :rtype: Dict
        """
        return self.__fetch_resources(
            "vouchers",
            resource_number=voucher_number,
            voucher_series=voucher_series,
            params=params,
        )

    def upload_voucher(self, voucher):
        return self.__request(
            f"{FORTNOX_API_URL}vouchers", "POST", data=json.dumps(dict(Voucher=voucher))
        )

    def __get_access_token(self):
        """
        Retrieve the access_token for Fortnox Authentication.

        The function will first check if the current token has expired.
        If the token has expired, or fails in call to the 'companyinformation' endpoint.
        The function will then use the 'refresh_token' to get a new access_token.
        If the token is valid, it returns the existing token.

        Returns:
            str: The access token for Fortnox Authentication.

        Raises:
            Exception: If an error occurs while retrieving the access token.
        """

        credentials = self.database.credentials.find_one({"provider": "fortnox"})
        access_token = credentials["accessToken"]
        refresh_token = credentials["refreshToken"]
        client_identity = credentials["clientIdentity"]
        client_secret = credentials["clientSecret"]
        expires_at = credentials["expiresAt"]

        if (
            access_token is None
            or datetime.utcnow() > expires_at
            or self.__request(
                f"{FORTNOX_API_URL}companyinformation",
                "GET",
                access_token=access_token,
                raise_exception=False,
            ).status_code
            != 200
        ):

            auth = base64.b64encode(
                f"{client_identity}:{client_secret}".encode()
            ).decode()
            response = requests.post(
                FORTNOX_TOKEN_ENDPOINT,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth}",
                },
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                timeout=self.request_timeout,
            )

            if response.status_code != 200:
                print(
                    f"Received unexpected status code from fortnox while refreshing token: ${response.status_code} - {response.text}"
                )
                return ""

            json_token = response.json()

            access_token = json_token["access_token"]
            refresh_token = json_token["refresh_token"]
            expires_in = json_token["expires_in"]
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            self.database.credentials.update_one(
                {"provider": "fortnox"},
                {
                    "$set": {
                        "expiresAt": expires_at,
                        "accessToken": access_token,
                        "refreshToken": refresh_token,
                    }
                },
            )

        return access_token


if __name__ == "__main__":
    fire.Fire(Client)
    # Usage:
    #   from fortnox import Client
    #   api = Client(os.environ['DB_CONNECTION_STRING'])
    #   print(str(api.invoices(params=dict(limit=10, page=1, sortorder="descending"))))
    #   print(str(api.accounts(account_number=1000)))
