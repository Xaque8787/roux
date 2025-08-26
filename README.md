# Food Cost Management System

A comprehensive web application for managing restaurant food costs, ingredients, recipes, batches, dishes, inventory, and utilities.

## Features

### 🔐 Authentication & Authorization
- Secure JWT-based authentication with HTTP-only cookies
- Role-based access control (Admin/User roles)
- One-time setup wizard for initial admin user

### 🥕 Ingredients Management
- Track ingredients with units and costs
- Categorize ingredients for better organization
- Cost tracking for accurate recipe pricing

### 📖 Recipe Management
- Create reusable recipe templates
- Define ingredient quantities and ratios
- Calculate total recipe costs automatically

### 👨‍🍳 Batch Production
- Track actual prep work based on recipes
- Record yields and labor time
- Support for portion breakdowns (half, quarter batches)

### 🍽️ Dish/Menu Management
- Create menu items using batch portions
- Set sale prices and calculate profit margins
- Track food cost vs. sale price

### 📦 Inventory Management
- Daily inventory tracking with par levels
- Visual indicators for below/near par items
- Task assignment and time tracking
- Day finalization for record keeping

### ⚡ Utility Cost Tracking
- Track monthly utility costs (power, gas, water)
- Prorate costs for accurate dish pricing
- Admin-only utility management

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd food-cost-management
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Start the application:
```bash
docker-compose up -d
```

4. Access the application at `http://localhost:8000`

5. Complete the initial setup by creating an admin user

### Development Setup

1. Install Python 3.11+ and dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export SECRET_KEY="your-secret-key"
export DATABASE_URL="sqlite:///./food_cost.db"
```

3. Run the development server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Usage Guide

### Initial Setup
1. Navigate to the application URL
2. You'll be redirected to the setup page
3. Create the first admin user
4. Default categories will be created automatically

### Managing Ingredients
1. Go to **Ingredients** section
2. Add ingredients with their units and costs
3. Assign categories for better organization

### Creating Recipes
1. Go to **Recipes** section
2. Create recipes by selecting ingredients and quantities
3. View recipe details including total cost

### Production Batches
1. Go to **Batches** section
2. Select a recipe and enter yield amount and labor time
3. Optionally enable portion breakdowns

### Menu Items (Dishes)
1. Go to **Dishes** section
2. Create dishes using portions from batches
3. Set sale prices to calculate profit margins

### Daily Inventory
1. Go to **Inventory** section
2. Add inventory items with par levels
3. Start a new day and assign employees
4. Enter daily quantities (items below par are highlighted)
5. Create and track tasks
6. Finalize the day when complete

### Utility Costs (Admin Only)
1. Go to **Utilities** section
2. Add monthly costs for utilities
3. View daily prorated costs

## System Architecture

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: ORM for database operations
- **Pydantic**: Data validation and serialization
- **JWT**: Secure authentication
- **Jinja2**: Server-side templating

### Frontend
- **Bootstrap 5**: Responsive UI framework
- **Font Awesome**: Icons
- **Vanilla JavaScript**: Form enhancements

### Database
- **SQLite**: Default database (production-ready)
- **PostgreSQL**: Optional for larger deployments

### Deployment
- **Docker**: Containerized deployment
- **Gunicorn**: Production WSGI server
- **Multi-stage builds**: Optimized container images

## Security Features

- HTTP-only cookies for JWT storage
- Password hashing with bcrypt
- Role-based access control
- CSRF protection via SameSite cookies
- Input validation and sanitization

## Data Persistence

- Database files stored in `./data` directory
- Docker volume mounting for data persistence
- Automatic database table creation

## API Endpoints

### Authentication
- `GET /setup` - Initial setup form
- `POST /setup` - Create admin user
- `GET /login` - Login form
- `POST /login` - Authenticate user
- `GET /logout` - Logout user

### Core Features
- `/ingredients` - Ingredient management
- `/recipes` - Recipe management
- `/batches` - Batch production
- `/dishes` - Menu item management
- `/inventory` - Daily inventory tracking
- `/utilities` - Utility cost management (admin only)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please create an issue in the repository or contact the development team.