from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import ChatThread, Message


class ChatSyncTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='testpass123')
        self.bob = User.objects.create_user(username='bob', password='testpass123')
        self.thread, _ = ChatThread.get_or_create_thread(self.alice, self.bob)

    def test_fetch_messages_marks_incoming_messages_read_and_returns_status(self):
        message = Message.objects.create(
            thread=self.thread,
            sender=self.bob,
            content='Hello from Bob',
        )
        self.client.force_login(self.alice)

        response = self.client.get(reverse('chat:fetch_messages', args=[self.thread.id]), {'after': 0})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('messages', payload)
        self.assertIn('status', payload)
        self.assertEqual(len(payload['messages']), 1)
        self.assertIn('timestamp_raw', payload['messages'][0])

        message.refresh_from_db()
        self.assertTrue(message.is_read)
        self.assertIsNotNone(message.read_at)
        self.assertIn('seen_status', payload['status'])

    def test_typing_status_requires_post(self):
        self.client.force_login(self.alice)

        response = self.client.get(reverse('chat:update_typing_status', args=[self.thread.id]))

        self.assertEqual(response.status_code, 405)

    def test_presence_heartbeat_updates_thread_status_presence(self):
        self.client.force_login(self.bob)
        heartbeat_response = self.client.post(reverse('chat:update_presence', args=[self.thread.id]))
        self.assertEqual(heartbeat_response.status_code, 200)

        self.client.force_login(self.alice)
        status_response = self.client.get(reverse('chat:thread_status', args=[self.thread.id]))

        self.assertEqual(status_response.status_code, 200)
        payload = status_response.json()
        self.assertIn('presence', payload)
        self.assertTrue(payload['presence']['is_online'])
        self.assertTrue(payload['presence']['is_active_here'])
        self.assertIsNotNone(payload['presence']['last_seen_raw'])

    def test_presence_heartbeat_requires_post(self):
        self.client.force_login(self.alice)

        response = self.client.get(reverse('chat:update_presence', args=[self.thread.id]))

        self.assertEqual(response.status_code, 405)
