from unittest.mock import Mock, call

from manman.repository.rabbitmq.util import (
    add_routing_key_prefix,
    add_routing_key_suffix,
    bind_queue_to_exchanges,
    declare_exchange,
    declare_queue,
    generate_name_from_exchanges,
    normalize_exchanges_config,
)


def test_add_routing_key_suffix_with_suffix():
    routing_key = "test.route"
    suffix = "suffix"
    expected_routing_key = "test.route.suffix"
    assert add_routing_key_suffix(routing_key, suffix) == expected_routing_key


def test_add_routing_key_suffix_without_suffix():
    routing_key = "test.route"
    suffix = None
    expected_routing_key = "test.route"
    assert add_routing_key_suffix(routing_key, suffix) == expected_routing_key


def test_add_routing_key_suffix_with_suffix_and_dot():
    routing_key = "test.route."
    suffix = "suffix"
    expected_routing_key = "test.route.suffix"
    assert add_routing_key_suffix(routing_key, suffix) == expected_routing_key


def test_add_routing_key_suffix_empty_routing_key():
    routing_key = ""
    suffix = "suffix"
    expected_routing_key = ""
    assert add_routing_key_suffix(routing_key, suffix) == expected_routing_key


def test_add_routing_key_suffix_empty_suffix():
    routing_key = "test.route"
    suffix = ""
    expected_routing_key = "test.route"
    assert add_routing_key_suffix(routing_key, suffix) == expected_routing_key


def test_add_routing_key_prefix_with_prefix():
    routing_key = "test.route"
    prefix = "prefix"
    expected_routing_key = "prefix.test.route"
    assert add_routing_key_prefix(routing_key, prefix) == expected_routing_key


def test_add_routing_key_prefix_without_prefix():
    routing_key = "test.route"
    prefix = None
    expected_routing_key = "test.route"
    assert add_routing_key_prefix(routing_key, prefix) == expected_routing_key


def test_add_routing_key_prefix_with_prefix_and_dot():
    routing_key = ".test.route"
    prefix = "prefix"
    expected_routing_key = "prefix.test.route"
    assert add_routing_key_prefix(routing_key, prefix) == expected_routing_key


def test_add_routing_key_prefix_empty_routing_key():
    routing_key = ""
    prefix = "prefix"
    expected_routing_key = ""
    assert add_routing_key_prefix(routing_key, prefix) == expected_routing_key


def test_add_routing_key_prefix_empty_prefix():
    routing_key = "test.route"
    prefix = ""
    expected_routing_key = "test.route"
    assert add_routing_key_prefix(routing_key, prefix) == expected_routing_key


def test_declare_exchange():
    mock_channel = Mock()
    exchange_name = "test-exchange"
    
    declare_exchange(mock_channel, exchange_name)
    
    mock_channel.exchange.declare.assert_called_once_with(
        exchange=exchange_name,
        exchange_type="topic",
        durable=True,
        auto_delete=False,
    )


def test_declare_exchange_custom_params():
    mock_channel = Mock()
    exchange_name = "test-exchange"
    
    declare_exchange(mock_channel, exchange_name, exchange_type="direct", durable=False, auto_delete=True)
    
    mock_channel.exchange.declare.assert_called_once_with(
        exchange=exchange_name,
        exchange_type="direct",
        durable=False,
        auto_delete=True,
    )


def test_declare_queue():
    mock_channel = Mock()
    mock_channel.queue.declare.return_value = {"queue": "test-queue-123"}
    
    result = declare_queue(mock_channel, "test-queue")
    
    assert result == "test-queue-123"
    mock_channel.queue.declare.assert_called_once_with(
        queue="test-queue",
        auto_delete=False,
        exclusive=False,
    )


def test_declare_queue_random_name():
    mock_channel = Mock()
    mock_channel.queue.declare.return_value = {"queue": "random-queue-456"}
    
    result = declare_queue(mock_channel)
    
    assert result == "random-queue-456"
    mock_channel.queue.declare.assert_called_once_with(
        queue="",
        auto_delete=False,
        exclusive=False,
    )


def test_declare_queue_failure():
    mock_channel = Mock()
    mock_channel.queue.declare.return_value = None
    
    try:
        declare_queue(mock_channel, "test-queue")
        assert False, "Expected RuntimeError"
    except RuntimeError as e:
        assert str(e) == "Failed to create queue"


def test_normalize_exchanges_config_legacy():
    result = normalize_exchanges_config(
        exchange="test-exchange", 
        routing_key_base="test.route"
    )
    
    expected = {"test-exchange": ["test.route"]}
    assert result == expected


def test_normalize_exchanges_config_new_format():
    config = {
        "exchange1": "route1",
        "exchange2": ["route2", "route3"]
    }
    
    result = normalize_exchanges_config(exchanges_config=config)
    
    expected = {
        "exchange1": ["route1"],
        "exchange2": ["route2", "route3"]
    }
    assert result == expected


def test_normalize_exchanges_config_missing_params():
    try:
        normalize_exchanges_config()
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Either 'exchange' and 'routing_key_base' or 'exchanges_config' must be provided" in str(e)


def test_generate_name_from_exchanges():
    config = {
        "exchange1": "route1",
        "exchange2": ["route2", "route3"]
    }
    
    result = generate_name_from_exchanges(config)
    
    assert result == "exchange1-exchange2"


def test_generate_name_from_exchanges_with_prefix():
    config = {
        "exchange1": "route1",
        "exchange2": "route2"
    }
    
    result = generate_name_from_exchanges(config, "prefix")
    
    assert result == "prefix-exchange1-exchange2"


def test_bind_queue_to_exchanges_single_routing_key():
    mock_channel = Mock()
    queue_name = "test-queue"
    exchanges_config = {
        "exchange1": "route1",
        "exchange2": "route2"
    }
    
    bind_queue_to_exchanges(mock_channel, queue_name, exchanges_config)
    
    expected_calls = [
        call(exchange="exchange1", queue=queue_name, routing_key="route1"),
        call(exchange="exchange2", queue=queue_name, routing_key="route2")
    ]
    mock_channel.queue.bind.assert_has_calls(expected_calls, any_order=True)


def test_bind_queue_to_exchanges_multiple_routing_keys():
    mock_channel = Mock()
    queue_name = "test-queue"
    exchanges_config = {
        "exchange1": ["route1", "route2"],
        "exchange2": "route3"
    }
    
    bind_queue_to_exchanges(mock_channel, queue_name, exchanges_config)
    
    expected_calls = [
        call(exchange="exchange1", queue=queue_name, routing_key="route1"),
        call(exchange="exchange1", queue=queue_name, routing_key="route2"),
        call(exchange="exchange2", queue=queue_name, routing_key="route3")
    ]
    mock_channel.queue.bind.assert_has_calls(expected_calls, any_order=True)
