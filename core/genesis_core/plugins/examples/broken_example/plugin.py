"""Absichtlich fehlerhaftes Beispiel-Plugin (§34).

Dient als Testbeweis, dass ein kaputtes Plugin den GENESIS-Host NICHT
destabilisiert - `PluginRegistry.discover_and_load` faengt diese
Exception ab (sie entsteht bereits beim Modul-Import, also noch VOR jeder
Instanziierung/Validierung) und markiert dieses Plugin lediglich mit
einem `load_error`, statt den gesamten Ladevorgang oder gar den Host
abstuerzen zu lassen. Siehe `core/tests/test_plugins.py` fuer den
entsprechenden Regressionstest.
"""
from __future__ import annotations

raise RuntimeError(
    "Dies ist ein absichtlich fehlerhaftes Test-Plugin (§34) - wenn du diese "
    "Fehlermeldung in einem echten Fehlerbericht siehst, wurde dieses Beispiel "
    "versehentlich in ein echtes Plugin-Verzeichnis kopiert statt nur als "
    "Stabilitaetstest zu dienen."
)
