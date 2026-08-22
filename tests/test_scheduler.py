"""
test_scheduler.py — Tests para pipeline/scheduler.py.
"""
import os
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.scheduler import _parse_hora, _proxima_ejecucion


class TestParseHora:
    def test_hora_valida(self):
        assert _parse_hora("22:00") == (22, 0)
        assert _parse_hora("09:30") == (9, 30)

    def test_hora_invalida(self):
        with pytest.raises(ValueError):
            _parse_hora("abc")


class TestProximaEjecucion:
    def test_proxima_hoy_si_falta(self):
        ahora = datetime.now()
        hora_futura = (ahora + timedelta(hours=2)).hour
        prox = _proxima_ejecucion(hora_futura, 0)
        assert prox.hour == hora_futura
        assert prox.date() == ahora.date()
