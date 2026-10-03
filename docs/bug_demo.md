# Bug demo

Proof that the cross-backend regression catches a real hardware bug and says where it is.

Two deliberate bugs can be planted, in the RTL or in the Python model:

| Name | What it does | Planted in RTL by |
|---|---|---|
| dma_len_off_by_one | the DMA copies LEN + 1 words | rtl/dma.v, `ifdef INJECT_DMA_LEN_OFF_BY_ONE` |
| timer_w1c_ignored | writing 1 to TIMER.STATUS.MATCH no longer clears it | rtl/timer.v, `ifndef INJECT_TIMER_W1C_IGNORED` |

Without the define the RTL is unchanged, the normal simulator and all existing tests are not affected. Bugged simulators are separate builds in build/sim_bug_NAME/.

## Run it

    make xplat-bugdemo

builds both bugged simulators, runs the regression with each bug in the RTL, and fails if a bug is not caught. By hand:

    python3 xplat/run_regression.py --backends model,rtl --inject-bug dma_len_off_by_one
    python3 xplat/run_regression.py --backends model,rtl --inject-bug timer_w1c_ignored
    python3 xplat/run_regression.py --backends model,rtl --inject-bug dma_len_off_by_one --bug-target model

The exit code is 1 when the bug is caught. The first run builds build/sim_bug_NAME/soc_sim, which takes about a minute.

## Bug 1: DMA copies one word too many

    TEST              model        rtl          VERDICT
    ---------------------------------------------------
    reg_reset_values  PASS 0.00s   PASS 0.13s   ok
    reg_access_types  PASS 0.00s   PASS 0.50s   ok
    timer_basic       PASS 0.00s   PASS 0.21s   ok
    dma_copy_basic    PASS 0.00s   FAIL 0.45s   MISMATCH
    dma_copy_edge     PASS 0.01s   FAIL 0.33s   MISMATCH
    dma_done_flag     PASS 0.00s   PASS 0.17s   ok
    random_dma        PASS 0.00s   FAIL 0.27s   MISMATCH

    MISMATCH dma_copy_basic
        agree:    model
        disagree: rtl
            where:    guard word after dst
            expected: 0xa5a5a5a5
            actual:   0xdeadbeef
    MISMATCH dma_copy_edge
        agree:    model
        disagree: rtl
            where:    guard word at region end (first word to last word)
            expected: 0xa5a5a5a5
            actual:   0xd7835f92

How to read it. The model and the RTL agree on every register test, so the registers are fine. All three copy tests fail only on the RTL, and the data points at the cause: in dma_copy_basic the guard word sits right after the destination block (0x0000a080 for 32 words at 0xa000), and it was overwritten with whatever followed the source block. 0xdeadbeef is the untouched RAM fill, so the source word one past the end was copied. That is an off-by-one in the length counter, which is what was planted.

dma_done_flag still passes because it never looks past the end of its destination. The test that can see the bug is the one with a guard word.

random_dma gives an exact reproduction: it prints the iteration, src, dst, words and seed of the failing transfer, the address of the first wrong word, and how many words differ.

## Bug 2: timer match flag cannot be cleared

    reg_access_types  PASS 0.00s   FAIL 0.30s   MISMATCH
    timer_basic       PASS 0.00s   FAIL 0.14s   MISMATCH

    MISMATCH reg_access_types
        agree:    model
        disagree: rtl
            where:    TIMER.STATUS.MATCH after writing 1
            expected: 0x00000000
            actual:   0x00000001

The where line is the register and field (0x1000100c is TIMER.STATUS) and the operation, write 1 to clear. The DMA tests all pass, which narrows it to the timer block.

## Planting the bug in the model instead

    python3 xplat/run_regression.py --backends model,rtl --inject-bug dma_len_off_by_one --bug-target model

Now the model fails and the clean RTL passes. The verdict is still MISMATCH, only the side that disagrees changes (`disagree: model`). A regression cannot tell which side is wrong, it only tells you they differ, and the where line tells you what to look at. With a reference model that is trusted, the disagreeing side is the one to debug.

The fake FPGA backend wraps the same model, so with `--bug-target model` it carries the bug too. Compare the model against the RTL when planting there.

## Reports

Each run can write JUnit XML (`--junit`) and an HTML report (`--html`). make xplat-bugdemo writes reports/bug_NAME.html, reports/bug_NAME.xml and reports/bug_NAME.txt. In the JUnit file every mismatch is also a failing test case in a suite called xplat.cross-backend, so a CI system flags it even when one backend alone looks fine.
