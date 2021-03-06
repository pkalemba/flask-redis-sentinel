# Copyright 2015, 2016, 2017 Exponea s r.o. <info@exponea.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import threading
from unittest import TestCase
from flask import Flask
from mock import MagicMock
import redis
from flask_redis_sentinel import SentinelExtension


class FakeRedis(MagicMock):
    def __init__(self, host='localhost', port=6379,
                 db=0, password=None, socket_timeout=None,
                 socket_connect_timeout=None,
                 socket_keepalive=None, socket_keepalive_options=None,
                 connection_pool=None, unix_socket_path=None,
                 encoding='utf-8', encoding_errors='strict',
                 charset=None, errors=None,
                 decode_responses=False, retry_on_timeout=False,
                 ssl=False, ssl_keyfile=None, ssl_certfile=None,
                 ssl_cert_reqs=None, ssl_ca_certs=None):
        super(FakeRedis, self).__init__()
        self.kwargs = {
            'host': host,
            'port': port,
            'db': db,
            'password': password,
            'socket_timeout': socket_timeout,
            'socket_connect_timeout': socket_connect_timeout,
            'socket_keepalive': socket_keepalive,
            'socket_keepalive_options': socket_keepalive_options,
            'connection_pool': connection_pool,
            'unix_socket_path': unix_socket_path,
            'encoding': encoding,
            'encoding_errors': encoding_errors,
            'charset': charset,
            'errors': errors,
            'decode_responses': decode_responses,
            'retry_on_timeout': retry_on_timeout,
            'ssl': ssl,
            'ssl_keyfile': ssl_keyfile,
            'ssl_certfile': ssl_certfile,
            'ssl_cert_reqs': ssl_cert_reqs,
            'ssl_ca_certs': ssl_ca_certs
        }

    @classmethod
    def from_url(cls, url, **kwargs):
        i = cls()
        i.kwargs = {'url': url}
        i.kwargs.update(kwargs)
        return i


class FakeSentinel(object):
    def __init__(self, sentinels, min_other_sentinels=0, sentinel_kwargs=None,
                 **connection_kwargs):
        self._sentinels = sentinels
        self.min_other_sentinels = min_other_sentinels
        self.sentinel_kwargs = sentinel_kwargs
        self.connection_kwargs = connection_kwargs

    def _update_kwargs(self, kwargs, connection_kwargs):
        connection = dict(self.connection_kwargs)
        connection.update(connection_kwargs)
        kwargs['connection_kwargs'] = connection

    def master_for(self, service_name, redis_class=redis.StrictRedis,
                   connection_pool_class=redis.sentinel.SentinelConnectionPool, **kwargs):
        i = FakeRedis()
        i.kwargs = {
            'is_master': True,
            'service_name': service_name,
            'redis_class': redis_class,
            'connection_pool_class': connection_pool_class
        }
        self._update_kwargs(i.kwargs, kwargs)
        return i

    def slave_for(self, service_name, redis_class=redis.StrictRedis,
                  connection_pool_class=redis.sentinel.SentinelConnectionPool, **kwargs):
        i = FakeRedis()
        i.kwargs = {
            'is_master': False,
            'service_name': service_name,
            'redis_class': redis_class,
            'connection_pool_class': connection_pool_class
        }
        self._update_kwargs(i.kwargs, kwargs)
        return i


class TestWithApp(TestCase):
    def setUp(self):
        self.app = Flask('test')

    def test_default_connection(self):
        sentinel = SentinelExtension(client_class=FakeRedis)
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://localhost/0')

    def test_default_connection_with_config_class(self):
        sentinel = SentinelExtension()
        self.app.config['REDIS_CLASS'] = FakeRedis
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://localhost/0')

    def test_default_connection_with_init_class(self):
        sentinel = SentinelExtension()
        sentinel.init_app(self.app, client_class=FakeRedis)
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://localhost/0')

    def test_default_connection_with_config_class_string(self):
        sentinel = SentinelExtension()
        self.app.config['REDIS_CLASS'] = 'test_flask_redis_sentinel.FakeRedis'
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://localhost/0')

    def test_default_connection_redis_url(self):
        sentinel = SentinelExtension(client_class=FakeRedis)
        self.app.config['REDIS_URL'] = 'redis://hostname:7001/3'
        self.app.config['REDIS_HOST'] = 'ignored'  # should be ignored
        self.app.config['REDIS_PORT'] = 5000  # should be ignored
        self.app.config['REDIS_DB'] = 7  # should be ignored
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://hostname:7001/3')
            self.assertNotIn('host', inst.kwargs)
            self.assertNotIn('port', inst.kwargs)
            self.assertNotIn('db', inst.kwargs)

    def test_default_connection_redis_vars(self):
        sentinel = SentinelExtension(client_class=FakeRedis)
        self.app.config['REDIS_URL'] = 'redis://hostname:7001/3'
        self.app.config['REDIS_DECODE_RESPONSES'] = True
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://hostname:7001/3')
            self.assertEqual(inst.kwargs['decode_responses'], True)

    def test_sentinel_kwargs_from_config(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/mymaster/3'
        self.app.config['REDIS_SENTINEL_SOCKET_CONNECT_TIMEOUT'] = 0.3
        sentinel.init_app(self.app)
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)
            self.assertEquals(sentinel.sentinel.sentinel_kwargs, {'socket_connect_timeout': 0.3})

    def test_default_connection_sentinel_url_master(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/mymaster/3'
        self.app.config['REDIS_DECODE_RESPONSES'] = True
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)

            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['is_master'], True)
            self.assertEqual(inst.kwargs['service_name'], 'mymaster')
            self.assertEqual(inst.kwargs['connection_kwargs']['db'], 3)
            self.assertEqual(inst.kwargs['connection_kwargs']['decode_responses'], True)

    def test_default_connection_sentinel_url_slave(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/myslave/3?client_type=slave'
        self.app.config['REDIS_DECODE_RESPONSES'] = True
        self.app.config['REDIS_SENTINEL_SOCKET_CONNECT_TIMEOUT'] = 0.3
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)

            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['is_master'], False)
            self.assertEqual(inst.kwargs['service_name'], 'myslave')
            self.assertEqual(inst.kwargs['connection_kwargs']['db'], 3)
            self.assertEqual(inst.kwargs['connection_kwargs']['decode_responses'], True)

    def test_unsupported_url_scheme(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis+something://hostname:7001/myslave/3?slave=true'
        with self.assertRaisesRegexp(ValueError, r'Unsupported redis URL scheme: redis\+something'):
            sentinel.init_app(self.app)

    def test_default_connection_with_init_sentinel_class(self):
        sentinel = SentinelExtension(client_class=FakeRedis)
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/mymaster/3'
        sentinel.init_app(self.app, sentinel_class=FakeSentinel)
        conn = sentinel.default_connection
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['is_master'], True)

    def test_default_connection_with_config_sentinel_class(self):
        sentinel = SentinelExtension(client_class=FakeRedis)
        self.app.config['REDIS_SENTINEL_CLASS'] = FakeSentinel
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/mymaster/3'
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['is_master'], True)

    def test_default_connection_with_config_sentinel_class_string(self):
        sentinel = SentinelExtension(client_class=FakeRedis)
        self.app.config['REDIS_SENTINEL_CLASS'] = 'test_flask_redis_sentinel.FakeSentinel'
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/mymaster/3'
        sentinel.init_app(self.app)
        conn = sentinel.default_connection
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['is_master'], True)

    def test_duplicate_prefix_registration(self):
        sentinel = SentinelExtension()
        sentinel2 = SentinelExtension()

        sentinel.init_app(self.app)

        msg = 'Redis sentinel extension with config prefix REDIS is already registered'
        with self.assertRaisesRegexp(RuntimeError, msg):
            sentinel2.init_app(self.app)

    def test_multiple_prefix_registration(self):
        sentinel = SentinelExtension()
        sentinel2 = SentinelExtension()

        sentinel.init_app(self.app)
        sentinel2.init_app(self.app, config_prefix='ANOTHER_REDIS')

    def test_init_app_in_constructor(self):
        self.app.config['REDIS_URL'] = 'redis://hostname:7001/3'
        sentinel = SentinelExtension(app=self.app, client_class=FakeRedis)
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://hostname:7001/3')

    def test_init_app_with_prefix_in_constructor(self):
        self.app.config['REDIS_URL'] = 'redis://hostname:7001/3'
        self.app.config['CUSTOM_REDIS_URL'] = 'redis://hostname2:7003/5'
        sentinel = SentinelExtension(app=self.app, client_class=FakeRedis, config_prefix='CUSTOM_REDIS')
        conn = sentinel.default_connection
        with self.app.app_context():
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['url'], 'redis://hostname2:7003/5')

    def _check_threads(self, sentinel):
        connections = {}
        with self.app.app_context():
            connections['from_main_thread'] = sentinel.default_connection._get_current_object()

        def in_another_thread():
            with self.app.app_context():
                connections['from_another_thread'] = sentinel.default_connection._get_current_object()

        thread = threading.Thread(target=in_another_thread)
        thread.start()
        thread.join()

        with self.app.app_context():
            connections['from_main_thread_later'] = sentinel.default_connection._get_current_object()

        return connections

    def test_sentinel_threads(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/myslave/0'
        sentinel.init_app(self.app)

        connections = self._check_threads(sentinel)
        self.assertIsNot(connections['from_another_thread'], connections['from_main_thread'])
        self.assertIsNot(connections['from_another_thread'], connections['from_main_thread_later'])
        self.assertIs(connections['from_main_thread'], connections['from_main_thread_later'])

    def test_redis_threads(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis://hostname:7001/0'
        sentinel.init_app(self.app)

        connections = self._check_threads(sentinel)
        self.assertIs(connections['from_another_thread'], connections['from_main_thread'])
        self.assertIs(connections['from_another_thread'], connections['from_main_thread_later'])
        self.assertIs(connections['from_main_thread'], connections['from_main_thread_later'])

    def test_mixed_apps(self):
        sentinel1 = SentinelExtension(app=self.app, client_class=FakeRedis)
        conn1 = sentinel1.default_connection

        self.app2 = Flask('test2')
        sentinel2 = SentinelExtension(app=self.app2, config_prefix='CUSTOM_REDIS', client_class=FakeRedis)
        conn2 = sentinel2.default_connection

        self.app3 = Flask('test3')

        with self.app2.app_context():
            msg = 'Redis sentinel extension with config prefix REDIS was not initialized for application test2'
            with self.assertRaisesRegexp(RuntimeError, msg):
                conn1._get_current_object()

        with self.app3.app_context():
            msg = 'Redis sentinel extension with config prefix REDIS was not initialized for application test3'
            with self.assertRaisesRegexp(RuntimeError, msg):
                conn1._get_current_object()

    def test_named_master(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/mymaster/3'
        self.app.config['REDIS_DECODE_RESPONSES'] = True
        sentinel.init_app(self.app)
        conn = sentinel.master_for('othermaster', db=6)
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['is_master'], True)
            self.assertEqual(inst.kwargs['service_name'], 'othermaster')
            self.assertEqual(inst.kwargs['connection_kwargs']['db'], 6)
            self.assertEqual(inst.kwargs['connection_kwargs']['decode_responses'], True)

    def test_named_master_no_sentinel(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis://hostname:7001/3'
        sentinel.init_app(self.app)
        conn = sentinel.master_for('othermaster', db=6)
        with self.app.app_context():
            self.assertIsNone(sentinel.sentinel._get_current_object())
            with self.assertRaisesRegexp(RuntimeError, 'Cannot get master othermaster using non-sentinel configuration'):
                inst = conn._get_current_object()

    def test_named_slave(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis+sentinel://hostname:7001/mymaster/3'
        self.app.config['REDIS_DECODE_RESPONSES'] = True
        sentinel.init_app(self.app)
        conn = sentinel.slave_for('otherslave', db=6)
        with self.app.app_context():
            self.assertIsNotNone(sentinel.sentinel)
            inst = conn._get_current_object()
            self.assertEqual(inst.kwargs['is_master'], False)
            self.assertEqual(inst.kwargs['service_name'], 'otherslave')
            self.assertEqual(inst.kwargs['connection_kwargs']['db'], 6)
            self.assertEqual(inst.kwargs['connection_kwargs']['decode_responses'], True)

    def test_named_slave_no_sentinel(self):
        sentinel = SentinelExtension(client_class=FakeRedis, sentinel_class=FakeSentinel)
        self.app.config['REDIS_URL'] = 'redis://hostname:7001/3'
        sentinel.init_app(self.app)
        conn = sentinel.slave_for('otherslave', db=6)
        with self.app.app_context():
            self.assertIsNone(sentinel.sentinel._get_current_object())
            with self.assertRaisesRegexp(RuntimeError, 'Cannot get slave otherslave using non-sentinel configuration'):
                inst = conn._get_current_object()
