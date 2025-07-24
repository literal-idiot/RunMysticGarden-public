# Mystical Garden Runner API

## Overview

Mystical Garden Runner is a gamified running application backend that combines fitness tracking with virtual gardening. Users earn coins by logging runs, which they can use to purchase and grow virtual plants in their mystical garden. The system encourages consistent running through plant care mechanics and intensity-based rewards.

## System Architecture

### Backend Framework
- **Flask**: Lightweight Python web framework chosen for its simplicity and flexibility
- **SQLAlchemy**: ORM for database operations with support for multiple database backends
- **Flask-JWT-Extended**: JWT token-based authentication for stateless API security
- **Flask-CORS**: Cross-origin resource sharing for frontend integration

### Database Design
- **Primary Database**: SQLite for development, PostgreSQL for production
- **ORM Pattern**: SQLAlchemy with declarative base for clean model definitions
- **Database Pooling**: Connection pooling with pre-ping health checks for reliability

### Authentication Strategy
- **JWT Tokens**: Stateless authentication suitable for mobile applications
- **No Token Expiration**: Simplified for mobile app convenience (trade-off for UX)
- **Password Hashing**: Werkzeug's secure password hashing

## Key Components

### Core Models
- **User**: Account management with email/username authentication
- **StravaAccount**: OAuth integration storing Strava tokens and athlete data
- **Run**: Fitness tracking with distance, duration, and intensity metrics
- **CoinWallet**: Virtual currency system for gamification
- **Garden/Plant/Seed**: Virtual gardening mechanics
- **IntensityLevel**: Enum for run difficulty (low, moderate, high, extreme)
- **PlantStage**: Enum for plant growth phases (seed to blooming)

### API Endpoints
- **Authentication**: `/auth/register`, `/auth/login`, `/auth/profile`
- **Strava OAuth**: `/auth/strava/connect`, `/auth/strava/callback`, `/auth/strava/link`, `/auth/strava/status`, `/auth/strava/disconnect`
- **Run Tracking**: `/api/runs` (POST for logging runs, GET for history)
- **Strava Sync**: `/api/strava/sync`, `/api/strava/stats`
- **Garden Management**: Plant purchasing, growth tracking, and garden visualization
- **Testing**: `/strava-test` (interactive testing interface)

### Business Logic
- **Coin Calculation**: Distance-based rewards with intensity multipliers and milestone bonuses
- **Plant Growth**: Run consistency requirements for virtual plant care
- **Gamification**: Achievement system through plant collection and garden building

## Data Flow

1. **User Registration**: Email validation → Password hashing → Default wallet/garden creation
2. **Run Logging**: Distance/duration validation → Coin calculation → Plant growth updates
3. **Garden Interaction**: Coin spending → Seed purchasing → Plant care mechanics
4. **Progress Tracking**: Weekly distance goals → Plant health → Achievement unlocks

## External Dependencies

### Python Packages
- **Flask Stack**: Flask, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-CORS
- **Database**: psycopg2-binary for PostgreSQL connectivity
- **Validation**: email-validator for input sanitization
- **Deployment**: Gunicorn WSGI server for production
- **Strava Integration**: stravalib for OAuth and API access, requests for HTTP calls

### Infrastructure
- **Replit Environment**: Nix-based Python 3.11 runtime
- **Database**: PostgreSQL with OpenSSL for secure connections
- **Deployment**: Autoscale deployment target with Gunicorn

## Deployment Strategy

### Development
- **Local Server**: Flask development server with hot reload
- **Database**: SQLite for rapid iteration
- **Debug Mode**: Enabled for development workflow

### Production
- **WSGI Server**: Gunicorn with bind to 0.0.0.0:5000
- **Database**: PostgreSQL with connection pooling
- **Scalability**: Autoscale deployment on Replit infrastructure
- **Process Management**: Port reuse and reload capabilities

### Configuration
- **Environment Variables**: Database URL, JWT secrets, session keys
- **Proxy Handling**: ProxyFix middleware for proper header forwarding
- **CORS**: Enabled for cross-origin frontend requests

## Changelog

```
Changelog:
- July 24, 2025. Strava OAuth integration added with full activity sync
- June 24, 2025. Initial setup
```

## User Preferences

```
Preferred communication style: Simple, everyday language.
```