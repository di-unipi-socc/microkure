from microfreshener.core.model.nodes import Compute, Service

from microkure.extender.kubeworker import KubeWorker
from microkure.extender.worker_names import COMPUTE_NODE_WORKER
from microkure.ignorer.impl.ignore_nothing import IgnoreNothing


class ComputeNodeWorker(KubeWorker):

    def __init__(self):
        super().__init__(COMPUTE_NODE_WORKER)

    def refine(self, model, cluster, ignorer=IgnoreNothing()):
        self._add_compute_nodes(model, cluster, ignorer)
        return model

    def _add_compute_nodes(self, model, cluster, ignorer):
        not_ignored_nodes = self._get_nodes_not_ignored(model.nodes, ignorer)

        for workload in cluster.workloads:
            compute_node = self._get_or_create_compute(model, workload.typed_fullname)

            if compute_node not in not_ignored_nodes:

                for container in workload.containers:
                    node = model.get_node_by_name(container.typed_fullname)

                    if node and node in not_ignored_nodes:
                        model.add_deployed_on(node, compute_node)

    def _get_or_create_compute(self, model, compute_name):
        compute_node = model.get_node_by_name(compute_name, Compute)

        if compute_node is None:
            compute_node = Compute(compute_name)
            model.add_node(compute_node)

        return compute_node
