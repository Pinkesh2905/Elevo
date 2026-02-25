from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q, Max, Count, Subquery, OuterRef
from django.utils import timezone

from .models import ChatThread, Message


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

    messages = thread.messages.select_related('sender').order_by('created_at')

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
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    content = request.POST.get('content', '').strip()

    if not content:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    message = Message.objects.create(
        thread=thread,
        sender=request.user,
        content=content,
    )

    # Update thread timestamp
    thread.updated_at = timezone.now()
    thread.save(update_fields=['updated_at'])

    return JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'content': message.content,
            'sender': message.sender.username,
            'sender_avatar': message.sender.profile.avatar.url if message.sender.profile.avatar else None,
            'created_at': message.created_at.strftime('%b %d, %I:%M %p'),
            'is_mine': True,
        }
    })


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
        .select_related('sender', 'sender__profile')
        .order_by('created_at')
    )

    # Mark incoming messages as read
    new_messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages_data = []
    for msg in new_messages:
        messages_data.append({
            'id': msg.id,
            'content': msg.content,
            'sender': msg.sender.username,
            'sender_avatar': msg.sender.profile.avatar.url if msg.sender.profile.avatar else None,
            'created_at': msg.created_at.strftime('%b %d, %I:%M %p'),
            'is_mine': msg.sender == request.user,
        })

    return JsonResponse({'messages': messages_data})


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
