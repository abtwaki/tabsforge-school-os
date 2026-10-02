"""Tenant-scoped internal messaging: 1:1 and group conversations."""
from django.db import models

from core.models import TenantModel


class Conversation(TenantModel):
    """A conversation thread — may be 1:1 or a named group."""
    name = models.CharField(
        max_length=200, blank=True,
        help_text='Group name (blank for 1:1 chats)',
    )
    is_group = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, related_name='created_conversations',
    )
    participants = models.ManyToManyField(
        'accounts.User',
        through='ConversationParticipant',
        related_name='conversations',
    )

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Conversation'

    def __str__(self):
        if self.is_group:
            return f"Group: {self.name or self.pk} ({self.school})"
        return f"1:1 conversation ({self.school})"

    @property
    def display_name(self):
        return self.name if self.is_group else '1:1 Chat'


class ConversationParticipant(TenantModel):
    """Membership of a user in a conversation."""
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='memberships',
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='conversation_memberships',
    )
    is_admin = models.BooleanField(default=False)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['school', 'conversation', 'user']]
        verbose_name = 'Conversation Participant'

    def __str__(self):
        return f"{self.user} in {self.conversation}"

    @property
    def unread_count(self):
        qs = self.conversation.messages.filter(
            sender__isnull=False,
        )
        if self.last_read_at:
            qs = qs.filter(created_at__gt=self.last_read_at)
        return qs.exclude(sender=self.user).count()


class Message(TenantModel):
    """A single message within a conversation."""
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages',
    )
    sender = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, related_name='sent_messages',
    )
    content = models.TextField()
    attachment = models.FileField(
        upload_to='messaging/attachments/', blank=True, null=True,
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message'

    def __str__(self):
        return f"Message from {self.sender} in {self.conversation}"
