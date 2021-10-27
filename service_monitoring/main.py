import logging
import os
import multiprocessing

from dotenv import load_dotenv

from .email_handler import EmailHandler
from .notion_handler import NotionHandler as notion

load_dotenv()

NOTION_API_BASE_URL = 'https://api.notion.com/v1'
NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

POSTMARK_FROM = os.getenv('POSTMARK_FROM')
POSTMARK_TO = os.getenv('POSTMARK_TO')
POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN')

EMAIL_HANDLER = EmailHandler(POSTMARK_FROM,POSTMARK_TO,POSTMARK_API_TOKEN)

MY_NOTION = notion(NOTION_API_BASE_URL,NOTION_API_TOKEN,NOTION_DATABASE_ID)

global SERVICES_WITH_PROBLEM
SERVICES_WITH_PROBLEM = []
SEND_SINGLE_EMAIL = False

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
    logging.info('email enviado')

def proc_check_updated_service(services):
    """
    Proc de callback da pool de checagem de emails criada em main()
    Essa função é chamada ao final da execução da pool assincrona
    """
    services_with_problem = []
    for service in services:
        if  service.new_status != 'Operational' and service.new_status != service.last_status:
            services_with_problem.append(service)
    
    return services_with_problem

def main():
    logging.info('Monitoramento iniciado')
    services:list = MY_NOTION.get_services_to_monitor()

    try:
        with multiprocessing.Pool() as pool:
            r = pool.map_async(MY_NOTION.task_check_service,services,callback=proc_check_updated_service)
            r.wait()
            pool.close()
            pool.join()
    except:
        return

    if len(SERVICES_WITH_PROBLEM) > 0:
        send_alert_email()
    logging.info('finalizado')

if __name__ == '__main__':
    main()