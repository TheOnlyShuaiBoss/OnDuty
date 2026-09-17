"""tests.test_scheduler_v02 — once_at 触发/去重、失败重试排期与清零、workdir 锁派发。"""
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta

from onduty import runner, scheduler
from onduty.state import StateStore


def mkjob(name, once_at=None, retry_max=0, workdir="w", notify=None):
    return {"name": name, "agent": "dsh", "mode": "new", "model": None, "workdir": workdir,
            "prompt": "p", "prompt_file": None, "notify": notify or ["log"], "timeout_minutes": 5,
            "allow_danger": False, "catchup": False,
            "retry": {"max": retry_max, "backoff_minutes": 0.001},
            "schedule": {"kind": "once_at" if once_at else "manual", "cron": None,
                         "after": None, "once_at": once_at, "on": "success"}}


def fake_result(job, status="success"):
    return runner.RunResult(job=job["name"], agent=job["agent"], status=status,
                            trigger="-", exit_code=0 if status == "success" else 1,
                            duration_s=0.1, output=f"OUT-{job['name']}")


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.state = StateStore(self._td.name)
        self.calls = []
        self._orig_run = runner.run_job
        self._orig_disp = scheduler._dispatch
        scheduler._retry_q.clear()

    def tearDown(self):
        runner.run_job = self._orig_run
        scheduler._dispatch = self._orig_disp
        scheduler._retry_q.clear()
        self._td.cleanup()

    def cfg(self, jobs):
        return {"jobs": jobs, "adapters": {}, "agents": {}, "notify": {}, "base": self._td.name}


class TestOnceAt(Base):
    def _capture_dispatch(self):
        fired = []

        def fake_dispatch(cfg, state, job, trigger, prev_output="", session_source=None):
            fired.append((job["name"], trigger))
            return True
        scheduler._dispatch = fake_dispatch
        return fired

    def test_fires_when_due(self):
        past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
        job = mkjob("o1", once_at=past)
        fired = self._capture_dispatch()
        scheduler._once_tick(self.cfg([job]), self.state)
        self.assertEqual(fired, [("o1", "once_at")])
        self.assertTrue(self.state.job("o1").get("once_fired"))

    def test_not_fires_before_due(self):
        future = (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds")
        job = mkjob("o2", once_at=future)
        fired = self._capture_dispatch()
        scheduler._once_tick(self.cfg([job]), self.state)
        self.assertEqual(fired, [])

    def test_fires_only_once(self):
        past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
        job = mkjob("o3", once_at=past)
        fired = self._capture_dispatch()
        scheduler._once_tick(self.cfg([job]), self.state)
        scheduler._once_tick(self.cfg([job]), self.state)  # 第二次 tick 不再触发
        self.assertEqual(len(fired), 1)


class TestRetry(Base):
    def _fail_run(self, status="failed"):
        def fake_run_job(cfg, state, job, trigger="manual", prev_output="", session_source=None):
            self.calls.append((job["name"], trigger))
            return fake_result(job, status)
        runner.run_job = fake_run_job

    def test_failed_job_schedules_retry(self):
        job = mkjob("r1", retry_max=2)
        self._fail_run("failed")
        scheduler.run_chain(self.cfg([job]), self.state, job, "manual")
        self.assertEqual(len(scheduler._retry_q), 1)
        self.assertEqual(self.state.job("r1")["retry_attempt"], 1)

    def test_retry_exhausts_after_max(self):
        job = mkjob("r2", retry_max=1)
        self._fail_run("failed")
        scheduler.run_chain(self.cfg([job]), self.state, job, "manual")
        self.assertEqual(self.state.job("r2")["retry_attempt"], 1)
        q_before = len(scheduler._retry_q)          # 第一次失败已排队
        # 模拟这次重试也失败 → 达上限: 清零且不再新增排队
        scheduler.run_chain(self.cfg([job]), self.state, job, "retry")
        self.assertEqual(self.state.job("r2")["retry_attempt"], 0)
        self.assertEqual(len(scheduler._retry_q), q_before)  # 未新增(仍有首次那条待 _retry_tick 消费)

    def test_success_clears_retry_attempt(self):
        job = mkjob("r3", retry_max=2)
        self.state.update_job("r3", retry_attempt=1)
        self._fail_run("success")
        scheduler.run_chain(self.cfg([job]), self.state, job, "manual")
        self.assertEqual(self.state.job("r3")["retry_attempt"], 0)

    def test_no_retry_by_default(self):
        job = mkjob("r4", retry_max=0)
        self._fail_run("failed")
        scheduler.run_chain(self.cfg([job]), self.state, job, "manual")
        self.assertEqual(len(scheduler._retry_q), 0)

    def test_retry_tick_dispatches_due(self):
        job = mkjob("r5", retry_max=2)
        nb = datetime.now() - timedelta(seconds=1)
        with scheduler._retry_mu:
            scheduler._retry_q.append({"job": job, "not_before": nb, "attempt": 1})
        fired = []

        def fake_dispatch(cfg, state, job, trigger, prev_output="", session_source=None):
            fired.append((job["name"], trigger))
            return True
        scheduler._dispatch = fake_dispatch
        scheduler._retry_tick(self.cfg([job]), self.state)
        self.assertEqual(fired, [("r5", "retry")])
        self.assertEqual(len(scheduler._retry_q), 0)


class TestWorkdirLock(Base):
    def test_same_workdir_serializes(self):
        job_a = mkjob("pa", workdir="w_same")
        job_b = mkjob("pb", workdir="w_same")
        self.assertIs(scheduler._wd_lock("w_same"), scheduler._wd_lock("W_SAME".lower()))
        # RLock 同线程可重入(链式同目录不死锁)
        with scheduler._wd_lock("w_same"):
            with scheduler._wd_lock("w_same"):
                pass

    def test_dispatch_skips_inflight(self):
        job = mkjob("dup", workdir="w1")
        started = threading.Event()
        release = threading.Event()

        def slow_run(cfg, state, job, trigger="manual", prev_output="", session_source=None):
            started.set()
            release.wait(5)
            return fake_result(job)
        runner.run_job = slow_run
        ok1 = scheduler._dispatch(self.cfg([job]), self.state, job, "manual")
        started.wait(3)
        ok2 = scheduler._dispatch(self.cfg([job]), self.state, job, "manual")  # 在飞 → 拒绝
        release.set()
        # 等线程彻底写完状态再断言/清理(否则 tearDown 删目录撞占用)
        for _ in range(50):
            with scheduler._inflight_mu:
                if not scheduler._inflight:
                    break
            time.sleep(0.05)
        self.assertTrue(ok1)
        self.assertFalse(ok2)


if __name__ == "__main__":
    unittest.main()
