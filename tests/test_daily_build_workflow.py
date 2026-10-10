"""Exercise the actual publication shell block without contacting GitHub."""

import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-build.yml"
MARKER = "      - name: Commit updated data files\n        run: |\n"


def run_publication(tmp_path, *, push_failures=0, no_changes=False, pull_fails=False):
    _, marker, script = WORKFLOW.read_text().partition(MARKER)
    assert marker, "Publication step was not found in the workflow"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text(
        textwrap.dedent("""\
        #!/usr/bin/env python3
        import os
        import sys
        from pathlib import Path

        state = Path(os.environ['TEST_GIT_STATE'])
        args = sys.argv[1:]
        with (state / 'git-calls').open('a') as f:
            f.write(' '.join(args) + '\\n')
        if args[0] == 'diff':
            sys.exit(0 if os.environ['TEST_NO_CHANGES'] == '1' else 1)
        if args[0] == 'pull' and os.environ['TEST_PULL_FAILS'] == '1':
            sys.exit(1)
        if args[0] == 'push':
            counter = state / 'push-count'
            attempts = int(counter.read_text()) + 1 if counter.exists() else 1
            counter.write_text(str(attempts))
            if attempts <= int(os.environ['TEST_PUSH_FAILURES']):
                print('remote: Internal Server Error', file=sys.stderr)
                sys.exit(1)
        sys.exit(0)
        """)
    )
    sleep = bin_dir / "sleep"
    sleep.write_text(
        textwrap.dedent("""\
        #!/usr/bin/env python3
        import os
        import sys
        from pathlib import Path

        with (Path(os.environ['TEST_GIT_STATE']) / 'sleep-calls').open('a') as f:
            f.write(sys.argv[1] + '\\n')
        """)
    )
    git.chmod(0o755)
    sleep.chmod(0o755)
    env = dict(
        os.environ,
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        TEST_GIT_STATE=str(tmp_path),
        TEST_PUSH_FAILURES=str(push_failures),
        TEST_NO_CHANGES="1" if no_changes else "0",
        TEST_PULL_FAILS="1" if pull_fails else "0",
    )
    result = subprocess.run(
        ["bash", "-e", "-c", textwrap.dedent(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    calls = (tmp_path / "git-calls").read_text().splitlines()
    sleep_path = tmp_path / "sleep-calls"
    waits = sleep_path.read_text().splitlines() if sleep_path.exists() else []
    return result, calls, waits


def test_successful_push_needs_no_retry(tmp_path):
    result, calls, waits = run_publication(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls.count("push") == 1
    assert calls.count("pull --rebase -X theirs") == 1
    assert waits == []


def test_transient_failures_succeed_on_the_third_attempt(tmp_path):
    result, calls, waits = run_publication(tmp_path, push_failures=2)

    assert result.returncode == 0, result.stderr
    assert calls.count("push") == 3
    assert calls.count("pull --rebase -X theirs") == 3
    assert sum(call.startswith("commit ") for call in calls) == 1
    assert waits == ["10", "20"]
    assert not any("--force" in call for call in calls)


def test_persistent_failure_remains_a_failed_workflow(tmp_path):
    result, calls, waits = run_publication(tmp_path, push_failures=3)

    assert result.returncode != 0
    assert calls.count("push") == 3
    assert waits == ["10", "20"]
    assert "::error::Failed to publish data after 3 attempts." in result.stdout


def test_unchanged_data_does_not_create_or_push_a_commit(tmp_path):
    result, calls, waits = run_publication(tmp_path, no_changes=True)

    assert result.returncode == 0, result.stderr
    assert not any(call.startswith(("commit ", "pull", "push")) for call in calls)
    assert waits == []


def test_rebase_failure_stops_before_push(tmp_path):
    result, calls, waits = run_publication(tmp_path, pull_fails=True)

    assert result.returncode != 0
    assert calls.count("pull --rebase -X theirs") == 1
    assert "push" not in calls
    assert waits == []
