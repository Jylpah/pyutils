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

def test_1_create_eventcounter(test_source_categories_0: list[str]) -> None:
	"""Test __init__(), log(), get_categories()"""
	cats : list[str] = test_source_categories_0
	ec : EventCounter = mk_eventcounter_one('Test 1', cats)
	assert ec.get_categories().sort() == cats.sort(), "Failed to create categories"
	assert ec.sum(cats) == len(cats), "Incorrect event count"


def test_2_create_eventcounter(test_source_categories_0: list[str]) -> None:
	cats : list[str] = test_source_categories_0
	ec : EventCounter = mk_eventcounter_linear('Test 1', cats)
	assert ec.get_categories().sort() == cats.sort(), "Failed to create categories"
	assert ec.sum(cats) == (1 + len(cats)) / 2 * len(cats), "Incorrect event count"


