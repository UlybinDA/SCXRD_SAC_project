from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging
from django.urls import reverse
from celery import shared_task
from application.models import Application
from django.db.models import Q, Case, When, Value, BooleanField
from django.core.mail import EmailMultiAlternatives
from ccu_project.settings import SITE_NAME
from django.core.mail.backends.smtp import EmailBackend
import smtplib
from email.utils import parseaddr
from email import message_from_string
import io
from django.core.mail import get_connection

logger = logging.getLogger(__name__)


class LoggingEmailBackend(EmailBackend):
    """
    Custom email backend with comprehensive logging for debugging email issues.

    Extends Django's SMTP EmailBackend to add detailed logging of email content,
    headers, and SMTP communication for troubleshooting email delivery problems.

    Attributes:
        Inherits all attributes from EmailBackend.
    """

    def send_messages(self, email_messages):
        """
        Send email messages with logging and connection management.

        Overrides the base method to add detailed logging before sending
        and proper connection lifecycle management.

        Args:
            email_messages (list): List of EmailMessage instances to send.

        Returns:
            int: Number of successfully sent messages.
        """
        if not email_messages:
            return 0

        with self._lock:
            new_conn_created = self.open()
            if not self.connection or new_conn_created is None:
                logger.error("SMTP соединение не установлено")
                return 0

            num_sent = 0
            try:
                for message in email_messages:
                    self._log_email_details(message)
                    sent = self._send(message)
                    if sent:
                        num_sent += 1
            finally:
                if new_conn_created:
                    self.close()

            return num_sent

    def _log_email_details(self, message):
        """
        Log comprehensive details of an email message for debugging.

        Records sender, recipients, subject, content type, headers, and
        message body content to aid in troubleshooting email issues.

        Args:
            message (EmailMessage): The email message to log.
        """
        try:
            logger.debug("=== ДЕТАЛИ EMAIL СООБЩЕНИЯ ===")
            logger.debug(f"From: {message.from_email}")
            logger.debug(f"To: {message.to}")
            logger.debug(f"Cc: {message.cc}")
            logger.debug(f"Bcc: {message.bcc}")
            logger.debug(f"Subject: {message.subject}")
            logger.debug(f"Content type: {getattr(message, 'content_subtype', 'plain')}")


            logger.debug("--- Заголовки ---")
            for key, value in message.extra_headers.items():
                logger.debug(f"{key}: {value}")


            logger.debug("--- Тело сообщения ---")
            if hasattr(message, 'body'):
                logger.debug(f"Body: {message.body}")
            if hasattr(message, 'alternatives') and message.alternatives:
                for alt in message.alternatives:
                    logger.debug(f"Alternative ({alt[1]}): {alt[0][:500]}...")

            logger.debug("=== КОНЕЦ ДЕТАЛЕЙ EMAIL ===")

        except Exception as e:
            logger.error(f"Ошибка при логировании деталей email: {e}")

    def _send(self, email_message):
        """
        Send an individual email message with SMTP protocol logging.

        Enables SMTP debug logging and captures raw SMTP communication
        for detailed troubleshooting of email delivery issues.

        Args:
            email_message (EmailMessage): The email message to send.

        Returns:
            bool: True if sent successfully, False otherwise.

        Raises:
            Exception: Any exception from the underlying SMTP send operation.
        """
        try:

            if self.connection:
                self.connection.set_debuglevel(1)





            if not email_message.recipients():
                return False

            encoding = email_message.encoding or settings.DEFAULT_CHARSET
            from_email = email_message.from_email


            msg = email_message.message()


            logger.debug("=== СЫРОЕ SMTP СООБЩЕНИЕ ===")
            string_io = io.StringIO()
            for line in msg.as_string().splitlines():
                logger.debug(f"SMTP> {line}")
                string_io.write(line + "\n")
            raw_message = string_io.getvalue()
            logger.debug("=== КОНЕЦ СЫРОГО SMTP СООБЩЕНИЯ ===")


            return super()._send(email_message)

        except Exception as e:
            logger.error(f"Ошибка при отправке SMTP: {e}")
            raise


@shared_task
def send_email_task(subject, plain_message, from_email, recipient_list, html_message=None):
    """
    Celery task for asynchronous email sending with comprehensive logging.

    Handles both HTML and plain text email sending through a custom logging
    backend for reliable delivery with detailed error reporting.

    Args:
        subject (str): Email subject line.
        plain_message (str): Plain text version of the email body.
        from_email (str): Sender email address.
        recipient_list (list): List of recipient email addresses.
        html_message (str, optional): HTML version of the email body.

    Returns:
        int: Number of successfully sent emails.

    Raises:
        smtplib.SMTPException: For SMTP-specific delivery errors.
        Exception: For general email sending errors.
    """
    try:
        logger.info(f"Начинаем отправку email: {subject} -> {recipient_list}")


        backend = LoggingEmailBackend()

        if html_message:
            msg = EmailMessage(
                subject,
                html_message,
                from_email,
                recipient_list
            )
            msg.content_subtype = "html"


            logger.debug("=== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ===")
            logger.debug(f"HTML сообщение: {html_message[:500]}...")
            logger.debug("================================")


            result = backend.send_messages([msg])
        else:

            connection = LoggingEmailBackend()

            result = send_mail(
                subject=subject,
                message=plain_message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
                connection=connection
            )


            logger.debug("=== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ===")
            logger.debug(f"Plain text сообщение: {plain_message[:500]}...")
            logger.debug("================================")

        logger.info(f"Email отправлен успешно. Результат: {result} получателям: {recipient_list}")
        return result

    except smtplib.SMTPException as e:
        logger.error(f"SMTP ошибка отправки email: {str(e)}")
        logger.error(f"Код ошибки: {getattr(e, 'smtp_code', 'N/A')}")
        logger.error(f"Сообщение ошибки: {getattr(e, 'smtp_error', 'N/A')}")
        raise
    except Exception as e:
        logger.error(f"Общая ошибка отправки email: {str(e)}", exc_info=True)
        raise


class EmailService:
    """
    Service class for sending various types of application-related emails.

    Provides static methods for generating and sending standardized email
    notifications for application status changes, data publication, and
    sample return reminders.
    """

    @staticmethod
    def _prepare_plain_status_message(application, status, application_url):
        """
        Generate standardized plain text message for application status emails.

        Args:
            application (Application): The application instance.
            status (str): Status description in Russian (e.g., 'выполнена', 'отклонена').
            application_url (str): Full URL to the application detail page.

        Returns:
            str: Formatted plain text email message.
        """
        return f"""
            Уважаемый пользователь {application.client.get_full_name()},

            Ваша заявка #{application.sample_code} была {status}.

            Детали заявки:
            - Код образца: {application.sample_code}
            - Состав: {application.composition}
            - Дата создания: {application.date.strftime('%d.%m.%Y')}
            - Статус: {application.get_status_display()}

            Просмотреть детали заявки: {application_url}

            С уважением,
            Команда {settings.SITE_NAME}
            """

    @staticmethod
    def send_application_completed_email(application):
        """
        Send notification email when an application is completed.

        Args:
            application (Application): The completed application instance.

        Returns:
            bool: True if email task was successfully queued.
        """
        subject = f'Ваша заявка #{application.sample_code} выполнена'
        application_url = settings.SITE_URL + reverse('application_detail',
                                                      kwargs={'application_code': application.application_code})
        application_url = prepare_url(application_url)

        html_message = render_to_string('emails/complete_app.html', {
            'application': application,
            'user': application.client,
            'application_url': application_url,
            'site_name': settings.SITE_NAME
        })

        plain_message = EmailService._prepare_plain_status_message(application, 'выполнена', application_url)

        send_email_task.delay(
            subject=subject,
            plain_message=strip_tags(plain_message),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.client.email],
            html_message=html_message
        )

        return True

    @staticmethod
    def send_application_rejected_email(application):
        """
        Send notification email when an application is rejected.

        Args:
            application (Application): The rejected application instance.

        Returns:
            bool: True if email task was successfully queued.
        """
        subject = f'Ваша заявка #{application.sample_code} отклонена'
        application_url = settings.SITE_URL + reverse('application_detail',
                                                      kwargs={'application_code': application.application_code})
        application_url = prepare_url(application_url)
        html_message = render_to_string('emails/reject_app.html', {
            'application': application,
            'user': application.client,
            'application_url': application_url,
            'site_name': settings.SITE_NAME
        })

        plain_message = EmailService._prepare_plain_status_message(application, 'отклонена', application_url)

        # Запускаем отправку через Celery
        send_email_task.delay(
            subject=subject,
            plain_message=strip_tags(plain_message),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.client.email],
            html_message=html_message
        )

        return True

    @staticmethod
    def send_data_published_email(application):
        """
        Send notification email when application data is published/available.

        Args:
            application (Application): The application with published data.

        Returns:
            bool: True if email task was successfully queued.
        """
        subject = f'Данные по заявке {application.sample_code} выложены'
        application_url = settings.SITE_URL + reverse('application_detail',
                                                      kwargs={'application_code': application.application_code})
        application_url = prepare_url(application_url)
        html_message = render_to_string('emails/data_published.html', {
            'application': application,
            'user': application.client,
            'application_url': application_url,
            'site_name': settings.SITE_NAME
        })

        plain_message = f"""
            Уважаемый пользователь {application.client.get_full_name()},

            Данные по заявке #{application.sample_code} были выложены.

            Детали заявки:
            - Код образца: {application.sample_code}
            - Состав: {application.composition}
            - Дата создания: {application.date.strftime('%d.%m.%Y')}
            - Статус: {application.get_status_display()}

            Просмотреть детали заявки: {application_url}

            С уважением,
            Команда {settings.SITE_NAME}
            """

        # Запускаем отправку через Celery
        send_email_task.delay(
            subject=subject,
            plain_message=strip_tags(plain_message),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.client.email],
            html_message=html_message
        )

        return True

    @staticmethod
    def send_sample_return_email(email_data):
        """
        Send reminder email about samples that need to be retrieved.

        Args:
            email_data (dict): Dictionary containing:
                - samples (list): Sample codes requiring collection.
                - mail (str): Recipient email address.
                - user (str): Recipient username.
                - storage (list): Storage locations for each sample.

        Returns:
            bool: True if email task was successfully queued.
        """
        sample_codes_str = ', '.join(email_data['samples'])
        mail = email_data['mail']
        user = email_data['user']
        subject = f'Необходимо забрать образцы {sample_codes_str}'

        sample_desc = "\n".join([
            f'• {sample_code} - {storage}'
            for sample_code, storage in zip(email_data['samples'], email_data['storage'])
        ])
        url = settings.SITE_URL + reverse('application_list')
        url = prepare_url(url)

        html_message = render_to_string('emails/remind_sample.html', {
            'samples': sample_codes_str,
            'user': user,
            'url': url,
            'site_name': settings.SITE_NAME,
            'sample_description': sample_desc.replace('\n', '<br>'),  # Для HTML заменяем переносы
        })
        plain_message = f"""
        Уважаемый пользователь {user},

        Пожалуйста, заберите образцы из места хранения и сделайте соответствующую отметку в журнале {url}.

        Детали хранения образцов:
        {sample_desc}

        С уважением,
        Команда {settings.SITE_NAME}
        """
        send_email_task.delay(
            subject=subject,
            plain_message=strip_tags(plain_message),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[mail],
            html_message=html_message
        )

        return True


@shared_task
def sample_takeaway_reminder_email():
    """
    Celery task to send reminder emails about unreturned samples.

    Scans all applications with unreturned samples (excluding submitted
    applications) and sends reminder emails to clients grouped by user.

    Returns:
        str: Status message with counts of emails sent and samples covered.
    """
    try:
        applications = Application.objects.filter(
            Q(sample_returned=False) &
            Q(client__is_active=True) &
            ~Q(status='submitted')
        ).select_related('client', 'operator')

        logger.info(f"Найдено {applications.count()} заявок с не возвращенными образцами")

        mail_data = {}
        for application in applications:
            try:
                user = application.client
                user_key = user.get_full_name()

                if user_key not in mail_data:
                    mail_data[user_key] = {}
                    mail_data[user_key]['samples'] = []
                    mail_data[user_key]['storage'] = []
                    mail_data[user_key]['mail'] = application.client.email
                    mail_data[user_key]['user'] = user_key
                storage_value = application.sample_storage_post_exp
                storage_display = application.get_sample_storage_post_exp_display()
                if storage_value == 'operator':
                    mail_data[user_key]['storage'].append(f"{storage_display} {application.operator.name}")
                else:
                    mail_data[user_key]['storage'].append(storage_display)
                mail_data[user_key]['samples'].append(application.sample_code)

            except Exception as e:
                logger.error(f"Ошибка при сборе данных для напоминания для заявки #{application.id}: {str(e)}")
        counter_s = 0
        counter_u = 0
        for user in mail_data.keys():
            try:
                EmailService.send_sample_return_email(mail_data[user])
                counter_u += 1
                counter_s += len(mail_data[user]['samples'])
            except Exception as e:
                logger.error(
                    f"Ошибка {e} при отправке напоминания о забытых образцах, пользователю {user}, образцов {mail_data[user]['samples']}")
        return f"Отправлено {counter_u} писем, по {counter_s} заявкам"

    except Exception as e:
        logger.error(f"Ошибка в задаче sample_takeaway_reminder_email: {str(e)}")
        raise


@shared_task
def send_password_reset_email(context, from_email, to_email):
    """
    Celery task to send password reset emails.

    Renders password reset email template with provided context and sends
    via the custom logging email backend.

    Args:
        context (dict): Template context for password reset email.
        from_email (str): Sender email address.
        to_email (str): Recipient email address.

    Raises:
        Exception: If email sending fails.
    """
    try:
        logger.debug(f"send_password_reset_email task started: to={to_email}, from={from_email}")

        subject = f'Восстановление пароля {SITE_NAME}'
        body = render_to_string('emails/password_reset_email.html', context)

        logger.debug(f"Email subject: {subject}")
        logger.debug(f"Email body length: {len(body)}")
        logger.debug(f"Context: {context}")

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        email_message.content_subtype = "html"

        # Логируем перед отправкой
        logger.debug(f"About to send email: From: {from_email}, To: {to_email}")

        email_message.send()

        logger.info(f"Password reset email sent successfully to {to_email}")

    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}", exc_info=True)
        raise


def prepare_url(url):
    """
    Normalize URL by removing double slashes for consistent formatting.

    Args:
        url (str): Original URL possibly containing double slashes.

    Returns:
        str: Normalized URL with single slashes.
    """
    return url.replace(r'//', '/')