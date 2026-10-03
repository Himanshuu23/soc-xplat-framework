from xplat.framework import expect_eq, expect_true, register
from xplat.hal.base import Backend
from xplat.tests.common import TIMER_ENABLE, TIMER_MATCH, TIMER_RELOAD

POLLS = 60
TARGET_STEPS = 12
RELOAD_STEPS = 6
TOLERANCE_STEPS = 4


def wait_match(b: Backend) -> int:
    for polls in range(1, POLLS + 1):
        if b.read("TIMER.STATUS") & TIMER_MATCH:
            return polls
    return 0


@register("timer_basic", "compare match fires within a tolerance, reload wraps the counter")
def timer_basic(b: Backend, log) -> None:
    first = b.read("TIMER.COUNT")
    expect_eq("TIMER.COUNT frozen while disabled", b.read("TIMER.COUNT"), first)

    b.write("TIMER.CTRL", TIMER_ENABLE)
    c1 = b.read("TIMER.COUNT")
    c2 = b.read("TIMER.COUNT")
    b.write("TIMER.CTRL", 0)
    step = c2 - c1
    expect_true("TIMER.COUNT advances while enabled", step > 0, "two reads gave %d then %d" % (c1, c2))
    log("calibrated: %d timer cycles per register read" % step)

    target = TARGET_STEPS * step
    b.write("TIMER.COMPARE", target)
    b.write("TIMER.COUNT", 0)
    b.write("TIMER.STATUS", TIMER_MATCH)
    expect_eq("TIMER.STATUS.MATCH before enabling", b.read("TIMER.STATUS") & TIMER_MATCH, 0)
    b.write("TIMER.CTRL", TIMER_ENABLE)
    polls = wait_match(b)
    expect_true("TIMER.STATUS.MATCH raised", polls > 0, "no match in %d polls, compare=%d" % (POLLS, target))
    observed = b.read("TIMER.COUNT")
    log("match seen after %d polls, count=%d, compare=%d" % (polls, observed, target))
    expect_true(
        "TIMER.COUNT when match is seen",
        target <= observed <= target + TOLERANCE_STEPS * step,
        "count %d outside [%d, %d]" % (observed, target, target + TOLERANCE_STEPS * step),
    )
    b.write("TIMER.CTRL", 0)
    b.write("TIMER.STATUS", TIMER_MATCH)
    expect_eq("TIMER.STATUS.MATCH after clear", b.read("TIMER.STATUS") & TIMER_MATCH, 0)

    compare = RELOAD_STEPS * step
    b.write("TIMER.COMPARE", compare)
    b.write("TIMER.COUNT", 0)
    b.write("TIMER.CTRL", TIMER_ENABLE | TIMER_RELOAD)
    expect_true("TIMER.STATUS.MATCH raised with reload", wait_match(b) > 0)
    samples = [b.read("TIMER.COUNT") for _ in range(2 * RELOAD_STEPS + 2)]
    expect_true("TIMER.COUNT stays at or below compare with reload", max(samples) <= compare, "max %d, compare %d" % (max(samples), compare))
    wrapped = any(later < earlier for earlier, later in zip(samples, samples[1:]))
    expect_true("TIMER.COUNT wraps with reload", wrapped, "samples %s" % samples)
    b.write("TIMER.CTRL", 0)
