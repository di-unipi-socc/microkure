import copy
from unittest import TestCase

from microfreshener.core.model import MicroToscaModel, Service, MessageRouter, Edge

from project.extender.extender import KubeExtender
from project.extender.workerimpl.service_worker import ServiceWorker
from data.kube_objects_dict import DEFAULT_SVC, POD_WITH_ONE_CONTAINER
from project.kmodel.kube_cluster import KubeCluster
from project.kmodel.kube_networking import KubeService
from project.kmodel.kube_workload import KubePod


class TestServiceExtender(TestCase):

    '''
    Test case: a Kubernetes Service is represented as Service and not MessageRouter node type in the graph, the type
    of this graph is switched to MessageRouter and all relations are maintained
    '''
    def test_model_service_is_kubernetes_service(self):
        model = MicroToscaModel(name="test_model_service_is_kubernetes_service")
        cluster = KubeCluster()

        # Add objects to cluster
        k_svc = KubeService(copy.deepcopy(DEFAULT_SVC))
        k_pod_1 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_2 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_3 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_3.data["metadata"]["labels"] = {'app': 'test'}
        k_pod_1.data["metadata"]["name"] = k_pod_1.data["metadata"]["name"] + "_1"
        k_pod_2.data["metadata"]["name"] = k_pod_2.data["metadata"]["name"] + "_2"
        k_pod_3.data["metadata"]["name"] = k_pod_3.data["metadata"]["name"] + "_3"
        cluster.add_object(k_svc)
        cluster.add_object(k_pod_1)
        cluster.add_object(k_pod_2)
        cluster.add_object(k_pod_3)

        # Add Service to Tosca Model
        svc1 = Service(k_pod_1.get_containers()[0].get_name() + "." + k_pod_1.get_fullname())
        svc2 = Service(k_pod_2.get_containers()[0].get_name() + "." + k_pod_2.get_fullname())
        svc3 = Service(k_pod_3.get_containers()[0].get_name() + "." + k_pod_3.get_fullname())
        mr = Service(k_svc.get_fullname() + ".svc.cluster.local")
        model.add_node(svc1)
        model.add_node(svc2)
        model.add_node(svc3)
        model.add_node(mr)
        model.add_interaction(source_node=svc1, target_node=mr)
        model.add_interaction(source_node=svc2, target_node=mr)
        model.add_interaction(source_node=mr, target_node=svc3)

        self.assertEqual(len(cluster.cluster_objects), 4)
        self.assertEqual(len(list(model.nodes)), 4)

        extender: KubeExtender = KubeExtender(worker_list=[ServiceWorker()])
        extender.extend(model, cluster)

        count = 0
        for node in model.nodes:
            if isinstance(node, MessageRouter):
                count += 1
                mr = node
        self.assertEqual(count, 1)

        self.assertEqual(len(svc1.interactions), 1)
        self.assertEqual(len(svc1.incoming_interactions), 0)
        self.assertEqual(len(svc2.interactions), 1)
        self.assertEqual(len(svc2.incoming_interactions), 0)
        self.assertEqual(len(mr.interactions), 1)
        self.assertEqual(len(mr.incoming_interactions), 2)
        self.assertEqual(len(svc3.interactions), 0)
        self.assertEqual(len(svc3.incoming_interactions), 1)

        self.assertEqual(len(cluster.cluster_objects), 4)
        self.assertEqual(len(list(model.nodes)), 4)

    '''
    Test case: there is a direct communication between two pods but the service defined does not expone them.
    '''
    def test_message_router_not_found_in_model(self):
        model = MicroToscaModel(name="service-model")
        model.add_group(Edge("edge"))
        cluster = KubeCluster()

        # Add objects to cluster
        k_svc = KubeService(copy.deepcopy(DEFAULT_SVC))
        k_svc.data["spec"]["selector"] = {'err': 'err'}
        k_pod_1 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_3 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_3.data["metadata"]["labels"] = {'app': 'test'}
        k_pod_1.data["metadata"]["name"] = k_pod_1.data["metadata"]["name"] + "_1"
        k_pod_3.data["metadata"]["name"] = k_pod_3.data["metadata"]["name"] + "_3"
        cluster.add_object(k_svc)
        cluster.add_object(k_pod_1)
        cluster.add_object(k_pod_3)

        # Add Service to Tosca Model
        svc1 = Service(k_pod_1.get_containers()[0].get_name() + "." + k_pod_1.get_fullname())
        svc3 = Service(k_pod_3.get_containers()[0].get_name() + "." + k_pod_3.get_fullname())
        model.add_node(svc1)
        model.add_node(svc3)
        model.add_interaction(source_node=svc1, target_node=svc3)

        self.assertEqual(len(cluster.cluster_objects), 3)
        self.assertEqual(len(list(model.nodes)), 2)

        extender: KubeExtender = KubeExtender(worker_list=[ServiceWorker()])
        extender.extend(model, cluster)

        count = 0
        for node in model.nodes:
            if isinstance(node, MessageRouter):
                count += 1
        self.assertEqual(count, 0)

        self.assertEqual(len(svc1.interactions), 1)
        self.assertEqual(len(svc1.incoming_interactions), 0)
        self.assertEqual(len(svc3.interactions), 0)
        self.assertEqual(len(svc3.incoming_interactions), 1)

        self.assertEqual(len(cluster.cluster_objects), 3)
        self.assertEqual(len(list(model.nodes)), 2)

    '''
    Test case: the communication between two pods is direct, but there's in the K8s deploy a SVC between the pods
    '''

    def test_service_not_found(self):
        model = MicroToscaModel(name="service-model")
        model.add_group(Edge("edge"))
        cluster = KubeCluster()
        label = {'app': 'test'}

        # Add objects to cluster
        k_svc = KubeService(copy.deepcopy(DEFAULT_SVC))
        k_pod_1 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_2 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_3 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_1.data["metadata"]["name"] = k_pod_1.data["metadata"]["name"] + "_1"
        k_pod_2.data["metadata"]["name"] = k_pod_2.data["metadata"]["name"] + "_2"
        k_pod_3.data["metadata"]["name"] = k_pod_3.data["metadata"]["name"] + "_3"
        cluster.add_object(k_svc)
        cluster.add_object(k_pod_1)
        cluster.add_object(k_pod_2)
        cluster.add_object(k_pod_3)

        k_pod_3.data["metadata"]["labels"] = label
        k_svc.data["spec"]["selector"] = label

        # Add Service to Tosca Model
        svc1 = Service(k_pod_1.get_containers()[0].get_name() + "." + k_pod_1.get_fullname())
        svc2 = Service(k_pod_2.get_containers()[0].get_name() + "." + k_pod_2.get_fullname())
        svc3 = Service(k_pod_3.get_containers()[0].get_name() + "." + k_pod_3.get_fullname())
        model.add_node(svc1)
        model.add_node(svc2)
        model.add_node(svc3)
        model.add_interaction(source_node=svc1, target_node=svc3)
        model.add_interaction(source_node=svc2, target_node=svc3)

        self.assertEqual(len(cluster.cluster_objects), 4)
        self.assertEqual(len(list(model.nodes)), 3)

        extender: KubeExtender = KubeExtender(worker_list=[ServiceWorker()])
        extender.extend(model, cluster)

        count = 0
        for node in model.nodes:
            if isinstance(node, MessageRouter):
                count += 1
                mr = node
        self.assertEqual(count, 1)

        self.assertEqual(len(svc1.interactions), 1)
        self.assertEqual(len(svc1.incoming_interactions), 0)
        self.assertEqual(len(svc2.interactions), 1)
        self.assertEqual(len(svc2.incoming_interactions), 0)
        self.assertEqual(len(mr.interactions), 1)
        self.assertEqual(len(mr.incoming_interactions), 2)
        self.assertEqual(len(svc3.interactions), 0)
        self.assertEqual(len(svc3.incoming_interactions), 1)

        self.assertEqual(len(cluster.cluster_objects), 4)
        self.assertEqual(len(list(model.nodes)), 4)

    '''
    Test case: MessageRouter found
    '''

    def test_service_is_present(self):
        model = MicroToscaModel(name="service-model")
        cluster = KubeCluster()

        # Add objects to cluster
        k_svc = KubeService(copy.deepcopy(DEFAULT_SVC))
        k_pod_1 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_3 = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_pod_3.data["metadata"]["labels"] = {'app': 'test'}
        k_pod_1.data["metadata"]["name"] = k_pod_1.data["metadata"]["name"] + "_1"
        k_pod_3.data["metadata"]["name"] = k_pod_3.data["metadata"]["name"] + "_3"
        cluster.add_object(k_svc)
        cluster.add_object(k_pod_1)
        cluster.add_object(k_pod_3)

        # Add Service to Tosca Model
        svc1 = Service(k_pod_1.get_containers()[0].get_name() + "." + k_pod_1.get_fullname())
        svc3 = Service(k_pod_3.get_containers()[0].get_name() + "." + k_pod_3.get_fullname())
        mr = MessageRouter(k_svc.get_fullname() + ".svc.cluster.local")
        model.add_node(svc1)
        model.add_node(svc3)
        model.add_node(mr)
        model.add_interaction(source_node=svc1, target_node=svc3)
        model.add_interaction(source_node=mr, target_node=svc3)

        self.assertEqual(len(cluster.cluster_objects), 3)
        self.assertEqual(len(list(model.nodes)), 3)

        extender: KubeExtender = KubeExtender(worker_list=[ServiceWorker()])
        extender.extend(model, cluster)

        count = 0
        for node in model.nodes:
            if isinstance(node, MessageRouter):
                count += 1
        self.assertEqual(count, 1)

        self.assertEqual(len(svc1.interactions), 1)
        self.assertEqual(len(svc1.incoming_interactions), 0)
        self.assertEqual(len(mr.interactions), 1)
        self.assertEqual(len(mr.incoming_interactions), 1)
        self.assertEqual(len(svc3.interactions), 0)
        self.assertEqual(len(svc3.incoming_interactions), 1)

        self.assertEqual(len(cluster.cluster_objects), 3)
        self.assertEqual(len(list(model.nodes)), 3)

    '''
    Test case: Service node is edge node and K8s Service is exponed on the host (for ex. NodePort)
    '''

    def test_tosca_service_edge_and_with_kservice_published(self):
        model = MicroToscaModel(name="service-model")
        model.add_group(Edge("edge"))
        cluster = KubeCluster()

        # Add objects to cluster
        k_svc = KubeService(copy.deepcopy(DEFAULT_SVC))
        pod = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_svc.data["spec"]["type"] = "NodePort"
        pod.data["metadata"]["labels"] = {'app': 'test'}
        cluster.add_object(k_svc)
        cluster.add_object(pod)

        # Add Service to Tosca Model
        svc = Service(pod.get_containers()[0].get_name() + "." + pod.get_fullname())
        model.add_node(svc)
        model.edge.add_member(svc)

        self.assertEqual(len(cluster.cluster_objects), 2)
        self.assertEqual(len(list(model.nodes)), 1)

        extender: KubeExtender = KubeExtender(worker_list=[ServiceWorker()])
        extender.extend(model, cluster)

        count = 0
        for node in model.nodes:
            if isinstance(node, MessageRouter):
                count += 1
                mr = node
        self.assertEqual(count, 1)

        self.assertEqual(len(svc.interactions), 0)
        self.assertEqual(len(svc.incoming_interactions), 1)
        self.assertTrue(svc not in model.edge)
        self.assertTrue(mr in model.edge)
        self.assertEqual(len(mr.interactions), 1)
        self.assertEqual(len(cluster.cluster_objects), 2)
        self.assertEqual(len(list(model.nodes)), 2)

    '''
    Test case: Service node is edge node and K8s Service is ClusterIP
    '''

    def test_tosca_service_edge_and_with_kservice_clusterip(self):
        model = MicroToscaModel(name="service-model")
        model.add_group(Edge("edge"))
        cluster = KubeCluster()

        # Add objects to cluster
        k_svc = KubeService(copy.deepcopy(DEFAULT_SVC))
        pod = KubePod(copy.deepcopy(POD_WITH_ONE_CONTAINER))
        k_svc.data["spec"]["type"] = "ClusterIP"
        pod.data["metadata"]["labels"] = {'app': 'test'}
        cluster.add_object(k_svc)
        cluster.add_object(pod)

        # Add Service to Tosca Model
        svc = Service(pod.get_containers()[0].get_name() + "." + pod.get_fullname())
        model.add_node(svc)
        model.edge.add_member(svc)

        self.assertEqual(len(cluster.cluster_objects), 2)
        self.assertEqual(len(list(model.nodes)), 1)

        extender: KubeExtender = KubeExtender(worker_list=[ServiceWorker()])
        extender.extend(model, cluster)

        count = 0
        for node in model.nodes:
            if isinstance(node, MessageRouter):
                count += 1
                mr = node
        self.assertEqual(count, 1)

        self.assertEqual(len(svc.interactions), 0)
        self.assertEqual(len(svc.incoming_interactions), 1)
        self.assertTrue(svc in model.edge)
        self.assertTrue(mr not in model.edge)
        self.assertEqual(len(mr.interactions), 1)
        self.assertEqual(len(cluster.cluster_objects), 2)
        self.assertEqual(len(list(model.nodes)), 2)
