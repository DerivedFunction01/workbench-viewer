"""Dataset derivations and the guarded SQL console.

The package form of the former flat pair: derivations
(classification, schema, paged rows, and column stats
over repo files) live in derivations.py; the guarded
read-only SQL console lives in console.py. This
__init__ re-exports the combined public surface so
`import lib.datasets` and every current importer keep
working unchanged; console importers name
lib.datasets.console directly.
"""

from . import derivations as _derivations
from .derivations import (DEFAULT_LIMIT, MAX_LIMIT,
                          PAGE_BYTES, QUERY_TIMEOUT_S,
                          SINGLE_TABLE, DatasetError,
                          available, classify,
                          dataset_rows, dataset_schema,
                          dataset_stats)

# The console and the test suite reach a few derivation
# internals through the package surface (the registry
# package re-exports its internals the same way); they
# stay reachable here, outside __all__.
_execute = _derivations._execute
_open = _derivations._open
_sqlite_engine = _derivations._sqlite_engine
_json_safe = _derivations._json_safe
from .console import (CONSOLE_TIMEOUT_S,
                      MAX_PAYLOAD_BYTES, MAX_SQL_ROWS,
                      run_dataset_sql)

__all__ = ["DatasetError", "available", "classify",
           "dataset_rows", "dataset_schema",
           "dataset_stats", "SINGLE_TABLE", "PAGE_BYTES",
           "DEFAULT_LIMIT", "MAX_LIMIT",
           "QUERY_TIMEOUT_S", "MAX_SQL_ROWS",
           "MAX_PAYLOAD_BYTES", "CONSOLE_TIMEOUT_S",
           "run_dataset_sql"]
