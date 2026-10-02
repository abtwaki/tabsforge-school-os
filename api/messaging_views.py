"""Tenant-scoped internal messaging API."""
import logging
from datetime import timezone as dt_tz

from django.utils import timezone
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import Class
from accounts.models import User
from core.utils import filter_by_school, get_current_school
from messaging.models import Conversation, ConversationParticipant, Message

logger = logging.getLogger(__name__)

# Internal (staff-side) roles that can converse with each other and with
# families. Families (parents/students) can only message internal roles —
# never each other.
INTERNAL_ROLES = {
    User.Roles.SUPER_ADMIN,
    User.Roles.GROUP_OWNER,
    User.Roles.SCHOOL_ADMIN,
    User.Roles.PRINCIPAL,
    User.Roles.VICE_PRINCIPAL,
    User.Roles.ADMISSIONS_OFFICER,
    User.Roles.TEACHER,
    User.Roles.FORM_TEACHER,
    User.Roles.EXAM_OFFICER,
    User.Roles.HR_ADMIN,
    User.Roles.LIBRARIAN,
    User.Roles.STAFF,
    User.Roles.ACCOUNTANT,
}
FAMILY_ROLES = {User.Roles.PARENT, User.Roles.STUDENT}


def _can_message(user_a, user_b):
    """Messaging matrix: internal↔internal and family↔internal only."""
    a_internal = user_a.role in INTERNAL_ROLES
    b_internal = user_b.role in INTERNAL_ROLES
    if a_internal and b_internal:
        return True
    if user_a.role in FAMILY_ROLES and b_internal:
        return True
    if user_b.role in FAMILY_ROLES and a_internal:
        return True
    return False


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

class ParticipantSerializer(drf_serializers.ModelSerializer):
    user_name = drf_serializers.CharField(source='user.full_name', read_only=True)
    user_role = drf_serializers.CharField(source='user.role', read_only=True)
    unread_count = drf_serializers.SerializerMethodField()

    class Meta:
        model = ConversationParticipant
        fields = ['id', 'user', 'user_name', 'user_role', 'is_admin', 'last_read_at', 'unread_count']

    def get_unread_count(self, obj):
        return obj.unread_count


class MessageSerializer(drf_serializers.ModelSerializer):
    sender_name = drf_serializers.CharField(source='sender.full_name', read_only=True, allow_null=True)
    sender_role = drf_serializers.CharField(source='sender.role', read_only=True, allow_null=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'sender_name', 'sender_role',
                  'content', 'attachment', 'is_deleted', 'created_at', 'updated_at']
        read_only_fields = ['id', 'sender', 'sender_name', 'sender_role', 'created_at', 'updated_at']


class ConversationSerializer(drf_serializers.ModelSerializer):
    participants_detail = drf_serializers.SerializerMethodField()
    last_message = drf_serializers.SerializerMethodField()
    my_unread = drf_serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'school', 'name', 'is_group', 'created_by',
                  'participants_detail', 'last_message', 'my_unread',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'school', 'created_by', 'created_at', 'updated_at']

    def get_participants_detail(self, obj):
        memberships = obj.memberships.select_related('user').all()
        return ParticipantSerializer(memberships, many=True).data

    def get_last_message(self, obj):
        msg = obj.messages.filter(is_deleted=False).last()
        if msg:
            return MessageSerializer(msg).data
        return None

    def get_my_unread(self, obj):
        request = self.context.get('request')
        if request:
            membership = obj.memberships.filter(user=request.user).first()
            return membership.unread_count if membership else 0
        return 0


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------

class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # User can only see conversations they participate in
        return Conversation.objects.filter(
            school=user.school,
            memberships__user=user,
        ).distinct().order_by('-updated_at')

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        conv = serializer.save(school=school, created_by=self.request.user)
        # Add creator as admin participant
        ConversationParticipant.objects.get_or_create(
            school=school, conversation=conv, user=self.request.user,
            defaults={'is_admin': True},
        )

    @action(detail=False, methods=['post'], url_path='start-dm')
    def start_dm(self, request):
        """Start a 1:1 conversation with another user."""
        other_id = request.data.get('user_id')
        school = get_current_school(request)
        if not other_id or not school:
            return Response({'error': 'user_id is required.'}, status=400)

        try:
            other = User.objects.get(pk=other_id, school=school)
        except User.DoesNotExist:
            return Response({'error': 'User not found in this school.'}, status=404)

        if not _can_message(request.user, other):
            return Response(
                {'error': f"Messaging between {request.user.role} and {other.role} is not permitted."},
                status=403,
            )

        # Check for existing 1:1 between these two users
        existing = (
            Conversation.objects
            .filter(school=school, is_group=False,
                    memberships__user=request.user)
            .filter(memberships__user=other)
            .first()
        )
        if existing:
            return Response(ConversationSerializer(existing, context={'request': request}).data)

        conv = Conversation.objects.create(school=school, is_group=False, created_by=request.user)
        for u in [request.user, other]:
            ConversationParticipant.objects.create(
                school=school, conversation=conv, user=u,
                is_admin=(u == request.user),
            )
        return Response(
            ConversationSerializer(conv, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='contacts')
    def contacts(self, request):
        """List users the caller may start a chat with (role-pair enforced)."""
        school = get_current_school(request) or request.user.school
        qs = User.objects.filter(school=school, is_active=True).exclude(pk=request.user.pk)
        contacts = [
            {
                'id': u.id, 'name': u.full_name, 'email': u.email,
                'role': u.role, 'role_label': u.get_role_display(),
            }
            for u in qs if _can_message(request.user, u)
        ]
        # Staff/teaching roles may also broadcast to all parents of their classes.
        staff_profile = getattr(request.user, 'staff_profile', None)
        can_class_broadcast = bool(
            request.user.role in INTERNAL_ROLES
            and (staff_profile is None or request.user.role in User.TEACHING_ROLES
                 or request.user.role in User.ADMIN_LIKE_ROLES
                 or request.user.role in {User.Roles.SCHOOL_ADMIN, User.Roles.SUPER_ADMIN})
        )
        return Response({'contacts': contacts, 'can_class_broadcast': can_class_broadcast})

    @action(detail=False, methods=['post'], url_path='message-class-parents')
    def message_class_parents(self, request):
        """Staff → group chat with every parent of pupils in their class(es).

        `class_id` is optional — without it, all classes assigned to the
        caller's staff profile are used (or all classes for admins).
        """
        user = request.user
        if user.role not in INTERNAL_ROLES:
            return Response({'error': 'Only staff can message class parents.'}, status=403)
        school = get_current_school(request) or user.school

        classes = Class.objects.filter(school=school)
        class_id = request.data.get('class_id')
        staff_profile = getattr(user, 'staff_profile', None)
        # Admin-like roles may broadcast to any class; teachers are limited
        # to their assigned classes (and must have at least one assigned).
        unrestricted = (
            user.is_superuser
            or user.role in User.ADMIN_LIKE_ROLES
            or user.role in {User.Roles.EXAM_OFFICER, User.Roles.SUPER_ADMIN}
        )
        if class_id:
            classes = classes.filter(pk=class_id)
            if not classes.exists():
                return Response({'error': 'Class not found in this school.'}, status=404)
            if not unrestricted:
                assigned = staff_profile.assigned_classes.values('pk') if staff_profile else []
                if not classes.filter(pk__in=assigned).exists():
                    return Response(
                        {'error': 'You can only message parents of your assigned classes.'},
                        status=403)
        elif not unrestricted:
            assigned = staff_profile.assigned_classes.values('pk') if staff_profile else []
            if staff_profile is not None and staff_profile.assigned_classes.exists():
                classes = classes.filter(pk__in=assigned)
            else:
                return Response(
                    {'error': 'No classes assigned to you. Ask an admin to assign classes first.'},
                    status=400,
                )

        parents = User.objects.filter(
            school=school, role=User.Roles.PARENT, is_active=True,
            guardian_profile__wards__student__enrollments__section__school_class__in=classes,
            guardian_profile__wards__student__enrollments__status='active',
        ).distinct()

        if not parents.exists():
            return Response(
                {'error': 'No parents with accounts found for those classes.'},
                status=404,
            )

        class_names = ', '.join(c.name for c in classes[:4])
        conv = Conversation.objects.create(
            school=school, is_group=True,
            name=request.data.get('name') or f'Class Parents — {class_names}',
            created_by=user,
        )
        ConversationParticipant.objects.create(
            school=school, conversation=conv, user=user, is_admin=True,
        )
        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(school=school, conversation=conv, user=p)
            for p in parents
        ])
        return Response(
            ConversationSerializer(conv, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='add-member')
    def add_member(self, request, pk=None):
        conv = self.get_object()
        if not conv.is_group:
            return Response({'error': 'Cannot add members to a 1:1 conversation.'}, status=400)
        user_id = request.data.get('user_id')
        school = conv.school
        try:
            user = User.objects.get(pk=user_id, school=school)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=404)
        ConversationParticipant.objects.get_or_create(
            school=school, conversation=conv, user=user, defaults={'is_admin': False},
        )
        return Response({'detail': f'{user.full_name} added to conversation.'})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        conv = self.get_object()
        membership = conv.memberships.filter(user=request.user).first()
        if membership:
            membership.last_read_at = timezone.now()
            membership.save(update_fields=['last_read_at'])
        return Response({'detail': 'Marked as read.'})


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        conv_id = self.request.query_params.get('conversation')
        since = self.request.query_params.get('since')

        qs = Message.objects.filter(
            school=user.school,
            conversation__memberships__user=user,
            is_deleted=False,
        ).distinct()

        if conv_id:
            qs = qs.filter(conversation_id=conv_id)
        if since:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(since)
            if dt:
                qs = qs.filter(created_at__gt=dt)
        return qs.order_by('created_at')

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        conv = serializer.validated_data.get('conversation')

        # Ensure sender is a participant
        if not conv.memberships.filter(user=self.request.user).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You are not a participant of this conversation.')

        msg = serializer.save(school=school, sender=self.request.user)

        # Update conversation updated_at for ordering
        conv.save(update_fields=['updated_at'])
        _broadcast_message(conv, msg)


def _broadcast_message(conv, msg):
    """Push a new message to WebSocket subscribers (best-effort).

    When the channel layer is unavailable (e.g. Redis not running yet) this
    degrades silently — the message is already persisted and polling still
    works.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer is None:
            return
        payload = MessageSerializer(msg).data
        async_to_sync(layer.group_send)(
            f'conv_{conv.id}',
            {'type': 'chat.message', 'message': payload},
        )
        for user_id in conv.memberships.values_list('user_id', flat=True):
            async_to_sync(layer.group_send)(
                f'user_{user_id}',
                {
                    'type': 'chat.notify',
                    'conversation_id': conv.id,
                    'message': payload,
                },
            )
    except Exception:
        logger.exception('WebSocket broadcast failed for message %s', msg.id)
