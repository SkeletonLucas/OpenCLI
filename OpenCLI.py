#!/usr/bin/env python3
"""OpenCLI — single-file interactive CLI for everyday tasks.[cite: 1]

Requires Python 3.10+ and two packages:[cite: 1]

    pip install psutil requests[cite: 1]

Run:[cite: 1]

    python opencli.py[cite: 1]
    python opencli.py help[cite: 1]
    python opencli.py calc "2 + 2"[cite: 1]
    python opencli.py system memory[cite: 1]
"""

from __future__ import annotations

import ast
import base64
import fnmatch
import hashlib
import json
import math
import operator
import os
import platform
import re
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import webbrowser
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

try:
    import psutil
except ImportError:
    sys.stderr.write("Error: psutil is required. Install with:  pip install psutil\n")
    sys.exit(1)

try:
    import requests
except ImportError:
    sys.stderr.write("Error: requests is required. Install with:  pip install requests\n")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Terminal colors (works in Windows Terminal, modern PowerShell, and Unix)[cite: 1]
# ---------------------------------------------------------------------------

def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


_USE_COLOR = None  # resolved lazily[cite: 1]

# Palette: black #000000, yellow #F6F930, gray #A9ACA9, slate #576490, red #E71D36[cite: 1]
_PAL = {
    "black":  (0, 0, 0),
    "yellow": (246, 249, 48),
    "gray":   (169, 172, 169),
    "slate":  (87, 100, 144),
    "red":    (231, 29, 54),
}


def _enable_windows_ansi() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _ensure_color() -> bool:
    global _USE_COLOR
    if _USE_COLOR is None:
        _USE_COLOR = _color_enabled()
        if _USE_COLOR:
            _enable_windows_ansi()
    return bool(_USE_COLOR)


def _rgb(r: int, g: int, b: int, text: str, bold: bool = False) -> str:
    if not _ensure_color():
        return text
    prefix = "\033[1;" if bold else "\033["
    return f"{prefix}38;2;{r};{g};{b}m{text}\033[0m"


def _pal(name: str, text: str, bold: bool = False) -> str:
    r, g, b = _PAL[name]
    return _rgb(r, g, b, text, bold=bold)


def bold(t: str) -> str:
    if not _ensure_color():
        return t
    return f"\033[1m{t}\033[0m"


def dim(t: str) -> str:
    return _pal("gray", t)


def cyan(t: str) -> str:
    return _pal("slate", t)


def green(t: str) -> str:
    return _pal("slate", t)


def yellow(t: str) -> str:
    return _pal("yellow", t)


def red(t: str) -> str:
    return _pal("red", t)


def magenta(t: str) -> str:
    return _pal("slate", t)


def blue(t: str) -> str:
    return _pal("slate", t)


def header(t: str) -> str:
    return _pal("yellow", t, bold=True)


def ok(t: str) -> str:
    return _pal("slate", t)


def warn(t: str) -> str:
    return _pal("yellow", t)


def err(t: str) -> str:
    return _pal("red", t, bold=True)


def clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def _term_width(default: int = 72) -> int:
    try:
        return max(40, shutil.get_terminal_size(fallback=(default, 24)).columns)
    except Exception:
        return default


def _hide_cursor() -> None:
    if _ensure_color():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()


def _show_cursor() -> None:
    if _ensure_color():
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


def _draw_frame(lines: list[str], first: bool = False) -> None:
    width = _term_width()
    def visible_len(s: str) -> int:
        out = []
        i = 0
        while i < len(s):
            if s[i] == "\033":
                i += 1
                if i < len(s) and s[i] == "[":
                    i += 1
                    while i < len(s) and not s[i].isalpha():
                        i += 1
                    i += 1
                continue
            out.append(s[i])
            i += 1
        return len(out)

    padded = []
    for line in lines:
        vis = visible_len(line)
        if vis < width:
            padded.append(line + (" " * (width - vis)))
        else:
            padded.append(line)

    buf = []
    if first:
        buf.append("\033[2J\033[H")
    else:
        buf.append("\033[H")
    buf.append("\n".join(padded))
    buf.append("\033[J")
    sys.stdout.write("".join(buf))
    sys.stdout.flush()


def rule(char: str = "─", width: int = 56) -> str:
    return dim(char * width)


def bar(pct: float, width: int = 20) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    empty = width - filled
    fill_ch = "█" * filled
    empty_ch = "░" * empty
    if pct >= 90:
        body = red(fill_ch) + dim(empty_ch)
    elif pct >= 70:
        body = yellow(fill_ch) + dim(empty_ch)
    else:
        body = cyan(fill_ch) + dim(empty_ch)
    return f"[{body}] {pct:5.1f}%"


# ========================================================================
# Utils[cite: 1]
# ========================================================================

def human_bytes(n: float) -> str:
    if n < 0:
        return f"-{human_bytes(-n)}"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def human_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return "  ".join(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt_row(cells: Sequence[str]) -> str:
        return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    lines.extend(fmt_row(row) for row in rows)
    return "\n".join(lines)


def truncate(text: str, max_len: int = 200) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "\u2026"


# ---------------------------------------------------------------------------
# Safe calculator (AST whitelist)[cite: 1]
# ---------------------------------------------------------------------------

class CalculatorError(Exception):
    pass


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {
    "sqrt": math.sqrt, "abs": abs, "round": round,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log2": math.log2, "log10": math.log10,
    "exp": math.exp, "floor": math.floor, "ceil": math.ceil,
    "min": min, "max": max,
}
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_MAX_POWER_EXPONENT = 1000


def evaluate(expression: str) -> float:
    expression = expression.strip()
    if not expression:
        raise CalculatorError("No expression given")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"Invalid expression: {exc.msg}") from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise CalculatorError("Only numeric constants are allowed")
    if isinstance(node, ast.BinOp):
        op_func = _BIN_OPS.get(type(node.op))
        if op_func is None:
            raise CalculatorError(f"Operator not allowed: {type(node.op).__name__}")
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_POWER_EXPONENT:
            raise CalculatorError("Exponent too large")
        try:
            return op_func(left, right)
        except ZeroDivisionError as exc:
            raise CalculatorError("Division by zero") from exc
    if isinstance(node, ast.UnaryOp):
        op_func = _UNARY_OPS.get(type(node.op))
        if op_func is None:
            raise CalculatorError(f"Operator not allowed: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise CalculatorError(f"Unknown identifier: {node.id}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise CalculatorError("Only whitelisted functions are allowed")
        if node.keywords:
            raise CalculatorError("Keyword arguments are not supported")
        args = [_eval_node(arg) for arg in node.args]
        try:
            return _FUNCTIONS[node.func.id](*args)
        except (TypeError, ValueError) as exc:
            raise CalculatorError(str(exc)) from exc
    raise CalculatorError(f"Expression not allowed: {type(node).__name__}")

# ========================================================================
# Core[cite: 1]
# ========================================================================

@dataclass(frozen=True)
class Argument:
    name: str
    description: str = ""
    required: bool = True
    variadic: bool = False


@dataclass(frozen=True)
class Option:
    name: str
    description: str = ""
    short: Optional[str] = None
    takes_value: bool = True
    default: Any = None
    choices: Optional[tuple[str, ...]] = None


@dataclass
class CommandContext:
    args: list[str]
    options: dict[str, Any]
    raw_input: str
    config: Any = None
    shell: Any = None


@dataclass
class CommandResult:
    output: str = ""
    success: bool = True
    data: Any = None

    def __bool__(self) -> bool:
        return self.success


Handler = Callable[[CommandContext], CommandResult]


@dataclass(frozen=True)
class Subcommand:
    name: str
    description: str
    handler: Handler
    arguments: tuple[Argument, ...] = field(default_factory=tuple)
    options: tuple[Option, ...] = field(default_factory=tuple)
    usage: Optional[str] = None

    def usage_line(self, parent: str) -> str:
        if self.usage:
            return self.usage
        parts = [parent, self.name]
        for arg in self.arguments:
            token = f"<{arg.name}>" if arg.required else f"[{arg.name}]"
            parts.append(token + ("..." if arg.variadic else ""))
        return " ".join(parts)


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    handler: Optional[Handler] = None
    arguments: tuple[Argument, ...] = field(default_factory=tuple)
    options: tuple[Option, ...] = field(default_factory=tuple)
    subcommands: tuple[Subcommand, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    usage: Optional[str] = None

    def get_subcommand(self, name: str) -> Optional[Subcommand]:
        for sub in self.subcommands:
            if sub.name == name:
                return sub
        return None

    def usage_line(self) -> str:
        if self.usage:
            return self.usage
        if self.subcommands:
            return f"{self.name} <subcommand>"
        parts = [self.name]
        for arg in self.arguments:
            token = f"<{arg.name}>" if arg.required else f"[{arg.name}]"
            parts.append(token + ("..." if arg.variadic else ""))
        return " ".join(parts)


class ParseError(Exception):
    pass


@dataclass
class ParsedInput:
    command: str
    subcommand: str | None = None
    args: list[str] = field(default_factory=list)
    options: dict[str, str | bool] = field(default_factory=dict)
    raw: str = ""


def _is_option(token: str) -> bool:
    return token.startswith("-") and token != "-" and not _looks_like_negative_number(token)


def _looks_like_negative_number(token: str) -> bool:
    if not token.startswith("-"):
        return False
    try:
        float(token)
        return True
    except ValueError:
        return False


def parse(line: str) -> ParsedInput | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        raise ParseError(str(exc)) from exc
    if not tokens:
        return None

    command = tokens[0]
    rest = tokens[1:]
    args: list[str] = []
    options: dict[str, str | bool] = {}
    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--"):
            key = token[2:]
            if "=" in key:
                key, value = key.split("=", 1)
                options[key] = value
            elif i + 1 < len(rest) and not _is_option(rest[i + 1]):
                options[key] = rest[i + 1]
                i += 1
            else:
                options[key] = True
        elif token.startswith("-") and _is_option(token):
            key = token[1:]
            if i + 1 < len(rest) and not _is_option(rest[i + 1]):
                options[key] = rest[i + 1]
                i += 1
            else:
                options[key] = True
        else:
            args.append(token)
        i += 1

    subcommand = args[0] if args else None
    remaining_args = args[1:] if args else []
    return ParsedInput(
        command=command,
        subcommand=subcommand,
        args=remaining_args,
        options=options,
        raw=stripped,
    )


class DuplicateCommandError(Exception):
    pass


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}

    def register(self, command: Command) -> None:
        if command.name in self._commands:
            raise DuplicateCommandError(f"Command '{command.name}' is already registered")
        self._commands[command.name] = command
        for alias in command.aliases:
            if alias in self._aliases or alias in self._commands:
                raise DuplicateCommandError(f"Alias '{alias}' conflicts with an existing name")
            self._aliases[alias] = command.name

    def get(self, name: str) -> Optional[Command]:
        canonical = self._aliases.get(name, name)
        return self._commands.get(canonical)

    def all(self) -> Iterable[Command]:
        return sorted(self._commands.values(), key=lambda c: c.name)

    def names(self) -> list[str]:
        return sorted(self._commands.keys())

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None


class RoutingError(Exception):
    pass


class Router:
    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry

    def dispatch(self, parsed: ParsedInput, *, config=None, shell=None) -> CommandResult:
        command = self.registry.get(parsed.command)
        if command is None:
            raise RoutingError(f"Unknown command: '{parsed.command}'")

        if command.subcommands and parsed.subcommand is not None:
            sub = command.get_subcommand(parsed.subcommand)
            if sub is not None:
                context = CommandContext(
                    args=parsed.args,
                    options=parsed.options,
                    raw_input=parsed.raw,
                    config=config,
                    shell=shell,
                )
                return sub.handler(context)
            if command.handler is None:
                valid = ", ".join(s.name for s in command.subcommands)
                return CommandResult(
                    output=(
                        err(f"Unknown subcommand '{parsed.subcommand}' for {command.name}.")
                        + "\n\n" + bold("Valid:") + f" {valid}"
                    ),
                    success=False,
                )

        if command.handler is None:
            valid = ", ".join(s.name for s in command.subcommands)
            return CommandResult(
                output=(
                    header(command.name) + "\n"
                    + (command.description or "") + "\n\n"
                    + bold("Subcommands:") + "\n"
                    + "\n".join(f"  {cyan(s.name):<20} {s.description}" for s in command.subcommands)
                    + "\n\n" + bold("Usage:") + f" {command.usage_line()}"
                ),
                success=False,
            )

        full_args = ([parsed.subcommand] if parsed.subcommand is not None else []) + parsed.args
        context = CommandContext(
            args=full_args,
            options=parsed.options,
            raw_input=parsed.raw,
            config=config,
            shell=shell,
        )
        return command.handler(context)


def default_config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "opencli"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "opencli"


def default_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "opencli"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "opencli"


@dataclass
class Config:
    default_search_dir: str = "~"
    max_search_results: int = 20
    history_size: int = 1000
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or (default_config_dir() / "config.json")
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return cls()
        raw.pop("ai", None)
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path | None = None) -> None:
        path = path or (default_config_dir() / "config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")

    def get(self, dotted_key: str, default: Any = None) -> Any:
        parts = dotted_key.split(".")
        node: Any = self
        for part in parts:
            if hasattr(node, part):
                node = getattr(node, part)
            elif isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, dotted_key: str, value: Any) -> bool:
        parts = dotted_key.split(".")
        node: Any = self
        for part in parts[:-1]:
            if hasattr(node, part):
                node = getattr(node, part)
            else:
                return False
        last = parts[-1]
        if hasattr(node, last):
            current = getattr(node, last)
            if isinstance(current, bool):
                value = str(value).lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int) and not isinstance(current, bool):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return False
            setattr(node, last, value)
            return True
        return False


class History:
    def __init__(self, max_size: int = 1000, path: Path | None = None) -> None:
        self.max_size = max_size
        self.path = path
        self._entries: list[str] = []
        if path and path.exists():
            self._load()

    def add(self, entry: str) -> None:
        entry = entry.strip()
        if not entry:
            return
        if self._entries and self._entries[-1] == entry:
            return
        self._entries.append(entry)
        if len(self._entries) > self.max_size:
            self._entries = self._entries[-self.max_size :]

    def all(self) -> list[str]:
        return list(self._entries)

    def last(self, n: int = 10) -> list[str]:
        return self._entries[-n:]

    def clear(self) -> None:
        self._entries.clear()

    def _load(self) -> None:
        try:
            lines = self.path.read_text().splitlines()
            self._entries = [line for line in lines if line.strip()][-self.max_size :]
        except OSError:
            self._entries = []

    def save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("\n".join(self._entries) + "\n")
        except OSError:
            pass

    def __len__(self) -> int:
        return len(self._entries)

# ========================================================================
# Services[cite: 1]
# ========================================================================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)

    @contextmanager
    def cursor(self):
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


@dataclass
class CPUInfo:
    logical_cores: int
    physical_cores: int | None
    percent: float
    per_core_percent: list[float]
    frequency_mhz: float | None


@dataclass
class MemoryInfo:
    total: int
    available: int
    used: int
    percent: float
    swap_total: int
    swap_used: int
    swap_percent: float


@dataclass
class DiskUsage:
    mountpoint: str
    device: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass
class NetworkInterface:
    name: str
    is_up: bool
    addresses: list[str]
    bytes_sent: int
    bytes_recv: int


@dataclass
class ProcessInfo:
    pid: int
    name: str
    username: str | None
    cpu_percent: float
    memory_percent: float
    status: str


@dataclass
class SystemSummary:
    hostname: str
    os_name: str
    os_version: str
    architecture: str
    uptime_seconds: float
    boot_time: float


class SystemService:
    def summary(self) -> SystemSummary:
        return SystemSummary(
            hostname=socket.gethostname(),
            os_name=platform.system(),
            os_version=platform.release(),
            architecture=platform.machine(),
            uptime_seconds=time.time() - psutil.boot_time(),
            boot_time=psutil.boot_time(),
        )

    def cpu(self) -> CPUInfo:
        per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        freq = psutil.cpu_freq()
        return CPUInfo(
            logical_cores=psutil.cpu_count(logical=True) or 0,
            physical_cores=psutil.cpu_count(logical=False),
            percent=sum(per_core) / len(per_core) if per_core else 0.0,
            per_core_percent=per_core,
            frequency_mhz=freq.current if freq else None,
        )

    def memory(self) -> MemoryInfo:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return MemoryInfo(
            total=vm.total, available=vm.available, used=vm.used, percent=vm.percent,
            swap_total=sw.total, swap_used=sw.used, swap_percent=sw.percent,
        )

    def disks(self) -> list[DiskUsage]:
        results = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            results.append(DiskUsage(
                mountpoint=part.mountpoint, device=part.device, fstype=part.fstype,
                total=usage.total, used=usage.used, free=usage.free, percent=usage.percent,
            ))
        return results

    def network(self) -> list[NetworkInterface]:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        io_counters = psutil.net_io_counters(pernic=True)
        results = []
        for name, stat in stats.items():
            addr_list = [a.address for a in addrs.get(name, []) if a.address]
            io = io_counters.get(name)
            results.append(NetworkInterface(
                name=name, is_up=stat.isup, addresses=addr_list,
                bytes_sent=io.bytes_sent if io else 0,
                bytes_recv=io.bytes_recv if io else 0,
            ))
        return results

    def processes(self, limit: int = 15, sort_by: str = "cpu") -> list[ProcessInfo]:
        procs = []
        for proc in psutil.process_iter(
            ["pid", "name", "username", "cpu_percent", "memory_percent", "status"]
        ):
            try:
                info = proc.info
                procs.append(ProcessInfo(
                    pid=info["pid"], name=info["name"] or "?",
                    username=info.get("username"),
                    cpu_percent=info.get("cpu_percent") or 0.0,
                    memory_percent=info.get("memory_percent") or 0.0,
                    status=info.get("status") or "?",
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        key = "memory_percent" if sort_by == "memory" else "cpu_percent"
        procs.sort(key=lambda p: getattr(p, key), reverse=True)
        return procs[:limit]


_SKIP_DIR_NAMES = {
    "System Volume Information",
    "$Recycle.Bin",
    ".git", ".hg", ".svn", "node_modules", "__pycache__",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", ".tox",
}
_SKIP_ROOTS = {"/proc", "/sys", "/dev", "/run"}


@dataclass
class FileMatch:
    path: str
    size: int
    is_dir: bool


class FileSearchError(Exception):
    pass


class FileService:
    def find(
        self,
        pattern: str,
        start_dir: str | Path = ".",
        max_results: int = 200,
        max_depth: int | None = None,
        case_sensitive: bool = False,
    ) -> list[FileMatch]:
        root = Path(start_dir).expanduser().resolve()
        if not root.exists():
            raise FileSearchError(f"Directory does not exist: {root}")
        if not root.is_dir():
            raise FileSearchError(f"Not a directory: {root}")

        is_glob = any(ch in pattern for ch in "*?[]")
        needle = pattern if case_sensitive else pattern.lower()
        matches: list[FileMatch] = []
        start_depth = len(root.parts)

        for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=lambda e: None):
            if any(str(dirpath).startswith(skip) for skip in _SKIP_ROOTS):
                dirnames[:] = []
                continue
            depth = len(Path(dirpath).parts) - start_depth
            if max_depth is not None and depth >= max_depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]
            names = list(dirnames) + list(filenames)
            for name in names:
                haystack = name if case_sensitive else name.lower()
                matched = fnmatch.fnmatch(haystack, needle) if is_glob else needle in haystack
                if not matched:
                    continue
                full = Path(dirpath) / name
                try:
                    is_dir = full.is_dir()
                    size = 0 if is_dir else full.stat().st_size
                except OSError:
                    continue
                matches.append(FileMatch(path=str(full), size=size, is_dir=is_dir))
                if len(matches) >= max_results:
                    return matches
        return matches


_SEARCH_ENDPOINT = "https://api.duckduckgo.com/"
_TIMEOUT = 8


class SearchError(Exception):
    pass


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str


def _clean(text: str | None) -> str:
    return (text or "").strip()


class SearchService:
    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        query = query.strip()
        if not query:
            raise SearchError("Empty search query")
        try:
            response = requests.get(
                _SEARCH_ENDPOINT,
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 0},
                timeout=_TIMEOUT,
                headers={"User-Agent": "OpenCLI/1.0"},
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise SearchError("The search request timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise SearchError("Unable to reach the search service.") from exc
        except requests.exceptions.RequestException as exc:
            raise SearchError(f"Search request failed: {exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise SearchError("Search service returned an unreadable response.") from exc

        results: list[SearchResult] = []
        heading = _clean(data.get("Heading"))
        abstract = _clean(data.get("AbstractText"))
        abstract_url = _clean(data.get("AbstractURL"))
        if abstract and abstract_url:
            results.append(SearchResult(title=heading or query, snippet=abstract, url=abstract_url))

        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if "Topics" in topic:
                for sub in topic["Topics"]:
                    if len(results) >= max_results:
                        break
                    text = _clean(sub.get("Text"))
                    url = _clean(sub.get("FirstURL"))
                    if text and url:
                        title = text.split(" - ", 1)[0]
                        results.append(SearchResult(title=title, snippet=text, url=url))
                continue
            text = _clean(topic.get("Text"))
            url = _clean(topic.get("FirstURL"))
            if text and url:
                title = text.split(" - ", 1)[0]
                results.append(SearchResult(title=title, snippet=text, url=url))
        return results[:max_results]


_SUMMARY_ENDPOINT = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_WIKI_SEARCH_ENDPOINT = "https://en.wikipedia.org/w/api.php"


class WikipediaError(Exception):
    pass


class WikipediaNotFoundError(WikipediaError):
    pass


@dataclass
class WikipediaSummary:
    title: str
    extract: str
    url: str


class WikipediaService:
    def _get(self, url: str, **kwargs) -> requests.Response:
        try:
            return requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "OpenCLI/1.0"}, **kwargs)
        except requests.exceptions.Timeout as exc:
            raise WikipediaError("The Wikipedia request timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise WikipediaError("Unable to reach Wikipedia.") from exc
        except requests.exceptions.RequestException as exc:
            raise WikipediaError(f"Wikipedia request failed: {exc}") from exc

    def _find_best_title(self, query: str) -> str:
        response = self._get(
            _WIKI_SEARCH_ENDPOINT,
            params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 1},
        )
        if response.status_code != 200:
            raise WikipediaNotFoundError(f"No Wikipedia article found for '{query}'.")
        results = response.json().get("query", {}).get("search", [])
        if not results:
            raise WikipediaNotFoundError(f"No Wikipedia article found for '{query}'.")
        return results[0]["title"]

    def summary(self, query: str, full: bool = True) -> WikipediaSummary:
        query = query.strip()
        if not query:
            raise WikipediaError("Empty query")

        title = query
        response = self._get(_SUMMARY_ENDPOINT.format(title=query.replace(" ", "_")))
        if response.status_code == 404:
            title = self._find_best_title(query)
        elif response.status_code == 200:
            data = response.json()
            if data.get("type") == "disambiguation":
                raise WikipediaError(
                    f"'{query}' is ambiguous on Wikipedia. Try a more specific title."
                )
            title = data.get("title", query)
        else:
            raise WikipediaNotFoundError(f"No Wikipedia article found for '{query}'.")

        response = self._get(
            _WIKI_SEARCH_ENDPOINT,
            params={
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "exsectionformat": "plain",
                "titles": title,
                "format": "json",
            },
        )
        if response.status_code != 200:
            raise WikipediaError("Could not fetch the full Wikipedia article.")
        pages = response.json().get("query", {}).get("pages", {})
        if not pages:
            raise WikipediaNotFoundError(f"No Wikipedia article found for '{query}'.")
        page = next(iter(pages.values()))
        if "missing" in page:
            raise WikipediaNotFoundError(f"No Wikipedia article found for '{query}'.")
        extract = (page.get("extract") or "").strip()
        if not extract:
            raise WikipediaNotFoundError(f"No Wikipedia article found for '{query}'.")
        page_title = page.get("title", title)
        url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
        return WikipediaSummary(title=page_title, extract=extract, url=url)


_URL_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class BrowserError(Exception):
    pass


def normalize_url(target: str) -> str:
    target = target.strip()
    if not target:
        raise BrowserError("No URL given")
    if _URL_PATTERN.match(target):
        return target
    return f"https://{target}"


class BrowserService:
    def open(self, target: str) -> str:
        url = normalize_url(target)
        try:
            opened = webbrowser.open(url)
        except Exception as exc:
            raise BrowserError(f"Could not open browser: {exc}") from exc
        if not opened:
            raise BrowserError("No browser could be launched. Is a display/browser available?")
        return url


@dataclass
class Note:
    id: int
    text: str
    created_at: str


class NotesService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, text: str) -> Note:
        text = text.strip()
        if not text:
            raise ValueError("Note text cannot be empty")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO notes (text, created_at) VALUES (?, ?)", (text, now))
            note_id = cur.lastrowid
        return Note(id=note_id, text=text, created_at=now)

    def list(self) -> list[Note]:
        with self.db.cursor() as cur:
            rows = cur.execute("SELECT id, text, created_at FROM notes ORDER BY id").fetchall()
        return [Note(id=r["id"], text=r["text"], created_at=r["created_at"]) for r in rows]

    def get(self, note_id: int) -> Note | None:
        with self.db.cursor() as cur:
            row = cur.execute(
                "SELECT id, text, created_at FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
        if row is None:
            return None
        return Note(id=row["id"], text=row["text"], created_at=row["created_at"])

    def delete(self, note_id: int) -> bool:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return cur.rowcount > 0

    def clear(self) -> int:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM notes")
            return cur.rowcount


@dataclass
class Todo:
    id: int
    text: str
    done: bool
    created_at: str
    completed_at: str | None = None


class TodoService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, text: str) -> Todo:
        text = text.strip()
        if not text:
            raise ValueError("Todo text cannot be empty")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO todos (text, done, created_at) VALUES (?, 0, ?)", (text, now))
            todo_id = cur.lastrowid
        return Todo(id=todo_id, text=text, done=False, created_at=now)

    def list(self, include_done: bool = True) -> list[Todo]:
        query = "SELECT id, text, done, created_at, completed_at FROM todos"
        if not include_done:
            query += " WHERE done = 0"
        query += " ORDER BY id"
        with self.db.cursor() as cur:
            rows = cur.execute(query).fetchall()
        return [
            Todo(
                id=r["id"], text=r["text"], done=bool(r["done"]),
                created_at=r["created_at"], completed_at=r["completed_at"],
            )
            for r in rows
        ]

    def mark_done(self, todo_id: int) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE todos SET done = 1, completed_at = ? WHERE id = ? AND done = 0",
                (now, todo_id),
            )
            return cur.rowcount > 0

    def mark_undone(self, todo_id: int) -> bool:
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE todos SET done = 0, completed_at = NULL WHERE id = ? AND done = 1",
                (todo_id,),
            )
            return cur.rowcount > 0

    def remove(self, todo_id: int) -> bool:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            return cur.rowcount > 0

    def clear_done(self) -> int:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE done = 1")
            return cur.rowcount


class GitError(Exception):
    pass


class NotAGitRepositoryError(GitError):
    pass


class GitNotInstalledError(GitError):
    pass


@dataclass
class GitStatus:
    branch: str
    clean: bool
    raw: str


@dataclass
class GitBranch:
    name: str
    is_current: bool


@dataclass
class GitLogEntry:
    hash: str
    subject: str
    author: str
    relative_date: str


class GitService:
    def __init__(self, cwd: str | Path = ".") -> None:
        self.cwd = Path(cwd)

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        if shutil.which("git") is None:
            raise GitNotInstalledError("git is not installed or not on PATH.")
        try:
            return subprocess.run(
                ["git", *args], cwd=self.cwd, capture_output=True, text=True, timeout=15, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError("Git command timed out.") from exc

    def _require_repo(self) -> None:
        result = self._run(["rev-parse", "--is-inside-work-tree"])
        if result.returncode != 0:
            raise NotAGitRepositoryError("Not inside a git repository.")

    def status(self) -> GitStatus:
        self._require_repo()
        branch_result = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_result.stdout.strip() or "HEAD"
        status_result = self._run(["status", "--short"])
        raw = status_result.stdout
        return GitStatus(branch=branch, clean=not raw.strip(), raw=raw)

    def branches(self) -> list[GitBranch]:
        self._require_repo()
        result = self._run(["branch", "--list"])
        branches = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            is_current = line.startswith("*")
            name = line.lstrip("* ").strip()
            branches.append(GitBranch(name=name, is_current=is_current))
        return branches

    def log(self, limit: int = 10) -> list[GitLogEntry]:
        self._require_repo()
        fmt = "%h%x1f%s%x1f%an%x1f%ar"
        result = self._run(["log", f"-n{limit}", f"--pretty=format:{fmt}"])
        entries = []
        for line in result.stdout.splitlines():
            if not line:
                continue
            parts = line.split("\x1f")
            if len(parts) != 4:
                continue
            entries.append(GitLogEntry(hash=parts[0], subject=parts[1], author=parts[2], relative_date=parts[3]))
        return entries


_MARKERS: dict[str, str] = {
    ".git": "git", "pyproject.toml": "python", "setup.py": "python",
    "package.json": "node", "Cargo.toml": "rust", "go.mod": "go",
    "pom.xml": "java (maven)", "build.gradle": "java (gradle)",
    "Gemfile": "ruby", "composer.json": "php", "CMakeLists.txt": "c/c++ (cmake)",
}
_PROJECT_SKIP = {"node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".tox"}


@dataclass
class Project:
    path: str
    name: str
    types: list[str] = field(default_factory=list)


class ProjectService:
    def discover(self, roots: list[str | Path], max_depth: int = 3) -> list[Project]:
        projects: dict[str, Project] = {}
        for root in roots:
            root_path = Path(root).expanduser()
            if not root_path.exists() or not root_path.is_dir():
                continue
            self._scan(root_path, root_path, max_depth, projects)
        return sorted(projects.values(), key=lambda p: p.path)

    def _scan(self, root: Path, current: Path, max_depth: int, projects: dict[str, Project]) -> None:
        try:
            entries = list(os.scandir(current))
        except (PermissionError, OSError):
            return
        marker_names = {e.name for e in entries}
        matched_types = [label for marker, label in _MARKERS.items() if marker in marker_names]
        if matched_types:
            path_str = str(current)
            projects[path_str] = Project(path=path_str, name=current.name, types=matched_types)
            return
        depth = len(current.relative_to(root).parts)
        if depth >= max_depth:
            return
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name.startswith(".") and entry.name != ".git":
                continue
            if entry.name in _PROJECT_SKIP:
                continue
            self._scan(root, Path(entry.path), max_depth, projects)

# ========================================================================
# Commands[cite: 1]
# ========================================================================

def _general_help(registry) -> str:
    lines = [
        header("OpenCLI commands"),
        rule(),
        "",
    ]
    for command in registry.all():
        name = cyan(f"{command.name:<12}")
        lines.append(f"  {name} {command.description}")
    lines.append("")
    lines.append("  " + cyan(f"{'help':<12}") + " Help for a command  ·  help <name>")
    lines.append("  " + cyan(f"{'exit':<12}") + " Leave OpenCLI")
    lines.append("")
    lines.append(rule())
    lines.append(dim("  Tip: run a command alone to see its usage  ·  system live for a live monitor"))
    return "\n".join(lines)


def _command_help(command: Command) -> str:
    lines = [f"{command.name} -- {command.description}", "", f"Usage: {command.usage_line()}"]
    if command.arguments:
        lines.append("")
        lines.append("Arguments:")
        for arg in command.arguments:
            req = "" if arg.required else " (optional)"
            lines.append(f"  {arg.name}{req} - {arg.description}")
    if command.options:
        lines.append("")
        lines.append("Options:")
        for opt in command.options:
            short = f", -{opt.short}" if opt.short else ""
            lines.append(f"  --{opt.name}{short} - {opt.description}")
    if command.subcommands:
        lines.append("")
        lines.append("Subcommands:")
        for sub in command.subcommands:
            lines.append(f"  {sub.name:<10} {sub.description}")
            lines.append(f"      usage: {sub.usage_line(command.name)}")
    if command.aliases:
        lines.append("")
        lines.append(f"Aliases: {', '.join(command.aliases)}")
    return "\n".join(lines)


def _help(ctx: CommandContext) -> CommandResult:
    registry = ctx.shell.registry
    if not ctx.args:
        return CommandResult(output=_general_help(registry))
    name = ctx.args[0]
    command = registry.get(name)
    if command is None:
        return CommandResult(output=f"Unknown command: '{name}'. Type 'help' for a list.", success=False)
    return CommandResult(output=_command_help(command))


def _build_help() -> Command:
    return Command(
        name="help",
        description="Show help for OpenCLI or a specific command",
        handler=_help,
        arguments=(Argument(name="command", description="Command to get help on", required=False),),
        usage="help [command]",
    )


def _temps() -> list[str]:
    lines = []
    try:
        if not hasattr(psutil, "sensors_temperatures"):
            return [dim("(Temperature sensors not available on this system)")]
        temps = psutil.sensors_temperatures()
        if not temps:
            return [dim("(No temperature sensors reported)")]
        for name, entries in temps.items():
            for entry in entries:
                label = entry.label or name
                current = entry.current
                high = entry.high
                parts = [f"  {label}: {current:.0f}°C"]
                if high:
                    parts.append(f"(high {high:.0f}°C)")
                line = " ".join(parts)
                if high and current >= high:
                    line = red(line)
                elif high and current >= high * 0.85:
                    line = yellow(line)
                else:
                    line = green(line) if current < 70 else yellow(line)
                lines.append(line)
    except Exception:
        return [dim("(Could not read temperature sensors)")]
    return lines or [dim("(No temperature sensors reported)")]


def _overview(ctx: CommandContext) -> CommandResult:
    svc = ctx.shell.system_service
    info = svc.summary()
    mem = svc.memory()
    cpu = svc.cpu()
    lines = [
        header("System overview"),
        "",
        f"  {bold('Host')}     {info.hostname}",
        f"  {bold('OS')}       {info.os_name} {info.os_version} ({info.architecture})",
        f"  {bold('Uptime')}   {human_duration(info.uptime_seconds)}",
        "",
        header("CPU"),
        f"  Cores:  {cpu.logical_cores} logical"
        + (f", {cpu.physical_cores} physical" if cpu.physical_cores else ""),
        f"  Usage:  {bar(cpu.percent)}",
    ]
    if cpu.frequency_mhz:
        lines.append(f"  Freq:   {cpu.frequency_mhz:.0f} MHz")
    lines += [
        "",
        header("Memory"),
        f"  RAM:    {bar(mem.percent)}  {human_bytes(mem.used)} / {human_bytes(mem.total)}",
        f"  Free:   {human_bytes(mem.available)}",
        f"  Swap:   {bar(mem.swap_percent)}  {human_bytes(mem.swap_used)} / {human_bytes(mem.swap_total)}",
        "",
        header("Temperatures"),
    ]
    lines.extend(_temps())
    lines += ["", dim("Tip: system live  ·  system processes  ·  system cpu  ·  system memory")]
    return CommandResult(output="\n".join(lines), data=info)


def _memory(ctx: CommandContext) -> CommandResult:
    mem = ctx.shell.system_service.memory()
    lines = [
        header("Memory"),
        f"  Total:     {human_bytes(mem.total)}",
        f"  Used:      {human_bytes(mem.used)}  {bar(mem.percent)}",
        f"  Available: {human_bytes(mem.available)}",
        f"  Swap:      {human_bytes(mem.swap_used)} / {human_bytes(mem.swap_total)}  {bar(mem.swap_percent)}",
    ]
    return CommandResult(output="\n".join(lines), data=mem)


def _cpu(ctx: CommandContext) -> CommandResult:
    cpu = ctx.shell.system_service.cpu()
    lines = [
        header("CPU"),
        f"  Logical cores:  {cpu.logical_cores}",
        f"  Physical cores: {cpu.physical_cores if cpu.physical_cores else 'unknown'}",
        f"  Overall usage:  {bar(cpu.percent)}",
    ]
    if cpu.frequency_mhz:
        lines.append(f"  Frequency:      {cpu.frequency_mhz:.0f} MHz")
    if cpu.per_core_percent:
        lines.append("")
        lines.append(bold("  Per core:"))
        for i, p in enumerate(cpu.per_core_percent):
            lines.append(f"    Core {i:>2}:  {bar(p, width=16)}")
    lines.append("")
    lines.append(header("Temperatures"))
    lines.extend(_temps())
    return CommandResult(output="\n".join(lines), data=cpu)


def _disk(ctx: CommandContext) -> CommandResult:
    disks = ctx.shell.system_service.disks()
    if not disks:
        return CommandResult(output=warn("No disk information available."))
    lines = [header("Disks"), ""]
    for d in disks:
        lines.append(f"  {bold(d.mountpoint)}  ({d.device}, {d.fstype})")
        lines.append(f"    {bar(d.percent)}  {human_bytes(d.used)} / {human_bytes(d.total)}")
        lines.append("")
    return CommandResult(output="\n".join(lines).rstrip(), data=disks)


def _network(ctx: CommandContext) -> CommandResult:
    interfaces = ctx.shell.system_service.network()
    if not interfaces:
        return CommandResult(output=warn("No network interfaces found."))
    rows = [
        [
            iface.name,
            ok("up") if iface.is_up else dim("down"),
            ", ".join(iface.addresses) or "-",
            human_bytes(iface.bytes_sent),
            human_bytes(iface.bytes_recv),
        ]
        for iface in interfaces
    ]
    table = render_table(["Interface", "Status", "Addresses", "Sent", "Received"], rows)
    return CommandResult(output=header("Network") + "\n" + table, data=interfaces)


def _processes(ctx: CommandContext) -> CommandResult:
    sort_by = ctx.options.get("sort", "cpu")
    if isinstance(sort_by, bool):
        sort_by = "cpu"
    limit_raw = ctx.options.get("limit", 20)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 20

    procs = ctx.shell.system_service.processes(limit=limit, sort_by=str(sort_by))
    if not procs:
        return CommandResult(output=warn("No process information available."))

    mem = ctx.shell.system_service.memory()
    cpu = ctx.shell.system_service.cpu()
    lines = [
        header("Task manager"),
        f"  CPU {bar(cpu.percent, 12)}   RAM {bar(mem.percent, 12)}",
        "",
    ]
    rows = [
        [
            str(p.pid),
            (p.name[:22] + "…") if len(p.name) > 23 else p.name,
            (p.username or "-")[:12],
            f"{p.cpu_percent:.1f}%",
            f"{p.memory_percent:.1f}%",
            p.status[:10],
        ]
        for p in procs
    ]
    table = render_table(["PID", "Name", "User", "CPU%", "Mem%", "Status"], rows)
    lines.append(table)
    lines.append("")
    lines.append(dim(f"Sorted by {sort_by}. Use: system processes --sort memory --limit 30"))
    lines.append(dim("CPU% may read 0.0 on the first sample; run again for accurate figures."))
    return CommandResult(output="\n".join(lines), data=procs)


def _live(ctx: CommandContext) -> CommandResult:
    interval_raw = ctx.options.get("interval", 0.5)
    try:
        interval = float(interval_raw)
    except (TypeError, ValueError):
        interval = 0.5
    interval = max(0.2, min(interval, 30.0))

    sort_by = ctx.options.get("sort", "cpu")
    if isinstance(sort_by, bool):
        sort_by = "cpu"
    limit_raw = ctx.options.get("limit", 15)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 15

    try:
        for p in psutil.process_iter(["cpu_percent"]):
            try:
                p.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        psutil.cpu_percent(interval=None)
    except Exception:
        pass

    first = True
    _hide_cursor()
    try:
        while True:
            svc = ctx.shell.system_service
            info = svc.summary()
            cpu_pct = psutil.cpu_percent(interval=0.15)
            mem = svc.memory()
            try:
                freq = psutil.cpu_freq()
                freq_mhz = freq.current if freq else None
            except Exception:
                freq_mhz = None
            cores = psutil.cpu_count(logical=True) or 0
            procs = svc.processes(limit=limit, sort_by=str(sort_by))

            lines = [
                header("OpenCLI · Live") + "  " + dim(f"{interval:g}s  ·  Ctrl+C stop"),
                rule(),
                f"  {bold('Host')}  {info.hostname}    {bold('Up')}  {human_duration(info.uptime_seconds)}",
                f"  {header('CPU')}   {bar(cpu_pct, 18)}   {cores} cores"
                + (f"  {freq_mhz:.0f} MHz" if freq_mhz else ""),
                f"  {header('RAM')}   {bar(mem.percent, 18)}   "
                f"{human_bytes(mem.used)} / {human_bytes(mem.total)}",
                f"  {header('Swap')}  {bar(mem.swap_percent, 18)}   "
                f"{human_bytes(mem.swap_used)} / {human_bytes(mem.swap_total)}",
            ]
            temps = _temps()
            usable = [
                t for t in temps
                if "No temperature" not in t and "not available" not in t and "Could not" not in t
            ]
            if usable:
                lines.append(f"  {header('Temp')}  " + "  ".join(t.strip() for t in usable[:4]))
            lines.append(rule())
            lines.append(bold("  Top processes") + dim(f"  (by {sort_by})"))
            rows = [
                [
                    str(p.pid),
                    (p.name[:20] + "…") if len(p.name) > 21 else p.name,
                    (p.username or "-")[:10],
                    f"{p.cpu_percent:5.1f}%",
                    f"{p.memory_percent:5.1f}%",
                    p.status[:9],
                ]
                for p in procs
            ]
            table = render_table(["PID", "Name", "User", "CPU%", "Mem%", "Status"], rows)
            for ln in table.splitlines():
                lines.append("  " + ln)
            lines.append(rule())
            lines.append(dim(f"  sort={sort_by}  limit={limit}  interval={interval:g}s"))

            _draw_frame(lines, first=first)
            first = False
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        _show_cursor()
        print()
    return CommandResult(output=dim("Live monitor stopped."))


def _build_system() -> Command:
    return Command(
        name="system",
        description="Task manager: overview, live monitor, CPU, memory, processes",
        handler=_overview,
        subcommands=(
            Subcommand(
                name="live",
                description="Real-time updating task manager (Ctrl+C to stop)",
                handler=_live,
                options=(
                    Option(name="interval", description="Refresh seconds (default 1)"),
                    Option(name="sort", description="Sort processes by 'cpu' or 'memory'", choices=("cpu", "memory")),
                    Option(name="limit", description="Processes to show (default 15)"),
                ),
            ),
            Subcommand(name="memory", description="Memory usage with bars", handler=_memory),
            Subcommand(name="cpu", description="CPU usage, per-core bars, temperatures", handler=_cpu),
            Subcommand(name="disk", description="Disk usage", handler=_disk),
            Subcommand(name="network", description="Network interfaces", handler=_network),
            Subcommand(
                name="processes",
                description="Running processes (task list)",
                handler=_processes,
                options=(
                    Option(name="sort", description="Sort by 'cpu' or 'memory'", choices=("cpu", "memory")),
                    Option(name="limit", description="Number of processes to show (default 20)"),
                ),
            ),
        ),
        usage="system | system live | system cpu | system memory | system processes",
    )


def _find(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=(
            header("find") + "\n"
            "Search for files or directories by name.\n\n"
            + bold("Usage:") + "\n"
            "  find <pattern> [--in <directory>] [--limit <n>]\n\n"
            + bold("Examples:") + "\n"
            "  find main.py\n"
            "  find *.txt --in Documents\n"
            "  find report --limit 20"
        ), success=False)
    pattern = " ".join(ctx.args)
    start_dir = ctx.options.get("in") or ctx.options.get("dir") or "."
    if isinstance(start_dir, bool):
        start_dir = "."
    limit_raw = ctx.options.get("limit", 200)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 200
    try:
        matches = ctx.shell.file_service.find(pattern, start_dir=start_dir, max_results=limit)
    except FileSearchError as exc:
        return CommandResult(output=f"Error: {exc}", success=False)
    if not matches:
        return CommandResult(output=f"No files matching '{pattern}' found under {start_dir}.")
    lines = []
    for m in matches:
        marker = "/" if m.is_dir else ""
        size = "" if m.is_dir else f"  ({human_bytes(m.size)})"
        lines.append(f"{m.path}{marker}{size}")
    footer = f"\n\n{len(matches)} result(s)"
    if len(matches) >= limit:
        footer += f" (limit {limit} reached; refine your search or pass --limit)"
    return CommandResult(output="\n".join(lines) + footer, data=matches)


def _build_find() -> Command:
    return Command(
        name="find",
        description="Search for files or directories by name",
        handler=_find,
        arguments=(Argument(name="pattern", description="Name or glob pattern to search for", variadic=True),),
        options=(
            Option(name="in", description="Directory to search in (default: current directory)"),
            Option(name="limit", description="Maximum number of results (default 200)"),
        ),
        usage="find <pattern> [--in <directory>] [--limit <n>]",
    )


def _search(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=(
            header("search") + "\n"
            "Search the web (topic/factual queries).\n\n"
            + bold("Usage:") + "  search <query>\n"
            + bold("Example:") + "  search how does TCP work"
        ), success=False)
    query = " ".join(ctx.args)
    try:
        results = ctx.shell.search_service.search(query)
    except SearchError as exc:
        return CommandResult(output=f"Error: {exc}", success=False)
    if not results:
        return CommandResult(
            output=(
                f"No results found for '{query}'.\n"
                "(This search covers factual/topic queries; it is not a full web index.)"
            )
        )
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title}")
        lines.append(f"   {truncate(r.snippet, 160)}")
        lines.append(f"   {r.url}")
    return CommandResult(output="\n".join(lines), data=results)


def _build_search() -> Command:
    return Command(
        name="search",
        description="Search the web for a topic or question",
        handler=_search,
        arguments=(Argument(name="query", description="What to search for", variadic=True),),
        usage="search <query>",
    )


def _format_wiki_article(title: str, extract: str, url: str) -> str:
    lines: list[str] = []
    lines.append(header(title))
    lines.append(rule("═", min(60, max(20, len(title) + 4))))
    lines.append("")

    paragraphs = extract.split("\n")
    for para in paragraphs:
        para = para.strip()
        if not para:
            lines.append("")
            continue
        is_heading = (
            len(para) < 80
            and not para.endswith((".", ",", ";", ":", ")", "]"))
            and para[0].isupper()
            and " " in para
            and para.count(" ") < 10
            and not para.startswith(" ")
        )
        if is_heading and len(para.split()) <= 8:
            lines.append("")
            lines.append(bold(cyan("▸ " + para)))
            lines.append(rule("─", min(48, len(para) + 4)))
            continue

        width = 88
        while len(para) > width:
            cut = para.rfind(" ", 0, width)
            if cut < width // 2:
                cut = width
            lines.append(para[:cut].rstrip())
            para = para[cut:].lstrip()
        if para:
            lines.append(para)

    lines.append("")
    lines.append(rule("─", 40))
    if url:
        lines.append(dim("Source: ") + blue(url))
    return "\n".join(lines)


def _wiki(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(
            output=(
                header("wiki") + "\n"
                + rule() + "\n"
                + "Read a full Wikipedia article, formatted for the terminal.\n\n"
                + bold("Usage") + "\n"
                + "  wiki <topic>\n\n"
                + bold("Examples") + "\n"
                + "  wiki Alan Turing\n"
                + "  wiki Python (programming language)\n"
                + "  wiki Black hole"
            ),
            success=False,
        )
    query = " ".join(ctx.args)
    try:
        summary = ctx.shell.wikipedia_service.summary(query, full=True)
    except WikipediaError as exc:
        return CommandResult(output=err(f"Error: {exc}"), success=False)

    output = _format_wiki_article(summary.title, summary.extract, summary.url)
    return CommandResult(output=output, data=summary)


def _build_wiki() -> Command:
    return Command(
        name="wiki",
        description="Read a full Wikipedia article",
        handler=_wiki,
        arguments=(Argument(name="topic", description="Topic to look up", variadic=True),),
        usage="wiki <topic>",
    )


def _open(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=(
            header("open") + "\n"
            "Open a URL in your default browser.\n\n"
            + bold("Usage:") + "  open <url>\n"
            + bold("Example:") + "  open github.com"
        ), success=False)
    target = " ".join(ctx.args)
    try:
        url = ctx.shell.browser_service.open(target)
    except BrowserError as exc:
        return CommandResult(output=f"Error: {exc}", success=False)
    return CommandResult(output=f"Opened {url}")


def _build_open() -> Command:
    return Command(
        name="open",
        description="Open a URL in the default browser",
        handler=_open,
        arguments=(Argument(name="url", description="URL to open", variadic=True),),
        usage="open <url>",
    )


def _note_usage() -> str:
    return (
        header("note") + "\n"
        "Save and manage personal notes.\n\n"
        + bold("Usage:") + "\n"
        "  note <text>           Add a note\n"
        "  note list             Show all notes\n"
        "  note remove <id>      Delete a note\n"
        "  note clear            Delete all notes\n\n"
        + bold("Examples:") + "\n"
        "  note buy milk\n"
        "  note list\n"
        "  note remove 1"
    )


def _note_add(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=_note_usage(), success=False)
    text = " ".join(ctx.args)
    note = ctx.shell.notes_service.add(text)
    return CommandResult(output=ok(f"Note #{note.id} saved."), data=note)


def _note_list(ctx: CommandContext) -> CommandResult:
    notes = ctx.shell.notes_service.list()
    if not notes:
        return CommandResult(output=dim("No notes yet. Add one with: note <text>"))
    lines = [header(f"Notes ({len(notes)})"), ""]
    for n in notes:
        lines.append(f"  {cyan(f'#{n.id}')}  {n.text}")
    lines.append("")
    lines.append(dim("Remove with: note remove <id>"))
    return CommandResult(output="\n".join(lines), data=notes)


def _note_remove(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(
            output=bold("Usage:") + " note remove <id>\n" + dim("See all notes: note list"),
            success=False,
        )
    try:
        note_id = int(ctx.args[0])
    except ValueError:
        return CommandResult(output=err("Error: note id must be a number"), success=False)
    if not ctx.shell.notes_service.delete(note_id):
        return CommandResult(output=err(f"No note with id {note_id}."), success=False)
    return CommandResult(output=ok(f"Note #{note_id} removed."))


def _note_clear(ctx: CommandContext) -> CommandResult:
    count = ctx.shell.notes_service.clear()
    return CommandResult(output=ok(f"Removed {count} note(s)."))


def _build_note() -> Command:
    return Command(
        name="note",
        description="Save and manage personal notes",
        handler=_note_add,
        arguments=(Argument(name="text", description="Note text to save", variadic=True, required=False),),
        subcommands=(
            Subcommand(name="list", description="List all notes", handler=_note_list),
            Subcommand(
                name="remove",
                description="Remove a note by id",
                handler=_note_remove,
                arguments=(Argument(name="id", description="Note id"),),
            ),
            Subcommand(name="clear", description="Remove all notes", handler=_note_clear),
        ),
        usage="note <text> | note list | note remove <id> | note clear",
    )


def _todo_add(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output="Usage: todo add <text>", success=False)
    text = " ".join(ctx.args)
    todo = ctx.shell.todo_service.add(text)
    return CommandResult(output=f"Todo #{todo.id} added.", data=todo)


def _todo_list(ctx: CommandContext) -> CommandResult:
    include_done = bool(ctx.options.get("all"))
    todos = ctx.shell.todo_service.list(include_done=True if include_done else False)
    if not todos:
        return CommandResult(output="No todos. Add one with: todo add <text>")
    lines = []
    for t in todos:
        box = "[x]" if t.done else "[ ]"
        lines.append(f"{box} #{t.id}  {t.text}")
    return CommandResult(output="\n".join(lines), data=todos)


def _todo_done(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output="Usage: todo done <id>", success=False)
    try:
        todo_id = int(ctx.args[0])
    except ValueError:
        return CommandResult(output="Error: todo id must be a number", success=False)
    if not ctx.shell.todo_service.mark_done(todo_id):
        return CommandResult(output=f"No pending todo with id {todo_id}.", success=False)
    return CommandResult(output=f"Todo #{todo_id} marked done.")


def _todo_undone(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output="Usage: todo undone <id>", success=False)
    try:
        todo_id = int(ctx.args[0])
    except ValueError:
        return CommandResult(output="Error: todo id must be a number", success=False)
    if not ctx.shell.todo_service.mark_undone(todo_id):
        return CommandResult(output=f"No completed todo with id {todo_id}.", success=False)
    return CommandResult(output=f"Todo #{todo_id} marked pending.")


def _todo_remove(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output="Usage: todo remove <id>", success=False)
    try:
        todo_id = int(ctx.args[0])
    except ValueError:
        return CommandResult(output="Error: todo id must be a number", success=False)
    if not ctx.shell.todo_service.remove(todo_id):
        return CommandResult(output=f"No todo with id {todo_id}.", success=False)
    return CommandResult(output=f"Todo #{todo_id} removed.")


def _todo_clear_done(ctx: CommandContext) -> CommandResult:
    count = ctx.shell.todo_service.clear_done()
    return CommandResult(output=f"Removed {count} completed todo(s).")


def _build_todo() -> Command:
    return Command(
        name="todo",
        description="Manage a persistent todo list",
        subcommands=(
            Subcommand(
                name="add",
                description="Add a todo",
                handler=_todo_add,
                arguments=(Argument(name="text", description="Todo text", variadic=True),),
            ),
            Subcommand(
                name="list",
                description="List todos (pending only, unless --all)",
                handler=_todo_list,
                options=(Option(name="all", description="Include completed todos", takes_value=False),),
            ),
            Subcommand(
                name="done",
                description="Mark a todo as done",
                handler=_todo_done,
                arguments=(Argument(name="id", description="Todo id"),),
            ),
            Subcommand(
                name="undone",
                description="Mark a todo as not done",
                handler=_todo_undone,
                arguments=(Argument(name="id", description="Todo id"),),
            ),
            Subcommand(
                name="remove",
                description="Remove a todo",
                handler=_todo_remove,
                arguments=(Argument(name="id", description="Todo id"),),
            ),
            Subcommand(name="clear-done", description="Remove all completed todos", handler=_todo_clear_done),
        ),
        usage="todo add <text> | todo list [--all] | todo done <id> | todo remove <id>",
    )


def _calc(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=(
            header("calc") + "\n"
            "Evaluate a math expression safely.\n\n"
            + bold("Usage:") + "  calc <expression>\n"
            + bold("Examples:") + "\n"
            "  calc 2 + 2\n"
            "  calc sqrt(144) + 2**3\n"
            "  calc sin(pi/2)"
        ), success=False)
    expression = " ".join(ctx.args)
    try:
        result = evaluate(expression)
    except CalculatorError as exc:
        return CommandResult(output=f"Error: {exc}", success=False)
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return CommandResult(output=f"{expression} = {result}", data=result)


def _build_calc() -> Command:
    return Command(
        name="calc",
        description="Evaluate a mathematical expression",
        handler=_calc,
        arguments=(Argument(name="expression", description="Expression to evaluate", variadic=True),),
        usage="calc <expression>  (supports + - * / // % **, sqrt, sin, cos, log, pi, e, ...)",
    )


def _projects(ctx: CommandContext) -> CommandResult:
    config = ctx.shell.config
    roots = config.extra.get("project_roots") if config else None
    if not roots:
        roots = ["~"]
    depth_raw = ctx.options.get("depth", 3)
    try:
        max_depth = int(depth_raw)
    except (TypeError, ValueError):
        max_depth = 3
    projects = ctx.shell.project_service.discover(roots, max_depth=max_depth)
    if not projects:
        return CommandResult(
            output=(
                "No projects found under: " + ", ".join(roots) + "\n"
                "Set 'project_roots' in config to search elsewhere."
            )
        )
    rows = [[p.name, ", ".join(p.types), p.path] for p in projects]
    return CommandResult(output=render_table(["Name", "Type", "Path"], rows), data=projects)


def _build_projects() -> Command:
    return Command(
        name="projects",
        description="Discover development projects",
        handler=_projects,
        usage="projects [--depth <n>]",
    )


def _git_status(ctx: CommandContext) -> CommandResult:
    try:
        status = ctx.shell.git_service().status()
    except GitError as exc:
        return CommandResult(output=f"Error: {exc}", success=False)
    lines = [f"On branch {status.branch}"]
    if status.clean:
        lines.append("Working tree clean.")
    else:
        lines.append("")
        lines.append(status.raw.rstrip())
    return CommandResult(output="\n".join(lines), data=status)


def _git_branches(ctx: CommandContext) -> CommandResult:
    try:
        branches = ctx.shell.git_service().branches()
    except GitError as exc:
        return CommandResult(output=f"Error: {exc}", success=False)
    if not branches:
        return CommandResult(output="No branches found.")
    lines = [f"{'* ' if b.is_current else '  '}{b.name}" for b in branches]
    return CommandResult(output="\n".join(lines), data=branches)


def _git_log(ctx: CommandContext) -> CommandResult:
    limit_raw = ctx.options.get("limit", 10)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 10
    try:
        entries = ctx.shell.git_service().log(limit=limit)
    except GitError as exc:
        return CommandResult(output=f"Error: {exc}", success=False)
    if not entries:
        return CommandResult(output="No commits found.")
    lines = [f"{e.hash}  {e.subject}  ({e.author}, {e.relative_date})" for e in entries]
    return CommandResult(output="\n".join(lines), data=entries)


def _build_git() -> Command:
    return Command(
        name="git",
        description="Git repository helpers (status, branches, log)",
        subcommands=(
            Subcommand(name="status", description="Show working tree status", handler=_git_status),
            Subcommand(name="branches", description="List branches", handler=_git_branches),
            Subcommand(name="log", description="Show recent commits", handler=_git_log),
        ),
        usage="git status | git branches | git log [--limit <n>]",
    )


def _config_show(ctx: CommandContext) -> CommandResult:
    data = asdict(ctx.shell.config)
    lines = _flatten(data)
    return CommandResult(output="\n".join(lines), data=data)


def _flatten(data: dict, prefix: str = "") -> list[str]:
    lines = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            lines.extend(_flatten(value, full_key))
        else:
            lines.append(f"{full_key} = {value}")
    return lines


def _config_get(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output="Usage: config get <key>", success=False)
    key = ctx.args[0]
    value = ctx.shell.config.get(key, "<not set>")
    return CommandResult(output=f"{key} = {value}")


def _config_set(ctx: CommandContext) -> CommandResult:
    if len(ctx.args) < 2:
        return CommandResult(output="Usage: config set <key> <value>", success=False)
    key, value = ctx.args[0], " ".join(ctx.args[1:])
    if key.startswith("ai.api_key") or "secret" in key.lower():
        return CommandResult(
            output=err("Error: secrets cannot be stored in config."),
            success=False,
        )
    ok = ctx.shell.config.set(key, value)
    if not ok:
        return CommandResult(output=f"Error: unknown config key '{key}'", success=False)
    ctx.shell.config.save(ctx.shell.config_path)
    return CommandResult(output=f"{key} set to {value}")


def _build_config() -> Command:
    return Command(
        name="config",
        description="View and change OpenCLI configuration",
        handler=_config_show,
        subcommands=(
            Subcommand(name="show", description="Show all configuration", handler=_config_show),
            Subcommand(
                name="get",
                description="Show one config value",
                handler=_config_get,
                arguments=(Argument(name="key", description="Dotted config key, e.g. history_size"),),
            ),
            Subcommand(
                name="set",
                description="Set a config value",
                handler=_config_set,
                arguments=(
                    Argument(name="key", description="Dotted config key, e.g. history_size"),
                    Argument(name="value", description="New value", variadic=True),
                ),
            ),
        ),
        usage="config show | config get <key> | config set <key> <value>",
    )


# ---------------------------------------------------------------------------
# New Utilities (weather, net, http, hash, text, timer, stopwatch)
# ---------------------------------------------------------------------------

def _weather(ctx: CommandContext) -> CommandResult:
    location = " ".join(ctx.args) if ctx.args else ""
    url = f"https://wttr.in/{location}?format=3" if location else "https://wttr.in/?format=3"
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "curl/7.68.0"})
        resp.raise_for_status()
        return CommandResult(output=resp.text.strip())
    except Exception as exc:
        return CommandResult(output=err(f"Weather lookup failed: {exc}"), success=False)


def _build_weather() -> Command:
    return Command(
        name="weather",
        description="Show current weather for a location",
        handler=_weather,
        arguments=(Argument(name="location", description="City or location", required=False, variadic=True),),
        usage="weather [location]",
    )


def _net_ip(ctx: CommandContext) -> CommandResult:
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=5)
        data = resp.json()
        lines = [
            header("Public IP Info"),
            f"  IP:       {data.get('ip', 'N/A')}",
            f"  City:     {data.get('city', 'N/A')}",
            f"  Region:   {data.get('region', 'N/A')}",
            f"  Country:  {data.get('country', 'N/A')}",
            f"  Org:      {data.get('org', 'N/A')}",
        ]
        return CommandResult(output="\n".join(lines), data=data)
    except Exception as exc:
        return CommandResult(output=err(f"Could not retrieve IP info: {exc}"), success=False)


def _net_dns(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=err("Usage: net dns <domain>"), success=False)
    domain = ctx.args[0]
    try:
        ip = socket.gethostbyname(domain)
        return CommandResult(output=f"{domain} -> {ip}")
    except socket.gaierror:
        return CommandResult(output=err(f"Could not resolve domain: {domain}"), success=False)


def _build_net() -> Command:
    return Command(
        name="net",
        description="Network utilities (ip, dns)",
        subcommands=(
            Subcommand(name="ip", description="Show public IP and location info", handler=_net_ip),
            Subcommand(
                name="dns",
                description="Resolve domain name to IP address",
                handler=_net_dns,
                arguments=(Argument(name="domain", description="Domain name"),),
            ),
        ),
        usage="net ip | net dns <domain>",
    )


def _http_get(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=err("Usage: http get <url>"), success=False)
    try:
        url = normalize_url(ctx.args[0])
        resp = requests.get(url, timeout=10)
        try:
            body = json.dumps(resp.json(), indent=2)
        except Exception:
            body = resp.text[:1000]
        lines = [
            header(f"HTTP {resp.status_code} {resp.reason}"),
            dim(f"URL: {url}"),
            "",
            body,
        ]
        return CommandResult(output="\n".join(lines))
    except Exception as exc:
        return CommandResult(output=err(f"HTTP request failed: {exc}"), success=False)


def _build_http() -> Command:
    return Command(
        name="http",
        description="Quick HTTP API client",
        subcommands=(
            Subcommand(
                name="get",
                description="Perform HTTP GET request",
                handler=_http_get,
                arguments=(Argument(name="url", description="URL to request"),),
            ),
        ),
        usage="http get <url>",
    )


def _hash_calc(ctx: CommandContext, algo: str) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=err(f"Usage: hash {algo} <target>"), success=False)
    target = " ".join(ctx.args)
    h = getattr(hashlib, algo)()
    if os.path.isfile(target):
        try:
            with open(target, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
        except OSError as exc:
            return CommandResult(output=err(f"Cannot read file: {exc}"), success=False)
    else:
        h.update(target.encode("utf-8"))
    return CommandResult(output=f"{algo.upper()}: {h.hexdigest()}")


def _build_hash() -> Command:
    return Command(
        name="hash",
        description="Compute MD5 / SHA256 checksums",
        subcommands=(
            Subcommand(
                name="md5",
                description="MD5 hash of string or file",
                handler=lambda ctx: _hash_calc(ctx, "md5"),
                arguments=(Argument(name="target", description="Text or file path", variadic=True),),
            ),
            Subcommand(
                name="sha256",
                description="SHA256 hash of string or file",
                handler=lambda ctx: _hash_calc(ctx, "sha256"),
                arguments=(Argument(name="target", description="Text or file path", variadic=True),),
            ),
        ),
        usage="hash md5 <target> | hash sha256 <target>",
    )


def _text_b64enc(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=err("Usage: text b64enc <text>"), success=False)
    raw = " ".join(ctx.args).encode("utf-8")
    return CommandResult(output=base64.b64encode(raw).decode("utf-8"))


def _text_b64dec(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=err("Usage: text b64dec <encoded>"), success=False)
    try:
        decoded = base64.b64decode(" ".join(ctx.args)).decode("utf-8")
        return CommandResult(output=decoded)
    except Exception as exc:
        return CommandResult(output=err(f"Invalid base64 string: {exc}"), success=False)


def _text_json(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=err("Usage: text json <string>"), success=False)
    raw = " ".join(ctx.args)
    try:
        parsed = json.loads(raw)
        return CommandResult(output=json.dumps(parsed, indent=2))
    except Exception as exc:
        return CommandResult(output=err(f"Invalid JSON: {exc}"), success=False)


def _build_text() -> Command:
    return Command(
        name="text",
        description="Text conversion utilities (base64, json format)",
        subcommands=(
            Subcommand(name="b64enc", description="Encode string to base64", handler=_text_b64enc, arguments=(Argument(name="text", description="Text to encode", variadic=True),)),
            Subcommand(name="b64dec", description="Decode base64 string", handler=_text_b64dec, arguments=(Argument(name="encoded", description="Base64 text", variadic=True),)),
            Subcommand(name="json", description="Pretty print JSON string", handler=_text_json, arguments=(Argument(name="string", description="JSON string", variadic=True),)),
        ),
        usage="text b64enc <text> | text b64dec <encoded> | text json <string>",
    )


def _timer(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=err("Usage: timer <duration> (e.g. 10, 10s, 2m, 1h)"), success=False)
    val = ctx.args[0].lower()
    try:
        if val.endswith("s"):
            sec = int(val[:-1])
        elif val.endswith("m"):
            sec = int(val[:-1]) * 60
        elif val.endswith("h"):
            sec = int(val[:-1]) * 3600
        else:
            sec = int(val)
    except ValueError:
        return CommandResult(output=err("Invalid duration format. Use numbers or 10s, 2m, 1h."), success=False)

    _hide_cursor()
    try:
        for rem in range(sec, -1, -1):
            pct = ((sec - rem) / sec * 100) if sec > 0 else 100
            lines = [
                header("Timer"),
                f"  Remaining: {bold(human_duration(rem))}",
                f"  {bar(pct, width=30)}",
            ]
            _draw_frame(lines, first=(rem == sec))
            if rem > 0:
                time.sleep(1)
    except KeyboardInterrupt:
        return CommandResult(output="\nTimer cancelled.")
    finally:
        _show_cursor()
        print()
    return CommandResult(output=ok("Timer finished!"))


def _build_timer() -> Command:
    return Command(
        name="timer",
        description="Countdown timer",
        handler=_timer,
        arguments=(Argument(name="duration", description="Duration (e.g., 30, 10s, 5m)"),),
        usage="timer <duration>",
    )


def _stopwatch(ctx: CommandContext) -> CommandResult:
    _hide_cursor()
    start = time.time()
    first = True
    try:
        while True:
            elapsed = time.time() - start
            lines = [
                header("Stopwatch"),
                f"  Elapsed: {bold(f'{elapsed:.1f}s')} ({human_duration(elapsed)})",
                dim("  Press Ctrl+C to stop"),
            ]
            _draw_frame(lines, first=first)
            first = False
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        _show_cursor()
        print()
    elapsed = time.time() - start
    return CommandResult(output=ok(f"Stopwatch stopped at {elapsed:.2f}s."))


def _build_stopwatch() -> Command:
    return Command(
        name="stopwatch",
        description="Live stopwatch (Ctrl+C to stop)",
        handler=_stopwatch,
        usage="stopwatch",
    )


def _clear(ctx: CommandContext) -> CommandResult:
    clear_screen()
    return CommandResult(output="")


def _build_clear() -> Command:
    return Command(
        name="clear",
        description="Clear the terminal screen",
        handler=_clear,
        aliases=("cls",),
        usage="clear",
    )


def register_all(registry: CommandRegistry) -> None:
    for builder in (
        _build_help,
        _build_clear,
        _build_system,
        _build_find,
        _build_search,
        _build_wiki,
        _build_open,
        _build_note,
        _build_todo,
        _build_calc,
        _build_projects,
        _build_git,
        _build_config,
        _build_weather,
        _build_net,
        _build_http,
        _build_hash,
        _build_text,
        _build_timer,
        _build_stopwatch,
    ):
        registry.register(builder())

# ========================================================================
# Application[cite: 1]
# ========================================================================

class Application:
    def __init__(
        self,
        config: Config | None = None,
        config_path: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.config_path = config_path or (default_config_dir() / "config.json")
        self.config: Config = config or Config.load(self.config_path)
        self.data_dir = data_dir or default_data_dir()

        self.history = History(
            max_size=self.config.history_size,
            path=self.data_dir / "history",
        )
        self.registry = CommandRegistry()
        self.router = Router(self.registry)

        self._db: Database | None = None
        self._system_service: SystemService | None = None
        self._file_service: FileService | None = None
        self._search_service: SearchService | None = None
        self._wikipedia_service: WikipediaService | None = None
        self._browser_service: BrowserService | None = None
        self._notes_service: NotesService | None = None
        self._todo_service: TodoService | None = None
        self._project_service: ProjectService | None = None

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(self.data_dir / "opencli.db")
        return self._db

    @property
    def system_service(self) -> SystemService:
        if self._system_service is None:
            self._system_service = SystemService()
        return self._system_service

    @property
    def file_service(self) -> FileService:
        if self._file_service is None:
            self._file_service = FileService()
        return self._file_service

    @property
    def search_service(self) -> SearchService:
        if self._search_service is None:
            self._search_service = SearchService()
        return self._search_service

    @property
    def wikipedia_service(self) -> WikipediaService:
        if self._wikipedia_service is None:
            self._wikipedia_service = WikipediaService()
        return self._wikipedia_service

    @property
    def browser_service(self) -> BrowserService:
        if self._browser_service is None:
            self._browser_service = BrowserService()
        return self._browser_service

    @property
    def notes_service(self) -> NotesService:
        if self._notes_service is None:
            self._notes_service = NotesService(self.db)
        return self._notes_service

    @property
    def todo_service(self) -> TodoService:
        if self._todo_service is None:
            self._todo_service = TodoService(self.db)
        return self._todo_service

    @property
    def project_service(self) -> ProjectService:
        if self._project_service is None:
            self._project_service = ProjectService()
        return self._project_service

    def git_service(self, cwd: str | Path = ".") -> GitService:
        return GitService(cwd=cwd)

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
        self.history.save()

# ========================================================================
# CLI[cite: 1]
# ========================================================================

_EXIT_COMMANDS = {"exit", "quit"}


class Shell:
    def __init__(self, app: Application | None = None) -> None:
        self.app = app or Application()
        register_all(self.app.registry)
        self._setup_autocompletion()

    def _setup_autocompletion(self) -> None:
        try:
            import readline
            def completer(text: str, state: int) -> str | None:
                options = [c for c in self.app.registry.names() if c.startswith(text)]
                if state < len(options):
                    return options[state]
                return None
            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass

    def run(self) -> int:
        print()
        print(header("╔══════════════════════════════════════╗"))
        print(header("║           OpenCLI  v0.2              ║"))
        print(header("╚══════════════════════════════════════╝"))
        print(dim("  help · clear · system live · exit"))
        print()
        try:
            while True:
                try:
                    line = input(cyan("opencli") + dim(" › "))
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print()
                    continue
                if not self._handle_line(line):
                    break
        finally:
            self.app.close()
        return 0

    def _handle_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if stripped in _EXIT_COMMANDS:
            return False
        self.app.history.add(stripped)
        try:
            parsed = parse(stripped)
        except ParseError as exc:
            print(err(f"Error: {exc}"))
            return True
        if parsed is None:
            return True
        try:
            result = self.app.router.dispatch(parsed, config=self.app.config, shell=self.app)
        except RoutingError as exc:
            print(err(f"Error: {exc}") + dim("  ·  type help for commands"))
            return True
        except Exception as exc:
            print(err(f"Unexpected error: {exc}"))
            return True
        if result.output:
            print(result.output)
        return True

    def run_once(self, line: str) -> int:
        try:
            parsed = parse(line)
        except ParseError as exc:
            print(err(f"Error: {exc}"))
            return 1
        if parsed is None:
            return 0
        try:
            result = self.app.router.dispatch(parsed, config=self.app.config, shell=self.app)
        except RoutingError as exc:
            print(err(f"Error: {exc}") + dim("  ·  type help for commands"))
            return 1
        finally:
            self.app.close()
        if result.output:
            print(result.output)
        return 0 if result.success else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    shell = Shell()
    if argv:
        return shell.run_once(" ".join(argv))
    return shell.run()


if __name__ == "__main__":
    raise SystemExit(main())
