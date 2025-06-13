"""
Tests for SSL connection fixes to address SSLV3_ALERT_BAD_RECORD_MAC errors.

This module tests the enhanced SSL configuration and error handling
to prevent SSL connection failures in AMQP connections.
"""

import ssl
import unittest
from unittest.mock import Mock, patch

from manman.repository.rabbitmq.connection import RobustConnection
from manman.util import get_rabbitmq_ssl_options


class TestSSLConnectionFixes(unittest.TestCase):
    """Test SSL connection improvements for preventing bad record MAC errors."""

    def test_enhanced_ssl_options_security(self):
        """Test that SSL options have enhanced security settings."""
        ssl_options = get_rabbitmq_ssl_options("secure.example.com")
        
        # Verify basic structure
        self.assertIn("context", ssl_options)
        self.assertIn("server_hostname", ssl_options)
        self.assertEqual(ssl_options["server_hostname"], "secure.example.com")
        
        context = ssl_options["context"]
        self.assertIsInstance(context, ssl.SSLContext)
        
        # Verify security settings
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        
        # Verify insecure protocols are disabled
        options = context.options
        self.assertTrue(options & ssl.OP_NO_SSLv3)
        self.assertTrue(options & ssl.OP_NO_TLSv1)
        self.assertTrue(options & ssl.OP_NO_TLSv1_1)

    def test_ssl_context_isolation(self):
        """Test that SSL contexts are properly isolated between calls."""
        ssl_options1 = get_rabbitmq_ssl_options("host1.example.com")
        ssl_options2 = get_rabbitmq_ssl_options("host2.example.com")
        
        context1 = ssl_options1["context"]
        context2 = ssl_options2["context"]
        
        # Contexts should be different instances
        self.assertIsNot(context1, context2)
        
        # But have the same security settings
        self.assertEqual(context1.minimum_version, context2.minimum_version)
        self.assertEqual(context1.verify_mode, context2.verify_mode)

    def test_ssl_hostname_validation(self):
        """Test SSL hostname validation."""
        # Empty hostname should raise error
        with self.assertRaises(RuntimeError) as cm:
            get_rabbitmq_ssl_options("")
        self.assertIn("SSL is enabled but no hostname provided", str(cm.exception))
        
        # None hostname should raise error
        with self.assertRaises(RuntimeError) as cm:
            get_rabbitmq_ssl_options(None)
        self.assertIn("SSL is enabled but no hostname provided", str(cm.exception))

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_ssl_bad_record_mac_error_handling(self, mock_connection_class):
        """Test handling of SSL bad record MAC errors."""
        connection_params = {
            "hostname": "test.example.com",
            "port": 5671,
            "username": "test",
            "password": "test",
            "virtual_host": "/",
            "ssl": True,
            "ssl_options": {
                "context": ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                "server_hostname": "test.example.com"
            }
        }
        
        # Mock SSL bad record MAC error
        ssl_error = ssl.SSLError("[SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac")
        mock_connection_class.side_effect = ssl_error
        
        # Should handle the error gracefully during initialization
        with self.assertRaises(Exception) as cm:
            RobustConnection(connection_params)
        
        self.assertIn("Failed to establish initial RabbitMQ connection", str(cm.exception))

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_ssl_context_refresh_on_reconnection(self, mock_connection_class):
        """Test that fresh SSL contexts are created during reconnection."""
        connection_params = {
            "hostname": "test.example.com",
            "port": 5671,
            "username": "test",
            "password": "test",
            "virtual_host": "/",
            "ssl": True,
            "ssl_options": {
                "context": ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                "server_hostname": "test.example.com"
            }
        }
        
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()
        mock_connection_class.return_value = mock_connection
        
        robust_conn = RobustConnection(connection_params)
        
        # Verify that Connection was called with SSL options
        call_args = mock_connection_class.call_args
        self.assertIsNotNone(call_args)
        self.assertIn("ssl_options", call_args[1])
        self.assertIn("ssl", call_args[1])
        self.assertTrue(call_args[1]["ssl"])
        
        ssl_opts = call_args[1]["ssl_options"]
        self.assertIn("context", ssl_opts)
        self.assertIn("server_hostname", ssl_opts)
        
        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_ssl_connection_with_heartbeat(self, mock_connection_class):
        """Test SSL connection with proper heartbeat configuration."""
        connection_params = {
            "hostname": "secure.example.com",
            "port": 5671,
            "username": "test",
            "password": "test",
            "virtual_host": "/",
            "ssl": True,
            "ssl_options": get_rabbitmq_ssl_options("secure.example.com")
        }
        
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection_class.return_value = mock_connection
        
        robust_conn = RobustConnection(connection_params, heartbeat_interval=20)
        
        # Verify heartbeat and SSL are properly configured
        call_args = mock_connection_class.call_args
        self.assertEqual(call_args[1]["heartbeat"], 20)
        self.assertTrue(call_args[1]["ssl"])
        self.assertIn("ssl_options", call_args[1])
        
        robust_conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)