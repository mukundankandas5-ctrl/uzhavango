# UzhavanGo Production Architecture

## Runtime layers
- Flask app factory (`app/__init__.py`) with modular blueprints.
- SQLAlchemy models with migration-ready schema and index strategy.
- Service layer for domain workflows (auth, bookings, reviews, uploads, notifications).
- Web templates for browser UI + API v1 for mobile/KivyMD clients.
- KivyMD client module in `mobile/` for branded native-like app UX.

## Core feature modules
- `BookingService`: lifecycle transitions (Requested -> Accepted -> In Progress -> Completed -> Paid), receipt generation, payment creation, owner earnings.
- `ReviewService`: single-review-per-farmer enforcement and average rating recomputation.
- `NotificationService`: trigger-based alerts for booking/payment events with unread tracking.
- `web_receipt` blueprint: receipt page and PDF export endpoint.
- `web_admin` blueprint: KPI dashboard + analytics charts.

## Security controls
- Bcrypt password hashing.
- CSRF protection for form workflows.
- Role-based guards (`farmer`, `owner`, `admin`).
- Safe file upload and camera payload handling.
- Session hardening via secure cookie flags.

## Future hooks
- Payment gateway integration can replace internal auto-paid step in `BookingService._create_payment_for_booking`.
- Push/WebSocket notification transport can be added without schema changes.
- API versioning already partitioned under `/api/v1`.
