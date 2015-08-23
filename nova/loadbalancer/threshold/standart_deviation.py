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
from nova.i18n import _
from nova.loadbalancer.threshold import base
from nova.loadbalancer import utils
from nova.openstack.common import log as logging

from oslo.config import cfg


lb_opts = [
    cfg.FloatOpt('threshold_cpu',
                 default=0.05,
                 help='Standart Deviation Threshold'),
    cfg.FloatOpt('threshold_memory',
                 default=0.3,
                 help='Standart Deviation Threshold')
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer_standart_deviation')


class Standart_Deviation(base.Base):

    def __init__(self):
        pass

    def indicate(self, context):
        cpu_threshold = CONF.loadbalancer_standart_deviation.threshold_cpu
        mem_threshold = CONF.loadbalancer_standart_deviation.threshold_memory
        compute_nodes = db.get_compute_node_stats(context)
        instances = []
        # TODO: Make only one query that returns all instances placed on active
        # hosts.
        for node in compute_nodes:
            node_instances = db.get_instances_stat(
                context,
                node['hypervisor_hostname'])
            instances.extend(node_instances)
        compute_stats = utils.fill_compute_stats(instances, compute_nodes)
        host_loads = utils.calculate_host_loads(compute_nodes, compute_stats)
        LOG.debug(_(host_loads))
        ram_sd = utils.calculate_sd(host_loads, 'mem')
        cpu_sd = utils.calculate_sd(host_loads, 'cpu')
        if cpu_sd > cpu_threshold or ram_sd > mem_threshold:
            extra_info = {'cpu_overload': False}
            if cpu_sd > cpu_threshold:
                overloaded_host = sorted(host_loads,
                                         key=lambda x: host_loads[x]['cpu'],
                                         reverse=True)[0]
                extra_info['cpu_overload'] = True
            else:
                overloaded_host = sorted(host_loads,
                                         key=lambda x: host_loads[x]['mem'],
                                         reverse=True)[0]
            host = filter(
                lambda x:
                x['hypervisor_hostname'] == overloaded_host, compute_nodes)[0]
            LOG.debug(_(host))
            return host, compute_nodes, extra_info
        return [], [], {}
