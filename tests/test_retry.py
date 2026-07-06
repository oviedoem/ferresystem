"""Tests para el decorador with_retry de core/erp_adapter."""
import pytest
from unittest.mock import patch, MagicMock, call
from core.erp_adapter import ERPAdapter, Producto, with_retry


# Adapter mínimo para testear el decorador en contexto de subclase
class _StubAdapter(ERPAdapter):
    def get_productos(self): return []
    def get_stock(self): return []
    def get_ventas(self, d, h): return []
    def get_pedidos(self): return []
    def test_conexion(self): return True


class TestWithRetry:

    def test_exito_inmediato_no_reintenta(self):
        llamadas = []

        @with_retry()
        def fn():
            llamadas.append(1)
            return "ok"

        assert fn() == "ok"
        assert len(llamadas) == 1

    def test_reintenta_tras_fallo_y_tiene_exito(self):
        contador = {"n": 0}

        @with_retry(backoff_base=2.0)
        def fn():
            contador["n"] += 1
            if contador["n"] < 2:
                raise IOError("temporal")
            return "listo"

        with patch("time.sleep"):
            result = fn()

        assert result == "listo"
        assert contador["n"] == 2

    def test_agota_reintentos_y_lanza_ultima_excepcion(self):
        @with_retry(max_intentos=3, backoff_base=2.0)
        def fn():
            raise ValueError("persistente")

        with patch("time.sleep"):
            with pytest.raises(ValueError, match="persistente"):
                fn()

    def test_numero_correcto_de_llamadas(self):
        mock_fn = MagicMock(side_effect=RuntimeError("fallo"))
        wrapped = with_retry(max_intentos=3)(mock_fn)

        with patch("time.sleep"):
            with pytest.raises(RuntimeError):
                wrapped()

        assert mock_fn.call_count == 3

    def test_backoff_exponencial_correcto(self):
        @with_retry(max_intentos=3, backoff_base=2.0)
        def fn():
            raise IOError("x")

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(IOError):
                fn()

        # intento 1 falla → espera 2^1=2.0; intento 2 falla → espera 2^2=4.0;
        # intento 3 falla → es el último, no hay espera más
        assert mock_sleep.call_args_list == [call(2.0), call(4.0)]

    def test_filtra_excepciones_no_especificadas(self):
        """ValueError no reintenta cuando excepciones=(IOError,)."""
        contador = {"n": 0}

        @with_retry(max_intentos=3, excepciones=(IOError,), backoff_base=2.0)
        def fn():
            contador["n"] += 1
            raise ValueError("no reintentable")

        with patch("time.sleep"):
            with pytest.raises(ValueError):
                fn()

        assert contador["n"] == 1

    def test_reintenta_excepcion_especificada(self):
        contador = {"n": 0}

        @with_retry(max_intentos=3, excepciones=(IOError,), backoff_base=2.0)
        def fn():
            contador["n"] += 1
            raise IOError("reintentable")

        with patch("time.sleep"):
            with pytest.raises(IOError):
                fn()

        assert contador["n"] == 3

    def test_preserva_nombre_y_docstring(self):
        @with_retry()
        def mi_funcion():
            """mi doc"""
            pass

        assert mi_funcion.__name__ == "mi_funcion"
        assert mi_funcion.__doc__ == "mi doc"

    def test_devuelve_valor_de_retorno_intacto(self):
        @with_retry()
        def fn():
            return {"registros": [1, 2, 3]}

        assert fn() == {"registros": [1, 2, 3]}

    def test_max_intentos_uno_no_reintenta(self):
        mock_fn = MagicMock(side_effect=IOError("fallo"))
        wrapped = with_retry(max_intentos=1)(mock_fn)

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(IOError):
                wrapped()

        assert mock_fn.call_count == 1
        mock_sleep.assert_not_called()

    def test_funciona_como_metodo_de_subclase_erp_adapter(self):
        class MiAdapter(_StubAdapter):
            @with_retry(max_intentos=2, backoff_base=2.0)
            def get_productos(self):
                return [Producto(codigo="X001", descripcion="Tornillo")]

        adapter = MiAdapter({"tipo": "test"})
        with patch("time.sleep"):
            prods = adapter.get_productos()

        assert len(prods) == 1
        assert prods[0].codigo == "X001"

    def test_metodo_reintenta_en_adapter(self):
        """Adapter method que falla una vez, luego tiene éxito."""
        class MiAdapter(_StubAdapter):
            _llamadas = 0

            @with_retry(max_intentos=3, backoff_base=2.0)
            def get_productos(self):
                self._llamadas += 1
                if self._llamadas < 2:
                    raise ConnectionError("sin red")
                return [Producto(codigo="A", descripcion="ok")]

        adapter = MiAdapter({"tipo": "test"})
        with patch("time.sleep"):
            prods = adapter.get_productos()

        assert prods[0].codigo == "A"
        assert adapter._llamadas == 2
