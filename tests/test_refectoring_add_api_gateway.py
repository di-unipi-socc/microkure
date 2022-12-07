from unittest import TestCase

from microfreshener.core.analyser.smell import NoApiGatewaySmell
from microfreshener.core.model import MicroToscaModel, Edge, Service

from project.kmodel.kCluster import KCluster
from project.kmodel.kDeployment import KDeployment
from project.kmodel.kPod import KPod
from data.kube_objects_dict import POD_WITH_ONE_CONTAINER, DEPLOYMENT_WITH_ONE_CONTAINER, POD_WITH_TWO_CONTAINER
from project.kmodel.kService import KService

from project.kmodel.kobject_kind import KObjectKind
from project.solver.add_API_gateway_refactoring import AddAPIGatewayRefactoring


class TestAddAPIGatewayRefactoring(TestCase):

    '''
    Test case: Pod has hostNetwork set as True
    '''
    def test_pod_with_hostnetwork(self):
        model = MicroToscaModel("model")
        model.add_group(Edge("edge"))
        cluster = KCluster()

        # Cluster
        k_pod = KPod.from_dict(POD_WITH_ONE_CONTAINER)
        k_pod.spec.host_network = True
        cluster.add_object(k_pod, KObjectKind.POD)

        # Model
        svc = Service(k_pod.get_containers()[0].name + "." + k_pod.get_fullname())
        model.add_node(svc)
        model.edge.add_member(svc)

        # Smell
        smell = NoApiGatewaySmell(svc)

        # Check model and cluster
        self.assertEqual(len(cluster.get_all_objects()), 1)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        # Refactoring
        solver: AddAPIGatewayRefactoring = AddAPIGatewayRefactoring(model, cluster)
        solver.apply(smell)

        # Check
        self.assertEqual(len(cluster.get_all_objects()), 2)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        k_services: list = cluster.get_objects_by_kind(KObjectKind.SERVICE)
        self.assertEquals(len(k_services), 1)
        k_service: KService = k_services[0]

        #TODO self.assertFalse(k_pod.spec.host_network)

        self.assertEqual(k_service.get_fullname(), f"{k_pod.metadata.name}-MF.{k_pod.get_namespace()}")
        self.assertTrue(f"{k_pod.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        container_name = k_pod.get_containers()[0].name
        k_pod_port_strings = [
            f"{p.get('name', container_name+'.'+k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']} {p['containerPort']}"
            for p in k_pod.get_containers()[0].ports]
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']} {p['node_port']}"
            for p in k_service.get_ports()]

        self.assertEqual(len(k_service.get_ports()), 2)
        for port in k_pod_port_strings:
            self.assertTrue(port in k_svc_port_strings)


    '''
    Test case: one port has hostPort set and the other not
    '''
    def test_pod_with_host_port(self):
        model = MicroToscaModel("model")
        model.add_group(Edge("edge"))
        cluster = KCluster()

        # Cluster
        pod_host_port = 90
        k_pod = KPod.from_dict(POD_WITH_ONE_CONTAINER)
        k_pod.get_containers()[0].ports[0]["hostPort"] = pod_host_port
        cluster.add_object(k_pod, KObjectKind.POD)

        # Model
        svc = Service(k_pod.get_containers()[0].name + "." + k_pod.get_fullname())
        model.add_node(svc)
        model.edge.add_member(svc)

        # Smell
        smell = NoApiGatewaySmell(svc)

        # Check model and cluster
        self.assertEqual(len(cluster.get_all_objects()), 1)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        # Refactoring
        solver: AddAPIGatewayRefactoring = AddAPIGatewayRefactoring(model, cluster)
        solver.apply(smell)

        # Check
        self.assertEqual(len(cluster.get_all_objects()), 2)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        k_services: list = cluster.get_objects_by_kind(KObjectKind.SERVICE)
        self.assertEquals(len(k_services), 1)
        k_service: KService = k_services[0]

        self.assertEqual(len(k_service.get_ports()), 1)

        self.assertEqual(k_service.get_fullname(), f"{k_pod.metadata.name}-MF.{k_pod.get_namespace()}")
        self.assertTrue(f"{k_pod.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        for container in k_pod.get_containers():
            for port in container.ports:
                self.assertIsNone(port.get("hostPort"))

        self.assertEqual(len(k_service.get_ports()), 1)

        container_name = k_pod.get_containers()[0].name
        k_pod_port_strings = [
            f"{container_name}.{p.get('name', k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']}"
            for p in k_pod.get_containers()[0].ports[0:0]] # I take only the 0 cause is the one with hostPort set
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']}" for p in k_service.get_ports()]
        for port in k_pod_port_strings:
            self.assertTrue(port in k_svc_port_strings)

        # Check node port
        self.assertEqual(k_service.get_ports()[0]["node_port"], pod_host_port)

    '''
    Test case: Deployment has hostNetwork set as True
    '''
    def test_deployment_with_hostnetwork(self):
        model = MicroToscaModel("model")
        model.add_group(Edge("edge"))
        cluster = KCluster()

        # Cluster
        k_deploy = KDeployment.from_dict(DEPLOYMENT_WITH_ONE_CONTAINER)
        k_deploy.get_pod_template_spec().spec.host_network = True
        cluster.add_object(k_deploy, KObjectKind.DEPLOYMENT)

        # Model
        svc = Service(k_deploy.get_containers()[0].name + "." + k_deploy.get_fullname())
        model.add_node(svc)
        model.edge.add_member(svc)

        # Smell
        smell = NoApiGatewaySmell(svc)

        # Check model and cluster
        self.assertEqual(len(cluster.get_all_objects()), 1)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        # Refactoring
        solver: AddAPIGatewayRefactoring = AddAPIGatewayRefactoring(model, cluster)
        solver.apply(smell)

        # Check
        self.assertEqual(len(cluster.get_all_objects()), 2)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        #TODO self.assertFalse(k_deploy.get_pod_template_spec().spec.host_network)

        k_services: list = cluster.get_objects_by_kind(KObjectKind.SERVICE)
        self.assertEquals(len(k_services), 1)
        k_service: KService = k_services[0]

        self.assertEqual(k_service.get_fullname(), f"{k_deploy.metadata.name}-MF.{k_deploy.get_namespace()}")
        self.assertTrue(f"{k_deploy.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        container_name = k_deploy.get_pod_template_spec().get_containers()[0].name
        k_deploy_port_strings = [
            f"{p.get('name', container_name+k_deploy.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']} {p['containerPort']}"
            for p in k_deploy.get_containers()[0].ports]
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']} {p['node_port']}"
            for p in k_service.get_ports()]

        self.assertEqual(len(k_service.get_ports()), len(k_deploy.get_containers()[0].ports))
        for port in k_deploy_port_strings:
            self.assertTrue(port in k_svc_port_strings)

    '''
    Test case: one port has hostPort set and the other not
    '''
    def test_deployment_with_host_port(self):
        model = MicroToscaModel("model")
        model.add_group(Edge("edge"))
        cluster = KCluster()

        # Cluster
        deployment_host_port = 90
        k_deploy = KDeployment.from_dict(DEPLOYMENT_WITH_ONE_CONTAINER)
        k_deploy.get_pod_template_spec().get_containers()[0].ports[0]["hostPort"] = deployment_host_port
        cluster.add_object(k_deploy, KObjectKind.DEPLOYMENT)


        # Model
        svc = Service(k_deploy.get_pod_template_spec().get_containers()[0].name + "." + k_deploy.get_fullname())
        model.add_node(svc)
        model.edge.add_member(svc)

        # Smell
        smell = NoApiGatewaySmell(svc)

        # Check model and cluster
        self.assertEqual(len(cluster.get_all_objects()), 1)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        # Refactoring
        solver: AddAPIGatewayRefactoring = AddAPIGatewayRefactoring(model, cluster)
        solver.apply(smell)

        # Check
        self.assertEqual(len(cluster.get_all_objects()), 2)
        self.assertEqual(len([n for n in model.nodes]), 1)
        self.assertEqual(len(model.edge.members), 1)

        k_services: list = cluster.get_objects_by_kind(KObjectKind.SERVICE)
        self.assertEquals(len(k_services), 1)
        k_service: KService = k_services[0]

        self.assertEqual(len(k_service.get_ports()), 1)

        self.assertEqual(k_service.get_fullname(), f"{k_deploy.metadata.name}-MF.{k_deploy.get_namespace()}")
        self.assertTrue(f"{k_deploy.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        # Check hostPort is none
        for container in k_deploy.get_containers():
            for port in container.ports:
                self.assertIsNone(port.get("hostPort"))

        # Check ports
        k_pod_port_strings = [
            f"{p.get('name', k_deploy.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']}"
            for p in k_deploy.get_containers()[0].ports]
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']}"
            for p in k_service.get_ports()]

        self.assertEqual(len(k_service.get_ports()), 1)
        self.assertEqual(len(k_pod_port_strings), 1)
        for port in k_pod_port_strings:
            self.assertTrue(port in k_svc_port_strings)

        # Check service exponed ports
        self.assertEqual(k_service.get_ports()[0]["node_port"], deployment_host_port)

    '''
    Test case: the pod defines two container and has hostNetwork = True
    '''
    def test_pod_with_two_container_host_port(self):
        model = MicroToscaModel("model")
        model.add_group(Edge("edge"))
        cluster = KCluster()

        # Cluster
        host_ports = [80,81]
        k_pod = KPod.from_dict(POD_WITH_TWO_CONTAINER)
        k_pod.get_containers()[1].ports[0]['containerPort'] = 8001
        k_pod.get_containers()[0].ports[0]['hostPort'] = host_ports[0]
        k_pod.get_containers()[1].ports[0]['hostPort'] = host_ports[1]
        cluster.add_object(k_pod, KObjectKind.POD)

        # Model
        svc_1 = Service(k_pod.get_containers()[0].name + "." + k_pod.get_fullname())
        svc_2 = Service(k_pod.get_containers()[1].name + "." + k_pod.get_fullname())
        model.add_node(svc_1)
        model.add_node(svc_2)
        model.edge.add_member(svc_1)
        model.edge.add_member(svc_2)

        # Smell
        smell_1 = NoApiGatewaySmell(svc_1)
        smell_2 = NoApiGatewaySmell(svc_2)

        # Check model and cluster
        self.assertEqual(len(cluster.get_all_objects()), 1)
        self.assertEqual(len([n for n in model.nodes]), 2)
        self.assertEqual(len(model.edge.members), 2)

        # Refactoring
        solver: AddAPIGatewayRefactoring = AddAPIGatewayRefactoring(model, cluster)
        solver.apply(smell_1)
        solver.apply(smell_2)

        # Check
        self.assertEqual(len(cluster.get_all_objects()), 2)
        self.assertEqual(len([n for n in model.nodes]), 2)
        self.assertEqual(len(model.edge.members), 2)

        k_services: list = cluster.get_objects_by_kind(KObjectKind.SERVICE)
        self.assertEquals(len(k_services), 1)
        k_service: KService = k_services[0]

        self.assertEqual(k_service.get_fullname(), f"{k_pod.metadata.name}-MF.{k_pod.get_namespace()}")
        self.assertTrue(f"{k_pod.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        # Check that hostPort is removed
        for container in k_pod.get_containers():
            for port in container.ports:
                self.assertIsNone(port.get("hostPort"))

        # Check port protocols, names, and container port
        k_pod_port_strings = [
            f"{p.get('name', k_pod.get_containers()[0].name+'.'+k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']}"
            for p in k_pod.get_containers()[0].ports]
        k_pod_port_strings += [
            f"{p.get('name', k_pod.get_containers()[1].name+'.'+k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']}"
            for p in k_pod.get_containers()[1].ports]
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']}"
            for p in k_service.get_ports()]
        self.assertEqual(len(k_service.get_ports()), 2)

        for port in k_pod_port_strings:
            self.assertTrue(port in k_svc_port_strings)

        # Check node ports exponed
        for host_port in host_ports:
            self.assertTrue(host_port in [p["node_port"] for p in k_service.get_ports()])

    '''
    Test case: the pod defines two container and has hostNetwork = True, but expose the same port
    This case is not feasible in reality, but simulate when two different pods are exposed by the same SVC and the sw
    need to add the ports to the message router
    '''
    #TODO if runned with the other functions, this test fails. I don't know why
    def test_pod_with_two_container_hostnetwork_equal_ports(self):
        model = MicroToscaModel("model")
        model.add_group(Edge("edge"))
        cluster = KCluster()

        # Cluster
        k_pod = KPod.from_dict(POD_WITH_TWO_CONTAINER)
        k_pod.spec.host_network = True
        k_pod.get_containers()[0].ports[0]['containerPort'] = 8000
        k_pod.get_containers()[1].ports[0]['containerPort'] = 8000
        cluster.add_object(k_pod, KObjectKind.POD)

        # Model
        svc_1 = Service(k_pod.get_containers()[0].name + "." + k_pod.get_fullname())
        svc_2 = Service(k_pod.get_containers()[1].name + "." + k_pod.get_fullname())
        model.add_node(svc_1)
        model.add_node(svc_2)
        model.edge.add_member(svc_1)
        model.edge.add_member(svc_2)

        # Smell
        smell_1 = NoApiGatewaySmell(svc_1)
        smell_2 = NoApiGatewaySmell(svc_2)

        # Check model and cluster
        self.assertEqual(len(cluster.get_all_objects()), 1)
        self.assertEqual(len([n for n in model.nodes]), 2)
        self.assertEqual(len(model.edge.members), 2)

        # Refactoring
        solver: AddAPIGatewayRefactoring = AddAPIGatewayRefactoring(model, cluster)
        solver.apply(smell_1)
        solver.apply(smell_2)

        # Check
        # TODO lanciando l'intera suite, questo test salta ma lanciandolo in solitaria no. Non capisco perché
        self.assertEqual(len(cluster.get_all_objects()), 3)
        self.assertEqual(len([n for n in model.nodes]), 2)
        self.assertEqual(len(model.edge.members), 2)

        k_services: list = cluster.get_objects_by_kind(KObjectKind.SERVICE)
        self.assertEquals(len(k_services), 2)

        # Test service 1
        k_service: KService = k_services[0]

        self.assertEqual(k_service.get_fullname(), f"{k_pod.metadata.name}-MF.{k_pod.get_namespace()}")
        self.assertTrue(f"{k_pod.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        #TODO self.assertFalse(k_pod.spec.host_network)

        k_pod_port_strings = [
            f"{p.get('name', k_pod.get_containers()[0].name+'.'+k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']} {p['containerPort']}"
            for p in k_pod.get_containers()[0].ports]
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']} {p['node_port']}"
            for p in k_service.get_ports()]
        self.assertEqual(len(k_service.get_ports()), 1)

        for port in k_pod_port_strings:
            self.assertTrue(port in k_svc_port_strings)

        # Test service 2
        k_service: KService = k_services[1]

        self.assertEqual(k_service.get_fullname(), f"{k_pod.metadata.name}-MF.{k_pod.get_namespace()}")
        self.assertTrue(f"{k_pod.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        k_pod_port_strings = [
            f"{p.get('name', k_pod.get_containers()[1].name+'.'+k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']} {p['containerPort']}"
            for p in k_pod.get_containers()[1].ports]
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']} {p['node_port']}"
            for p in k_service.get_ports()]
        self.assertEqual(len(k_service.get_ports()), 1)

        for port in k_pod_port_strings:
            self.assertTrue(port in k_svc_port_strings)

    '''
    Test case: the pod defines two container and has hostNetwork = True
    '''
    def test_pod_with_two_container_hostnetwork(self):
        model = MicroToscaModel("model")
        model.add_group(Edge("edge"))
        cluster = KCluster()

        # Cluster
        k_pod = KPod.from_dict(POD_WITH_TWO_CONTAINER)
        k_pod.spec.host_network = True
        k_pod.get_containers()[0].ports[0]['containerPort'] = 8001
        k_pod.get_containers()[1].ports[0]['containerPort'] = 8000
        cluster.add_object(k_pod, KObjectKind.POD)

        # Model
        svc_1 = Service(k_pod.get_containers()[0].name + "." + k_pod.get_fullname())
        svc_2 = Service(k_pod.get_containers()[1].name + "." + k_pod.get_fullname())
        model.add_node(svc_1)
        model.add_node(svc_2)
        model.edge.add_member(svc_1)
        model.edge.add_member(svc_2)

        # Smell
        smell_1 = NoApiGatewaySmell(svc_1)
        smell_2 = NoApiGatewaySmell(svc_2)

        # Check model and cluster
        self.assertEqual(len(cluster.get_all_objects()), 1)
        self.assertEqual(len([n for n in model.nodes]), 2)
        self.assertEqual(len(model.edge.members), 2)

        # Refactoring
        solver: AddAPIGatewayRefactoring = AddAPIGatewayRefactoring(model, cluster)
        solver.apply(smell_1)
        solver.apply(smell_2)

        # Check
        self.assertEqual(len(cluster.get_all_objects()), 2)
        self.assertEqual(len([n for n in model.nodes]), 2)
        self.assertEqual(len(model.edge.members), 2)

        k_services: list = cluster.get_objects_by_kind(KObjectKind.SERVICE)
        self.assertEquals(len(k_services), 1)
        k_service: KService = k_services[0]

        #TODO self.assertFalse(k_pod.spec.host_network)

        self.assertEqual(k_service.get_fullname(), f"{k_pod.metadata.name}-MF.{k_pod.get_namespace()}")
        self.assertTrue(f"{k_pod.get_fullname()}-svc-MF" in k_service.get_selectors().keys())
        self.assertEqual(k_service.spec.type, "NodePort")

        k_pod_port_strings = [
            f"{p.get('name', k_pod.get_containers()[0].name+'.'+k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']} {p['containerPort']}"
            for p in k_pod.get_containers()[0].ports]
        k_pod_port_strings += [
            f"{p.get('name', k_pod.get_containers()[1].name+'.'+k_pod.get_fullname()+'-port-'+str(p['containerPort'])+'-MF')} {p.get('protocol', 'PROTOCOL?')} {p['containerPort']} {p['containerPort']}"
            for p in k_pod.get_containers()[1].ports]
        k_svc_port_strings = [
            f"{p.get('name', '')} {p.get('protocol', 'PROTOCOL?')} {p['port']} {p['node_port']}"
            for p in k_service.get_ports()]
        self.assertEqual(len(k_service.get_ports()), 2)

        for port in k_pod_port_strings:
            self.assertTrue(port in k_svc_port_strings)