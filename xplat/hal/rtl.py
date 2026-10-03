import os
import socket
import sys
from typing import Any, Callable, Optional

from .base import Backend, BackendError, BackendProtocolError, BackendTimeout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from regtool import RegBridge  # noqa: E402

DEFAULT_SIM = os.path.join(ROOT, "build", "sim", "soc_sim")
DEFAULT_FW = os.path.join(ROOT, "build", "fw", "monitor.bin")


class RtlBackend(Backend):
    name = "rtl"

    def __init__(
        self,
        sim: str = DEFAULT_SIM,
        firmware: str = DEFAULT_FW,
        timeout: float = 10.0,
        bridge_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.sim = sim
        self.firmware = firmware
        self.timeout = timeout
        self.bridge_factory = bridge_factory or self.spawn_bridge
        self.bridge: Any = None
        self.reset()

    def spawn_bridge(self) -> Any:
        for path, hint in ((self.sim, "make sim"), (self.firmware, "make fw")):
            if not os.path.exists(path):
                raise BackendError("%s not found, build it first with: %s" % (path, hint))
        return RegBridge(sim=self.sim, firmware=self.firmware, timeout=self.timeout)

    def call(self, what: str, fn: Callable[..., Any], *args: Any) -> Any:
        try:
            return fn(*args)
        except socket.timeout:
            raise BackendTimeout("rtl simulation gave no reply to %s within %.1fs" % (what, self.timeout))
        except RuntimeError as e:
            raise BackendError("rtl simulation connection failed during %s: %s" % (what, e))
        except ValueError as e:
            raise BackendProtocolError("rtl monitor reply for %s was invalid: %s" % (what, e))
        except OSError as e:
            raise BackendError("rtl simulation socket error during %s: %s" % (what, e))

    def reset(self) -> None:
        self.close()
        self.bridge = self.call("startup", self.bridge_factory)

    def read_reg(self, addr: int) -> int:
        return self.call("read 0x%08x" % addr, self.bridge.read_reg, addr)

    def write_reg(self, addr: int, val: int) -> None:
        self.call("write 0x%08x" % addr, self.bridge.write_reg, addr, val)

    def close(self) -> None:
        if self.bridge is not None:
            try:
                self.bridge.close()
            finally:
                self.bridge = None
