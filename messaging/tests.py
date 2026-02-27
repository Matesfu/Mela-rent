"""
Mela Rent – Messaging App Comprehensive E2E Test Suite
=======================================================
Tests the ENTIRE messaging module end-to-end as a professional-grade
communication system comparable to Airbnb's inquiry/messaging flow.

Coverage Map:
  1. Starting Conversations (5 tests)
  2. Sending Messages (4 tests)
  3. Retrieving Conversations & Messages (4 tests)
  4. Mark as Read / Unread Count (3 tests)
  5. Security & Access Control (5 tests)
  6. Full User Journey (2 tests)
"""

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.test import override_settings

from properties.models import Property
from messaging.models import Conversation, Message

User = get_user_model()


# ===========================================================================
# 1. STARTING CONVERSATIONS
# ===========================================================================

class StartConversationE2ETest(APITestCase):
    """E2E tests for the POST /conversations/start/ endpoint."""

    def setUp(self):
        self.tenant = User.objects.create_user(username='msg_tenant', password='P!', role='TENANT')
        self.owner = User.objects.create_user(username='msg_owner', password='P!', role='OWNER')
        self.prop = Property.objects.create(
            owner=self.owner, title='Chat Prop', house_type='Villa',
            price=5000, description='D', location='X', bedrooms=1,
            bathrooms=1, max_guests=1, amenities='N'
        )
        self.start_url = '/api/messaging/conversations/start/'

    def test_tenant_can_start_conversation_with_owner(self):
        """Tenant should be able to initiate a conversation about a property."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.start_url, {
            'recipient_id': self.owner.id,
            'property_id': self.prop.id,
            'initial_message': 'Is this property available?'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['participants']), 2)
        self.assertIsNotNone(response.data['last_message'])
        self.assertEqual(response.data['property_title'], 'Chat Prop')

    def test_cannot_start_conversation_with_self(self):
        """Users should not be able to message themselves."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.start_url, {
            'recipient_id': self.tenant.id,
            'initial_message': 'Talking to myself'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_start_duplicate_conversation(self):
        """Starting a second conversation with the same user about the same property should fail."""
        self.client.force_authenticate(user=self.tenant)
        self.client.post(self.start_url, {
            'recipient_id': self.owner.id,
            'property_id': self.prop.id,
            'initial_message': 'First inquiry'
        })
        response = self.client.post(self.start_url, {
            'recipient_id': self.owner.id,
            'property_id': self.prop.id,
            'initial_message': 'Duplicate inquiry'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_conversation_with_nonexistent_user(self):
        """Starting a conversation with a non-existent user should return 400."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.start_url, {
            'recipient_id': 99999,
            'initial_message': 'Hello ghost'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_start_conversation(self):
        """Anonymous users should get 401."""
        response = self.client.post(self.start_url, {
            'recipient_id': self.owner.id,
            'initial_message': 'Anonymous inquiry'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# 2. SENDING MESSAGES
# ===========================================================================

class SendMessageE2ETest(APITestCase):
    """E2E tests for the POST /conversations/{id}/send_message/ endpoint."""

    def setUp(self):
        self.tenant = User.objects.create_user(username='snd_tenant', password='P!', role='TENANT')
        self.owner = User.objects.create_user(username='snd_owner', password='P!', role='OWNER')
        self.conv = Conversation.objects.create()
        self.conv.participants.add(self.tenant, self.owner)

    def _send_url(self, conv_id):
        return f'/api/messaging/conversations/{conv_id}/send_message/'

    def test_participant_can_send_message(self):
        """A participant should be able to send a message."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self._send_url(self.conv.id), {'content': 'Hello owner!'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content'], 'Hello owner!')

    def test_owner_can_reply(self):
        """The other participant (owner) can reply in the same conversation."""
        Message.objects.create(conversation=self.conv, sender=self.tenant, content='Inquiry')
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self._send_url(self.conv.id), {'content': 'Yes, available!'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.filter(conversation=self.conv).count(), 2)

    def test_empty_message_rejected(self):
        """Empty or whitespace-only messages should return 400."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self._send_url(self.conv.id), {'content': '   '})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_message_without_content_rejected(self):
        """Sending without content field should return 400."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self._send_url(self.conv.id), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# 3. RETRIEVING CONVERSATIONS & MESSAGES
# ===========================================================================

class RetrieveConversationE2ETest(APITestCase):
    """E2E tests for listing and retrieving conversations and messages."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='ret_user1', password='P!', role='TENANT')
        self.user2 = User.objects.create_user(username='ret_user2', password='P!', role='OWNER')
        self.user3 = User.objects.create_user(username='ret_user3', password='P!', role='TENANT')
        self.conv = Conversation.objects.create()
        self.conv.participants.add(self.user1, self.user2)
        Message.objects.create(conversation=self.conv, sender=self.user1, content='Hello')
        Message.objects.create(conversation=self.conv, sender=self.user2, content='Hi there')

    def test_participant_can_list_conversations(self):
        """User should see conversations they participate in."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/messaging/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_non_participant_sees_empty_list(self):
        """Non-participant should see no conversations."""
        self.client.force_authenticate(user=self.user3)
        response = self.client.get('/api/messaging/conversations/')
        self.assertEqual(len(response.data['results']), 0)

    def test_retrieve_conversation_shows_last_message(self):
        """Conversation detail should include last message preview."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/messaging/conversations/{self.conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['last_message'])
        self.assertEqual(response.data['last_message']['content'], 'Hi there')

    def test_retrieve_messages_in_conversation(self):
        """GET /conversations/{id}/messages/ should return all messages chronologically."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/messaging/conversations/{self.conv.id}/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['content'], 'Hello')
        self.assertEqual(response.data[1]['content'], 'Hi there')


# ===========================================================================
# 4. MARK AS READ / UNREAD COUNT
# ===========================================================================

class MarkAsReadE2ETest(APITestCase):
    """E2E tests for the mark_as_read action and unread_count field."""

    def setUp(self):
        self.sender = User.objects.create_user(username='rd_sender', password='P!', role='TENANT')
        self.receiver = User.objects.create_user(username='rd_receiver', password='P!', role='OWNER')
        self.conv = Conversation.objects.create()
        self.conv.participants.add(self.sender, self.receiver)
        # Sender sends 3 unread messages
        for i in range(3):
            Message.objects.create(
                conversation=self.conv, sender=self.sender,
                content=f'Message {i+1}', is_read=False,
            )

    def test_unread_count_shows_correct_value(self):
        """Receiver should see unread_count=3 for messages from the sender."""
        self.client.force_authenticate(user=self.receiver)
        response = self.client.get('/api/messaging/conversations/')
        self.assertEqual(response.data['results'][0]['unread_count'], 3)

    def test_mark_as_read_clears_unread(self):
        """After marking as read, unread_count should drop to 0."""
        self.client.force_authenticate(user=self.receiver)
        response = self.client.post(
            f'/api/messaging/conversations/{self.conv.id}/mark_as_read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('3 message(s) marked as read', response.data['detail'])

        # Verify unread count is now 0
        list_resp = self.client.get('/api/messaging/conversations/')
        self.assertEqual(list_resp.data['results'][0]['unread_count'], 0)

    def test_sender_unread_count_is_zero(self):
        """Sender should not see their own messages as unread."""
        self.client.force_authenticate(user=self.sender)
        response = self.client.get('/api/messaging/conversations/')
        self.assertEqual(response.data['results'][0]['unread_count'], 0)


# ===========================================================================
# 5. SECURITY & ACCESS CONTROL
# ===========================================================================

class MessagingSecurityE2ETest(APITestCase):
    """E2E tests for messaging access control (Airbnb-level privacy)."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='sec_user1', password='P!', role='TENANT')
        self.user2 = User.objects.create_user(username='sec_user2', password='P!', role='OWNER')
        self.outsider = User.objects.create_user(username='sec_outsider', password='P!', role='TENANT')
        self.conv = Conversation.objects.create()
        self.conv.participants.add(self.user1, self.user2)
        Message.objects.create(conversation=self.conv, sender=self.user1, content='Private msg')

    def test_outsider_cannot_view_conversation(self):
        """Non-participant should get 404 (not 403, to avoid leaking existence)."""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/messaging/conversations/{self.conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_cannot_read_messages(self):
        """Non-participant should not access messages."""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/messaging/conversations/{self.conv.id}/messages/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_cannot_send_message(self):
        """Non-participant should not be able to inject a message."""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(
            f'/api/messaging/conversations/{self.conv.id}/send_message/',
            {'content': 'Injection attempt'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_cannot_mark_as_read(self):
        """Non-participant should not be able to mark messages as read."""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(
            f'/api/messaging/conversations/{self.conv.id}/mark_as_read/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_access_conversations(self):
        """Unauthenticated access should return 401."""
        response = self.client.get('/api/messaging/conversations/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# 6. FULL USER JOURNEY
# ===========================================================================

class MessagingUserJourneyE2ETest(APITestCase):
    """
    Complete end-to-end user journey simulating real-world messaging
    comparable to Airbnb's inquiry flow.
    """

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_full_inquiry_flow_tenant_to_owner(self):
        """
        Full Inquiry Flow (Airbnb-style):
        1. Tenant registers and logs in
        2. Owner has a property listed
        3. Tenant starts a conversation about the property
        4. Owner sees the conversation in their inbox with unread badge
        5. Owner reads messages (mark as read)
        6. Owner replies
        7. Tenant sees the reply and unread badge
        8. Both sides have full message history
        """
        # Setup: Owner with a property
        owner = User.objects.create_user(username='journey_owner', password='P!', role='OWNER')
        prop = Property.objects.create(
            owner=owner, title='Journey Villa', house_type='Villa',
            price=10000, description='Beautiful villa', location='Bole',
            bedrooms=3, bathrooms=2, max_guests=6, amenities='WiFi, Pool'
        )

        # Step 1: Tenant registers
        reg_resp = self.client.post('/api/auth/register/', {
            'username': 'journey_tenant', 'email': 'jt@test.com',
            'password': 'StrongPass123!', 'password2': 'StrongPass123!',
        })
        self.assertEqual(reg_resp.status_code, status.HTTP_201_CREATED)

        # Step 2: Tenant logs in
        token_resp = self.client.post('/api/auth/token/', {
            'username': 'journey_tenant', 'password': 'StrongPass123!',
        })
        tenant_token = token_resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tenant_token}')

        # Step 3: Tenant starts conversation
        start_resp = self.client.post('/api/messaging/conversations/start/', {
            'recipient_id': owner.id,
            'property_id': prop.id,
            'initial_message': 'Hi! Is this villa available next month?',
        })
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        conv_id = start_resp.data['id']

        # Step 4: Owner checks inbox – should see unread badge
        self.client.force_authenticate(user=owner)
        inbox_resp = self.client.get('/api/messaging/conversations/')
        self.assertEqual(len(inbox_resp.data['results']), 1)
        self.assertEqual(inbox_resp.data['results'][0]['unread_count'], 1)

        # Step 5: Owner reads messages
        read_resp = self.client.post(f'/api/messaging/conversations/{conv_id}/mark_as_read/')
        self.assertEqual(read_resp.status_code, status.HTTP_200_OK)

        # Step 6: Owner replies
        reply_resp = self.client.post(
            f'/api/messaging/conversations/{conv_id}/send_message/',
            {'content': 'Yes! It is available. Would you like to book?'}
        )
        self.assertEqual(reply_resp.status_code, status.HTTP_201_CREATED)

        # Step 7: Tenant checks inbox – should see unread reply
        tenant = User.objects.get(username='journey_tenant')
        self.client.force_authenticate(user=tenant)
        tenant_inbox = self.client.get('/api/messaging/conversations/')
        self.assertEqual(tenant_inbox.data['results'][0]['unread_count'], 1)

        # Step 8: Both see full history
        msgs_resp = self.client.get(f'/api/messaging/conversations/{conv_id}/messages/')
        self.assertEqual(len(msgs_resp.data), 2)
        self.assertEqual(msgs_resp.data[0]['content'], 'Hi! Is this villa available next month?')
        self.assertEqual(msgs_resp.data[1]['content'], 'Yes! It is available. Would you like to book?')

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_multi_conversation_isolation(self):
        """
        Two separate conversations between different user pairs
        should be completely isolated from each other.
        """
        user_a = User.objects.create_user(username='iso_a', password='P!', role='TENANT')
        user_b = User.objects.create_user(username='iso_b', password='P!', role='OWNER')
        user_c = User.objects.create_user(username='iso_c', password='P!', role='TENANT')

        # User A starts conv with User B
        self.client.force_authenticate(user=user_a)
        resp1 = self.client.post('/api/messaging/conversations/start/', {
            'recipient_id': user_b.id,
            'initial_message': 'A to B'
        })
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # User C starts conv with User B
        self.client.force_authenticate(user=user_c)
        resp2 = self.client.post('/api/messaging/conversations/start/', {
            'recipient_id': user_b.id,
            'initial_message': 'C to B'
        })
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)

        # User A should only see 1 conversation
        self.client.force_authenticate(user=user_a)
        inbox_a = self.client.get('/api/messaging/conversations/')
        self.assertEqual(len(inbox_a.data['results']), 1)

        # User B should see 2 conversations
        self.client.force_authenticate(user=user_b)
        inbox_b = self.client.get('/api/messaging/conversations/')
        self.assertEqual(len(inbox_b.data['results']), 2)

        # User C should only see 1 conversation
        self.client.force_authenticate(user=user_c)
        inbox_c = self.client.get('/api/messaging/conversations/')
        self.assertEqual(len(inbox_c.data['results']), 1)

        # User A cannot see User C's conversation
        conv_c_id = resp2.data['id']
        self.client.force_authenticate(user=user_a)
        snoop_resp = self.client.get(f'/api/messaging/conversations/{conv_c_id}/')
        self.assertEqual(snoop_resp.status_code, status.HTTP_404_NOT_FOUND)
