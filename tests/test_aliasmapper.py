import sys
import pytest # type: ignore
from typing import Literal
from pydantic import BaseModel, Field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / 'src'))

from pyutils import AliasMapper
from pyutils.aliasmapper import T


########################################################
#
# Test Plan: AliasMapper()
#
########################################################

# 0) Create instance 
# 1) alias()
# 2) map()
# 3) map() FAIL
# 4) mapper()

NdxType = Literal[1, 0 , -1 ]
NDXS : list[int] = [1, 0 , -1 ]

@pytest.fixture
def test_fields() -> list[str]:
	return ['number', 'string', 'boolean', 'child.integer', 'child.string' ]


@pytest.fixture
def test_indexes() -> list[tuple[str, NdxType]]:
	indexes : list[tuple[str, NdxType]] 
	indexes = [ ('number', 1), 
				('string', 0),
				('boolean', -1), 
				('child.integer', 0), 
				('child.string', -1)
			  ]
	return indexes


@pytest.fixture
def test_model() -> type[BaseModel]:
	class TestModelChild(BaseModel):
		integer : int = Field(alias='i')
		string : str  = Field(alias='s')

	class TestModel(BaseModel):
		number: int 	= Field(default=0, alias='n')
		string: str 	= Field(default=..., alias='s')
		boolean: bool 	= Field(default=True, alias='b')
		child : TestModelChild = Field(default=..., alias='c')

	return TestModel

def _test_alias(field: str) -> str:
	return '.'.join([f[0] for f in field.split('.')])

def test_1_alias(test_model: type[BaseModel], test_fields: list[str]) -> None:
	mapper: AliasMapper = AliasMapper(test_model)
	for field in test_fields:
		assert mapper.alias(field) == _test_alias(field) , "Alias mapping failed"


def test_2_map(test_model: type[BaseModel], 
				test_indexes: list[tuple[str, NdxType]]
				) -> None:
	mapper: AliasMapper = AliasMapper(test_model)
	alias_map : dict[str, NdxType] = mapper.map(test_indexes)
	
	for field, ndx in test_indexes:
		assert alias_map[_test_alias(field)] == ndx, "Alias mapping failed"
	

def test_3_map_fails(test_model: type[BaseModel], 
					test_indexes: list[tuple[str, NdxType]]
					) -> None:
	mapper: AliasMapper = AliasMapper(test_model)

	failing_indexes : list[tuple[str, NdxType]] = list()
	for field, ndx in test_indexes:
		failing_indexes.append((field + '_DOES_NOT_EXISTS', ndx))

	try:
		alias_map : dict[str, NdxType] = mapper.map(failing_indexes)
	except KeyError:
		assert True
		return None
	assert False, "Invalid keys not caught"


def test_4_mapper(test_model: type[BaseModel], 
					test_indexes: list[tuple[str, NdxType]]
					) -> None:
	alias_map : dict[str, NdxType] = AliasMapper.mapper(test_model, test_indexes)
	mapper : AliasMapper = AliasMapper(test_model)
	for field, ndx in test_indexes:
		assert alias_map[mapper.alias(field)] == ndx, 'Mapping failed'