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

from oslo.config import cfg

from nova import db
from nova.loadbalancer import utils as lb_utils
from nova.loadbalancer.balancer.base import BaseBalancer
from nova.i18n import _
from nova.openstack.common import log as logging


lb_opts = [
    cfg.FloatOpt('cpu_weight',
                 default=1.0,
                 help='CPU weight'),
    cfg.FloatOpt('memory_weight',
                 default=1.0,
                 help='Memory weight'),
    cfg.FloatOpt('io_weight',
                 default=1.0,
                 help='IO weight'),
    cfg.FloatOpt('compute_cpu_weight',
                 default=1.0,
                 help='CPU weight'),
    cfg.FloatOpt('compute_memory_weight',
                 default=1.0,
                 help='Memory weight')
]


CONF = cfg.CONF
LOG = logging.getLogger(__name__)
CONF.register_opts(lb_opts, 'loadbalancer_classic')
CONF.import_opt('scheduler_host_manager', 'nova.scheduler.driver')


class Classic(BaseBalancer):
    def __init__(self, *args, **kwargs):
        super(Classic, self).__init__(*args, **kwargs)

    def _weight_hosts(self, normalized_hosts):
        weighted_hosts = []
        compute_cpu_weight = CONF.loadbalancer_classic.compute_cpu_weight
        compute_memory_weight = CONF.loadbalancer_classic.compute_memory_weight
        for host in normalized_hosts:
            weighted_host = {'host': host['host']}
            cpu_used = host['cpu_used_percent']
            memory_used = host['memory_used']
            weight = compute_cpu_weight * cpu_used + \
                compute_memory_weight * memory_used
            weighted_host['weight'] = weight
            weighted_hosts.append(weighted_host)
        return sorted(weighted_hosts,
                      key=lambda x: x['weight'], reverse=False)

    def _weight_instances(self, normalized_instances, extra_info=None):
        weighted_instances = []
        cpu_weight = CONF.loadbalancer_classic.cpu_weight
        if extra_info.get('k_cpu'):
            cpu_weight = extra_info['k_cpu']
        memory_weight = CONF.loadbalancer_classic.memory_weight
        io_weight = CONF.loadbalancer_classic.io_weight
        for instance in normalized_instances:
            weighted_instance = {'uuid': instance['uuid']}
            weight = cpu_weight * instance['cpu'] + \
                memory_weight * instance['memory'] + \
                io_weight * instance['io']
            weighted_instance['weight'] = weight
            weighted_instances.append(weighted_instance)
        return sorted(weighted_instances,
                      key=lambda x: x['weight'], reverse=False)

    def _choose_instance_to_migrate(self, instances, extra_info=None):
        instances_params = []
        for i in instances:
            instance_resources = lb_utils.get_instance_resources(i)
            if instance_resources:
                instances_params.append(instance_resources)
        LOG.debug(_(instances_params))
        normalized_instances = lb_utils.normalize_params(instances_params)
        LOG.info(_(normalized_instances))
        if extra_info.get('cpu_overload'):
            normalized_instances = filter(lambda x: x['memory'] == 0,
                                          normalized_instances)
            extra_info['k_cpu'] = -1
        weighted_instances = self._weight_instances(normalized_instances,
                                                    extra_info)
        LOG.info(_(weighted_instances))
        for chosen_instance in weighted_instances:
            chosen_instance['resources'] = filter(
                lambda x: x['uuid'] == chosen_instance['uuid'],
                instances_params)[0]
            yield chosen_instance

    def _choose_host_to_migrate(self, context, weighted_instances, nodes):
        for c in weighted_instances:
            filtered, filter_properties = self.filter_hosts(context, c, nodes)
            if filtered:
                chosen_instance = c
                break
        if not filtered:
            return None, None
        nodes = filter_properties['nodes']
        # 'memory_total' field shouldn't be normalized.
        for n in nodes:
            del n['memory_total']
        filtered_nodes = [
            n for n in nodes
            for host in filtered if n['host'] == host.hypervisor_hostname]
        normalized_hosts = lb_utils.normalize_params(filtered_nodes, 'host')
        weighted_hosts = self._weight_hosts(normalized_hosts)
        return weighted_hosts[0], chosen_instance

    def _classic(self, context, **kwargs):
        node = kwargs.get('node')
        nodes = kwargs.get('nodes')
        extra_info = kwargs.get('extra_info')
        instances = db.get_instances_stat(
            context,
            node['hypervisor_hostname'])
        weighted_instances = self._choose_instance_to_migrate(instances,
                                                              extra_info)
        c_host, c_instance = self._choose_host_to_migrate(context,
                                                          weighted_instances,
                                                          nodes)
        if not c_instance:
            return
        selected_pair = {c_host['host']: c_instance['uuid']}
        LOG.debug(_(selected_pair))
        if node['hypervisor_hostname'] == c_host['host']:
            LOG.debug("Source host is optimal."
                      " Live Migration will not be perfomed.")
            return
        self.migrate(context, c_instance['uuid'], c_host['host'])

    def balance(self, context, **kwargs):
        return self._classic(context, **kwargs)
