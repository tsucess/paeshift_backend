from django.test import TestCase
from core.schema_utils import HashableSchema
from pydantic import Field

class TestSchema(HashableSchema):
    name: str
    age: int = Field(default=0)

class HashableSchemaTestCase(TestCase):
    def test_hashable_schema(self):
        # Create two instances with the same values
        schema1 = TestSchema(name="John", age=30)
        schema2 = TestSchema(name="John", age=30)
        
        # Create a third instance with different values
        schema3 = TestSchema(name="Jane", age=25)
        
        # Test that schemas with the same values have the same hash
        self.assertEqual(hash(schema1), hash(schema2))
        self.assertNotEqual(hash(schema1), hash(schema3))
        
        # Test that schemas with the same values are equal
        self.assertEqual(schema1, schema2)
        self.assertNotEqual(schema1, schema3)
        
        # Test that schemas can be used as dictionary keys
        d = {}
        d[schema1] = "Value for schema1"
        self.assertEqual(d.get(schema2), "Value for schema1")
        self.assertIsNone(d.get(schema3))
