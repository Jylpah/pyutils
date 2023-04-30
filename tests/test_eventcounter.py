import sys
import pytest # type: ignore
from pytest import Config
from asyncio.log import logger
from os.path import dirname, realpath, join as pjoin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / 'src'))

from pyutils import EventCounter


########################################################
#
# Test Plan
#
########################################################

# 1) Create instance and log events
# 2) Create 2 instances, log events and merge
# 3) Create an instance and get categories


_CATEGORIES : list[str] = [ 'one', 'two', 'three', 'four' ]

@pytest.fixture
def test_source_categories_0() -> list[str]:
	return _CATEGORIES


def mk_eventcounter_one(name: str, cats : list[str]) -> EventCounter:
	ec : EventCounter = EventCounter(name)
	for c in cats:
		ec.log(c)
	return ec


def mk_eventcounter_linear(name: str, cats : list[str]) -> EventCounter:
	ec : EventCounter = EventCounter(name)
	for i in range(len(cats)):
		ec.log(cats[i], i+1)
	return ec


def test_1_create(test_source_categories_0: list[str]) -> None:
	"""Test __init__(), log(), get_categories()"""
	cats : list[str] = test_source_categories_0
	ec : EventCounter = mk_eventcounter_one('Test', cats)
	assert ec.get_categories().sort() == cats.sort(), "Failed to create categories"
	assert ec.sum(cats) == len(cats), "Incorrect event count"
	assert ec.get_value(cats[1]) == 1, "Incorrect value"


def test_2_create(test_source_categories_0: list[str]) -> None:
	cats : list[str] = test_source_categories_0
	ec : EventCounter = mk_eventcounter_linear('Test', cats)
	assert ec.get_categories().sort() == cats.sort(), "Failed to create categories"
	assert ec.sum(cats) == (1 + len(cats)) / 2 * len(cats), "Incorrect event count"
	assert ec.get_value(cats[1]) == 2, "Incorrect value"

def test_3_merge(test_source_categories_0: list[str]) -> None:
	cats : list[str] = test_source_categories_0
	ec1 : EventCounter = mk_eventcounter_linear('Test 1', cats)
	ec2 : EventCounter = mk_eventcounter_linear('Test 2', cats)
	ec1.merge(ec2)
	assert ec1.get_categories().sort() == cats.sort(), "Merging categories failed categories"
	assert ec1.sum(cats) == 2* (1 + len(cats)) / 2 * len(cats), "Incorrect event count"


def test_4_merge_child(test_source_categories_0: list[str]) -> None:
	cats : list[str] = test_source_categories_0
	ec1 : EventCounter = mk_eventcounter_linear('Test 1', cats)
	ec2 : EventCounter = mk_eventcounter_linear('Test 2', cats)
	ec1.merge_child(ec2)
	assert len(ec1.get_categories()) == 2 * len(cats), "Incorrect category count"
	assert ec1.sum(ec1.get_categories()) == 2* (1 + len(cats)) / 2 * len(cats), "Incorrect event count"


def test_5_error_categories(test_source_categories_0: list[str]) -> None:
	cats : list[str] = test_source_categories_0
	ec : EventCounter = mk_eventcounter_linear('Test', cats)
	assert not ec.get_error_status(), "Unintended errors logged"
	assert ec.add_error_categories(cats[:2]), "Errors not logged"


def test_6_categories(test_source_categories_0: list[str]) -> None:
	"""Test categories methods"""
	cats : list[str] = test_source_categories_0
	ec : EventCounter = mk_eventcounter_linear('Test', cats)
	assert type(ec._get_str(cats[1])) is str, f"Incorrect type returned: {type(ec._get_str(cats[1]))}"
	assert type(ec.get_long_cat(cats[1])) is str, f"Incorrect type returned: {type(ec.get_long_cat(cats[1]))}"
	assert issubclass(type(ec.get_values()), dict), f"Incorrect type returned: {type(ec.get_values())}"
	assert type(ec.print(do_print=False)) is str, "Incorrect type returned"
