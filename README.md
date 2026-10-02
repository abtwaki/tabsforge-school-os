# TabsForge School OS — Django Backend

A tenant-aware, RBAC-backed REST API for managing schools, built with Django 4.2 LTS and Django REST Framework.

## Tech Stack

- Python 3.10+
- Django 4.2 LTS
- Django REST Framework
- django-environ, django-cors-headers
- drf-spectacular (OpenAPI/Swagger)
- PostgreSQL (`psycopg2-binary`)
- Gunicorn + WhiteNoise
- Pillow (school logos)

## Project Layout

- `project/` — Django project package (`settings`, `urls`, `wsgi:application`, `asgi`)
- `core/` — `TenantModel`, `TenantMiddleware`, base tenant permission
- `accounts/` — custom `User` (email login) with roles
- `schools/`, `academics/`, `students/`, `staff/`, `attendance/`, `gradebook/`, `finance/`, `communications/`, `library/`, `transport/`, `hostel/`, `notifications/` — domain apps
- `api/` — DRF serializers, viewsets, routers, auth endpoints, onboarding, tests
- `api/management/commands/seed_demo.py` — demo data command

## Local Setup

1. Create a virtual environment and install dependencies:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Copy environment variables and adjust them:

```bash
cp .env.example .env
```

3. Run migrations and create a superuser:

```bash
python manage.py migrate
python manage.py createsuperuser
```

4. Seed demo data:

```bash
python manage.py seed_demo
```

5. Start the development server:

```bash
python manage.py runserver
```

## API Endpoints

All endpoints are under `/api/` and require authentication unless marked public.

| Resource | Endpoint |
|----------|----------|
| Auth | `POST /api/auth/login/` (public) |
| Auth | `POST /api/auth/logout/` |
| Auth | `GET /api/auth/me/` |
| Health | `GET /api/health/` (public) |
| Onboarding | `POST /api/onboarding/` (public) |
| Onboarding | `GET /api/onboarding/check_subdomain/?subdomain=...` (public) |
| Schools | `/api/schools/` |
| Calendar | `/api/academic-sessions/`, `/api/terms/` |
| Academics | `/api/classes/`, `/api/sections/`, `/api/subjects/`, `/api/class-subjects/`, `/api/timetable/` |
| Students | `/api/students/`, `/api/guardians/`, `/api/enrollments/`, `/api/guardian-students/` |
| Staff | `/api/staff/` |
| Attendance | `/api/attendance/` |
| Gradebook | `/api/assessments/`, `/api/grades/`, `/api/report-cards/` |
| Finance | `/api/fee-categories/`, `/api/fee-structures/`, `/api/invoices/`, `/api/payments/` |
| Communications | `/api/announcements/`, `/api/notices/` |
| Library (Bloom+) | `/api/library/books/`, `/api/library/borrows/` |
| Transport (Summit) | `/api/transport/routes/`, `/api/transport/vehicles/`, `/api/transport/assignments/` |
| Hostel (Summit) | `/api/hostels/`, `/api/hostel/rooms/`, `/api/hostel/allocations/` |

Documentation:

- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`

## Multi-Tenancy

- Every tenant-scoped model inherits `core.models.TenantModel` and has a `school` FK.
- `TenantMiddleware` attaches `request.current_school` from the authenticated user's school.
- Super admins may optionally scope data via `?school_id=<id>`.
- Non-super-admin users see only their own school's data.

## RBAC

Permission classes are in `api/permissions.py`:

- `IsSuperAdmin`
- `IsSchoolAdmin`
- `IsStaff`
- `IsAccountant`
- `IsParent`
- `IsStudent`

Viewsets enforce object-level and list-level filtering:

- Parents see only their linked children.
- Students see only their own records.
- Staff see only assigned classes/subjects.
- Accountants see only finance data.
- School admins see everything in their school.
- Super admins see everything.

## Deployment (Ubuntu VPS)

Target directory: `/var/www/tabsforge-app`

On this server, Apache owns port 80/443 and Nginx cannot bind. The live
configuration therefore uses Apache as the reverse proxy for TabsForge and the
React SPA is served directly from disk.

Current live values:
- VPS IP: `37.59.205.38`
- Domain: `app.tabsforge.com` (add an A record pointing to `37.59.205.38`)
- Gunicorn: `127.0.0.1:8002`
- systemd unit: `tabsforge-app.service`
- Apache vhost: `/etc/apache2/sites-available/tabsforge-app.conf`

Quick commands to manage the deployment:

```bash
sudo systemctl status tabsforge-app
sudo systemctl restart tabsforge-app
sudo systemctl reload apache2
```

To deploy or redeploy from a local copy:

1. Install system dependencies:

```bash
sudo apt update
sudo apt install python3-pip python3-venv python3-dev libpq-dev libjpeg-dev \
    libpng-dev apache2 nodejs npm postgresql
```

2. Create the application directory and upload the backend files:

```bash
sudo mkdir -p /var/www/tabsforge-app
# Upload backend/ contents into /var/www/tabsforge-app
```

3. Create a virtual environment and install requirements:

```bash
cd /var/www/tabsforge-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. Create a PostgreSQL database and user:

```bash
sudo -u postgres psql -c "CREATE USER tabsforge_user WITH PASSWORD 'your-secure-password';"
sudo -u postgres psql -c "CREATE DATABASE tabsforge_db OWNER tabsforge_user;"
sudo -u postgres psql -c "ALTER USER tabsforge_user CREATEDB;"
```

5. Create `/var/www/tabsforge-app/.env`:

```env
DEBUG=False
SECRET_KEY=your-very-secure-secret-key
DATABASE_URL=postgres://tabsforge_user:your-secure-password@localhost:5432/tabsforge_db
PORT=8002
ALLOWED_HOSTS=app.tabsforge.com,37.59.205.38,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://app.tabsforge.com,https://app.tabsforge.com
CORS_ALLOWED_ORIGINS=http://app.tabsforge.com,https://app.tabsforge.com
CORS_ALLOW_ALL_ORIGINS=False
TIME_ZONE=Africa/Lagos
CONN_MAX_AGE=60
LOG_LEVEL=INFO
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

6. Run migrations, collect static files, and seed demo data:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_demo
```

7. Build the React frontend:

```bash
cd /var/www/tabsforge-app/frontend
npm install
npm run build
```

8. Create the Gunicorn systemd service (`/etc/systemd/system/tabsforge-app.service`):

```ini
[Unit]
Description=TabsForge App
After=network.target postgresql.service

[Service]
WorkingDirectory=/var/www/tabsforge-app
EnvironmentFile=/var/www/tabsforge-app/.env
ExecStart=/var/www/tabsforge-app/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8002 project.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

9. Configure Apache (`/etc/apache2/sites-available/tabsforge-app.conf`):

```apache
<VirtualHost *:80>
    ServerName app.tabsforge.com

    DocumentRoot /var/www/tabsforge-app/frontend/dist
    <Directory /var/www/tabsforge-app/frontend/dist>
        Require all granted
        Options -Indexes
    </Directory>

    ProxyPass /static/ !
    Alias /static/ /var/www/tabsforge-app/staticfiles/
    <Directory /var/www/tabsforge-app/staticfiles>
        Require all granted
    </Directory>

    ProxyPass /media/ !
    Alias /media/ /var/www/tabsforge-app/media/
    <Directory /var/www/tabsforge-app/media>
        Require all granted
    </Directory>

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "http"
    ProxyPass /admin/ http://127.0.0.1:8002/admin/
    ProxyPassReverse /admin/ http://127.0.0.1:8002/admin/
    ProxyPass /api/ http://127.0.0.1:8002/api/
    ProxyPassReverse /api/ http://127.0.0.1:8002/api/

    <Directory /var/www/tabsforge-app/frontend/dist>
        RewriteEngine On
        RewriteBase /
        RewriteCond %{REQUEST_URI} !^/static/
        RewriteCond %{REQUEST_URI} !^/media/
        RewriteCond %{REQUEST_URI} !^/api/
        RewriteCond %{REQUEST_URI} !^/admin/
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule . /index.html [L]
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/tabsforge-app-error.log
    CustomLog ${APACHE_LOG_DIR}/tabsforge-app-access.log combined
</VirtualHost>
```

10. Enable modules, site and reload Apache:

```bash
sudo a2enmod proxy proxy_http headers rewrite
sudo a2ensite tabsforge-app.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

11. Start the app service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tabsforge-app
sudo systemctl start tabsforge-app
```

12. (Optional) Use Certbot for HTTPS:

```bash
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d app.tabsforge.com
```

After Certbot, update `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and
`CSRF_COOKIE_SECURE` to `True` in `.env` and restart `tabsforge-app`.

## Production Security Checklist

- Change the demo credentials created by `seed_demo`.
- Rotate the PostgreSQL `tabsforge_user` password and update `.env`.
- Rotate the VPS root password.
- Replace stub notification providers in `notifications/providers.py` with real
  SMS/email gateways before sending live messages.
- Keep `.env` readable only by the service user (`chmod 600`).

## Running Tests

```bash
python manage.py test
```

Key tests in `api/tests.py` prove that School A's admin cannot access School B's data.

## Notes & Assumptions

- The custom `User` uses `email` as the username field; the legacy `username` column has been removed.
- Notification providers (`notifications/providers.py`) are stubs and should be replaced with real SMS/email gateways before production.
- Library features require the `Bloom` tier or above; Transport and Hostel require `Summit`.
- Tier enforcement is applied at the API viewset level.
- The onboarding endpoint is public by design; protect it with additional rate limiting or approval flows if needed.
