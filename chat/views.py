import json
import os
import time

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import close_old_connections
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from .models import ChatThread, Message, MessageReaction


PRESENCE_TTL_SECONDS = 75
THREAD_ACTIVITY_TTL_SECONDS = 45
STREAM_POLL_INTERVAL_SECONDS = 1
STREAM_KEEPALIVE_SECONDS = 15


def _presence_cache_key(user_id):
    return f"presence_user_{user_id}"


def _thread_presence_cache_key(thread_id, user_id):
    return f"presence_thread_{thread_id}_{user_id}"


def _iso_local(dt):
    """Return an ISO 8601 timestamp in the active local timezone."""
    if not dt:
        return None
    return timezone.localtime(dt).isoformat()


def _mark_user_presence(user, thread_id=None):
    """Record a user's latest seen timestamp and active thread context."""
    now = timezone.now()
    cache.set(_presence_cache_key(user.id), _iso_local(now), timeout=PRESENCE_TTL_SECONDS)
    if thread_id is not None:
        cache.set(
            _thread_presence_cache_key(thread_id, user.id),
            True,
            timeout=THREAD_ACTIVITY_TTL_SECONDS,
        )
    return now


def _get_user_presence(user, thread_id=None):
    """Return online/last-seen information for a user."""
    if user is None:
        return {
            'is_online': False,
            'is_active_here': False,
            'last_seen_raw': None,
        }

    raw_last_seen = cache.get(_presence_cache_key(user.id))
    last_seen = parse_datetime(raw_last_seen) if raw_last_seen else None
    is_online = False
    if last_seen is not None:
        is_online = (timezone.now() - last_seen).total_seconds() < PRESENCE_TTL_SECONDS

    is_active_here = False
    if thread_id is not None:
        is_active_here = bool(cache.get(_thread_presence_cache_key(thread_id, user.id)))

    return {
        'is_online': is_online,
        'is_active_here': is_active_here,
        'last_seen_raw': _iso_local(last_seen),
    }


def _build_thread_list(user):
    """Build thread sidebar/inbox data without per-thread message lookups."""
    other_user_subquery = (
        User.objects
        .filter(chat_threads=OuterRef('pk'))
        .exclude(pk=user.pk)
        .values('pk')[:1]
    )
    last_message_subquery = (
        Message.objects
        .filter(thread=OuterRef('pk'))
        .order_by('-created_at', '-pk')
        .values('pk')[:1]
    )

    threads = list(
        ChatThread.objects
        .filter(participants=user)
        .annotate(
            last_message_time=Max('messages__created_at'),
            unread=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=user) & ~Q(messages__is_deleted_for_everyone=True) & ~Q(messages__deleted_by=user),
            ),
            other_user_id=Subquery(other_user_subquery),
            last_message_id=Subquery(last_message_subquery),
        )
        .order_by('-last_message_time', '-updated_at')
    )

    other_user_ids = [thread.other_user_id for thread in threads if thread.other_user_id]
    last_message_ids = [thread.last_message_id for thread in threads if thread.last_message_id]

    users_by_id = {
        profile_user.id: profile_user
        for profile_user in User.objects.filter(id__in=other_user_ids).select_related('profile')
    }
    messages_by_id = {
        message.id: message
        for message in Message.objects.filter(id__in=last_message_ids).select_related('sender')
    }

    thread_list = []
    for thread in threads:
        other_user = users_by_id.get(thread.other_user_id)
        if other_user is None:
            continue
        thread_list.append({
            'thread': thread,
            'other_user': other_user,
            'last_message': messages_by_id.get(thread.last_message_id),
            'unread': thread.unread,
        })
    return thread_list


def _build_seen_status(thread, user):
    last_sent = thread.messages.filter(sender=user).order_by('-created_at', '-pk').first()
    return {
        'is_read': bool(last_sent and last_sent.is_read),
        'read_at': (
            timezone.localtime(last_sent.read_at).strftime('%I:%M %p')
            if last_sent and last_sent.read_at
            else None
        ),
        'read_at_raw': _iso_local(last_sent.read_at) if last_sent else None,
    }


def _build_reaction_updates(thread, user, limit=20):
    reaction_updates = []
    for msg in thread.messages.order_by('-created_at', '-pk')[:limit]:
        reactions = list(
            msg.reactions.values('emoji')
            .annotate(count=Count('id'), reacted=Count('id', filter=Q(user=user)))
        )
        if reactions:
            reaction_updates.append({'id': msg.id, 'reactions': reactions})
    return reaction_updates


def _build_thread_status(thread, user):
    other_user = thread.get_other_participant(user)
    is_typing = cache.get(f"typing_{thread.id}_{other_user.id}", False) if other_user else False
    return {
        'is_typing': is_typing,
        'seen_status': _build_seen_status(thread, user),
        'reaction_updates': _build_reaction_updates(thread, user),
        'presence': _get_user_presence(other_user, thread.id),
    }


@login_required
def inbox(request):
    """
    Display all chat threads for the logged-in user, ordered by most recent activity.
    """
    _mark_user_presence(request.user)
    return render(request, 'chat/inbox.html', {
        'thread_list': _build_thread_list(request.user),
    })


@login_required
def chat_thread(request, thread_id):
    """
    Display a specific chat thread and its messages.
    Marks unread messages as read when viewed.
    """
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    other_user = thread.get_other_participant(request.user)
    _mark_user_presence(request.user, thread.id)

    first_unread = thread.messages.filter(is_read=False).exclude(sender=request.user).order_by('created_at').first()
    first_unread_message_id = first_unread.id if first_unread else None

    # Mark messages from the other user as read
    now = timezone.now()
    thread.messages.filter(is_read=False).exclude(sender=request.user).update(
        is_read=True,
        read_at=now,
    )

    messages = (
        thread.messages
        .exclude(deleted_by=request.user)
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

    return render(request, 'chat/thread.html', {
        'thread': thread,
        'other_user': other_user,
        'messages': messages,
        'thread_list': _build_thread_list(request.user),
        'first_unread_message_id': first_unread_message_id,
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
    if msg.is_deleted_for_everyone:
        return {
            'id': msg.id,
            'content': 'This message was deleted',
            'sender': msg.sender.username,
            'sender_avatar': (
                msg.sender.profile.avatar.url
                if hasattr(msg.sender, 'profile') and msg.sender.profile.avatar
                else None
            ),
            'created_at': timezone.localtime(msg.created_at).strftime('%I:%M %p'),
            'timestamp_raw': _iso_local(msg.created_at),
            'is_mine': msg.sender == user,
            'is_read': msg.is_read,
            'is_deleted': True,
            'reactions': []
        }

    return {
        'id': msg.id,
        'content': msg.content,
        'sender': msg.sender.username,
        'sender_avatar': (
            msg.sender.profile.avatar.url
            if hasattr(msg.sender, 'profile') and msg.sender.profile.avatar
            else None
        ),
        'created_at': timezone.localtime(msg.created_at).strftime('%I:%M %p'),
        'timestamp_raw': _iso_local(msg.created_at),
        'is_mine': msg.sender == user,
        'is_read': msg.is_read,
        'is_edited': msg.is_edited,
        'read_at': timezone.localtime(msg.read_at).strftime('%I:%M %p') if msg.read_at else None,
        'read_at_raw': _iso_local(msg.read_at),
        'message_type': msg.message_type,
        'image_url': msg.image.url if msg.image else None,
        'file_url': msg.file.url if msg.file else None,
        'file_name': os.path.basename(msg.file.name) if msg.file else None,
        'parent': {
            'id': msg.parent_message.id,
            'content': (msg.parent_message.content or msg.parent_message.message_type)[:50],
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
    _mark_user_presence(request.user, thread.id)
    after_id = request.GET.get('after', 0)

    try:
        after_id = int(after_id)
    except (ValueError, TypeError):
        after_id = 0

    new_messages = (
        thread.messages
        .filter(id__gt=after_id)
        .exclude(deleted_by=request.user)
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
    return JsonResponse({
        'messages': messages_data,
        'status': _build_thread_status(thread, request.user),
    })


@login_required
def update_typing_status(request, thread_id):
    """Update typing indicator in cache."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    _mark_user_presence(request.user, thread.id)
    cache.set(f"typing_{thread_id}_{request.user.id}", True, 5)
    return JsonResponse({'status': 'ok'})


@login_required
def update_presence(request, thread_id):
    """Heartbeat endpoint to keep presence and last-seen current."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    _mark_user_presence(request.user, thread.id)
    return JsonResponse({
        'status': 'ok',
        'presence': _get_user_presence(request.user, thread.id),
    })


@login_required
def get_thread_status(request, thread_id):
    """Return typing status of other user and seen status of last sent message."""
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    _mark_user_presence(request.user, thread.id)
    return JsonResponse(_build_thread_status(thread, request.user))


@login_required
def thread_stream(request, thread_id):
    """Stream new messages and status changes over Server-Sent Events."""
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    _mark_user_presence(request.user, thread.id)

    try:
        last_id = int(request.GET.get('last_id', 0))
    except (TypeError, ValueError):
        last_id = 0

    def event_stream():
        current_last_id = last_id
        last_status = None
        last_keepalive = time.monotonic()

        while True:
            close_old_connections()
            _mark_user_presence(request.user, thread.id)

            new_messages = list(
                thread.messages
                .filter(id__gt=current_last_id)
                .exclude(deleted_by=request.user)
                .select_related('sender', 'sender__profile', 'parent_message', 'parent_message__sender')
                .prefetch_related('reactions')
                .order_by('created_at', 'id')
            )

            if new_messages:
                unread_incoming_ids = [
                    message.id
                    for message in new_messages
                    if message.sender_id != request.user.id and not message.is_read
                ]
                if unread_incoming_ids:
                    now = timezone.now()
                    Message.objects.filter(id__in=unread_incoming_ids).update(
                        is_read=True,
                        read_at=now,
                    )
                    for message in new_messages:
                        if message.id in unread_incoming_ids:
                            message.is_read = True
                            message.read_at = now

                payload = [_serialize_message(message, request.user) for message in new_messages]
                current_last_id = new_messages[-1].id
                yield f"event: messages\ndata: {json.dumps(payload)}\n\n"

            status_payload = _build_thread_status(thread, request.user)
            serialized_status = json.dumps(status_payload, sort_keys=True)
            if serialized_status != last_status:
                last_status = serialized_status
                yield f"event: status\ndata: {serialized_status}\n\n"

            current_time = time.monotonic()
            if current_time - last_keepalive >= STREAM_KEEPALIVE_SECONDS:
                last_keepalive = current_time
                yield ": keep-alive\n\n"

            time.sleep(STREAM_POLL_INTERVAL_SECONDS)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@login_required
def toggle_reaction(request, message_id):
    """Toggle an emoji reaction on a message."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    message = get_object_or_404(Message, id=message_id, thread__participants=request.user)
    _mark_user_presence(request.user, message.thread_id)
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
    _mark_user_presence(request.user)
    count = (
        Message.objects
        .filter(thread__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .exclude(deleted_by=request.user)
        .exclude(is_deleted_for_everyone=True)
        .count()
    )
    return JsonResponse({'unread_count': count})

@login_required
def edit_message(request, message_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Content cannot be empty'}, status=400)
        
    message = get_object_or_404(Message, id=message_id, sender=request.user)
    
    if message.message_type != 'text':
        return JsonResponse({'error': 'Can only edit text messages'}, status=400)
        
    message.content = content
    message.is_edited = True
    message.save(update_fields=['content', 'is_edited'])
    
    return JsonResponse({
        'status': 'ok',
        'message': _serialize_message(message, request.user)
    })

@login_required
def delete_message(request, message_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    message = get_object_or_404(Message, id=message_id, thread__participants=request.user)
    delete_type = request.POST.get('delete_type', 'for_me')
    
    if delete_type == 'for_me':
        message.deleted_by.add(request.user)
    elif delete_type == 'for_everyone':
        if message.sender != request.user:
            return JsonResponse({'error': 'Not authorized to delete for everyone'}, status=403)
        message.is_deleted_for_everyone = True
        message.image = None
        message.file = None
        message.content = 'This message was deleted'
        message.save(update_fields=['is_deleted_for_everyone', 'image', 'file', 'content'])
        
    return JsonResponse({'status': 'ok'})

@login_required
def update_theme(request, thread_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    theme = request.POST.get('theme', 'default')
    
    valid_themes = [t[0] for t in ChatThread.THEME_CHOICES]
    if theme in valid_themes:
        thread.theme = theme
        thread.save(update_fields=['theme'])
        return JsonResponse({'status': 'ok', 'theme': theme})
        
    return JsonResponse({'error': 'Invalid theme'}, status=400)
