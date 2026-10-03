import os
from dataclasses import dataclass
from typing import Optional

from .base import Backend, BackendError
from .fake_serial import FakeSerial
from .fpga import FpgaBackend, open_serial
from .model import BUGS, ModelBackend
from .rtl import DEFAULT_FW, DEFAULT_SIM, ROOT, RtlBackend

BACKENDS = ("model", "rtl", "fpga")
FAKE_PORT = "fake"


@dataclass
class BackendOptions:
    bug: Optional[str] = None
    bug_target: str = "rtl"
    sim: str = DEFAULT_SIM
    firmware: str = DEFAULT_FW
    serial_port: str = FAKE_PORT
    baud: int = 115200
    reset_command: Optional[str] = None
    timeout: float = 10.0


def bug_sim_path(bug: str) -> str:
    return os.path.join(ROOT, "build", "sim_bug_%s" % bug, "soc_sim")


def create_backend(name: str, opts: Optional[BackendOptions] = None) -> Backend:
    opts = opts or BackendOptions()
    if opts.bug is not None and opts.bug not in BUGS:
        raise BackendError("unknown bug %r, choose from %s" % (opts.bug, ", ".join(BUGS)))
    model_bug = opts.bug if opts.bug_target == "model" else None

    if name == "model":
        return ModelBackend(bug=model_bug)

    if name == "rtl":
        sim = bug_sim_path(opts.bug) if opts.bug and opts.bug_target == "rtl" else opts.sim
        return RtlBackend(sim=sim, firmware=opts.firmware, timeout=opts.timeout)

    if name == "fpga":
        if opts.serial_port == FAKE_PORT:
            fake = FakeSerial(ModelBackend(bug=model_bug))
            return FpgaBackend(fake, reset_hook=fake.power_cycle, name="fpga")
        ser = open_serial(opts.serial_port, opts.baud, timeout=2.0)
        return FpgaBackend(ser, reset_command=opts.reset_command)

    raise BackendError("unknown backend %r, choose from %s" % (name, ", ".join(BACKENDS)))
