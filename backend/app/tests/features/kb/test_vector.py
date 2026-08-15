from types import SimpleNamespace

from app.features.kb.models import EmbeddingVector


def test_postgres_bind_processor_keeps_float_list() -> None:
    dialect = SimpleNamespace(name="postgresql")
    process = EmbeddingVector().bind_processor(dialect)
    assert process is not None
    values = [-0.011836824, 0.0038907486, 0.0064862967]
    bound = process(values)
    assert bound == values
    assert isinstance(bound, list)
    assert all(isinstance(x, float) for x in bound)
    assert not isinstance(bound, str)
