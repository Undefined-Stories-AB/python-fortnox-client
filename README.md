# Example usage

```python
from fortnox import Client
api = Client(os.environ['DB_CONNECTION_STRING'])

print(str(api.invoices(params=dict(limit=10, page=1, sortorder="descending"))))

print(str(api.accounts(account_number=1000)))
```