from unittest.mock import Mock, call

from manman.repository.rabbitmq.util import (
    add_routing_key_prefix,
    add_routing_key_suffix,
    bind_queue_to_exchanges,
    declare_exchange,
    declare_queue,
    ExchangeConfig,
    ExchangesConfig,
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
    assert result.to_dict() == expected


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
    assert result.to_dict() == expected


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


def test_exchange_config_with_string():
    config = ExchangeConfig("test-exchange", "route1")
    assert config.name == "test-exchange"
    assert config.routing_keys == ["route1"]


def test_exchange_config_with_list():
    config = ExchangeConfig("test-exchange", ["route1", "route2"])
    assert config.name == "test-exchange"
    assert config.routing_keys == ["route1", "route2"]


def test_exchanges_config_from_legacy():
    config = ExchangesConfig.from_legacy("test-exchange", "test.route")
    assert len(config.exchanges) == 1
    assert config.exchanges[0].name == "test-exchange"
    assert config.exchanges[0].routing_keys == ["test.route"]


def test_exchanges_config_from_dict():
    config_dict = {
        "exchange1": "route1",
        "exchange2": ["route2", "route3"]
    }
    config = ExchangesConfig.from_dict(config_dict)
    assert len(config.exchanges) == 2
    
    # Find exchanges by name
    exchange1 = next(e for e in config.exchanges if e.name == "exchange1")
    exchange2 = next(e for e in config.exchanges if e.name == "exchange2")
    
    assert exchange1.routing_keys == ["route1"]
    assert exchange2.routing_keys == ["route2", "route3"]


def test_exchanges_config_to_dict():
    config = ExchangesConfig([
        ExchangeConfig("exchange1", "route1"),
        ExchangeConfig("exchange2", ["route2", "route3"])
    ])
    
    result = config.to_dict()
    expected = {
        "exchange1": ["route1"],
        "exchange2": ["route2", "route3"]
    }
    assert result == expected


def test_exchanges_config_get_exchange_names():
    config = ExchangesConfig([
        ExchangeConfig("exchange1", "route1"),
        ExchangeConfig("exchange2", ["route2", "route3"])
    ])
    
    names = config.get_exchange_names()
    assert set(names) == {"exchange1", "exchange2"}


def test_bind_queue_to_exchanges_with_dataclass():
    mock_channel = Mock()
    queue_name = "test-queue"
    
    config = ExchangesConfig([
        ExchangeConfig("exchange1", ["route1", "route2"]),
        ExchangeConfig("exchange2", "route3")
    ])
    
    bind_queue_to_exchanges(mock_channel, queue_name, config)
    
    expected_calls = [
        call(exchange="exchange1", queue=queue_name, routing_key="route1"),
        call(exchange="exchange1", queue=queue_name, routing_key="route2"),
        call(exchange="exchange2", queue=queue_name, routing_key="route3")
    ]
    mock_channel.queue.bind.assert_has_calls(expected_calls, any_order=True)


def test_generate_name_from_exchanges_with_dataclass():
    config = ExchangesConfig([
        ExchangeConfig("exchange1", "route1"),
        ExchangeConfig("exchange2", "route2")
    ])
    
    result = generate_name_from_exchanges(config)
    assert result == "exchange1-exchange2"
    
    result_with_prefix = generate_name_from_exchanges(config, "prefix")
    assert result_with_prefix == "prefix-exchange1-exchange2"
