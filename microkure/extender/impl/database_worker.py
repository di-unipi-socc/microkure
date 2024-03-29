from microfreshener.core.model import Service, Datastore

from microkure.extender.kubeworker import KubeWorker
from microkure.extender.worker_names import DATABASE_WORKER, NAME_WORKER
from microkure.ignorer.impl.ignore_nothing import IgnoreNothing
from microkure.kmodel.kube_container import KubeContainer


class DatabaseWorker(KubeWorker):
    DATABASE_PORTS = [1433, 1434, 1521, 3306, 33060, 3050, 5432, 8001, 8080, 27017, 7199, 8089, 443, 10000,
                      8086, 7474, 7473]
    DATABASE_NAMES = ["mysql", "sql", "oracle", "redis", "mongodb", "mongo-db", "database", "mariadb"
                      "snowflake", "cassandra", "splunk", "dynamodb", "hive", "influxdb", "neo4j"]

    def __init__(self):
        super().__init__(DATABASE_WORKER)
        self.executed_only_after_workers.append(NAME_WORKER)

    def refine(self, model, cluster, ignorer=IgnoreNothing()):
        self._search_datastores(model, cluster, ignorer)
        return model

    def _search_datastores(self, model, cluster, ignorer):
        not_ignored_services = self._get_nodes_not_ignored(model.services, ignorer)

        for service_node in [s for s in not_ignored_services if len(s.interactions) == 0]:
            container = cluster.get_object_by_name(service_node.name, KubeContainer)

            if container and self._is_database(container):
                datastore_node = Datastore("TEMPORARY_DATASTORE_NAME")
                model.add_node(datastore_node)

                self._update_datastore_incoming_interactions(model, service_node, datastore_node)

                # Update deployed_on
                for dep in service_node.deployed_on.copy():
                    datastore_node.add_deployed_on(dep.target)

                model.delete_node(service_node)
                model.rename_node(datastore_node, service_node.name)

    def _update_datastore_incoming_interactions(self, model, service_node: Service, datastore_node: Datastore):
        for relation in list(service_node.incoming_interactions):
            model.add_interaction(
                source_node=relation.source,
                target_node=datastore_node,
                with_timeout=relation.timeout,
                with_circuit_breaker=relation.circuit_breaker,
                with_dynamic_discovery=relation.dynamic_discovery
            )
            model.delete_relationship(relation)

    def _is_database(self, container: KubeContainer):
        ports_check = len([v for v in container.get_container_ports() if v in self.DATABASE_PORTS]) > 0
        image_check = len([n for n in self.DATABASE_NAMES if n.upper() in container.image.upper()]) > 0
        name_check = len([n for n in self.DATABASE_NAMES if n.upper() in container.name.upper()]) > 0

        return ports_check or name_check or image_check
