# backend/common/emails.py
import logging
from pathlib import Path
from typing import Iterable, Mapping, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


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
    to_list = list(to)
    
    logger.info(
        f"[send_templated_mail] 📧 НАЧАЛО ОТПРАВКИ EMAIL\n"
        f"  Subject: '{subject}'\n"
        f"  Template: {template_base}\n"
        f"  Recipients: {to_list}\n"
        f"  From: {from_email or settings.DEFAULT_FROM_EMAIL}"
    )
    
    try:
        html_body = render_to_string(f"{template_base}.html", context)
        logger.info(f"[send_templated_mail] ✅ HTML шаблон загружен ({len(html_body)} символов)")
    except Exception as e:
        logger.error(f"[send_templated_mail] ❌ Ошибка загрузки HTML шаблона: {e}")
        raise
    
    # .txt файл опционален — если его нет, берём strip_tags от html
    try:
        text_body = render_to_string(f"{template_base}.txt", context)
        logger.info(f"[send_templated_mail] ✅ TXT шаблон загружен ({len(text_body)} символов)")
    except Exception:
        text_body = strip_tags(html_body)
        logger.info(f"[send_templated_mail] ⚠️ TXT шаблон не найден, используется strip_tags от HTML")

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=to_list,
    )
    email.attach_alternative(html_body, "text/html")

    if attachments:
        for name, data, mimetype in attachments:
            email.attach(name, data, mimetype)
            logger.info(f"[send_templated_mail] 📎 Вложение: {name} ({len(data)} bytes, {mimetype})")
    
    logger.info(f"[send_templated_mail] ➡️ Вызов email.send()...")
    
    try:
        result = email.send(fail_silently=False)
        logger.info(f"[send_templated_mail] ✅ EMAIL УСПЕШНО ОТПРАВЛЕН (result={result})")
        return result
    except Exception as e:
        logger.error(
            f"[send_templated_mail] ❌ ОШИБКА ОТПРАВКИ EMAIL: {type(e).__name__}: {e}",
            exc_info=True
        )
        raise

