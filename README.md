# GardenCity

High-end barbershop management system and premium dark-themed website built with Django, Tailwind CSS, Chart.js, and SQLite for development.

## Features

- Premium public landing page with hero, services, team, and booking CTA
- Staff-only authentication
- Role-based access control for `Admin`, `Manager`, and `Staff`
- Admin/manager CRUD for staff, services, sales, and expenses
- Staff dashboard with personal sales, commission, and upcoming appointments
- Sales and expense reporting with CSV export
- Commission calculation on every sale

## Tech Stack

- Django 4.2
- Tailwind CSS via CDN
- Chart.js via CDN
- SQLite for local development

## Run Locally

```bash
py -3.9 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_gardencity
.\.venv\Scripts\python.exe manage.py runserver
```

## Demo Accounts

- Admin: `admin` / `Admin123!`
- Manager: `manager` / `Manager123!`
- Staff: `barber` / `Barber123!`

Change these passwords immediately in any real deployment.

## Core Data Model

- `User`: full name, role, email, password, commission rate
- `Service`: service catalog, pricing, duration, category
- `Sale`: service rendered, price, staff, payment method, date
- `Expense`: category, amount, description, date
- `Payment`: staff payouts with period tracking
- `Appointment`: public booking requests and scheduled visits

## Reports

- Sales by staff with commission and net shop revenue
- Sales by category
- Expenses by category
- Date-range filtering and CSV export
