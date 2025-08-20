# backend/common/emails.py
from pathlib import Path
from typing import Iterable, Mapping, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_templated_mail(
    subject: str,
    to: Iterable[str],
    template_base: str,
    context: Mapping,
    from_email: Optional[str] = None,
    attachments: Optional[list[tuple[str, bytes, str]]] = None,
) -> int:
    """
    Отправляет письмо в HTML + plain текстах по шаблонам:
      templates/<template_base>.html
      templates/<template_base>.txt (опционально)
    attachments: список троек (name, content_bytes, mimetype)
    """
    html_body = render_to_string(f"{template_base}.html", context)
    # .txt файл опционален — если его нет, берём strip_tags от html
    try:
        text_body = render_to_string(f"{template_base}.txt", context)
    except Exception:
        text_body = strip_tags(html_body)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=list(to),
    )
    email.attach_alternative(html_body, "text/html")

    if attachments:
        for name, data, mimetype in attachments:
            email.attach(name, data, mimetype)

    return email.send(fail_silently=False)
