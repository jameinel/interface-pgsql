import re

from ops.framework import EventBase, EventsBase, EventSource, StoredState
from ops.model import ModelError, BlockedStatus, WaitingStatus

key_value_re = re.compile(r"""(?x)
                               (\w+) \s* = \s*
                               (?:
                                 (\S*)
                               )
                               (?=(?:\s|\Z))
                           """)


class PostgreSQLError(ModelError):
    """All errors raised by interface-pgsql will be subclasses of this error.

    It provides the attribute self.status to indicate what status and message the Unit should use based on this relation.
    (Eg, if there is no relation to PGSQl, it will raise a BlockedStatus('Missing relation <relation-name>')
    """

    def __init__(self, kind, message, relation_name):
        super().__init__()
        self.status = self.kind(f'{message}: {relation_name}')


class PostgreSQLDatabase:

    def __init__(self, master):
        # This is a pgsql 'key=value key2=value' connection string
        self.master = master
        self.properties = {}
        for key, val in key_value_re.findall(master):
            if key not in self.properties:
                self.properties[key] = val

    @property
    def host(self):
        return self.properties['host']

    @property
    def database(self):
        return self.properties['dbname']

    @property
    def port(self):
        return self.properties['port']

    @property
    def user(self):
        return self.properties['user']

    @property
    def password(self):
        return self.properties['password']


class PostgreSQLMasterChanged(EventBase):

    def __init__(self, handle, master):
        super().__init__(handle)
        self.master = master

    def snapshot(self):
        return {'master': self.master}

    def restore(self, snapshot):
        self.master = snapshot['master']


class PostgreSQLEvents(EventsBase):
    master_changed = EventSource(PostgreSQLMasterChanged)


class PostgreSQLClient(EventsBase):
    """This provides a Client that understands how to communicate with the PostgreSQL Charm.

    The two primary methods are .master() which will give you the connection information for the current PostgreSQL
    master (or raise an error if the relation or master is not properly established yet).
    And
    """
    on = PostgreSQLEvents()
    state = StoredState()

    def __init__(self, parent, name):
        super().__init__(parent, name)
        self.name = name
        self.framework.observe(parent.on[self.name].relation_changed, self.on_relation_changed)
        self.framework.observe(parent.on[self.name].relation_broken, self.on_relation_broken)
        self.state.set_default(master=None)

    def master(self):
        """Retrieve the libpq connection string for the Master postgresql database.

        This method will raise PostgreSQLError with a status of either Blocked or Waiting if the error does/doesn't need
        user intervention.
        """
        relations = self.framework.model.relations[self.name]
        if len(relations) == 1:
            if self.state.master is None:
                raise PostgreSQLError(WaitingStatus, 'master not ready yet', self.name)
            return PostgreSQLDatabase(self.state.master)
        if len(relations) == 0:
            raise PostgreSQLError(BlockedStatus, 'missing relation', self.name)
        if len(relations) > 1:
            raise PostgreSQLError(BlockedStatus, 'too many related applications', self.name)

    def standbys(self):
        """Retrieve the connection strings for all PostgreSQL standby machines."""
        pass

    @property
    def roles(self, value):
        """Indicate what roles you want available from PostgreSQL."""
        pass

    @property
    def extensions(self, value):
        """Indicate what extensions you want available from PostgreSQL."""
        pass

    def _resolve_master(self, new_master):
        # TODO: the pgsql charm likes to report that you can't actually connect as long as
        #  relation_data[myunit]['egress-subnets'] is not a subset of relation_data[psql]['allowed-subnets']
        #  As well as waiting for remote['database'] to match requested['database'], and roles and extensions.
        pass

    def on_relation_changed(self, event):
        # Check to see if the master is now at a different location
        relation = event.relation  # type: ops.model.Relation
        data = relation.data[event.unit]
        # TODO: do we check if any related units have a 'master' set?
        #  Also, we need to check if we actually have the database, roles, and access that we want
        master = data.get('master')
        if master is not None:
            should_emit = self.state.master != master
        if should_emit:
            self.state.master = master
            self.on.master_changed.emit(master)

    def on_relation_broken(self, event):
        pass
