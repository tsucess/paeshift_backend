
# Payshift - Modern Job Marketplace Platform

![Payshift Logo](https://github.com/Paeshift-Web-App/paeshift-frontend/assets/100290626/00000000-0000-0000-0000-000000000000)

Payshift is a comprehensive job marketplace platform that connects job seekers with clients, focusing on flexible work arrangements including single-day shifts, temporary positions, and part-time opportunities. Our platform streamlines the entire job lifecycle from posting to payment, with built-in escrow services, ratings, and dispute resolution.

## 🚀 Features

### For Job Seekers
- **Job Discovery**: Find flexible work opportunities based on skills and location
- **Secure Payments**: Get paid through our escrow system after job completion
- **Profile Building**: Build a reputation through ratings and reviews
- **Real-time Notifications**: Stay updated on job status and new opportunities
- **Wallet System**: Manage earnings in one place
- **Location Tracking**: Share location during job execution for safety and coordination

### For Clients
- **Talent Access**: Post jobs and find qualified applicants quickly
- **Verification**: Verify applicant skills and ratings before hiring
- **Secure Payments**: Pay into escrow and release funds after job completion
- **Dispute Resolution**: Access fair resolution if issues arise
- **Rating System**: Rate workers and build a reliable talent pool
- **Real-time Updates**: Track job progress and communicate with workers

### Platform Features
- **Dual User Interface**: Separate experiences for job seekers and clients
- **Payment Integration**: Seamless transactions with Paystack and Flutterwave
- **Real-time Communication**: Chat and notifications system
- **Location Services**: GPS-based job matching and tracking
- **Review System**: Build trust through transparent feedback
- **Admin Dashboard**: Comprehensive monitoring and management tools

## 🛠️ Technology Stack

### Backend
- **Framework**: Django with Django Ninja API
- **Database**: PostgreSQL
- **Caching**: Redis
- **Task Queue**: Django Q
- **Real-time**: WebSockets
- **Payment Processing**: Paystack and Flutterwave integration
- **Geolocation**: Google Maps API

### Frontend
- **Framework**: React with Vite
- **State Management**: Recoil
- **Styling**: CSS with responsive design
- **UI Components**: Custom components with Bootstrap integration
- **Notifications**: Toast notifications

## 🏗️ Architecture

Payshift follows a microservice-oriented architecture:
- **Core Django Application**: Main business logic and API endpoints
- **FastAPI Microservice**: Real-time services and monitoring
- **Redis Cache Layer**: Performance optimization
- **WebSocket Services**: Real-time communication
- **Payment Processing Service**: Secure transaction handling

## 🚦 Getting Started

### Prerequisites
- Python 3.9+
- Node.js 14+
- Redis
- PostgreSQL (optional, can use SQLite for development)

### Backend Setup
```bash
# Clone the repository
git clone https://github.com/Paeshift-Web-App/paeshift-frontend.git
cd paeshift-frontend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start the server
python manage.py runserver
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd paeshift-frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## 📚 API Documentation

Payshift provides a comprehensive API for integration:

### Summary of Endpoints

| **Category**         | **Endpoint**                          | **Method** | **Description**                                                                 |
|-----------------------|---------------------------------------|------------|---------------------------------------------------------------------------------|
| **Authentication**    | `/jobs/login`                         | POST       | Authenticates and logs in a user.                                               |
|                       | `/jobs/signup`                        | POST       | Creates a new user and profile.                                                 |
|                       | `/jobs/logout`                        | POST       | Logs out the current user.                                                      |
|                       | `/jobs/change-password`               | POST       | Changes the user's password.                                                    |
|                       | `/jobs/csrf-token`                    | GET        | Returns the CSRF token.                                                         |
| **User/Profile**      | `/jobs/all-users`                     | GET        | Returns a list of all users.                                                    |
|                       | `/jobs/profile`                       | GET        | Fetches the current user's profile info.                                        |
|                       | `/jobs/profile`                       | PUT        | Updates the user's profile.                                                     |
| **Jobs**              | `/jobs/job-industries/`               | GET        | Returns all job industries.                                                     |
|                       | `/jobs/job-subcategories/`            | GET        | Returns all job subcategories.                                                  |
|                       | `/jobs/create-job`                    | POST       | Creates a new job.                                                              |
|                       | `/jobs/clientjobs`                    | GET        | Retrieves jobs posted by a client with pagination.                              |
|                       | `/jobs/alljobs`                       | GET        | Returns all jobs.                                                               |
|                       | `/jobs/{job_id}`                      | GET        | Returns details for a single job.                                               |
| **Saved Jobs**        | `/jobs/save-job/{job_id}`             | POST       | Saves a job for the current user.                                               |
|                       | `/jobs/save-job/{job_id}`             | DELETE     | Removes a job from the user's saved list.                                       |
|                       | `/jobs/saved-jobs`                    | GET        | Lists all saved jobs for the authenticated user.                                |
| **Ratings**           | `/jobs/ratings`                       | POST       | Submits a rating for another user.                                              |
|                       | `/jobs/ratings/{user_id}`             | GET        | Retrieves all ratings for a user.                                               |
| **Disputes**          | `/jobs/{job_id}/disputes`             | POST       | Creates a dispute for a job.                                                    |
|                       | `/jobs/disputes/{dispute_id}`         | GET        | Fetches details for a dispute.                                                  |
|                       | `/jobs/disputes/{dispute_id}`         | PUT        | Updates an existing dispute.                                                    |
| **Location**          | `/jobs/update-location`               | POST       | Updates the user's location.                                                    |
|                       | `/jobs/track-applicant/{applicant_id}`| GET        | Retrieves the last known location of an applicant.                              |
|                       | `/jobs/{job_id}/update-location`      | POST       | Updates the location of a job seeker for a specific job.                        |
| **WebSocket**         | `ws/chat/{job_id}/`                   | WebSocket  | Real-time chat messages.                                                        |
|                       | `ws/jobs/{job_id}/location/`          | WebSocket  | Real-time job location updates.                                                 |
|                       | `ws/jobs/matching/`                   | WebSocket  | Real-time job matching updates.                                                 |
| **Miscellaneous**     | `/jobs/check-session`                 | GET        | Checks the current session.                                                     |
|                       | `/jobs/accepted-list`                 | GET        | Returns accepted applications with job details.                                 |
|                       | `/jobs/industries`                    | GET        | Returns all job industries.                                                     |
|                       | `/jobs/subcategories`                 | GET        | Returns job subcategories.                                                      |
|                       | `/jobs/payment`                       | POST       | Renders the payment page.                                                       |
|                       | `/jobs/whoami`                        | GET        | Returns the current user's ID, username, role, wallet balance, and reviews.     |

## 🔒 Security Features

- JWT Authentication
- Secure Payment Processing
- Data Encryption
- CSRF Protection
- Input Validation
- Rate Limiting

## 🌐 Deployment

Payshift can be deployed using Docker for containerization:

```bash
# Build and run with Docker Compose
docker-compose up -d
```

## 📊 Business Model

Payshift generates revenue through:
1. **Service Fees**: 5% commission on each successful job transaction
2. **Premium Features**: Additional tools for high-volume employers
3. **Featured Listings**: Priority placement for urgent job postings
4. **Verification Services**: Enhanced background checks for sensitive positions

## 👥 Contributing

We welcome contributions to Payshift! Please see our [Contributing Guidelines](CONTRIBUTING.md) for more information.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Contact

For questions or support, please contact us at [support@payshift.com](mailto:support@payshift.com).

Here


python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt


## Save the file, then run:
python manage.py makemigrations
python manage.py migrate



## Start your server again: run
python manage.py runserver

# paeshift_backend
