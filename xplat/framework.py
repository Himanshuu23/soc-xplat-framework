from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .hal.base import Backend

Log = Callable[[str], None]
TestFn = Callable[[Backend, Log], None]

DEFAULT_SEED = 0x5EED1234


class Config:
    seed: int = DEFAULT_SEED


config = Config()


class TestFailure(AssertionError):
    __test__ = False

    def __init__(self, where: str, expected: str, actual: str, note: str = "") -> None:
        self.where = where
        self.expected = expected
        self.actual = actual
        self.note = note
        text = "%s: expected %s, got %s" % (where, expected, actual)
        if note:
            text += " (%s)" % note
        super().__init__(text)


class Skip(Exception):
    pass


@dataclass(frozen=True)
class TestCase:
    __test__ = False

    name: str
    description: str
    fn: TestFn


REGISTRY: Dict[str, TestCase] = {}


def register(name: str, description: str) -> Callable[[TestFn], TestFn]:
    def wrap(fn: TestFn) -> TestFn:
        if name in REGISTRY:
            raise ValueError("duplicate test name %s" % name)
        REGISTRY[name] = TestCase(name, description, fn)
        return fn

    return wrap


def hexv(value: int) -> str:
    return "0x%08x" % value


def expect_eq(where: str, actual: int, expected: int, addr: Optional[int] = None) -> None:
    if actual != expected:
        note = "address %s" % hexv(addr) if addr is not None else ""
        raise TestFailure(where, hexv(expected), hexv(actual), note)


def expect_true(where: str, condition: bool, note: str = "") -> None:
    if not condition:
        raise TestFailure(where, "true", "false", note)


def expect_words(where: str, base: int, actual: List[int], expected: List[int]) -> None:
    if actual == expected:
        return
    bad = [i for i in range(len(expected)) if actual[i] != expected[i]]
    first = bad[0]
    raise TestFailure(
        "%s[%d] at %s" % (where, first, hexv(base + 4 * first)),
        hexv(expected[first]),
        hexv(actual[first]),
        "%d of %d words differ" % (len(bad), len(expected)),
    )
