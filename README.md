xplat

A cross-platform test framework for a small RV32I SoC. Each hardware test is written once in Python and runs unchanged on a Python model and on the Verilator RTL simulation. The runner compares results across backends and flags any test that passes on one and fails on another.

The SoC under test (PicoRV32, UART, timer, DMA, firmware, Verilator testbench) comes from the mini-soc-bringup repo. This repo adds the register spec, generators, backends, tests and regression runner on top of it.

How It Works

    spec/registers.yaml      one file: bases, offsets, fields, access, resets
         |  tools/gen_regs.py
         v
    gen/regs.h  gen/regs.py  gen/regs_pkg.sv
         |
    xplat/hal  Backend API: read_reg, write_reg, dma_copy, wait_irq, reset
         |
         +-- ModelBackend   Python model of the spec
         +-- RtlBackend     Verilator simulation, driven over the UART monitor
         +-- FpgaBackend    same protocol over pyserial
         |
    xplat/tests       7 tests, written against the Backend API only
         |
    xplat/run_regression.py   runs, compares, writes console table, JUnit XML, HTML

Tests contain no backend-specific code, so a difference in outcome is a difference in behaviour.

Building

    make CROSS=riscv64-elf- xplat

This checks the generated files are current, runs the pytest suite, and runs the regression. Drop CROSS= on Ubuntu.

Arch Linux:

    sudo pacman -S --needed base-devel verilator python python-yaml python-pytest python-pyserial riscv64-elf-gcc riscv64-elf-binutils

Ubuntu 24.04:

    sudo apt install verilator gcc-riscv64-unknown-elf binutils-riscv64-unknown-elf make python3 g++ python3-yaml python3-pytest python3-serial

Usage

    make check-gen                           fail if generated files are stale
    make gen                                 regenerate from spec/registers.yaml
    make xplat-unit                          pytest unit tests
    make CROSS=riscv64-elf- xplat-regress    regression run
    make CROSS=riscv64-elf- xplat-bugdemo    plant bugs, check they are caught
    make CROSS=riscv64-elf- all-tests        original SoC firmware tests

    python3 xplat/run_regression.py --backends model,rtl
    python3 xplat/run_regression.py --backend rtl --tests dma_copy_edge
    python3 xplat/run_regression.py --list

Reports go to reports/junit.xml and reports/report.html. Exit code is 0 when everything passes and no backends disagree, 1 otherwise.

Backends

| Backend | What it is |
|---|---|
| model | functional Python model generated from the spec |
| rtl | Verilator simulation driven through the UART monitor over a TCP socket |
| fpga | same R/W line protocol over pyserial. Implemented, not run on real hardware |

Tests

| Test | What it checks |
|---|---|
| reg_reset_values | every register reads its spec reset value |
| reg_access_types | RW, RO, WO and W1C behave as specified |
| timer_basic | match fires within a tolerance, reload wraps the counter |
| dma_copy_basic | 32 words copied, source and guard words untouched |
| dma_copy_edge | zero length, config writes ignored while busy, region boundaries |
| dma_done_flag | done sets, is sticky, clears on write 1, drives the dma irq |
| random_dma | 12 constrained-random transfers checked against a reference copy |

Register Spec

spec/registers.yaml is the only place a register is defined. tools/gen_regs.py validates it (overlapping fields, duplicate offsets, bad bit ranges) and generates the C header, the Python module and a SystemVerilog package. The firmware drivers include the generated header and check at compile time that every struct field sits at the spec offset. A unit test cross-checks the spec against the RTL and testbench.

Bug Demo

make xplat-bugdemo plants a deliberate bug in the RTL and checks the regression catches it. With the DMA length off by one:

    dma_copy_basic    PASS 0.00s   FAIL 0.45s   MISMATCH

    MISMATCH dma_copy_basic
        agree:    model
        disagree: rtl
            where:    guard word after dst
            expected: 0xa5a5a5a5
            actual:   0xdeadbeef

The model passes and the RTL fails, so the report points at the guard word the extra copy overwrote. A second bug (timer W1C ignored) is caught the same way.

Problems Hit

- The DMA busy window was invisible through the monitor. The testbench free-ran between commands, so a copy always finished before the next status read. Fixed with a lock-step socket mode in sim/tb.cpp, where simulated time advances only while UART bytes are in flight.
- random_dma took 49 seconds on the RTL because it checked thousands of words between source and destination. It now checks two small windows.
- A bug planted in the model reaches every backend that runs the model, so compare against the RTL.

Limitations

- The FPGA backend has not been run on hardware.
- The model matches the RTL on behaviour, not cycle by cycle.
- Interrupt delivery to the CPU is covered by the firmware tests, not the Python tests.
- The tests use a 24 KB scratch area (0x9000 to 0xF000) that the monitor does not touch.

Layout

    spec/registers.yaml     the register spec
    tools/gen_regs.py       generator and --check
    gen/                    generated files (committed)
    xplat/hal/              Backend, model, RTL and FPGA backends
    xplat/tests/            the seven tests
    xplat/unit/             pytest unit tests
    xplat/run_regression.py command line
    rtl/ fw/ sim/           the SoC, from mini-soc-bringup

License

MIT for the code in this repo. PicoRV32 is ISC licensed, see rtl/third_party/LICENSE.
