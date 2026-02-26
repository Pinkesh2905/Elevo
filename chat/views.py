from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q, Max, Count, Subquery, OuterRef
from django.utils import timezone

from django.core.cache import cache
from .models import ChatThread, Message, MessageReaction


@login_required
def inbox(request):
    """
    Display all chat threads for the logged-in user, ordered by most recent activity.
    """
    threads = (
        ChatThread.objects
        .filter(participants=request.user)
        .annotate(
            last_message_time=Max('messages__created_at'),
            unread=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
            ),
        )
        .order_by('-last_message_time')
    )

    # Build thread data with other participant info
    thread_list = []
    for thread in threads:
        other_user = thread.get_other_participant(request.user)
        if other_user is None:
            continue
        last_msg = thread.last_message()
        thread_list.append({
            'thread': thread,
            'other_user': other_user,
            'last_message': last_msg,
            'unread': thread.unread,
        })

    return render(request, 'chat/inbox.html', {
        'thread_list': thread_list,
    })


@login_required
def chat_thread(request, thread_id):
    """
    Display a specific chat thread and its messages.
    Marks unread messages as read when viewed.
    """
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    other_user = thread.get_other_participant(request.user)

    # Mark messages from the other user as read
    thread.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages = (
        thread.messages
        .select_related('sender', 'sender__profile', 'parent_message', 'parent_message__sender')
        .prefetch_related('reactions')
        .order_by('created_at')
    )

    # Attach grouped reactions to each message for easier template rendering
    for msg in messages:
        msg.grouped_reactions = list(
            msg.reactions.values('emoji')
            .annotate(count=Count('id'), reacted=Count('id', filter=Q(user=request.user)))
        )

    # Also get the inbox thread list for the sidebar
    threads = (
        ChatThread.objects
        .filter(participants=request.user)
        .annotate(
            last_message_time=Max('messages__created_at'),
            unread=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
            ),
        )
        .order_by('-last_message_time')
    )

    thread_list = []
    for t in threads:
        ou = t.get_other_participant(request.user)
        if ou is None:
            continue
        last_msg = t.last_message()
        thread_list.append({
            'thread': t,
            'other_user': ou,
            'last_message': last_msg,
            'unread': t.unread,
        })

    return render(request, 'chat/thread.html', {
        'thread': thread,
        'other_user': other_user,
        'messages': messages,
        'thread_list': thread_list,
    })


@login_required
def start_chat(request, username):
    """
    Start or resume a chat with a specific user.
    Creates a new thread if one doesn't exist, then redirects to it.
    """
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        return redirect('chat:inbox')

    thread, created = ChatThread.get_or_create_thread(request.user, other_user)
    return redirect('chat:thread', thread_id=thread.id)


@login_required
def send_message(request, thread_id):
    """
    Send a message in a thread (AJAX POST).
    Now supports images, files, and replies.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    content = request.POST.get('content', '').strip()
    parent_id = request.POST.get('parent_id')
    image = request.FILES.get('image')
    file = request.FILES.get('file')

    if not content and not image and not file:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    # Determine message type
    msg_type = 'text'
    if image:
        msg_type = 'image'
    elif file:
        # Check extension for video or general file
        ext = file.name.split('.')[-1].lower()
        msg_type = 'video' if ext in ['mp4', 'webm', 'mov'] else 'file'

    parent = None
    if parent_id:
        parent = Message.objects.filter(id=parent_id, thread=thread).first()

    message = Message.objects.create(
        thread=thread,
        sender=request.user,
        content=content,
        message_type=msg_type,
        parent_message=parent,
        image=image,
        file=file
    )

    # Update thread timestamp
    thread.updated_at = timezone.now()
    thread.save(update_fields=['updated_at'])

    return JsonResponse({
        'success': True,
        'message': _serialize_message(message, request.user)
    })


def _serialize_message(msg, user):
    """Helper to convert Message instance to dict."""
    return {
        'id': msg.id,
        'content': msg.content,
        'sender': msg.sender.username,
        'sender_avatar': msg.sender.profile.avatar.url if msg.sender.profile.avatar else None,
        'created_at': msg.created_at.strftime('%b %d, %I:%M %p'),
        'timestamp_raw': msg.created_at.isoformat(),
        'is_mine': msg.sender == user,
        'is_read': msg.is_read,
        'read_at': msg.read_at.strftime('%I:%M %p') if msg.read_at else None,
        'message_type': msg.message_type,
        'image_url': msg.image.url if msg.image else None,
        'file_url': msg.file.url if msg.file else None,
        'file_name': msg.file.name.split('/')[-1] if msg.file else None,
        'parent': {
            'id': msg.parent_message.id,
            'content': msg.parent_message.content[:50],
            'sender': msg.parent_message.sender.username
        } if msg.parent_message else None,
        'reactions': list(msg.reactions.values('emoji').annotate(count=Count('id'), reacted=Count('id', filter=Q(user=user))))
    }


@login_required
def fetch_messages(request, thread_id):
    """
    Fetch new messages since a given message ID (AJAX GET for polling).
    """
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    after_id = request.GET.get('after', 0)

    try:
        after_id = int(after_id)
    except (ValueError, TypeError):
        after_id = 0

    new_messages = (
        thread.messages
        .filter(id__gt=after_id)
        .select_related('sender', 'sender__profile', 'parent_message', 'parent_message__sender')
        .prefetch_related('reactions')
        .order_by('created_at')
    )

    # Mark incoming messages as read
    now = timezone.now()
    incoming = new_messages.filter(is_read=False).exclude(sender=request.user)
    if incoming.exists():
        incoming.update(is_read=True, read_at=now)

    messages_data = [_serialize_message(msg, request.user) for msg in new_messages]
    return JsonResponse({'messages': messages_data})


@login_required
def update_typing_status(request, thread_id):
    """Update typing indicator in cache."""
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    cache.set(f"typing_{thread_id}_{request.user.id}", True, 5)
    return JsonResponse({'status': 'ok'})


@login_required
def get_thread_status(request, thread_id):
    """Return typing status of other user and seen status of last sent message."""
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    other_user = thread.get_other_participant(request.user)
    
    is_typing = cache.get(f"typing_{thread_id}_{other_user.id}", False)
    
    last_sent = thread.messages.filter(sender=request.user).order_by('-created_at').first()
    seen_status = {
        'is_read': last_sent.is_read if last_sent else False,
        'read_at': last_sent.read_at.strftime('%I:%M %p') if last_sent and last_sent.read_at else None
    }

    # Get reaction updates for recent messages (last 20)
    recent_messages = thread.messages.order_by('-created_at')[:20]
    reaction_updates = []
    for msg in recent_messages:
        reactions = list(
            msg.reactions.values('emoji')
            .annotate(count=Count('id'), reacted=Count('id', filter=Q(user=request.user)))
        )
        if reactions:
            reaction_updates.append({
                'id': msg.id,
                'reactions': reactions
            })

    return JsonResponse({
        'is_typing': is_typing,
        'seen_status': seen_status,
        'reaction_updates': reaction_updates
    })


@login_required
def toggle_reaction(request, message_id):
    """Toggle an emoji reaction on a message."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    message = get_object_or_404(Message, id=message_id, thread__participants=request.user)
    emoji = request.POST.get('emoji')
    
    if not emoji:
        return JsonResponse({'error': 'Emoji required'}, status=400)
        
    reaction, created = MessageReaction.objects.get_or_create(
        message=message,
        user=request.user,
        emoji=emoji
    )
    
    if not created:
        reaction.delete()
        action = 'removed'
    else:
        action = 'added'

    # Get updated reaction data
    reactions_data = list(
        message.reactions.values('emoji')
        .annotate(count=Count('id'), reacted=Count('id', filter=Q(user=request.user)))
    )
        
    return JsonResponse({
        'status': 'ok', 
        'action': action,
        'reactions': reactions_data
    })


@login_required
def unread_count(request):
    """
    Return total unread message count for the logged-in user (AJAX GET for navbar badge).
    """
    count = (
        Message.objects
        .filter(thread__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({'unread_count': count})
