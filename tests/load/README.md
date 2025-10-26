# 🚀 Load Testing Guide
**FastAPI User Management System**

## 📦 Prerequisites

Locust should already be installed. Verify:
```bash
pip list | grep locust
```

If not installed:
```bash
pip install locust
```

---

## 🎯 HOW TO RUN LOAD TESTS

### **Method 1: Interactive Mode** (Recommended for First Time)

```bash
# Start Locust web interface
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Then open browser:
# http://localhost:8089
```

**In the web interface:**
1. Set **Number of users:** 50 (start small)
2. Set **Spawn rate:** 10 (10 users per second)
3. Click **Start swarming**
4. Watch real-time stats

### **Method 2: Headless Mode** (Command Line)

```bash
# Run 50 users for 60 seconds
locust -f tests/load/locustfile.py --headless --users 50 --spawn-rate 10 --run-time 60s --host=http://localhost:8000

# Run 200 users for 2 minutes
locust -f tests/load/locustfile.py --headless --users 200 --spawn-rate 10 --run-time 2m --host=http://localhost:8000

# Run 500 users for 5 minutes (stress test)
locust -f tests/load/locustfile.py --headless --users 500 --spawn-rate 20 --run-time 5m --host=http://localhost:8000
```

### **Method 3: Save Results**

```bash
# Save results to CSV
locust -f tests/load/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 60s \
  --host=http://localhost:8000 \
  --csv=tests/load/results/load_test_$(date +%Y%m%d_%H%M%S)
```

---

## 📊 TEST SCENARIOS

### **Scenario 1: Normal Load** (Recommended Start)
```bash
locust --headless --users 50 --spawn-rate 10 --run-time 2m
```
**Target:** All requests < 500ms

### **Scenario 2: Heavy Load**
```bash
locust --headless --users 200 --spawn-rate 10 --run-time 5m
```
**Target:** All requests < 1000ms, error rate < 1%

### **Scenario 3: Stress Test**
```bash
locust --headless --users 500 --spawn-rate 20 --run-time 10m
```
**Target:** System handles load, error rate < 5%

### **Scenario 4: Spike Test**
```bash
locust --headless --users 1000 --spawn-rate 50 --run-time 5m
```
**Target:** System recovers after spike

---

## 📈 INTERPRETING RESULTS

### **Key Metrics:**

1. **Response Times:**
   - Min: Best case
   - Max: Worst case
   - Average: Typical performance
   - P95: 95% of requests faster than this

2. **Request Rate:**
   - Total Requests: Total requests made
   - Requests/s: Throughput

3. **Failure Rate:**
   - Should be < 1% for normal load
   - < 5% for stress test

### **Target Benchmarks:**

| Endpoint | Target Response Time | Current |
|----------|---------------------|---------|
| Login | < 500ms | ? |
| User Dashboard | < 200ms | ? |
| Admin Dashboard | < 300ms | ? |
| Super Admin | < 500ms | ? |

---

## 🎯 QUICK START

1. **Make sure FastAPI server is running:**
   ```bash
   uvicorn main:app --reload
   ```

2. **Start Locust in another terminal:**
   ```bash
   locust -f tests/load/locustfile.py --host=http://localhost:8000
   ```

3. **Open browser:** http://localhost:8089

4. **Run test:**
   - Users: 50
   - Spawn rate: 10
   - Click "Start"

5. **Watch results!**

---

## 🔧 TROUBLESHOOTING

### **Problem: "Connection refused"**
**Solution:** Make sure FastAPI is running on localhost:8000

### **Problem: "429 Too Many Requests"**
**Solution:** Reduce number of users or increase rate limiting

### **Problem: All requests are slow**
**Solution:** Check database performance, add more indexes

---

## 📊 NEXT STEPS AFTER LOAD TEST

1. **Analyze bottlenecks**
2. **Optimize slow queries**
3. **Add more indexes if needed**
4. **Improve caching strategy**
5. **Re-test to verify improvements**

