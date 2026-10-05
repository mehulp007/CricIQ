"""CricIQ domain core.

Format-agnostic cricket rules and configuration shared by the data pipelines,
the ML package and the API. Anything that both training and serving depend on
lives here so the two can never drift apart.
"""

__version__ = "1.0.0"
