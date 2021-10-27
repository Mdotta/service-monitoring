import requests
from requests import status_codes
from requests.api import head
from requests.models import Response

class Service:
    def __init__(self,id,url,alias,identifier,last_status):
        self.id = id
        self.url = url
        self.alias = alias
        self.identifier = identifier
        self.last_status = last_status
        self.new_status = ''

    