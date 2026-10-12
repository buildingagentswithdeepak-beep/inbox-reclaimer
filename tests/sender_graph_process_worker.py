"""Subprocess-only crash injector for the real sender graph, journal and executor."""

import argparse
import json
import os
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from inbox_reclaimer.profile import account_lock
from inbox_reclaimer.models import ReclaimError
from sender_graph_helper import GraphEnvironment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("mode", choices=("prepare", "approve", "resume", "list", "reject", "export"))
    parser.add_argument("--approval")
    parser.add_argument("--fault")
    parser.add_argument("--now", type=float, default=1000.0)
    args = parser.parse_args()
    env = GraphEnvironment(args.root)
    env.clock[0] = args.now

    def fault(stage):
        if args.fault == stage:
            os._exit(73)

    begin, finish = env.journal.begin, env.journal.finish

    def crash_begin(*a, **kw):
        fault("before_intent")
        result = begin(*a, **kw)
        fault("after_intent")
        return result

    def crash_finish(*a, **kw):
        fault("before_outcome")
        result = finish(*a, **kw)
        fault("after_outcome")
        return result

    env.journal.begin = crash_begin
    env.journal.finish = crash_finish
    env.mailbox.hook = fault
    trash = env.mailbox.trash_ids

    def crash_response(ids):
        result = trash(ids)
        fault("after_response")
        return result

    env.mailbox.trash_ids = crash_response
    put = SqliteSaver.put

    def crash_checkpoint(self, config, checkpoint, metadata, new_versions):
        status = checkpoint.get("channel_values", {}).get("status")
        # Select the post-dispatch checkpoint, not preparation/approval checkpoints.
        if status == "sender_run_finished":
            fault("before_checkpoint")
        result = put(self, config, checkpoint, metadata, new_versions)
        if status == "sender_run_finished":
            fault("after_checkpoint")
        return result

    SqliteSaver.put = crash_checkpoint
    try:
        with account_lock(env.paths, env.identity.account_id):
            if args.mode == "approve":
                result = {"approval_id": env.approve()}
            elif args.mode == "export":
                fault("before_export")
                result = env.store.export_audit(args.root / "audit.jsonl")
                fault("after_export")
            elif args.mode == "prepare":
                result = env.run(writer=False)
                fault("after_interrupt")
            elif args.mode in ("list", "reject"):
                result = env.run(args.approval, decision=args.mode, writer=False)
            else:
                result = env.run(args.approval)
            result = dict(result)
            result["calls"] = env.mailbox.calls
            result["operations"] = [
                {"message_id": o["message_id"], "state": o["state"], "approval_id": o["approval_id"]}
                for o in env.journal.operations(env.plan.account_id)
            ]
            print(json.dumps(result))
    except (ValueError, RuntimeError, ReclaimError) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}))
        return 2
    finally:
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
