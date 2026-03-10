# TimeWise - Time Tracking & Billing SaaS

A production-grade time tracking and billing platform built with Django REST Framework and React. TimeWise enables teams to track time, manage projects, invoice clients, monitor expenses, and analyze profitability -- all in one place.

## Features

- **Time Tracking**: Start/stop timers, manual time entries, calendar and weekly views
- **Project Management**: Project-based tracking with budgets, tasks, and team assignments
- **Client Billing**: Flexible billing rates (hourly, fixed, per-project), multi-currency support
- **Invoicing**: Generate professional PDF invoices, track payments, send reminders
- **Expense Tracking**: Log expenses with receipt uploads, categorization, and reimbursement workflows
- **Team Timesheets**: Weekly timesheet submissions with multi-level approval workflows
- **Profitability Reports**: Real-time profitability analysis, utilization rates, budget tracking
- **Multi-Organization**: Full multi-tenancy with organization-level isolation

## Tech Stack

| Layer        | Technology                          |
|-------------|-------------------------------------|
| Backend     | Django 5.0, Django REST Framework   |
| Frontend    | React 18, Redux Toolkit, Recharts   |
| Database    | PostgreSQL 16                       |
| Cache/Queue | Redis 7, Celery 5                   |
| Proxy       | Nginx                               |
| Container   | Docker, Docker Compose              |

## Architecture

```
                    +----------+
                    |  Nginx   |
                    +----+-----+
                         |
              +----------+----------+
              |                     |
        +-----+-----+        +-----+-----+
        | React SPA |        | Django API |
        | (port 3000)|       | (port 8000)|
        +-----------+        +-----+-----+
                                   |
                    +--------------+--------------+
                    |              |              |
              +-----+----+  +----+-----+  +-----+-----+
              |PostgreSQL |  |  Redis   |  |  Celery   |
              |(port 5432)|  |(port 6379)|  |  Worker   |
              +----------+  +----------+  +-----------+
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourorg/timewise.git
cd timewise
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Build and start all services:
```bash
docker-compose up --build
```

4. Run database migrations:
```bash
docker-compose exec backend python manage.py migrate
```

5. Create a superuser:
```bash
docker-compose exec backend python manage.py createsuperuser
```

6. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/api/
   - Admin Panel: http://localhost:8000/admin/
   - API Documentation: http://localhost:8000/api/docs/

## Development Setup (without Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm start
```

## API Endpoints

### Authentication
| Method | Endpoint                  | Description          |
|--------|--------------------------|----------------------|
| POST   | /api/auth/register/      | Register new user    |
| POST   | /api/auth/login/         | Obtain JWT tokens    |
| POST   | /api/auth/refresh/       | Refresh access token |
| POST   | /api/auth/logout/        | Blacklist token      |

### Time Entries
| Method | Endpoint                       | Description               |
|--------|--------------------------------|---------------------------|
| GET    | /api/time-entries/             | List time entries         |
| POST   | /api/time-entries/             | Create time entry         |
| POST   | /api/time-entries/start-timer/ | Start a timer             |
| POST   | /api/time-entries/{id}/stop/   | Stop a running timer      |
| GET    | /api/time-entries/running/     | Get running timers        |
| POST   | /api/time-entries/bulk-create/ | Bulk create entries       |

### Projects
| Method | Endpoint                     | Description             |
|--------|------------------------------|-------------------------|
| GET    | /api/projects/               | List projects           |
| POST   | /api/projects/               | Create project          |
| GET    | /api/projects/{id}/budget/   | Get budget status       |
| GET    | /api/projects/{id}/summary/  | Project time summary    |

### Invoices
| Method | Endpoint                         | Description           |
|--------|----------------------------------|-----------------------|
| GET    | /api/invoices/                   | List invoices         |
| POST   | /api/invoices/                   | Create invoice        |
| POST   | /api/invoices/{id}/send/         | Send invoice          |
| POST   | /api/invoices/{id}/record-payment/ | Record payment      |
| GET    | /api/invoices/{id}/pdf/          | Download PDF          |

### Reports
| Method | Endpoint                            | Description            |
|--------|-------------------------------------|------------------------|
| GET    | /api/reports/profitability/         | Profitability report   |
| GET    | /api/reports/utilization/           | Team utilization       |
| GET    | /api/reports/project-summary/       | Project summary        |
| GET    | /api/reports/team-overview/         | Team overview          |

## Environment Variables

See `.env.example` for all available configuration options.

## Testing

```bash
# Backend tests
docker-compose exec backend python manage.py test

# Frontend tests
docker-compose exec frontend npm test
```

## Deployment

For production deployment:

1. Update `.env` with production values
2. Set `DJANGO_SETTINGS_MODULE=config.settings.prod`
3. Configure your domain in `nginx/nginx.conf`
4. Set up SSL certificates
5. Run: `docker-compose -f docker-compose.yml up -d`

## License

MIT License. See LICENSE for details.
