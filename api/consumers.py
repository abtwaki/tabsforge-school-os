"""WebSocket consumers for real-time chat and notification badges.

Auth: the SPA connects with ``?token=<DRF token>`` since browsers cannot set
custom headers on WebSocket handshakes. The token is resolved to a User in
``connect``; unauthenticated sockets are rejected.

Groups joined per socket:
  - ``user_<id>``      — per-user channel for badge/unread notifications
  - ``conv_<id>``      — one group per conversation the user participates in
"""
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = await self._authenticate()
        if user is None or not user.is_active:
            await self.close(code=4401)
            return
        self.user = user
        self.conversation_ids = await self._conversation_ids(user)

        await self.channel_layer.group_add(f'user_{user.id}', self.channel_name)
        for conv_id in self.conversation_ids:
            await self.channel_layer.group_add(f'conv_{conv_id}', self.channel_name)
        await self.accept()
        await self.send_json({
            'type': 'connected',
            'conversations': self.conversation_ids,
        })

    async def disconnect(self, close_code):
        if getattr(self, 'user', None):
            await self.channel_layer.group_discard(
                f'user_{self.user.id}', self.channel_name,
            )
            for conv_id in getattr(self, 'conversation_ids', []):
                await self.channel_layer.group_discard(
                    f'conv_{conv_id}', self.channel_name,
                )

    async def receive_json(self, content, **kwargs):
        """Handle client commands.

        ``{"action": "join", "conversation": <id>}`` joins a newly created
        conversation group after membership is verified.
        """
        action = content.get('action')
        if action == 'join':
            conv_id = content.get('conversation')
            if conv_id and await self._is_member(conv_id):
                await self.channel_layer.group_add(
                    f'conv_{conv_id}', self.channel_name,
                )
                self.conversation_ids.append(conv_id)
                await self.send_json({'type': 'joined', 'conversation': conv_id})
        elif action == 'ping':
            await self.send_json({'type': 'pong'})

    # Event handlers called by channel-layer broadcasts -------------------

    async def chat_message(self, event):
        await self.send_json({
            'type': 'chat.message',
            'message': event['message'],
        })

    async def chat_notify(self, event):
        await self.send_json({
            'type': 'chat.notify',
            'conversation_id': event['conversation_id'],
            'message': event['message'],
        })

    # Helpers -------------------------------------------------------------

    @database_sync_to_async
    def _authenticate(self):
        qs = parse_qs(self.scope['query_string'].decode())
        key = (qs.get('token') or [''])[0]
        if not key:
            return None
        try:
            return Token.objects.select_related('user').get(key=key).user
        except Token.DoesNotExist:
            return None

    @database_sync_to_async
    def _conversation_ids(self, user):
        from messaging.models import Conversation
        return list(
            Conversation.objects.filter(
                school=user.school, memberships__user=user,
            ).values_list('id', flat=True)
        )

    @database_sync_to_async
    def _is_member(self, conv_id):
        from messaging.models import ConversationParticipant
        return ConversationParticipant.objects.filter(
            conversation_id=conv_id, user=self.user,
        ).exists()
