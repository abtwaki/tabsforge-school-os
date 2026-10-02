"""
TabsForge AI Suite — multi-provider (Gemini → Grok → Claude fallback chain).

Providers are tried in the order given by settings.AI_PROVIDERS; a provider is
skipped when its API key is not configured, so the platform can run on
whichever key(s) are available.

Features:
- AI admissions assistant (evaluate application quality, suggest follow-up questions)
- AI fee debtor alerts (generate tailored reminder messages)
- AI lesson plan generator
- AI report card comment generator
"""
import json
import logging
import urllib.request

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.utils import get_current_school

logger = logging.getLogger(__name__)

_AI_TIMEOUT = 45


def _post_json(url, payload, headers=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=_AI_TIMEOUT) as resp:
        return json.loads(resp.read())


def _call_gemini(prompt, max_tokens):
    key = getattr(settings, 'GEMINI_API_KEY', '')
    if not key:
        return None, None
    model = getattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash')
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model}:generateContent?key={key}'
    )
    try:
        data = _post_json(url, {
            'contents': [{'parts': [{'text': prompt}]}],
            # Thinking models burn tokens on reasoning — floor the budget.
            'generationConfig': {
                'maxOutputTokens': max(max_tokens, 1024),
                'temperature': 0.4,
            },
        })
        parts = data['candidates'][0]['content'].get('parts') or []
        text = ''.join(p.get('text', '') for p in parts).strip()
        if not text:
            return None, 'Gemini returned an empty response'
        return text, None
    except Exception as exc:
        logger.exception('Gemini API error: %s', exc)
        return None, str(exc)


def _call_grok(prompt, max_tokens):
    key = getattr(settings, 'GROK_API_KEY', '')
    if not key:
        return None, None
    model = getattr(settings, 'GROK_MODEL', 'grok-3-mini')
    try:
        data = _post_json('https://api.x.ai/v1/chat/completions', {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': max_tokens,
            'temperature': 0.4,
        }, headers={'Authorization': f'Bearer {key}'})
        return data['choices'][0]['message']['content'], None
    except Exception as exc:
        logger.exception('Grok API error: %s', exc)
        return None, str(exc)


def _call_anthropic(prompt, max_tokens):
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        return None, None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=getattr(settings, 'ANTHROPIC_MODEL', 'claude-haiku-4-5'),
            max_tokens=max_tokens,
            messages=[{'role': 'user', 'content': prompt}],
        )
        return message.content[0].text, None
    except Exception as exc:
        logger.exception('Anthropic API error: %s', exc)
        return None, str(exc)


_AI_PROVIDERS = {
    'gemini': _call_gemini,
    'grok': _call_grok,
    'anthropic': _call_anthropic,
}


def _call_ai(prompt, max_tokens=1024):
    """Try each configured provider in order; return (text, error)."""
    errors = []
    for name in getattr(settings, 'AI_PROVIDERS', _AI_PROVIDERS.keys()):
        fn = _AI_PROVIDERS.get(name)
        if fn is None:
            continue
        text, err = fn(prompt, max_tokens)
        if text:
            return text, None
        if err:
            errors.append(f'{name}: {err}')
    if not errors:
        return None, (
            'AI features need an API key — set GEMINI_API_KEY, GROK_API_KEY, '
            'or ANTHROPIC_API_KEY in the server environment.'
        )
    return None, 'All configured AI providers failed — ' + '; '.join(errors)


# ---------------------------------------------------------------------------
# AI Admissions Assistant
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_admissions_assistant(request):
    """
    Evaluate an admission application and suggest review notes.

    POST body: { "application_id": <int> }
    """
    school = get_current_school(request)
    app_id = request.data.get('application_id')
    if not app_id:
        return Response({'error': 'application_id is required.'}, status=400)

    from admissions.models import Application
    try:
        app = Application.objects.get(pk=app_id, school=school)
    except Application.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=404)

    prompt = f"""You are an experienced school admissions officer at a Nigerian school.
Review this student application and provide:
1. A brief assessment of the applicant (2-3 sentences)
2. 3 suggested interview questions
3. Any concerns or areas to verify
4. A recommendation: Approve, Further Review Needed, or Decline

Application Details:
- Name: {app.first_name} {app.last_name}
- Date of Birth: {app.date_of_birth}
- Gender: {app.gender}
- Applying for: {app.applying_for_class}
- Previous School: {app.previous_school or 'Not provided'}
- Previous Class: {app.previous_class or 'Not provided'}
- Guardian: {app.guardian_name} ({app.guardian_relationship})

Respond in a professional, structured format."""

    text, error = _call_ai(prompt, max_tokens=800)
    if error:
        return Response({'error': error}, status=503)
    return Response({'assessment': text, 'application_id': app_id})


# ---------------------------------------------------------------------------
# AI Fee Debtor Alerts
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_debtor_alert(request):
    """
    Generate a personalised payment reminder message for a fee debtor.

    POST body: { "invoice_id": <int> }
    """
    school = get_current_school(request)
    invoice_id = request.data.get('invoice_id')
    if not invoice_id:
        return Response({'error': 'invoice_id is required.'}, status=400)

    from finance.models import Invoice
    try:
        inv = Invoice.objects.select_related('student', 'term').get(pk=invoice_id, school=school)
    except Invoice.DoesNotExist:
        return Response({'error': 'Invoice not found.'}, status=404)

    days_overdue = 0
    from datetime import date
    if inv.due_date < date.today():
        days_overdue = (date.today() - inv.due_date).days

    prompt = f"""Generate a polite but firm payment reminder message for a Nigerian school fee debtor.

Student: {inv.student.first_name} {inv.student.last_name}
Amount Outstanding: ₦{inv.balance:,.2f}
Term: {inv.term.name}
Days Overdue: {days_overdue}
School: {school.name}

Write:
1. A WhatsApp/SMS message (under 160 characters) for the parent/guardian
2. A formal email reminder (3-4 sentences)
3. Suggested next action if payment is not received within 7 days

Keep the tone respectful and professional, appropriate for a Nigerian school context."""

    text, error = _call_ai(prompt, max_tokens=600)
    if error:
        return Response({'error': error}, status=503)
    return Response({'reminder': text, 'invoice_id': invoice_id})


# ---------------------------------------------------------------------------
# AI Lesson Plan Generator
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_lesson_plan(request):
    """
    Generate a complete lesson plan.

    POST body: {
        "subject": "Mathematics",
        "class_level": "JSS 2",
        "topic": "Algebraic Expressions",
        "duration_minutes": 45,
        "objectives": "optional teacher-supplied learning objectives"
    }
    """
    subject = request.data.get('subject', '')
    class_level = request.data.get('class_level', '')
    topic = request.data.get('topic', '')
    duration = request.data.get('duration_minutes', 45)
    objectives = request.data.get('objectives', '')

    if not all([subject, class_level, topic]):
        return Response({'error': 'subject, class_level, and topic are required.'}, status=400)

    prompt = f"""Create a detailed, practical lesson plan for a Nigerian school classroom.

Subject: {subject}
Class Level: {class_level}
Topic: {topic}
Duration: {duration} minutes
{'Additional Objectives: ' + objectives if objectives else ''}

Structure the plan with these sections:
1. Learning Objectives (3-4 measurable outcomes)
2. Materials / Resources needed
3. Introduction / Motivation (5 min) — how to engage students
4. Development / Main Activity (step-by-step, with timing)
5. Class Activity / Worked Examples
6. Assessment / Class Exercise
7. Conclusion / Summary
8. Assignment / Homework

Align with the Nigerian curriculum (NERDC). Be specific, practical, and suitable for a class of 30-35 students."""

    text, error = _call_ai(prompt, max_tokens=1500)
    if error:
        return Response({'error': error}, status=503)
    return Response({'lesson_plan': text})


# ---------------------------------------------------------------------------
# AI Report Card Comment Generator
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_report_comment(request):
    """
    Generate personalised report card comments for a student.

    POST body: {
        "student_name": "Amina Ibrahim",
        "class_level": "SS 2 Science",
        "average_score": 72.5,
        "position": 4,
        "class_size": 30,
        "subjects": [{"name": "Mathematics", "score": 78, "grade": "B2"}, ...]
        "type": "teacher" | "principal"
    }
    """
    student_name = request.data.get('student_name', '')
    class_level = request.data.get('class_level', '')
    average = request.data.get('average_score', 0)
    position = request.data.get('position', '')
    class_size = request.data.get('class_size', '')
    subjects = request.data.get('subjects', [])
    comment_type = request.data.get('type', 'teacher')

    if not student_name:
        return Response({'error': 'student_name is required.'}, status=400)

    subjects_text = ', '.join(
        f"{s['name']} ({s['score']}%, {s.get('grade', '')})"
        for s in subjects[:10]
    ) if subjects else 'not provided'

    prompt = f"""Generate a {'class teacher' if comment_type == 'teacher' else 'principal'} report card comment for a Nigerian secondary school student.

Student: {student_name}
Class: {class_level}
Term Average: {average:.1f}%
Class Position: {position} out of {class_size}
Subject Performance: {subjects_text}

Requirements:
- 40-60 words
- Warm, professional, encouraging Nigerian school tone
- Acknowledge specific strengths
- Give one area for improvement
- End with encouragement
- Do NOT start with the student's name
- Do NOT use generic phrases like "has done well"

Write only the comment text, nothing else."""

    text, error = _call_ai(prompt, max_tokens=200)
    if error:
        return Response({'error': error}, status=503)
    return Response({'comment': text.strip()})


# ---------------------------------------------------------------------------
# AI Timetable Conflict Detector (rule-based, no AI needed)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_timetable_conflicts(request):
    """
    Detect conflicts in proposed timetable entries.

    POST body: {
        "entries": [
            {
                "teacher_id": 1,
                "section_id": 1,
                "subject_id": 1,
                "day": "monday",
                "start_time": "08:00",
                "end_time": "09:00",
                "room": "Room 1"
            }, ...
        ]
    }
    """
    from datetime import time as dtime
    school = get_current_school(request)
    entries = [dict(e, existing=False) for e in request.data.get('entries', [])]
    conflicts = []

    # Also compare proposed entries against persisted timetable rows for the
    # same days (unless the caller opted out).
    if request.data.get('check_existing', True) and school is not None:
        from academics.models import Timetable
        days = {e.get('day') for e in entries if e.get('day')}
        existing = Timetable.objects.filter(school=school, day__in=days)
        exclude_ids = {e.get('id') for e in entries if e.get('id')}
        for t in existing.select_related('section', 'subject', 'teacher'):
            if t.id in exclude_ids:
                continue
            entries.append({
                'id': t.id,
                'existing': True,
                'label': str(t),
                'teacher_id': t.teacher_id,
                'section_id': t.section_id,
                'subject_id': t.subject_id,
                'day': t.day,
                'start_time': t.start_time.strftime('%H:%M'),
                'end_time': t.end_time.strftime('%H:%M'),
                'room': t.room,
            })

    def parse_time(s):
        h, m = map(int, str(s).split(':')[:2])
        return dtime(h, m)

    def overlaps(s1, e1, s2, e2):
        return s1 < e2 and s2 < e1

    for i, a in enumerate(entries):
        for j, b in enumerate(entries):
            if i >= j:
                continue
            if a.get('day') != b.get('day'):
                continue
            try:
                as_, ae_ = parse_time(a['start_time']), parse_time(a['end_time'])
                bs_, be_ = parse_time(b['start_time']), parse_time(b['end_time'])
            except Exception:
                continue
            if not overlaps(as_, ae_, bs_, be_):
                continue

            def detail(other):
                if other.get('existing'):
                    return f" (conflicts with existing: {other.get('label')})"
                return ''

            # Check teacher double-booking
            if a.get('teacher_id') and a['teacher_id'] == b.get('teacher_id'):
                conflicts.append({
                    'type': 'teacher_conflict',
                    'message': (
                        f"Teacher assigned to two slots at the same time on "
                        f"{a['day'].title()}{detail(a if a.get('existing') else b)}"
                    ),
                    'entries': [i, j],
                })
            # Check room conflict
            if a.get('room') and a['room'] == b.get('room'):
                conflicts.append({
                    'type': 'room_conflict',
                    'message': (
                        f"Room '{a['room']}' double-booked on "
                        f"{a['day'].title()}{detail(a if a.get('existing') else b)}"
                    ),
                    'entries': [i, j],
                })
            # Check class/section conflict
            if a.get('section_id') and a['section_id'] == b.get('section_id'):
                conflicts.append({
                    'type': 'section_conflict',
                    'message': (
                        f"Section scheduled for two subjects at the same time on "
                        f"{a['day'].title()}{detail(a if a.get('existing') else b)}"
                    ),
                    'entries': [i, j],
                })

    return Response({
        'conflicts': conflicts,
        'has_conflicts': len(conflicts) > 0,
        'entries_checked': len(entries),
    })


# ---------------------------------------------------------------------------
# Generic AI chat — used by the frontend assistant; server chain first,
# browser-side Puter.js (Grok) fallback handled client-side.
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_chat(request):
    """
    POST body: { "prompt": "...", "max_tokens": 1024 }
    Returns { "text": "...", "provider": "<name>" }
    """
    prompt = (request.data.get('prompt') or '').strip()
    if not prompt:
        return Response({'error': 'prompt is required.'}, status=400)
    max_tokens = int(request.data.get('max_tokens') or 1024)
    text, error = _call_ai(prompt, max_tokens=min(max_tokens, 4096))
    if error:
        return Response({'error': error}, status=503)
    return Response({'text': text})
