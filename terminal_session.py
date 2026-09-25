"""In-app PTY terminal sessions.

Runs commands inside a pseudo-terminal so tools like ``sudo`` can prompt for a
password exactly like a real terminal. Output is streamed to the frontend via
SSE and keystrokes are forwarded to the PTY master.

Only one session is active at a time (the app is a single local user).
"""

import fcntl
import os
import pty
import queue
import select
import shlex
import signal
import struct
import subprocess
import termios
import threading
import time
import uuid

# A command can print a lot (a full journalctl dump, a verbose build). The queue
# is bounded like a terminal's scrollback: when it fills up, the oldest pending
# chunk is dropped instead of growing the process until the OOM killer steps in.
OUTPUT_QUEUE_MAXSIZE = 2000

# A session outlives its SSE client on purpose (page reload keeps the command
# running). If nobody has drained the output for this long, the session is
# orphaned and is stopped so it cannot keep producing into an unread queue.
ORPHANED_SESSION_TIMEOUT = 300.0

_active_session = None
_lock = threading.Lock()


def _setup_tty():
    """Give the child its own session with the PTY as controlling terminal,
    so Ctrl+C etc. work exactly like in a real terminal."""
    os.setsid()
    try:
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    except OSError:
        pass


def _build_script(commands, title):
    # The title is shell-interpolated, so it must be quoted: an unquoted
    # apostrophe would let it break out of the echo and inject commands.
    parts = [f"echo {shlex.quote('PC Analyzer Linux: ' + title)}"]
    for command in commands:
        if "'" not in command:
            parts.append(f"echo {shlex.quote('$ ' + command)}")
        parts.append(command)
    return "\n".join(parts)


class TerminalSession:
    def __init__(self, commands, title):
        self.id = uuid.uuid4().hex[:12]
        self.title = title
        self.commands = list(commands)
        self.master_fd = None
        self.proc = None
        self.output_q = queue.Queue(maxsize=OUTPUT_QUEUE_MAXSIZE)
        self.done = False
        self.exit_code = None
        self.last_drained_at = time.time()

    # -- output queue ------------------------------------------------------

    def _emit(self, item):
        """Queue an item, discarding the oldest pending one when full."""
        try:
            self.output_q.put_nowait(item)
        except queue.Full:
            try:
                self.output_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self.output_q.put_nowait(item)
            except queue.Full:
                pass

    def get_output(self, timeout):
        """Consume one item and mark the session as still being watched."""
        item = self.output_q.get(timeout=timeout)
        self.last_drained_at = time.time()
        return item

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        script = _build_script(self.commands, self.title)
        master, slave = pty.openpty()
        try:
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 120, 0, 0))
        except OSError:
            pass
        self.proc = subprocess.Popen(
            ["bash", "-c", script],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            preexec_fn=_setup_tty,
        )
        os.close(slave)
        self.master_fd = master
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._waiter, daemon=True).start()
        return self

    def _reader(self):
        try:
            while True:
                ready, _, _ = select.select([self.master_fd], [], [], 0.5)
                if not ready:
                    continue
                try:
                    data = os.read(self.master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                self._emit(("out", data.decode("utf-8", "replace")))
        except Exception:
            pass

    def _waiter(self):
        try:
            code = self.proc.wait()
        except Exception:
            code = -1
        # Give the reader a moment to drain the last bytes before the exit event.
        time.sleep(0.2)
        self.done = True
        self.exit_code = code
        self._emit(("exit", code))

    def is_orphaned(self, now=None):
        """True when nobody has read the output for a long time."""
        if self.done:
            return False
        return (now or time.time()) - self.last_drained_at > ORPHANED_SESSION_TIMEOUT

    def write_input(self, data):
        if self.master_fd is None or self.done or self.proc is None or self.proc.poll() is not None:
            return False
        try:
            os.write(self.master_fd, data.encode("utf-8"))
            return True
        except OSError:
            return False

    def stop(self):
        """Terminate the process group and close the PTY."""
        if self.proc is not None and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
            try:
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if not self.done:
            self.done = True
            self.exit_code = None
            self._emit(("exit", None))


def start_session(commands, title):
    """Start a new session, replacing any previously active one."""
    global _active_session
    with _lock:
        if _active_session is not None:
            _active_session.stop()
        session = TerminalSession(commands, title)
        session.start()
        _active_session = session
        return session


def get_active_session():
    with _lock:
        return _active_session


def stop_active_session():
    global _active_session
    with _lock:
        if _active_session is not None:
            _active_session.stop()
        _active_session = None