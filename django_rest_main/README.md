# Django REST Backend – Clinic Management System

This project is a Django REST Framework backend designed to manage clinics, departments, equipments, environments, events, tasks, parameters, and employees.

The application follows a **clean and scalable architecture** by separating:
- Models
- Serializers
- Services (business logic)
- Views (API layer)
- Tests

---

## 🚀 Tech Stack

- Python 3.11
- Django
- Django REST Framework
- drf-yasg (Swagger / OpenAPI)
- PostgreSQL (configurable)

---

## 📁 Project Structure

django_rest_main/
│
├── README.md
├── manage.py
│
├── django_rest_main/ # Django project configuration
│ ├── settings.py
│ ├── urls.py
│ ├── asgi.py
│ └── wsgi.py
│
├── restapi/ # Main application
│ ├── admin.py
│ ├── apps.py
│ ├── urls.py
│ ├── views.py
│ ├── pagination.py
│ ├── middleware.py
│ ├── exception_handler.py
│ │
│ ├── models/ # Domain models (module-wise)
│ │ ├── clinic.py
│ │ ├── department.py
│ │ ├── equipment.py
│ │ ├── environment.py
│ │ ├── event.py
│ │ ├── parameter.py
│ │ ├── task.py
│ │ └── employee.py
│ │
│ ├── serializers/ # DRF serializers
│ │ ├── clinic.py
│ │ ├── department.py
│ │ ├── equipment.py
│ │ ├── environment.py
│ │ ├── event.py
│ │ ├── parameter.py
│ │ ├── task.py
│ │ └── task_event.py
│ │
│ ├── services/ # Business logic layer
│ │ ├── clinic_service.py
│ │ ├── department_service.py
│ │ ├── equipment_service.py
│ │ ├── environment_service.py
│ │ ├── event_service.py
│ │ ├── parameter_service.py
│ │ └── task_service.py
│ │
│ ├── scripts/ # One-time / migration scripts
│ │ └── vidai_clinic_migration.py
│ │
│ ├── migrations/
│ └── log/
│
├── tests/ # Automated tests (module-wise)
│ ├── clinic/
│ ├── environment/
│ ├── equipment/
│ ├── event/
│ ├── parameter/
│ ├── task/
│ └── user/





---

## 🧠 Architecture Overview

### Models
- Define database schema
- Split by domain
- Located in `restapi/models/`

### Serializers
- Handle validation and data transformation
- One file per domain
- Located in `restapi/serializers/`

### Services
- Contain all business logic
- Keep views thin and clean
- Located in `restapi/services/`

### Views
- Expose REST APIs
- Call service layer
- Handle request/response only
- Located in `restapi/views.py`

### Tests
- Unit and API tests
- Organized by feature
- Located in `tests/`

---

## ▶️ How to Run the Project

### 1️⃣ Create virtual environment
```bash
python -m venv env
source env/bin/activate        # Linux / Mac
env\Scripts\activate           # Windows

2️⃣ Install dependencies
pip install -r requirements.txt



3️⃣ Run migrations
python manage.py makemigrations
python manage.py migrate


4️⃣ Start development server
python manage.py runserver


📚 API Documentation

Swagger UI:

http://127.0.0.1:8000/swagger/