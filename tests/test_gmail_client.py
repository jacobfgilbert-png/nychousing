from app.gmail_client import RealGmailClient


class _Execute:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Messages:
    def __init__(self):
        self.list_calls = 0
        self.get_calls = []

    def list(self, **kwargs):
        self.list_calls += 1
        if self.list_calls == 1:
            return _Execute({"messages": [{"id": "a"}], "nextPageToken": "next"})
        return _Execute({"messages": [{"id": "b"}]})

    def get(self, **kwargs):
        self.get_calls.append(kwargs["id"])
        return _Execute(
            {
                "id": kwargs["id"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "alerts@example.com"},
                        {"name": "Subject", "value": "Furnished room"},
                    ],
                    "body": {"data": "RnVybmlzaGVkIHJvb20gYXZhaWxhYmxl"},
                },
            }
        )


class _Users:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class _Service:
    def __init__(self):
        self.messages = _Messages()

    def users(self):
        return _Users(self.messages)


def test_real_gmail_client_paginates_without_duplicate_fetches():
    service = _Service()
    client = object.__new__(RealGmailClient)
    client.service = service

    messages = client.fetch_messages(["sublet"], max_messages_per_query=500)

    assert [message.raw_source_id for message in messages] == ["a", "b"]
    assert service.messages.list_calls == 2
    assert service.messages.get_calls == ["a", "b"]
