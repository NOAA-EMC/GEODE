"""Table-driven BUFR schema discovery and normalization utilities.

These modules do not import the ``bufr`` bindings so they can be unit tested
without the native BUFR stack. The registered ingestor that uses them lives in
``geode.ingest.ingestors.generic_bufr``.
"""
