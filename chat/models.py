from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ChatThread(models.Model):
    """
    Represents a private conversation between exactly two users.
    """
    participants = models.ManyToManyField(User, related_name='chat_threads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
        ]

    def __str__(self):
        names = ', '.join(u.username for u in self.participants.all())
        return f"Chat: {names}"

    def get_other_participant(self, user):
        """Return the other user in this thread."""
        return self.participants.exclude(id=user.id).first()

    def last_message(self):
        """Return the most recent message in this thread."""
        return self.messages.order_by('-created_at').first()

    def unread_count_for(self, user):
        """Return the number of unread messages for a given user."""
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    @staticmethod
    def get_or_create_thread(user1, user2):
        """
        Find an existing thread between two users, or create a new one.
        """
        threads = ChatThread.objects.filter(participants=user1).filter(participants=user2)
        if threads.exists():
            return threads.first(), False

        thread = ChatThread.objects.create()
        thread.participants.add(user1, user2)
        return thread, True


class Message(models.Model):
    """
    A single message within a chat thread.
    Supports text, images, videos, files, and replies.
    """
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('file', 'File'),
    ]

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField(blank=True, null=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')

    # Media Fields
    image = models.ImageField(upload_to='chat/images/', blank=True, null=True)
    file = models.FileField(upload_to='chat/files/', blank=True, null=True)

    # Reply Feature
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"{self.sender.username}: {self.content[:40] if self.content else self.message_type}"


class MessageReaction(models.Model):
    """
    Emoji reactions to a message.
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=20)  # Character or emoji
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message {self.message.id}"
