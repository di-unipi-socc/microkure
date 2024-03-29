from abc import abstractmethod

from microfreshener.core.model import MicroToscaModel

from microkure.ignorer.impl.ignore_config import IgnoreType
from microkure.ignorer.impl.ignore_nothing import IgnoreNothing
from microkure.ignorer.ignorer import Ignorer
from microkure.kmodel.kube_cluster import KubeCluster


class KubeWorker:

    def __init__(self, name):
        self.executed_only_after_workers = []
        self.name = name

    @abstractmethod
    def refine(self, model: MicroToscaModel, cluster: KubeCluster, ignorer: Ignorer = IgnoreNothing()) -> MicroToscaModel:
        pass

    def _get_nodes_not_ignored(self, nodes, ignore):
        if ignore is None:
            ignore = IgnoreNothing()

        return [n for n in nodes if not ignore.is_ignored(n, IgnoreType.WORKER, self.name)]
