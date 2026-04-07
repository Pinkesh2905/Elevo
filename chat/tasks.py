from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from .models import Message

def send_missed_message_emails():
    """
    Background task to find unread messages and send summary emails
    to users who haven't been on the platform recently.
    """
    # Define "missed" as unread messages older than 15 minutes that haven't been emailed yet
    threshold = timezone.now() - timedelta(minutes=15)
    
    unread_messages = Message.objects.filter(
        is_read=False,
        email_sent=False,
        created_at__lte=threshold
    ).select_related('sender', 'thread')

    if not unread_messages.exists():
        return "No new missed messages to notify."

    # Group messages by recipient
    # In our 2-person thread model, recipient = the participant who is NOT the sender
    recipient_map = {}
    
    for msg in unread_messages:
        # Get the recipient (the other participant in the thread)
        recipient = msg.thread.get_other_participant(msg.sender)
        
        if not recipient:
            continue
            
        # Check if recipient has email notifications enabled
        if not hasattr(recipient, 'profile') or not recipient.profile.email_notifications_enabled:
            continue

        if recipient not in recipient_map:
            recipient_map[recipient] = []
        
        recipient_map[recipient].append(msg)

    emails_sent_count = 0
    for recipient, messages in recipient_map.items():
        if not recipient.email:
            continue

        context = {
            'user': recipient,
            'messages': messages,
            'count': len(messages),
            'site_url': getattr(settings, 'DOMAIN_NAME', 'elevo.life')
        }

        subject = f"Elevo: You have {len(messages)} unread message{'s' if len(messages) > 1 else ''}"
        html_message = render_to_string('chat/emails/missed_messages.html', context)
        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            # Successfully sent, mark these messages as email_sent=True
            Message.objects.filter(id__in=[m.id for m in messages]).update(email_sent=True)
            emails_sent_count += 1
            
        except Exception as e:
            # In a real production app, we'd log this properly
            print(f"Failed to send missed message email to {recipient.email}: {str(e)}")

    return f"Sent {emails_sent_count} notification email(s) for {unread_messages.count()} messages."
