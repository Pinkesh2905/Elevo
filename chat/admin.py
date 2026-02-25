from django.contrib import admin
from .models import ChatThread, Message


class MessageInline(admin.TabularInline):
    model = Message
    readonly_fields = ('sender', 'content', 'created_at', 'is_read')
    extra = 0
    ordering = ['-created_at']


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_participants', 'updated_at', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('participants__username',)
    inlines = [MessageInline]

    def get_participants(self, obj):
        return ', '.join(u.username for u in obj.participants.all())
    get_participants.short_description = 'Participants'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'sender', 'short_content', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'content')
    readonly_fields = ('thread', 'sender', 'content', 'created_at')

    def short_content(self, obj):
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content
    short_content.short_description = 'Content'
