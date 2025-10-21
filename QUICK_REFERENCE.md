# Quick Reference Guide - Paeshift Phase 2

## 🚀 Quick Start

```bash
# Navigate to project
cd paeshift-recover

# Run all tests
python -m pytest -v

# Run with coverage report
python -m pytest --cov=accounts --cov=jobs --cov=payment --cov=rating --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
xdg-open htmlcov/index.html  # Linux

# Run specific test file
python -m pytest jobs/tests/test_jobs_api_comprehensive.py -v

# Run specific test
python -m pytest jobs/tests/test_jobs_api_comprehensive.py::TestJobsAPI::test_get_all_jobs -v

# Run with verbose output
python -m pytest -vv

# Run with print statements
python -m pytest -s

# Run and stop on first failure
python -m pytest -x

# Run last failed tests
python -m pytest --lf
```

---

## 📁 Project Structure

```
paeshift-recover/
├── conftest.py                          # Global fixtures and factories
├── pytest.ini                           # Pytest configuration
├── PHASE_2_IMPLEMENTATION_GUIDE.md      # Detailed guide
├── PHASE_2_PROGRESS_REPORT.md           # Progress metrics
├── PHASE_2_ACTION_PLAN.md               # Next steps
├── PHASE_2_SUMMARY.md                   # Summary
├── QUICK_REFERENCE.md                   # This file
│
├── accounts/
│   ├── api.py                           # Account endpoints
│   ├── models.py                        # User, Profile models
│   └── tests/
│       └── test_accounts_api.py         # Account tests
│
├── jobs/
│   ├── api.py                           # Job endpoints
│   ├── models.py                        # Job, Application models
│   └── tests/
│       └── test_jobs_api_comprehensive.py  # Job tests
│
├── payment/
│   ├── api.py                           # Payment endpoints
│   ├── models.py                        # Payment, Wallet models
│   └── tests/
│       └── test_payment_api.py          # Payment tests
│
└── rating/
    ├── api.py                           # Rating endpoints
    ├── models.py                        # Review model
    └── tests/
        └── test_rating_api.py           # Rating tests
```

---

## 🏭 Factories Reference

### UserFactory
```python
from conftest import UserFactory

user = UserFactory()  # Creates user with profile and wallet
user = UserFactory(email='custom@example.com')
user = UserFactory(password='custom_password')
```

### ProfileFactory
```python
from conftest import ProfileFactory

profile = ProfileFactory()
profile = ProfileFactory(role='client')
profile = ProfileFactory(bio='Custom bio')
```

### JobFactory
```python
from conftest import JobFactory

job = JobFactory()
job = JobFactory(title='Custom Job')
job = JobFactory(rate=Decimal('50.00'))
```

### ApplicationFactory
```python
from conftest import ApplicationFactory

app = ApplicationFactory()
app = ApplicationFactory(status='Applied')
```

### PaymentFactory
```python
from conftest import PaymentFactory

payment = PaymentFactory()
payment = PaymentFactory(amount=Decimal('500.00'))
```

### ReviewFactory
```python
from conftest import ReviewFactory

review = ReviewFactory()
review = ReviewFactory(rating=Decimal('5.0'))
```

---

## 🧪 Test Fixtures Reference

### Basic Fixtures
```python
def test_with_user(user):
    """user fixture provides a basic test user"""
    assert user.id > 0

def test_with_client_user(client_user):
    """client_user fixture provides a user with client role"""
    assert client_user.profile.role == 'client'

def test_with_applicant_user(applicant_user):
    """applicant_user fixture provides a user with applicant role"""
    assert applicant_user.profile.role == 'applicant'
```

### Job Fixtures
```python
def test_with_job(job):
    """job fixture provides a complete job"""
    assert job.title is not None
    assert job.client is not None

def test_with_application(application):
    """application fixture provides a job application"""
    assert application.job is not None
    assert application.applicant is not None
```

### Payment Fixtures
```python
def test_with_payment(payment):
    """payment fixture provides a payment record"""
    assert payment.amount > 0
    assert payment.job is not None
```

### Review Fixtures
```python
def test_with_review(review):
    """review fixture provides a review"""
    assert review.rating > 0
    assert review.reviewer is not None
    assert review.reviewed is not None
```

---

## 📊 Test Statistics

### Current Status
- **Total Tests**: 50
- **Passing**: 15+
- **Failing**: 20+
- **Errors**: 15+
- **Pass Rate**: 30%+

### By Module
- **Jobs**: 18 tests (33% passing)
- **Payment**: 15 tests (40% passing)
- **Rating**: 17 tests (18% passing)

### Coverage Target
- **Phase 2.1**: 30%+ ✅ COMPLETE
- **Phase 2.2**: 50%+ (Next)
- **Phase 2.3**: 70%+ (Goal)
- **Production**: 85%+ (Target)

---

## 🔍 Common Issues & Solutions

### Issue: "Cannot resolve endpoint"
**Solution**: Check endpoint path in api.py
```bash
grep -n "@.*router\.(post|get|put|delete)" paeshift-recover/jobs/api.py
```

### Issue: "Foreign key constraint failed"
**Solution**: Ensure related objects are created
```python
job = JobFactory()  # Creates job with client, industry, subcategory
```

### Issue: "Profile already exists"
**Solution**: Profile is created automatically via signals
```python
user = UserFactory()
profile = Profile.objects.get(user=user)  # Already exists
```

### Issue: "Celery connection refused"
**Solution**: Expected in test environment, can be mocked
```python
@patch('celery_app.send_task')
def test_with_celery(mock_celery):
    pass
```

---

## 📝 Writing New Tests

### Basic Test Template
```python
@pytest.mark.django_db
class TestMyAPI:
    def setup_method(self):
        self.client = TestClient(my_router)
    
    def test_success_case(self, fixture):
        payload = {'key': 'value'}
        response = self.client.post('/endpoint', json=payload)
        assert response.status_code == 200
        assert response.json()['success'] is True
    
    def test_error_case(self):
        payload = {'invalid': 'data'}
        response = self.client.post('/endpoint', json=payload)
        assert response.status_code == 400
```

### Using Fixtures
```python
def test_with_multiple_fixtures(self, client_user, job, applicant_user):
    # All fixtures are automatically injected
    assert client_user.id > 0
    assert job.client == client_user
    assert applicant_user.id > 0
```

### Using Factories
```python
def test_with_factory(self):
    user = UserFactory(email='test@example.com')
    job = JobFactory(client=user)
    assert job.client == user
```

---

## 🎯 Next Steps

### Phase 2.2: Database Optimization
1. Find correct endpoint paths
2. Mock external services
3. Achieve 50%+ test coverage
4. Add integration tests

### Phase 2.3: Frontend Integration
1. Setup React Query
2. Implement error boundaries
3. Add loading states
4. Centralize API error handling

### Phase 2.4: Performance Improvements
1. Enable Redis caching
2. Implement rate limiting
3. Optimize pagination
4. Move heavy operations to background tasks

---

## 📚 Documentation Files

- **PHASE_2_IMPLEMENTATION_GUIDE.md** - Detailed implementation guide
- **PHASE_2_PROGRESS_REPORT.md** - Current progress and metrics
- **PHASE_2_ACTION_PLAN.md** - Step-by-step action plan
- **PHASE_2_SUMMARY.md** - Summary of Phase 2.1
- **QUICK_REFERENCE.md** - This file

---

## 🔗 Useful Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Run tests with coverage
pytest --cov=accounts --cov=jobs --cov=payment --cov=rating --cov-report=html

# Generate coverage report
coverage report -m

# View coverage in browser
open htmlcov/index.html
```

---

## 💡 Tips & Tricks

1. **Use -x flag to stop on first failure**: `pytest -x`
2. **Use -v for verbose output**: `pytest -v`
3. **Use -s to see print statements**: `pytest -s`
4. **Use --lf to run last failed**: `pytest --lf`
5. **Use -k to filter tests**: `pytest -k "test_create"`
6. **Use --tb=short for shorter tracebacks**: `pytest --tb=short`

---

## 📞 Support

For questions or issues:
1. Check PHASE_2_ACTION_PLAN.md for next steps
2. Review PHASE_2_PROGRESS_REPORT.md for current status
3. Check PHASE_2_SUMMARY.md for lessons learned
4. Refer to PHASE_2_IMPLEMENTATION_GUIDE.md for detailed info


