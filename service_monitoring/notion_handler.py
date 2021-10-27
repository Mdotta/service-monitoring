import logging
import json
import time
from datetime import datetime, timedelta

import requests
from requests import status_codes
from requests.api import head
from requests.models import Response

from .service import Service


class NotionHandler:
    def __init__(self, base_url, api_token, database_id):
        self.base_url = base_url
        self.api_token = api_token
        self.database_id = database_id

    def get_services_to_monitor(self):
        """
        Chama a API do notion para obter a lista de serviços a serem monitorados
        """
        headers: dict = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2021-08-16",
        }

        response: Response = requests.post(
            f"{self.base_url}/databases/{self.database_id}/query", headers=headers
        )

        if response.status_code == 200:
            json_response: dict = response.json()["results"]
        else:
            print("ERRO: Algo deu errado")
            return

        # print(json_response)
        services: list = []

        for item in json_response:
            service: Service = Service(
                item["id"],
                item["properties"]["URL"]["title"][0]["text"]["content"],
                item["properties"]["Alias"]["rich_text"][0]["text"]["content"],
                item["properties"]["Identifier"]["rich_text"][0]["text"]["content"],
                item["properties"]["Status"]["select"]["name"],
            )
            services.append(service)

        # print(services)
        return services

    def get_status(self, service: Service):
        """
        Responsavel por obter e retornar o status do serviço informado e checar a presença do Identifier no html retornado
        """
        try:
            response: Response = requests.get(service.url)
        except requests.exceptions.SSLError:
            return "Down"

        if response is not None:
            status_code: int = response.status_code
            response_body: str = response.text

            try:
                if (
                    status_code >= 200
                    and status_code < 400
                    and service.identifier.lower() in response_body.lower()
                ):
                    return "Operational"
                elif status_code >= 200 and status_code < 400:
                    return "Doubtful"
                elif status_code >= 400 and status_code < 500:
                    return "Warning"
                elif status_code == 503:
                    return "Maintenance"
                else:
                    return "Down"
            except:
                print("ERRO: Algo deu errado")
                return

    def update_service_status(self, service: Service):
        """
        Essa função atualiza o status do serviço na tabela do notion através da API do notion
        """

        payload: dict = {
            "properties": {
                "Status": {"select": {"name": service.new_status}},
                "Last Update UTC": {
                    "date": {
                        "start": (
                            datetime.utcnow().replace(tzinfo=None) - timedelta(hours=3)
                        ).strftime("%Y-%m-%dT%H:%M:%S")
                    }
                },
            }
        }

        headers: dict = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2021-05-13",
        }

        requests.patch(
            f"{self.base_url}/pages/{service.id}",
            headers=headers,
            data=json.dumps(payload),
        )

    def task_check_service(self, service: Service):
        """
        Essa função é responsável por executar as tasks por serviço de forma assincrona, definida pela pool em main()
        """
        start_time = time.time()
        service.new_status = self.get_status(service)
        self.update_service_status(service)

        logging.info(
            "{} status is {} and has been updated in Notion. Exec time: {}s".format(
                service.url, service.new_status, round(time.time() - start_time)
            )
        )

        return service
