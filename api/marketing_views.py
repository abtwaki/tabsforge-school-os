"""Public marketing endpoints."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from schools.models import DemoLead


@api_view(['POST'])
@permission_classes([AllowAny])
def demo_request(request):
    """Receive a 'Book a Free Demo' lead from the marketing site."""
    data = request.data
    required = ['name', 'contact', 'email', 'phone']
    missing = [f for f in required if not data.get(f, '').strip()]
    if missing:
        return Response({'detail': f"Missing fields: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)
    DemoLead.objects.create(
        school_name=data.get('name', '').strip(),
        contact_name=data.get('contact', '').strip(),
        email=data.get('email', '').strip().lower(),
        phone=data.get('phone', '').strip(),
        student_count_range=data.get('students', '').strip(),
        message=data.get('message', '').strip(),
    )
    return Response({'detail': 'Demo request received.'}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def demo_leads(request):
    """List captured demo leads (platform admins only)."""
    if not (request.user.is_superuser or request.user.role == User.Roles.SUPER_ADMIN):
        return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
    rows = DemoLead.objects.all()[:200]
    return Response({
        'count': DemoLead.objects.count(),
        'results': [
            {
                'id': l.id,
                'school_name': l.school_name,
                'contact_name': l.contact_name,
                'email': l.email,
                'phone': l.phone,
                'student_count_range': l.student_count_range,
                'message': l.message,
                'contacted': l.contacted,
                'created_at': l.created_at,
            }
            for l in rows
        ],
    })


def _platform_admin(user):
    return user.is_superuser or user.role == User.Roles.SUPER_ADMIN


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def demo_lead_contact(request, pk):
    """Toggle a demo lead's contacted flag (platform admins only)."""
    if not _platform_admin(request.user):
        return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        lead = DemoLead.objects.get(pk=pk)
    except DemoLead.DoesNotExist:
        return Response({'detail': 'Lead not found.'}, status=404)
    lead.contacted = not lead.contacted if 'contacted' not in request.data else bool(request.data['contacted'])
    lead.save(update_fields=['contacted'])
    return Response({'id': lead.id, 'contacted': lead.contacted})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def demo_lead_delete(request, pk):
    """Remove a stale/demo lead (platform admins only)."""
    if not _platform_admin(request.user):
        return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        lead = DemoLead.objects.get(pk=pk)
    except DemoLead.DoesNotExist:
        return Response({'detail': 'Lead not found.'}, status=404)
    lead.delete()
    return Response({'detail': 'Lead removed.'})
