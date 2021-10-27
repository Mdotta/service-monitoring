import json
import os
from datetime import datetime, timedelta
import multiprocessing
from multiprocessing.context import Process
import time

import requests
from dotenv import load_dotenv
from requests import status_codes
from requests.api import head
from requests.models import Response
# from twilio.rest import Client

from service import Service
from email_handler import EmailHandler

load_dotenv()

# TWILIO_ACCOUNT_SID = os.getenv('ACCOUNT_SID')
# TWILIO_AUTH_TOKEN = os.getenv('AUTH_TOKEN')
NOTION_API_BASE_URL = 'https://api.notion.com/v1'
NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

POSTMARK_FROM = os.getenv('POSTMARK_FROM')
POSTMARK_TO = os.getenv('POSTMARK_TO')
POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN')

EMAIL_HANDLER = EmailHandler(POSTMARK_FROM,POSTMARK_TO,POSTMARK_API_TOKEN)

global SERVICES_WITH_PROBLEM
SERVICES_WITH_PROBLEM = []
SEND_SINGLE_EMAIL = False


def get_services_to_monitor():
    """
    Chama a API do notion para obter a lista de serviços a serem monitorados
    """
    headers: dict = {
        'Authorization': f'Bearer {NOTION_API_TOKEN}',
        'Content-Type':'application/json',
        'Notion-Version':'2021-08-16'
    }

    response: Response = requests.post(
        f"{NOTION_API_BASE_URL}/databases/{NOTION_DATABASE_ID}/query",headers=headers
    )

    if response.status_code==200:
        json_response: dict = response.json()['results']
    else:
        print("ERRO: Algo deu errado")
        return

    # print(json_response)
    services: list=[]

    for item in json_response:
        service:Service = Service(
            item['id'],
            item['properties']['URL']['title'][0]['text']['content'],
            item['properties']['Alias']['rich_text'][0]['text']['content'],
            item['properties']['Identifier']['rich_text'][0]['text']['content'],
            item['properties']['Status']['select']['name']
        )
        services.append(service)

    # print(services)
    return services

def get_status(service: Service):
    """
    Responsavel por obter e retornar o status do serviço informado e checar a presença do Identifier no html retornado
    """
    try:
        response: Response = requests.get(service.url)
    except requests.exceptions.SSLError:
        return 'Down'

    if response is not None:
        status_code: int = response.status_code
        response_body: str = response.text

        try:
            if status_code >= 200 and status_code < 400 and service.identifier.lower() in response_body.lower():
                return 'Operational'
            elif status_code >= 200 and status_code < 400:
                return 'Doubtful'
            elif status_code >= 400 and status_code < 500:
                return 'Warning'
            elif status_code == 503:
                return 'Maintenance'
            else:
                return 'Down'
        except:
            print("ERRO: Algo deu errado")
            return

def update_service_status(service:Service):
    """
    Essa função atualiza o status do serviço na tabela do notion através da API do notion
    """

    payload:dict = {
        'properties':{
            'Status':{
                'select':{
                    'name':service.new_status
                }
            },
            'Last Update UTC':{
                'date':{
                    'start':(datetime.utcnow().replace(tzinfo=None) - timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%S')
                }
            }
        }
    }

    headers: dict = {
        'Authorization': f'Bearer {NOTION_API_TOKEN}',
        'Content-Type':'application/json',
        'Notion-Version':'2021-05-13'
    }

    requests.patch(
        f'{NOTION_API_BASE_URL}/pages/{service.id}',
        headers = headers,
        data = json.dumps(payload)
    )

def send_alert_email():
    """
    essa função é responsável pelo envio de email no caso de serviços indisponiveis
    """
    if SEND_SINGLE_EMAIL:
        email_body = ''
        for service in SERVICES_WITH_PROBLEM:
            email_body+= f'{service.alias}, '
    
        EMAIL_HANDLER.send_email('Ambiente com problemas',email_body)
    else:
        for service in SERVICES_WITH_PROBLEM:
            email_body = f'{service.alias} foi de {service.last_status} para {service.new_status}'
            EMAIL_HANDLER.send_email(f'{service.alias} com problemas',email_body)

def task_check_service(service:Service):
    """
    Essa função é responsável por executar as tasks por serviço de forma assincrona, definida pela pool em main()
    """
    start_time = time.time()
    service.new_status = get_status(service)
    update_service_status(service)
    
    print("{} status is {} and has been updated in Notion. Exec time: {}s".format(service.url,service.new_status,round(time.time()-start_time)))
    
    return service

def proc_check_updated_service(services):
    """
    Proc de callback da pool de checagem de emails criada em main()
    Essa função é chamada ao final da execução da pool assincrona
    """

    for service in services:
        if  service.new_status != 'Operational' and service.new_status != service.last_status:
            SERVICES_WITH_PROBLEM.append(service)

def main():
    
    services:list = get_services_to_monitor()

    try:
        with multiprocessing.Pool() as pool:
            r = pool.map_async(task_check_service,services,callback=proc_check_updated_service)
            r.wait()
            pool.close()
            pool.join()
    except:
        return

    if len(SERVICES_WITH_PROBLEM) > 0:
        send_alert_email()

    print("finalizado")
    
if __name__ == '__main__':
    main()