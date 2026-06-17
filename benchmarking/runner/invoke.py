"""Invoke the formalize agent on a single problem via claude -p."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from benchmarking.config import RunConfig


@dataclass
class RunResult:
    """Result of invoking the formalize agent on a single problem."""

    problem_id: str
    success: bool
    exit_code: int
    duration_seconds: float
    lean_source: str | None = None
    problem_spec_json: dict | None = None
    agent_transcript: str = ""
    error_message: str = ""
    files_written: list[str] = field(default_factory=list)
    working_dir: str = ""

    def to_dict(self) -> dict:
        return {
            "problem_id": self.problem_id,
            "success": self.success,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "lean_source": self.lean_source,
            "problem_spec_json": self.problem_spec_json,
            "agent_transcript": self.agent_transcript[:50000],
            "error_message": self.error_message,
            "files_written": self.files_written,
        }


_DENIED_ENV_KEYS = {"PWD", "OLDPWD", "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV"}


def _prepare_workdir(project_root: Path) -> Path:
    """Create an isolated temp directory with only the agent definition."""
    workdir = Path(tempfile.mkdtemp(prefix="fc_bench_"))

    agents_src = project_root / ".claude" / "agents"
    agents_dst = workdir / ".claude" / "agents"
    if agents_src.exists():
        shutil.copytree(agents_src, agents_dst)

    return workdir


def _scrubbed_env() -> dict[str, str]:
    """Return environment with project-path vars removed to limit data leakage."""
    return {k: v for k, v in os.environ.items() if k not in _DENIED_ENV_KEYS}


def _is_within_allowed_roots(path: Path, roots: list[Path]) -> bool:
    """True if *path* resolves inside one of *roots* (no traversal escape)."""
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return False
    return any(resolved.is_relative_to(root.resolve()) for root in roots)


def _collect_outputs(workdir: Path, transcript: str) -> tuple[str | None, dict | None, list[str]]:
    """Collect outputs from workdir and agent transcript.

    The agent may write files to /tmp/ subdirectories rather than the workdir,
    so we also extract lean source from the JSON transcript's result text.
    """
    lean_source = None
    problem_spec = None
    files: list[str] = []

    for f in workdir.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(workdir))
        if rel.startswith(".claude"):
            continue
        files.append(rel)

        if f.suffix == ".lean" and lean_source is None:
            lean_source = f.read_text()
        elif f.name.endswith(".json") and "spec" in f.name.lower():
            try:
                problem_spec = json.loads(f.read_text())
            except json.JSONDecodeError:
                pass

    # If no lean source in workdir, try extracting from the transcript. Reads
    # are sandboxed to the run workdir and the system temp dir (where the agent
    # legitimately writes) so a regex-harvested path can't read arbitrary files.
    allowed_roots = [workdir, Path(tempfile.gettempdir())]
    if lean_source is None and transcript:
        lean_source, file_path = _extract_lean_from_transcript(transcript, allowed_roots)
        if file_path:
            files.append(file_path)
            # Also try reading the file if it still exists on disk
            p = Path(file_path)
            if (
                p.suffix == ".lean"
                and _is_within_allowed_roots(p, allowed_roots)
                and p.is_file()
            ):
                lean_source = p.read_text()

    return lean_source, problem_spec, files


def _extract_lean_from_transcript(
    transcript: str, allowed_roots: list[Path]
) -> tuple[str | None, str | None]:
    """Extract lean source code from the agent's JSON result output.

    Prefers an on-disk ``.lean`` file the agent mentions (that's the artifact it
    actually verified) over a fenced code block. Agents often write the proof to
    a path under the system temp dir (e.g. ``/tmp/foo.lean``) and only describe
    it in prose, so we accept any mentioned ``.lean`` path that resolves inside
    *allowed_roots* (the run workdir and the system temp dir); paths outside
    those roots are ignored rather than read.
    """
    import re

    try:
        result = json.loads(transcript)
    except (json.JSONDecodeError, TypeError):
        return None, None

    result_text = result.get("result", "")
    if not result_text:
        return None, None

    # Candidate .lean paths, in priority order: explicit "**File**: `...`",
    # then any backtick-quoted path, then bare paths in the prose.
    candidates: list[str] = []
    m = re.search(r'\*\*File\*\*:\s*`([^`]+\.lean)`', result_text)
    if m:
        candidates.append(m.group(1))
    candidates += re.findall(r'`([^`\n]+\.lean)`', result_text)
    candidates += re.findall(r'(?<![`\w])((?:/|\./)?[\w./-]+\.lean)\b', result_text)

    file_path = candidates[0] if candidates else None
    seen: set[str] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        p = Path(cand)
        if _is_within_allowed_roots(p, allowed_roots) and p.is_file():
            return p.read_text(), cand

    # Otherwise, fall back to the longest fenced ```lean block.
    lean_blocks = re.findall(r'```lean\n(.*?)```', result_text, re.DOTALL)
    if lean_blocks:
        return max(lean_blocks, key=len), file_path

    return None, file_path


async def invoke_single(
    problem: dict,
    config: RunConfig,
    project_root: Path,
) -> RunResult:
    """Run the formalize agent on a single problem.

    Creates an isolated working directory, invokes `claude -p --agent formalize`,
    and captures the result.
    """
    problem_id = problem["id"]
    narrative = problem["natural_language_statement"]
    prompt = f"Narrative: {narrative}"

    workdir = _prepare_workdir(project_root)

    cmd = config.claude_args + [prompt]
    env = _scrubbed_env()

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=config.timeout_seconds,
        )
        exit_code = proc.returncode or 0
        transcript = stdout.decode(errors="replace")
        error_msg = stderr.decode(errors="replace") if exit_code != 0 else ""

    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        duration = time.monotonic() - start
        return RunResult(
            problem_id=problem_id,
            success=False,
            exit_code=-1,
            duration_seconds=duration,
            error_message="Timeout exceeded",
            working_dir=str(workdir),
        )
    except FileNotFoundError:
        duration = time.monotonic() - start
        return RunResult(
            problem_id=problem_id,
            success=False,
            exit_code=-2,
            duration_seconds=duration,
            error_message="claude CLI not found. Install Claude Code and authenticate.",
            working_dir=str(workdir),
        )

    duration = time.monotonic() - start
    lean_source, problem_spec, files = _collect_outputs(workdir, transcript)

    return RunResult(
        problem_id=problem_id,
        success=exit_code == 0 and lean_source is not None,
        exit_code=exit_code,
        duration_seconds=duration,
        lean_source=lean_source,
        problem_spec_json=problem_spec,
        agent_transcript=transcript,
        error_message=error_msg,
        files_written=files,
        working_dir=str(workdir),
    )
