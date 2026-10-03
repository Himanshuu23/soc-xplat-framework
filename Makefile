CROSS ?= $(shell command -v riscv32-unknown-elf-gcc >/dev/null 2>&1 && echo riscv32-unknown-elf- || echo riscv64-unknown-elf-)
CC      := $(CROSS)gcc
OBJCOPY := $(CROSS)objcopy
OBJDUMP := $(CROSS)objdump

TESTS ?= uart_hello timer_irq dma_memcpy boot_check
APPS  := monitor
TEST  ?= uart_hello
TRACE ?= 0

BUILD  := build
FW_OUT := $(BUILD)/fw
SIM_OUT := $(BUILD)/sim
SIM    := $(SIM_OUT)/soc_sim

ARCH    := -march=rv32i -mabi=ilp32
CFLAGS  := $(ARCH) -Os -g -Wall -Wextra -ffreestanding -fno-tree-loop-distribute-patterns -mno-relax -Ifw -Igen
LDFLAGS := $(ARCH) -nostdlib -nostartfiles -Wl,--gc-sections -Wl,--no-relax -T fw/link.ld

FW_COMMON := fw/start.S $(wildcard fw/*.c)
FW_DEPS   := $(FW_COMMON) $(wildcard fw/*.h) gen/regs.h fw/link.ld
RTL       := $(wildcard rtl/*.v) rtl/third_party/picorv32.v

SIM_ARGS := --timeout 5000000
ifeq ($(TRACE),1)
SIM_ARGS += --trace --vcd $(BUILD)/$(TEST).vcd
endif

.PHONY: all fw sim all-tests regtool-test clean check-tools gen check-gen xplat-unit xplat-regress xplat sim-bug xplat-bugdemo
.SECONDARY:

all: all-tests

fw: $(addprefix $(FW_OUT)/,$(addsuffix .bin,$(TESTS) $(APPS)))

$(FW_OUT)/%.elf: fw/tests/%.c $(FW_DEPS)
	@mkdir -p $(FW_OUT)
	$(CC) $(CFLAGS) $(LDFLAGS) -Wl,-Map=$(FW_OUT)/$*.map -o $@ $(FW_COMMON) $< -lgcc

$(FW_OUT)/%.elf: fw/apps/%.c $(FW_DEPS)
	@mkdir -p $(FW_OUT)
	$(CC) $(CFLAGS) $(LDFLAGS) -Wl,-Map=$(FW_OUT)/$*.map -o $@ $(FW_COMMON) $< -lgcc

$(FW_OUT)/%.bin: $(FW_OUT)/%.elf
	$(OBJCOPY) -O binary $< $@
	$(OBJDUMP) -d -M no-aliases $< > $(FW_OUT)/$*.dis

$(SIM): $(RTL) sim/tb.cpp
	@mkdir -p $(SIM_OUT)
	verilator --cc --exe --build -j 0 --trace --public-flat-rw -Wno-lint -Wno-style -Wno-TIMESCALEMOD \
		--top-module soc_top --Mdir $(SIM_OUT) -o soc_sim \
		-CFLAGS "-O2" $(RTL) $(abspath sim/tb.cpp)

$(BUILD)/sim_bug_%/soc_sim: $(RTL) sim/tb.cpp
	@mkdir -p $(BUILD)/sim_bug_$*
	verilator --cc --exe --build -j 0 --trace --public-flat-rw -Wno-lint -Wno-style -Wno-TIMESCALEMOD \
		-DINJECT_$(shell echo $* | tr a-z A-Z)=1 \
		--top-module soc_top --Mdir $(BUILD)/sim_bug_$* -o soc_sim \
		-CFLAGS "-O2" $(RTL) $(abspath sim/tb.cpp)

sim-bug: $(BUILD)/sim_bug_$(BUG)/soc_sim

sim: $(SIM) $(FW_OUT)/$(TEST).bin
	$(SIM) $(SIM_ARGS) $(FW_OUT)/$(TEST).bin

all-tests: $(SIM) fw
	@REGTOOL="python3 tools/regtool.py --sim $(SIM) --firmware $(FW_OUT)/monitor.bin --selftest --quiet" \
		sim/run_tests.sh $(SIM) $(FW_OUT) $(TESTS)

regtool-test: $(SIM) fw
	python3 tools/regtool.py --sim $(SIM) --firmware $(FW_OUT)/monitor.bin --selftest

gen:
	python3 tools/gen_regs.py

check-gen:
	python3 tools/gen_regs.py --check

xplat-unit:
	python3 -m pytest xplat/unit -q

xplat-regress: $(SIM) fw
	python3 xplat/run_regression.py --backends model,rtl,fpga --junit reports/junit.xml --html reports/report.html

xplat-bugdemo: $(SIM) fw
	@mkdir -p reports
	@for bug in dma_len_off_by_one timer_w1c_ignored; do \
		python3 xplat/run_regression.py --backends model,rtl --inject-bug $$bug --quiet \
			--html reports/bug_$$bug.html --junit reports/bug_$$bug.xml > reports/bug_$$bug.txt; \
		rc=$$?; \
		if [ $$rc -ne 1 ]; then echo "bug $$bug was NOT caught (exit $$rc)"; exit 1; fi; \
		echo "bug $$bug caught: $$(grep -c '^MISMATCH ' reports/bug_$$bug.txt) mismatch(es), see reports/bug_$$bug.html"; \
	done

xplat: check-gen xplat-unit xplat-regress

check-tools:
	@command -v verilator >/dev/null || echo "missing: verilator"
	@command -v $(CC) >/dev/null || echo "missing: $(CC)"
	@command -v python3 >/dev/null || echo "missing: python3"
	@echo "tools ok"

clean:
	rm -rf $(BUILD)
