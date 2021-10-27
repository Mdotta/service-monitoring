from postmarker.core import PostmarkClient


class EmailHandler:
    def __init__(self, email_from, email_to, token):
        self.email_from = email_from
        self.email_to = email_to
        self.token = token

    def send_email(self, email_title, email_body):
        try:
            print(f"enviando email para {self.email_to}")
            postmark = PostmarkClient(server_token=self.token)
            postmark.emails.send(
                From=self.email_from,
                To=self.email_to,
                Subject=email_title,
                HtmlBody=email_body,
            )
        except:
            print("Erro ao enviar email")
