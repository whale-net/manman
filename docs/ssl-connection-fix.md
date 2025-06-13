# SSL Connection Error Fix

This document describes the fix for SSL connection errors (`SSLV3_ALERT_BAD_RECORD_MAC`) in AMQP connections.

## Problem

The ManMan experience API was experiencing persistent SSL connection failures with the following error:

```
SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac
```

This error typically indicates:
- SSL/TLS version mismatch between client and server
- SSL context reuse issues during reconnection
- Weak cipher suites causing MAC validation failures
- Insecure protocol versions being used

## Solution

### Enhanced SSL Context Configuration

Updated `get_rabbitmq_ssl_options()` in `src/manman/util.py`:

- **Disabled insecure protocols**: SSLv2, SSLv3, TLSv1.0, TLSv1.1
- **Set minimum TLS version**: TLS 1.2
- **Enhanced certificate verification**: Enabled hostname checking and required certificate validation
- **Secure cipher suites**: Restricted to strong ECDHE and DHE cipher suites
- **Prevented weak ciphers**: Explicitly excluded aNULL, MD5, and DSS ciphers

### Enhanced SSL Error Handling

Updated `RobustConnection._connect()` in `src/manman/repository/rabbitmq/connection.py`:

- **Fresh SSL context creation**: Each reconnection attempt creates a new SSL context
- **SSL-specific error handling**: Dedicated handling for different types of SSL errors
- **Enhanced security settings**: Applied same security restrictions during reconnection
- **Better error logging**: More descriptive logging for SSL connection issues

### Improved Reconnection Logic

Updated `RobustConnection._reconnect_loop()`:

- **SSL error tracking**: Count and handle SSL errors separately from other connection errors
- **Adaptive retry delays**: Shorter delays for bad record MAC errors, longer delays for repeated SSL errors
- **SSL-specific backoff**: Different retry strategies for SSL vs. connection errors

## Code Changes

### 1. SSL Options Enhancement (`src/manman/util.py`)

```python
def get_rabbitmq_ssl_options(hostname: str) -> dict:
    # Create SSL context with enhanced security settings
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs(purpose=ssl.Purpose.SERVER_AUTH)
    
    # Disable insecure protocols
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_TLSv1
    context.options |= ssl.OP_NO_TLSv1_1
    
    # Set minimum TLS version to 1.2
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    
    # Enable hostname checking and certificate verification
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    
    # Restrict to secure cipher suites
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
```

### 2. SSL Error Handling (`src/manman/repository/rabbitmq/connection.py`)

```python
except ssl.SSLError as ssl_error:
    error_msg = str(ssl_error).lower()
    if "bad record mac" in error_msg:
        logger.warning("SSL bad record MAC error detected - this usually indicates SSL context reuse issues: %s", ssl_error)
    elif "certificate" in error_msg:
        logger.error("SSL certificate error: %s", ssl_error)
    elif "handshake" in error_msg:
        logger.warning("SSL handshake failed: %s", ssl_error)
    else:
        logger.exception("SSL connection error: %s", ssl_error)
```

## Testing

Added comprehensive tests in `tests/test_ssl_connection_fixes.py`:

- SSL security settings validation
- SSL context isolation verification
- Bad record MAC error handling
- Fresh context creation during reconnection
- Hostname validation
- Heartbeat configuration with SSL

## Benefits

1. **Prevents SSL bad record MAC errors** through fresh context creation
2. **Enhanced security** with modern TLS versions and cipher suites
3. **Better error handling** with SSL-specific retry logic
4. **Improved stability** for SSL-enabled AMQP connections
5. **Better debugging** with enhanced SSL error logging

## Compatibility

- **Backward compatible**: No changes to existing API
- **Secure by default**: Enhanced security settings apply automatically when SSL is enabled
- **Graceful degradation**: Falls back to default cipher suites if custom ones fail

## Environment Variables

The fix works with existing environment variables:

- `MANMAN_RABBITMQ_ENABLE_SSL=true`: Enables SSL connections
- `MANMAN_RABBITMQ_SSL_HOSTNAME`: Sets the SSL hostname for verification

No additional configuration is required.