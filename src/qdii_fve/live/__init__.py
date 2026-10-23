"""Daily real-data pipeline for the premium dashboard: fetch, check, compute, publish.

``sources`` fetches and parses; ``model`` is pure (testable offline); ``update`` orchestrates and
refuses to write anything when a check fails, so the published page keeps its last good version.
"""
