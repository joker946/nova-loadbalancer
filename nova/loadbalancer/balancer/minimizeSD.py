# Copyright (c) 2015 Servionica, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from nova import db
from nova.loadbalancer import utils as lb_utils
from nova.loadbalancer.balancer.base import BaseBalancer
from nova.i18n import _
from nova.openstack.common import log as logging

from copy import deepcopy
from oslo.config import cfg


lb_opts = [
    cfg.FloatOpt('cpu_weight',
                 default=1.0,
                 help='LoadBalancer CPU weight.'),
    cfg.FloatOpt('memory_weight',
                 default=1.0,
                 help='LoadBalancer Memory weight.')
]

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer_minimizeSD')


class MinimizeSD(BaseBalancer):

    def __init__(self, *args, **kwargs):
        super(MinimizeSD, self).__init__(*args, **kwargs)
        self.cpu_weight = CONF.loadbalancer_minimizeSD.cpu_weight
        self.memory_weight = CONF.loadbalancer_minimizeSD.memory_weight

    def _simulate_migration(self, instance, node, host_loads, compute_nodes):
        source_host = instance.instance['host']
        target_host = node['hypervisor_hostname']
        vm_ram = instance['mem']
        vm_cpu = lb_utils.calculate_cpu(instance, compute_nodes)
        _host_loads = deepcopy(host_loads)
        LOG.debug(_(_host_loads))
        _host_loads[source_host]['mem'] -= vm_ram
        _host_loads[source_host]['cpu'] -= vm_cpu
        _host_loads[target_host]['mem'] += vm_ram
        _host_loads[target_host]['cpu'] += vm_cpu
        _host_loads = lb_utils.calculate_host_loads(compute_nodes, _host_loads)
        ram_sd = lb_utils.calculate_sd(_host_loads, 'mem')
        cpu_sd = lb_utils.calculate_sd(_host_loads, 'cpu')
        return {'cpu_sd': cpu_sd*self.cpu_weight,
                'ram_sd': ram_sd*self.memory_weight,
                'total_sd': cpu_sd*self.cpu_weight + ram_sd*self.memory_weight}

    def min_sd(self, context, **kwargs):
        compute_nodes = kwargs.get('nodes')
        instances = []
        for node in compute_nodes:
            node_instances = db.get_instances_stat(
                context,
                node['hypervisor_hostname'])
            instances.extend(node_instances)
        host_loads = lb_utils.fill_compute_stats(instances, compute_nodes)
        LOG.debug(_(host_loads))
        vm_host_map = []
        for instance in instances:
            for node in compute_nodes:
                h_hostname = node['hypervisor_hostname']
                # Source host shouldn't be use.
                if instance.instance['host'] != h_hostname:
                    sd = self._simulate_migration(instance, node, host_loads,
                                                  compute_nodes)
                    vm_host_map.append({'host': h_hostname,
                                        'vm': instance['instance_uuid'],
                                        'sd': sd})
        vm_host_map = sorted(vm_host_map, key=lambda x: x['sd']['total_sd'])
        LOG.debug(_(vm_host_map))
        for vm_host in vm_host_map:
            instance = filter(lambda x: x['instance_uuid'] == vm_host['vm'],
                              instances)[0]
            instance_resources = lb_utils.get_instance_resources(instance)
            if instance_resources:
                filter_instance = {'uuid': instance['instance_uuid'],
                                   'resources': instance_resources}
                filtered = self.filter_hosts(context, filter_instance,
                                             compute_nodes,
                                             host=vm_host['host'])
                if not filtered[0]:
                    continue
                self.migrate(context, instance['instance_uuid'],
                             vm_host['host'])
                return

    def balance(self, context, **kwargs):
        return self.min_sd(context, **kwargs)
