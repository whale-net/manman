"""
Test SSL parameter propagation fixes for ManMan RabbitMQ connections.

This test validates that SSL parameters are properly propagated and preserved
throughout the connection lifecycle, preventing "bad record mac" errors.
"""

import ssl
import unittest
from unittest.mock import Mock, patch

from manman.repository.rabbitmq.connection import RobustConnection
from manman.util import get_rabbitmq_ssl_options, init_rabbitmq


class TestSSLParameterPropagation(unittest.TestCase):
    """Test SSL parameter propagation fixes."""

    def test_ssl_parameter_deep_copy_in_robust_connection(self):
        """Test that RobustConnection properly handles SSL parameter copying."""
        ssl_options = get_rabbitmq_ssl_options("test.example.com")

        connection_params = {
            "hostname": "test.example.com",
            "port": 5671,
            "username": "test",
            "password": "test",
            "virtual_host": "/",
            "ssl": True,
            "ssl_options": ssl_options,
        }

        with patch(
            "manman.repository.rabbitmq.connection.Connection"
        ) as mock_connection_class:
            mock_connection = Mock()
            mock_connection.is_open = True
            mock_connection.check_for_errors = Mock()
            mock_connection_class.return_value = mock_connection

            robust_conn = RobustConnection(connection_params)

            # Verify SSL parameters are preserved
            stored_params = robust_conn._connection_params
            self.assertTrue(stored_params["ssl"])
            self.assertIn("ssl_options", stored_params)
            self.assertEqual(
                stored_params["ssl_options"]["server_hostname"], "test.example.com"
            )

            # Verify SSL hostname is stored separately for reconnection
            self.assertEqual(robust_conn._ssl_hostname, "test.example.com")

            robust_conn.close()

    def test_ssl_hostname_preservation_during_reconnection(self):
        """Test that SSL hostname is preserved during reconnection attempts."""
        ssl_options = get_rabbitmq_ssl_options("secure.example.com")

        connection_params = {
            "hostname": "secure.example.com",
            "port": 5671,
            "username": "test",
            "password": "test",
            "virtual_host": "/",
            "ssl": True,
            "ssl_options": ssl_options,
        }

        with patch(
            "manman.repository.rabbitmq.connection.Connection"
        ) as mock_connection_class:
            mock_connection = Mock()
            mock_connection.is_open = True
            mock_connection.check_for_errors = Mock()
            mock_connection_class.return_value = mock_connection

            robust_conn = RobustConnection(connection_params)

            # Get the connection call arguments to verify SSL hostname
            call_args = mock_connection_class.call_args
            self.assertIsNotNone(call_args)

            ssl_opts = call_args[1]["ssl_options"]
            self.assertIn("server_hostname", ssl_opts)
            self.assertEqual(ssl_opts["server_hostname"], "secure.example.com")

            # Test that fresh SSL context is created but hostname is preserved
            self.assertIn("context", ssl_opts)
            self.assertIsInstance(ssl_opts["context"], ssl.SSLContext)

            robust_conn.close()

    def test_ssl_parameter_validation(self):
        """Test SSL parameter validation during connection."""
        with patch(
            "manman.repository.rabbitmq.connection.Connection"
        ) as mock_connection_class:
            mock_connection = Mock()
            mock_connection.is_open = True
            mock_connection_class.return_value = mock_connection

            # Test with missing SSL hostname
            connection_params = {
                "hostname": "test.example.com",
                "port": 5671,
                "username": "test",
                "password": "test",
                "virtual_host": "/",
                "ssl": True,
                "ssl_options": {
                    "context": ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    # Missing server_hostname
                },
            }

            # Should fail to create connection due to missing hostname
            with self.assertRaises(Exception):
                RobustConnection(connection_params)

    def test_global_parameter_storage_with_ssl(self):
        """Test that global parameter storage properly handles SSL options."""
        ssl_options = get_rabbitmq_ssl_options("global.example.com")

        with patch("manman.util.RobustConnection") as mock_robust:
            mock_robust_instance = Mock()
            mock_robust.return_value = mock_robust_instance

            # Initialize RabbitMQ with SSL
            init_rabbitmq(
                host="global.example.com",
                port=5671,
                username="test",
                password="test",
                virtual_host="/test",
                ssl_enabled=True,
                ssl_options=ssl_options,
            )

            # Verify RobustConnection was called with proper SSL parameters
            call_args = mock_robust.call_args
            self.assertIsNotNone(call_args)

            connection_params = call_args[1]["connection_params"]
            self.assertTrue(connection_params["ssl"])
            self.assertIn("ssl_options", connection_params)
            self.assertEqual(
                connection_params["ssl_options"]["server_hostname"],
                "global.example.com",
            )

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_fresh_ssl_context_creation_preserves_hostname(self, mock_connection_class):
        """Test that fresh SSL context creation preserves the original hostname."""
        ssl_options = get_rabbitmq_ssl_options("fresh.example.com")
        original_hostname = ssl_options["server_hostname"]

        connection_params = {
            "hostname": "fresh.example.com",
            "port": 5671,
            "username": "test",
            "password": "test",
            "virtual_host": "/",
            "ssl": True,
            "ssl_options": ssl_options,
        }

        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()
        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(connection_params)

        # Verify the connection was called with preserved hostname
        call_args = mock_connection_class.call_args
        ssl_opts = call_args[1]["ssl_options"]

        # Hostname should be preserved even with fresh context
        self.assertEqual(ssl_opts["server_hostname"], original_hostname)
        self.assertEqual(ssl_opts["server_hostname"], "fresh.example.com")

        # Context should be fresh (different from original)
        self.assertIsInstance(ssl_opts["context"], ssl.SSLContext)
        # Note: We can't directly compare contexts as they're recreated

        robust_conn.close()

    def test_deep_copy_connection_params_method(self):
        """Test the _deep_copy_connection_params method directly."""
        ssl_options = get_rabbitmq_ssl_options("method.example.com")

        connection_params = {
            "hostname": "method.example.com",
            "port": 5671,
            "username": "test",
            "password": "test",
            "virtual_host": "/",
            "ssl": True,
            "ssl_options": ssl_options,
            "other_param": {"nested": "value"},
        }

        with patch(
            "manman.repository.rabbitmq.connection.Connection"
        ) as mock_connection_class:
            mock_connection = Mock()
            mock_connection.is_open = True
            mock_connection_class.return_value = mock_connection

            robust_conn = RobustConnection(connection_params)

            # Test the deep copy method directly
            copied_params = robust_conn._deep_copy_connection_params(connection_params)

            # SSL options should be copied but context preserved
            self.assertIsNot(
                copied_params["ssl_options"], connection_params["ssl_options"]
            )
            self.assertEqual(
                copied_params["ssl_options"]["server_hostname"],
                connection_params["ssl_options"]["server_hostname"],
            )
            self.assertIs(
                copied_params["ssl_options"]["context"],
                connection_params["ssl_options"]["context"],
            )

            # Other parameters should be deep copied
            self.assertIsNot(
                copied_params["other_param"], connection_params["other_param"]
            )
            self.assertEqual(
                copied_params["other_param"]["nested"],
                connection_params["other_param"]["nested"],
            )

            robust_conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
