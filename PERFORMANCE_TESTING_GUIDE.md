# Performance Testing Guide

## Quick Start

### Step 1: Create Test Users

Before running tests, create test users in your database:

```python
# Run this in your Flask shell or create a script
from app import create_app, db
from app.models import User, Organization

app = create_app()
with app.app_context():
    org = Organization.query.first()  # Get an organization
    
    # Create test users
    test_users = [
        User(email='test1@example.com', username='test1', organization_id=org.id),
        User(email='test2@example.com', username='test2', organization_id=org.id),
        User(email='test3@example.com', username='test3', organization_id=org.id),
    ]
    
    for user in test_users:
        user.set_password('TestPassword123!')
        db.session.add(user)
    
    db.session.commit()
    print("Test users created!")
```

### Step 2: Run Your Application

Make sure your Flask app is running:

```bash
# Activate virtual environment
venv\Scripts\activate

# Run the app
python run.py
```

### Step 3: Run Locust

Open a NEW terminal:

```bash
# Test locally
locust -f locustfile.py --host=http://localhost:5000

# Or test on Render
locust -f locustfile.py --host=https://your-app.onrender.com
```

### Step 4: Open Web UI

Open your browser: **http://localhost:8089**

You'll see the Locust interface where you can:
- Set number of users (start with 10)
- Set spawn rate (start with 2 users/second)
- Click "Start Swarming"

---

## Understanding the Results

### Key Metrics

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| **Response Time (Median)** | <500ms | 500-2000ms | >2000ms |
| **Response Time (95th percentile)** | <1000ms | 1000-3000ms | >3000ms |
| **Failure Rate** | 0% | <5% | >5% |
| **Requests/Second** | Higher is better | - | - |

### What Each Column Means

- **Type**: The endpoint being tested (e.g., "Submit Login", "View Dashboard")
- **# Requests**: Total number of requests made
- **# Fails**: How many failed (errors, timeouts)
- **Median**: 50% of requests finish faster than this
- **95%ile**: 95% of requests finish faster than this (important!)
- **Average**: Average response time
- **Min/Max**: Fastest and slowest response times
- **RPS**: Requests per second (throughput)

---

## Test Scenarios

### Test 1: Baseline Performance (10 Users)

**Goal**: Measure normal performance  
**Users**: 10  
**Spawn Rate**: 2/sec  
**Duration**: 5 minutes

**What to look for**:
- Login time: Should be <500ms
- Dashboard load: Should be <1500ms
- No failures

---

### Test 2: Moderate Load (50 Users)

**Goal**: Simulate busy period  
**Users**: 50  
**Spawn Rate**: 5/sec  
**Duration**: 10 minutes

**What to look for**:
- Response times stay under 2x baseline
- Failure rate stays below 1%
- CPU/Memory usage on server

---

### Test 3: High Load (100 Users)

**Goal**: Find system limits  
**Users**: 100  
**Spawn Rate**: 10/sec  
**Duration**: 10 minutes

**What to look for**:
- When do response times spike?
- When do errors start occurring?
- Database connection pool issues?

---

### Test 4: Stress Test (500+ Users)

**Goal**: Find breaking point  
**Users**: 500  
**Spawn Rate**: 20/sec  
**Duration**: 5 minutes

**What to look for**:
- System breaking point
- Error messages
- Recovery after load decreases

---

## Pakistan vs Australia Testing

### Expected Latency Differences

| Metric | Pakistan (You) | Australia (Customers) |
|--------|----------------|----------------------|
| Network Latency | 300-500ms | 10-50ms |
| Login Response | 600-800ms | 200-400ms |
| Dashboard Load | 2500-3500ms | 1500-2500ms |

**Remember**: Your tests from Pakistan will be slower due to distance. Focus on:
1. **Relative performance** (is login faster than dashboard?)
2. **Degradation patterns** (does 100 users = 2x slower than 10 users?)
3. **Error rates** (are requests failing?)

---

## Common Performance Issues

### Issue 1: Slow Dashboard (>3 seconds)

**Possible Causes**:
- Too many database queries (N+1 problem)
- No database indexes
- Loading too much data at once

**How to Fix**:
- Add database indexes on foreign keys
- Use lazy loading or pagination
- Cache frequently accessed data

---

### Issue 2: Upload Timeouts

**Possible Causes**:
- Large file processing without streaming
- Synchronous file validation
- No upload size limits

**How to Fix**:
- Stream large files
- Process uploads in background tasks
- Set reasonable size limits

---

### Issue 3: Database Connection Errors

**Symptoms**:
- Errors at >50 concurrent users
- "Too many connections" messages

**How to Fix**:
```python
# In config.py
SQLALCHEMY_POOL_SIZE = 20  # Increase from default 5
SQLALCHEMY_MAX_OVERFLOW = 40
SQLALCHEMY_POOL_TIMEOUT = 30
```

---

### Issue 4: Memory Leaks

**Symptoms**:
- Performance degrades over time
- Server runs out of memory

**How to Fix**:
- Close database sessions properly
- Don't store user data in memory
- Use proper context managers

---

## Advanced Testing

### Test Specific User Type

```bash
# Only test browsing users
locust -f locustfile.py --host=http://localhost:5000 --user-class BrowsingUser

# Only stress test
locust -f locustfile.py --host=http://localhost:5000 --user-class StressTestUser
```

### Headless Mode (No Web UI)

```bash
# Run without web UI
locust -f locustfile.py --host=http://localhost:5000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 10m \
  --headless \
  --html report.html
```

### Distributed Load Testing

If one machine isn't enough:

```bash
# Master
locust -f locustfile.py --master

# Workers (run on other machines)
locust -f locustfile.py --worker --master-host=<master-ip>
```

---

## Analysing Results

### Good Performance Example

```
Type              # Reqs  # Fails  Median  95%ile  Average  RPS
Submit Login        1000       0    250ms   450ms    280ms   5.2
View Dashboard      1500       0    800ms  1500ms    950ms   7.8
Upload File          300       2   2000ms  4500ms   2300ms   1.6

✅ Low failure rate (0.13%)
✅ Fast median response times
✅ Consistent performance
```

### Poor Performance Example

```
Type              # Reqs  # Fails  Median   95%ile  Average   RPS
Submit Login        1000     120   3500ms  12000ms   5200ms   2.1
View Dashboard      1200     340   8000ms  25000ms  11000ms   1.8
Upload File          150      89  15000ms  45000ms  22000ms   0.5

❌ High failure rate (36%)
❌ Very slow response times
❌ Poor throughput (RPS too low)
```

---

## Performance Optimization Checklist

After running tests, optimize:

### Database
- [ ] Add indexes on foreign keys
- [ ] Use `select_related()` / `joinedload()` to avoid N+1 queries
- [ ] Implement query result caching
- [ ] Add pagination to large result sets

### Application
- [ ] Enable Flask caching for static data
- [ ] Use background tasks for heavy processing
- [ ] Implement response compression (gzip)
- [ ] Optimize template rendering

### Infrastructure
- [ ] Increase database connection pool
- [ ] Add more server resources (CPU, RAM)
- [ ] Use CDN for static files
- [ ] Enable horizontal scaling (multiple servers)

---

## Next Steps

1. **Run Test 1** (10 users) - Get baseline metrics
2. **Fix obvious issues** - Slow queries, missing indexes
3. **Run Test 2** (50 users) - Validate improvements
4. **Document findings** - Share with team
5. **Test on Render** - Get real customer experience

Good luck! 🚀
