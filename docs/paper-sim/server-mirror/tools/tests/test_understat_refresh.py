"""Offline recovery tests. Synthetic results only exist inside temporary test dirs."""

import argparse
from contextlib import redirect_stdout
import copy
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "understat_refresh.py"
spec = importlib.util.spec_from_file_location("understat_refresh", MODULE)
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


def fixture(match_id, home, away, date):
    return {"id": str(match_id), "isResult": False,
            "h": {"id": str(home)}, "a": {"id": str(away)}, "datetime": date,
            "xG": {"h": None, "a": None}, "goals": {"h": None, "a": None}}


def complete(block, match):
    match["isResult"] = True
    match["xG"] = {"h": "1.25", "a": "0.5"}
    match["goals"] = {"h": "1", "a": "0"}
    for side, other in (("h", "a"), ("a", "h")):
        block["teams"][match[side]["id"]]["history"].append({
            "date": match["datetime"], "h_a": side,
            "xG": float(match["xG"][side]), "xGA": float(match["xG"][other]),
            "scored": int(match["goals"][side]), "missed": int(match["goals"][other]),
        })


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="offline-unit-", dir=refresh.ROOT / "round28/raw/understat_diagnostics")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.args = argparse.Namespace(seed=self.root / "seed.json", output=self.root / "snapshot.json",
                                       log=self.root / "recovery.jsonl", status=self.root / "status.json",
                                       latest=self.root / "latest.json",
                                       latest_meta=self.root / "latest_pointer.json")
        self.seed = {}
        self.fresh = {}
        for lg in refresh.LEAGUES:
            block = {"teams": {str(n): {"title": f"TEST TEAM {n}", "history": []}
                                for n in range(1, refresh.TEAM_COUNTS[lg] + 1)},
                     "players": [], "dates": [fixture(1, 1, 2, "2026-10-31 12:00:00")]}
            complete(block, block["dates"][0])
            for n in range(refresh.SUNDAY_COUNTS[lg]):
                block["dates"].append(fixture(100 + n, 2 * n + 1, 2 * n + 2,
                                               f"2026-11-01 {13 + n:02d}:00:00"))
            self.seed[lg + "_2026"] = block
            self.seed[lg + "_2025"] = {"teams": {"test": {"history": []}}, "players": [], "dates": []}
            fresh = copy.deepcopy(block)
            for match in fresh["dates"][1:]:
                complete(fresh, match)
            self.fresh[lg] = fresh
        self.args.seed.write_text(json.dumps(self.seed))

    def fetch(self, league, addresses, staging):
        return copy.deepcopy(self.fresh[league]), {
            "fetched_at_utc": refresh.utcnow(), "source_ip": "203.0.113.10",
            "source_url": f"https://understat.com/getLeagueData/{league}/2026",
            "resolution_source": "OFFLINE TEST ONLY", "tls_verified": True,
            "http_status": 200, "response_sha256": refresh.sha256(json.dumps(self.fresh[league]).encode()),
        }

    def run_recovery(self, fetch=None, addresses=None):
        with patch.object(refresh, "resolve_addresses", return_value={"203.0.113.10": "OFFLINE TEST ONLY"} if addresses is None else addresses), \
                patch.object(refresh, "fetch_league", side_effect=fetch or self.fetch) as mocked_fetch, \
                patch.object(refresh.time, "sleep"), redirect_stdout(io.StringIO()):
            code = refresh.run_once(self.args)
        return code, mocked_fetch

    def test_dns_outage_logs_and_does_not_create_snapshot(self):
        code, fetched = self.run_recovery(addresses={})
        self.assertEqual(code, 1)
        self.assertFalse(self.args.output.exists())
        fetched.assert_not_called()
        self.assertEqual(json.loads(self.args.status.read_text())["event"], "waiting_for_dns")
        # failing attempts must never touch the latest-snapshot pointer
        self.assertFalse(self.args.latest.exists())
        self.assertFalse(self.args.latest_meta.exists())

    def test_success_publishes_all_leagues_preserves_history_and_stops_fetching(self):
        code, fetched = self.run_recovery()
        self.assertEqual(code, 0)
        self.assertEqual(fetched.call_count, 5)
        data = json.loads(self.args.output.read_text())
        summary = refresh.validate_snapshot(data, self.seed)
        self.assertEqual(sum(s["sunday_completed_matches"] for s in summary.values()), 16)
        for lg in refresh.LEAGUES:
            self.assertEqual(data[lg + "_2025"], self.seed[lg + "_2025"])
        self.assertFalse(data["_provenance"]["preserved_historical_season"]["refetched"])
        original_bytes = self.args.output.read_bytes()
        with patch.object(refresh, "resolve_addresses", side_effect=AssertionError("No further DNS requests")), \
                patch.object(refresh, "fetch_league", side_effect=AssertionError("No further site requests")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(refresh.run_once(self.args), 0)
        self.assertEqual(self.args.output.read_bytes(), original_bytes)
        self.assertEqual(json.loads(self.args.status.read_text())["event"], "already_complete")

    def test_success_repoints_latest_snapshot_pointer(self):
        """Codex review #11 (2026-11-04): recovery must feed active scanning."""
        # seed the pointer at an older valid snapshot (the round25 stand-in)
        older = self.root / "older.json"
        shutil.copyfile(self.args.seed, older)
        # the seed itself is not a complete snapshot; point via a manual link
        self.args.latest.symlink_to(older.name)
        self.args.latest_meta.write_text(json.dumps({"target": str(older), "status": "stale-seed"}))
        code, _ = self.run_recovery()
        self.assertEqual(code, 0)
        # pointer now resolves to the freshly recovered output
        self.assertEqual(os.path.realpath(self.args.latest), str(self.args.output.resolve()))
        meta = json.loads(self.args.latest_meta.read_text())
        self.assertEqual(meta["target"], str(self.args.output.resolve()))
        self.assertEqual(meta["status"], "complete")
        self.assertTrue(meta["paper_only"])
        self.assertEqual(meta["sha256"], refresh.sha256(self.args.output.read_bytes()))
        self.assertEqual(sorted(meta["leagues"]), sorted(refresh.LEAGUES))
        # a failed later attempt must leave the pointer at the last valid target
        def broken_fetch(league, addresses, staging):
            raise ValueError("upstream broke after recovery")
        with patch.object(refresh, "resolve_addresses", return_value={"203.0.113.10": "x"}), \
                patch.object(refresh, "fetch_league", side_effect=broken_fetch), \
                redirect_stdout(io.StringIO()):
            # make the existing output invalid so recovery re-attempts the fetch
            data = json.loads(self.args.output.read_text())
            data["_provenance"]["status"] = "tampered"
            self.args.output.write_text(json.dumps(data))
            self.assertEqual(refresh.run_once(self.args), 1)
        self.assertEqual(os.path.realpath(self.args.latest), str(self.args.output.resolve()))
        self.assertEqual(json.loads(self.args.latest_meta.read_text())["target"],
                         str(self.args.output.resolve()))

    def test_partial_failure_preserves_previous_file(self):
        self.args.output.write_text("previous snapshot bytes\n")
        def fail_on_fifth(lg, addresses, staging):
            if lg == "Ligue_1":
                raise ValueError("upstream HTTP 503")
            return self.fetch(lg, addresses, staging)
        code, fetched = self.run_recovery(fetch=fail_on_fifth)
        self.assertEqual(code, 1)
        self.assertEqual(fetched.call_count, 5)
        self.assertEqual(self.args.output.read_text(), "previous snapshot bytes\n")
        self.assertEqual(list(self.root.glob(".understat-attempt-*")), [])

    def test_stale_payload_cannot_pass_as_recovery(self):
        self.fresh["EPL"] = self.seed["EPL_2026"]
        code, fetched = self.run_recovery()
        self.assertEqual(code, 1)
        self.assertEqual(fetched.call_count, 1)
        self.assertFalse(self.args.output.exists())
        self.assertIn("Sunday results are still missing", self.args.status.read_text())

    def test_missing_xg_and_nonfinite_xg_are_rejected(self):
        for value in (None, "NaN", "Infinity", -1, True):
            with self.subTest(value=value):
                broken = copy.deepcopy(self.fresh["EPL"])
                broken["dates"][-1]["xG"]["h"] = value
                with self.assertRaises(ValueError):
                    refresh.validate_league("EPL", broken, self.seed["EPL_2026"])

    def test_previously_completed_matches_cannot_disappear(self):
        broken = copy.deepcopy(self.fresh["EPL"])
        broken["dates"] = broken["dates"][1:]
        with self.assertRaisesRegex(ValueError, "previously completed"):
            refresh.validate_league("EPL", broken, self.seed["EPL_2026"])

    def test_result_and_team_history_disagreement_rejected(self):
        broken = copy.deepcopy(self.fresh["EPL"])
        broken["teams"]["1"]["history"][-1]["xG"] = 0.0
        with self.assertRaisesRegex(ValueError, "values disagree"):
            refresh.validate_league("EPL", broken, self.seed["EPL_2026"])

    def test_lock_prevents_overlapping_network_requests(self):
        with self.args.output.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, fetched = self.run_recovery()
        self.assertEqual(code, 0)
        fetched.assert_not_called()
        self.assertIn("skipped_locked", self.args.log.read_text())

    def test_atomic_write_failure_preserves_previous_file(self):
        self.args.output.write_text("previous complete file")
        with patch.object(refresh.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                refresh.atomic_json(self.args.output, {"new": "data"})
        self.assertEqual(self.args.output.read_text(), "previous complete file")
        self.assertEqual(list(self.root.glob(".snapshot.json.*")), [])

    def test_tls_failure_never_publishes_data(self):
        with patch.object(refresh, "command", return_value=(60, "", "certificate verification failed")):
            with self.assertRaisesRegex(ValueError, "curl exit 60"):
                refresh.fetch_league("EPL", {"45.90.32.72": "test"}, self.root)

    def test_doh_can_recover_when_system_dns_fails(self):
        def respond(cmd, timeout):
            if cmd[0].endswith("dig"):
                return 0, ";; status: SERVFAIL", ""
            answer = {"Status": 0, "Answer": [{"type": 1, "data": "45.90.32.72"}]} if cmd[-1].endswith("type=A") else {"Status": 0}
            return 0, json.dumps(answer), ""
        with patch.object(refresh, "command", side_effect=respond), redirect_stdout(io.StringIO()):
            self.assertEqual(refresh.resolve_addresses(self.args.log), {"45.90.32.72": "https://dns.google/resolve"})


if __name__ == "__main__":
    unittest.main()
