import sys
import pytest  # type: ignore
from pydantic import BaseModel
from random import randrange
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "src"))

from pyutils import BucketMapper
from pyutils.bucketmapper import T

########################################################
#
# Test Plan: BucketMapper()
#
########################################################

# 0) Create instance
# 1) keys are sorted
# 2) get()
# 3) get() FAIL
# 4) pop(item=I)
# 5) pop(key=X)

N: int = 500
LOOPS: int = 4
_KEYS: list[int] = [0, -5, 0, 1, 2, 3, 7, 3, 6, 8, -5]


class _TestItem(BaseModel):
    key: int
    data: int


def _mk_bucketmapper(n: int = 0, keys: list[int] = list()) -> BucketMapper[_TestItem]:
    bm: BucketMapper[_TestItem] = BucketMapper(attr="key")
    if len(keys) == 0:
        for _ in range(n):
            rand: int = randrange(n * 1000)
            keys.append(rand)
    # keys = list(set(keys))
    for k in keys:
        bm.insert(_TestItem(key=k, data=k))
    return bm


def _get_keys(bm: BucketMapper[_TestItem]) -> list[int]:
    bm_keys: list[int] = list()
    for item in bm.list():
        bm_keys.append(getattr(item, "key"))
    return bm_keys


@pytest.fixture
def test_keys() -> list[int]:
    # keys : list[int] = list()
    # for _ in range(N):
    # 	keys.append(randrange(N*1000))
    # return keys
    return [0, 10, -7, 3, 4, -3]


@pytest.fixture
def test_bucketmapper() -> BucketMapper[_TestItem]:
    return _mk_bucketmapper(keys=_KEYS)


def test_1_keys_sorted() -> None:
    for _ in range(LOOPS):
        bm: BucketMapper[_TestItem] = _mk_bucketmapper(N)
        bm_keys: list[int] = _get_keys(bm)
        assert bm_keys == sorted(bm_keys), "BucketMapper keys are not sorted"


def test_2_get(
    test_bucketmapper: BucketMapper[_TestItem],
    test_keys: list[int],
) -> None:
    bm: BucketMapper[_TestItem] = test_bucketmapper
    bm_keys: list[int] = _get_keys(bm)
    for key in test_keys:
        if (item := bm.get(key)) is not None:
            assert item.key >= key, "get() returned wrong item"
            assert item.key == min(
                [x for x in bm_keys if x > key]
            ), "get() return too large key"
        else:
            assert key >= max(bm_keys), "get() did not return key even one existed"


def test_3_get_fails(
    test_bucketmapper: BucketMapper[_TestItem],
) -> None:
    bm: BucketMapper[_TestItem] = test_bucketmapper
    bm_keys: list[int] = _get_keys(bm)
    max_key: int = max(bm_keys)
    for _ in range(LOOPS):
        if (item := bm.get(max_key + randrange(1, N))) is None:
            pass  # OK
        else:
            assert False, "get() should always return None if key outside key range"


def test_4_pop(
    test_bucketmapper: BucketMapper[_TestItem],
) -> None:
    bm: BucketMapper[_TestItem] = test_bucketmapper
    items: list[_TestItem] = bm.list()

    for _ in range(LOOPS):
        ndx: int = randrange(len(items))
        if (item := items.pop(ndx)) is None:
            assert False, "Test failure"
        else:
            if (bm_item := bm.pop(item=item)) is None:
                assert item.key > max(
                    [i.key for i in bm.list()]
                ), "pop() did not return an item even one exists"
            else:
                assert bm_item.key >= item.key, "pop() returned wrong item"


def test_5_pop_key(
    test_bucketmapper: BucketMapper[_TestItem], test_keys: list[int]
) -> None:
    bm: BucketMapper[_TestItem] = test_bucketmapper
    # items : list[_TestItem] = bm.list()
    for key in test_keys:
        # ndx : int = randrange(len(items))
        # item : _TestItem = items[ndx]
        if (bm_item := bm.pop(key=key)) is None:
            assert key > max(
                [i.key for i in bm.list()]
            ), "pop() returned None, even larger keys exist"
        else:
            assert (
                bm_item.key >= key
            ), f"pop() returned wrong item bm.keys: {[k.key for k in bm.list()]}"
