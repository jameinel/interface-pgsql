import os
import shutil
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

from ops import charm, framework, model
import yaml

import client


class TestPostgreSQLDatabase(unittest.TestCase):

    def test_master_host(self):
        master_str = "host=10.11.12.13 user=myuser"
        db = client.PostgreSQLDatabase(master_str)
        self.assertEqual(db.master, master_str)
        self.assertEqual(db.host, "10.11.12.13")
        self.assertEqual(db.properties, {"host": "10.11.12.13", "user": "myuser"})

    def test_real_master(self):
        # Taken from an actual connection to the postgresql charm
        master = "dbname=hello-juju_hello-juju host=10.210.24.14 password=PASS port=5432 user=juju_hello-juju"
        db = client.PostgreSQLDatabase(master)
        self.assertEqual(db.database, "hello-juju_hello-juju")
        self.assertEqual(db.host, "10.210.24.14")
        self.assertEqual(db.user, "juju_hello-juju")
        self.assertEqual(db.password, "PASS")
        self.assertEqual(db.port, "5432")


class FakeModelBackend:
    """This conforms to the interface for ModelBackend but provides canned data."""

    def __init__(self, unit_name):
        self.unit_name = unit_name
        self.app_name = self.unit_name.split('/')[0]

        self._is_leader = None
        self._relation_ids_map = {}  # relation name to [relation_ids,...]
        self._relation_names = {}  # reverse map from relation_id to relation_name
        self._relation_list_map = {}  # relation_id: [unit_name,...]
        self._relation_data = {}  # {relation_id: {name: data}}
        self._config = {}
        self._is_leader = False
        self._resources_map = {}
        self._pod_spec = None
        self._app_status = None
        self._unit_status = None

    def relation_ids(self, relation_name):
        return self._relation_ids_map[relation_name]

    def relation_list(self, relation_id):
        return self._relation_list_map[relation_id]

    def relation_get(self, relation_id, member_name, is_app):
        return self._relation_data[relation_id][member_name]

    def relation_set(self, relation_id, key, value, is_app):
        relation = self._relation_data[relation_id]
        if is_app:
            bucket_key = self.app_name
        else:
            bucket_key = self.unit_name
        if bucket_key not in relation:
            relation[bucket_key] = {}
        bucket = relation[bucket_key]
        bucket[key] = value

    def config_get(self):
        return self._config

    def is_leader(self):
        return self._is_leader

    def resource_get(self, resource_name):
        return self._resources_map[resource_name]

    def pod_spec_set(self, spec, k8s_resources):
        self._pod_spec = (spec, k8s_resources)

    def status_get(self, *, is_app=False):
        raise NotImplementedError(self.status_get)
        if is_app:
            return self._app_status
        else:
            return self._unit_status

    def status_set(self, status, message='', *, is_app=False):
        if is_app:
            self._app_status = (status, message)
        else:
            self._unit_status = (status, message)

    def storage_list(self, name):
        raise NotImplementedError(self.storage_list)

    def storage_get(self, storage_name_id, attribute):
        raise NotImplementedError(self.storage_get)

    def storage_add(self, name, count=1):
        raise NotImplementedError(self.storage_add)

    def action_get(self):
        raise NotImplementedError(self.action_get)

    def action_set(self, results):
        raise NotImplementedError(self.action_set)

    def action_log(self, message):
        raise NotImplementedError(self.action_log)

    def action_fail(self, message=''):
        raise NotImplementedError(self.action_fail)

    def network_get(self, endpoint_name, relation_id=None):
        raise NotImplementedError(self.network_get)


class FakeModelBuilder:
    """This is to make it easier to build up the state needed by a FakeModelBackend"""

    def __init__(self, fake_backend):
        self.fake_backend = fake_backend
        self._relation_id_counter = 0

    def create_relation(self, relation_name, remote_unit, remote_app_data={}, remote_unit_data={}):
        """Create a relation between fake_backend.unit_name and remote_unit.

        Seed that relation with the remote_app_data and remote_unit_data. The local data will be left empty.
        :return: The Relation ID for the newly created relation
        """
        remote_app_name = self.fake_backend.unit_name.split('/')[0]
        rel_id = self._relation_id_counter
        self._relation_id_counter += 1
        if relation_name not in self.fake_backend._relation_ids_map:
            self.fake_backend._relation_ids_map[relation_name] = []
        self.fake_backend._relation_ids_map[relation_name].append(rel_id)
        self.fake_backend._relation_names[rel_id] = relation_name
        self.fake_backend._relation_list_map[rel_id] = [remote_unit]
        relation_data = {
            remote_unit: remote_unit_data,
            remote_app_name: remote_app_data,
            self.fake_backend.unit_name: {},
            self.fake_backend.app_name: {},
        }
        self.fake_backend._relation_data[rel_id] = relation_data
        return rel_id


def build_relation_changed_args(model, fake_backend, relation_id, remote_name, remote_data):
    if relation_id not in fake_backend._relation_names:
        raise RuntimeError(f"relation_id: {relation_id} not in relation_names map")
    # TODO: we could check that remote_name is part of the fake_backend._relation_list_map[relation_id]
    relation_name = fake_backend._relation_names[relation_id]
    fake_backend._relation_data[relation_id][remote_name] = remote_data
    if '/' in remote_name:
        remote_unit_name = remote_name
        remote_app_name = remote_name.split('/')[0]
    else:
        remote_app_name = remote_name
        remote_unit_name = None
    relation = model.get_relation(relation_name, relation_id)
    remote_app = model.get_app(remote_app_name)
    if remote_unit_name is not None:
        remote_unit = model.get_unit(remote_unit_name)
        return (relation, remote_app, remote_unit)
    else:
        return (relation, remote_app)


class TestPostgreSQLClient(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir)
        # language=YAML
        self.meta = charm.CharmMeta.from_yaml('''
name: test-charm
requires:
  db:
    interface: pgsql
''')
        self.unit_name = 'test-charm/0'
        self.fake_backend = FakeModelBackend(self.unit_name)
        self.fake_builder = FakeModelBuilder(self.fake_backend)
        self.model = model.Model(self.unit_name, self.meta, self.fake_backend)
        self.framework = framework.Framework(":memory:", self.tmpdir, self.meta, self.model)
        self.charm = charm.CharmBase(self.framework, "charm")
        self.client = client.PostgreSQLClient(self.charm, "db")

    def test_stable_relation(self):
        # language=YAML
        relationContent = yaml.safe_load('''
allowed-subnets: 10.210.24.239/32
allowed-units: hello-juju/0
database: hello-juju_hello-juju
egress-subnets: 10.210.24.14/32
host: 10.210.24.14
ingress-address: 10.210.24.14
master: dbname=hello-juju_hello-juju host=10.210.24.14 password=MS6ycrxdzmwbRSpsNMnHhPS28bNkYf5b9nWVX8
  port=5432 user=juju_hello-juju
password: MS6ycrxdzmwbRSpsNMnHhPS28bNkYf5b9nWVX8
port: "5432"
private-address: 10.210.24.14
schema_password: MS6ycrxdzmwbRSpsNMnHhPS28bNkYf5b9nWVX8
schema_user: juju_hello-juju
state: standalone
user: juju_hello-juju
version: "10"
''')
        rel_id = self.fake_builder.create_relation('db', 'postgresql/0')
        args = build_relation_changed_args(self.model, self.fake_backend, rel_id, 'postgresql/0',
                                           remote_data=relationContent)
        self.charm.on.db_relation_changed.emit(*args)
        self.assertEqual('hello-juju_hello-juju', self.client.master().database)


if __name__ == '__main__':
    unittest.main()