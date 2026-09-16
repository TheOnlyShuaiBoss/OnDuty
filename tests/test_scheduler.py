"""tests.test_scheduler — 对账逻辑: cron 到期/初始化/补跑、manual 控制文件、after 链。"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from onduty import runner, scheduler
from onduty.state import StateStore


def mkjob(name, cron=None, after=None, on="success", catchup=False):
    kind = "cron" if cron else ("after" if after else "manual")
    return {"name": name, "agent": "dsh", "mode": "new", "model": None, "workdir": "w",
            "prompt": "p", "prompt_file": None, "notify": ["log"], "timeout_minutes": 5,
            "allow_danger": False, "catchup": catchup,
            "schedule": {"kind": kind, "cron": cron, "after": after, "on": on}}


def fake_result(job, status="success"):
    return runner.RunResult(job=job["name"], agent=job["agent"], status=status,
                            trigger="-", exit_code=0, duration_s=0.1, output=f"OUT-{job['name']}")


class SchedBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.state = StateStore(self._td.name)
        self.calls = []

        def fake_run_job(cfg, state, job, trigger="manual", prev_output=""):
            self.calls.append((job["name"], trigger, prev_output))
            return fake_result(job)
        self._orig = runner.run_job
        runner.run_job = fake_run_job

    def tearDown(self):
        runner.run_job = self._orig
        self._td.cleanup()

    def cfg(self, jobs):
        return {"jobs": jobs, "adapters": {}, "agents": {}, "notify": {}, "base": self._td.name}


class TestCron(SchedBase):
    def test_due_fires_and_reschedules(self):
        job = mkjob("c1", cron="* * * * *")
        cfg = self.cfg([job])
        past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
        self.state.update_job("c1", next_due=past)
        scheduler._cron_tick(cfg, self.state)
        self.assertEqual(self.calls, [("c1", "cron", "")])
        due = datetime.fromisoformat(self.state.job("c1")["next_due"])
        self.assertGreater(due, datetime.now())

    def test_not_due_skips(self):
        job = mkjob("c2", cron="0 8 * * *")
        future = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")
        self.state.update_job("c2", next_due=future)
        scheduler._cron_tick(self.cfg([job]), self.state)
        self.assertEqual(self.calls, [])

    def test_first_tick_initializes_future_due(self):
        job = mkjob("c3", cron="0 8 * * *")
        scheduler._cron_tick(self.cfg([job]), self.state)
        self.assertEqual(self.calls, [])
        self.assertIn("next_due", self.state.job("c3"))

    def test_catchup_from_last_run(self):
        job = mkjob("c4", cron="0 8 * * *", catchup=True)
        last = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        self.state.update_job("c4", last_run_at=last)
        scheduler._cron_tick(self.cfg([job]), self.state)
        self.assertEqual(self.calls, [("c4", "catchup", "")])


class TestAfterChain(SchedBase):
    def test_success_triggers_dependent_with_output(self):
        j1 = mkjob("j1")
        j2 = mkjob("j2", after="j1")
        scheduler.run_chain(self.cfg([j1, j2]), self.state, j1, "manual")
        self.assertEqual(self.calls, [("j1", "manual", ""), ("j2", "after", "OUT-j1")])

    def test_on_success_blocks_when_failed(self):
        j1 = mkjob("j1")
        j2 = mkjob("j2", after="j1")

        def failing(cfg, state, job, trigger="manual", prev_output=""):
            self.calls.append((job["name"], trigger, prev_output))
            return runner.RunResult(job=job["name"], agent="dsh", status="failed",
                                    trigger=trigger, exit_code=1, duration_s=0.1, output="")
        runner.run_job = failing
        scheduler.run_chain(self.cfg([j1, j2]), self.state, j1, "manual")
        self.assertEqual([c[0] for c in self.calls], ["j1"])

    def test_on_always_fires_even_failed(self):
        j1 = mkjob("j1")
        j2 = mkjob("j2", after="j1", on="always")

        def failing(cfg, state, job, trigger="manual", prev_output=""):
            self.calls.append((job["name"], trigger, prev_output))
            return runner.RunResult(job=job["name"], agent="dsh", status="failed",
                                    trigger=trigger, exit_code=1, duration_s=0.1, output="")
        runner.run_job = failing
        scheduler.run_chain(self.cfg([j1, j2]), self.state, j1, "manual")
        self.assertEqual([c[0] for c in self.calls], ["j1", "j2"])


class TestMarkers(SchedBase):
    def test_marker_consumed_and_job_runs(self):
        j1 = mkjob("m1")
        marker = os.path.join(self.state.root, "ctl", "run__m1.marker")
        with open(marker, "w", encoding="utf-8") as f:
            f.write("x")
        scheduler._handle_markers(self.cfg([j1]), self.state)
        self.assertEqual(self.calls, [("m1", "manual", "")])
        self.assertFalse(os.path.exists(marker))

    def test_unknown_marker_removed(self):
        marker = os.path.join(self.state.root, "ctl", "run__ghost.marker")
        with open(marker, "w", encoding="utf-8") as f:
            f.write("x")
        scheduler._handle_markers(self.cfg([]), self.state)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
