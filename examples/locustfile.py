import os

from locust_plugins.listeners import TimescaleListener
from locust_plugins.tasksets import TaskSetRPS
from locust.contrib.fasthttp import FastHttpLocust
from locust import task
from locust.wait_time import constant

TimescaleListener("example", os.environ["LOCUST_TEST_ENV"])

RPS = float(os.environ["LOCUST_RPS"])


class UserBehavior(TaskSetRPS):
    @task
    def my_task(self):
        self.rps_sleep(RPS)
        self.client.get("/")


class WebsiteUser(FastHttpLocust):
    task_set = UserBehavior
    wait_time = constant(0)
