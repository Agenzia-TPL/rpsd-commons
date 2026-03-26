# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
rpsd-settings: Composable settings system for rpsd-commons

This is an OPTIONAL convenience package that composes settings from all rpsd packages.
You can use RpsdSettings to get all settings at once, or import individual package
settings directly (e.g., StorageSettings, TransportSettings).
"""

from rpsd_settings.base import RpsdSettings

__all__ = ["RpsdSettings"]
