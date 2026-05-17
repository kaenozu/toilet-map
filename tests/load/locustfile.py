"""
tests/load/locustfile.py
Locust load test script for Streamlit map API.
Related: batch/api_server.py
"""
from locust import HttpUser, between, task


class StreamlitUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def health_check(self):
        self.client.get("/_stcore/health")

    @task(3)
    def load_page(self):
        self.client.get("/")
