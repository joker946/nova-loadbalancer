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
from nova.loadbalancer.underload.base import Base
from nova.loadbalancer import utils
from nova.openstack.common import log as logging

from oslo.config import cfg

lb_opts = [
    cfg.FloatOpt('threshold_cpu',
                 default=0.05,
                 help='CPU Underload Threshold'),
    cfg.FloatOpt('threshold_memory',
                 default=0.05,
                 help='Memory Underload Threshold')
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer_mean_underload')


class MeanUnderload(Base):
    def __init__(self):
        pass

    def indicate(self, context):
        cpu_max = CONF.loadbalancer_mean_underload.threshold_cpu
        memory_max = CONF.loadbalancer_mean_underload.threshold_memory
        compute_nodes = db.get_compute_node_stats(context, use_mean=True)
        instances = []
        for node in compute_nodes:
            node_instances = db.get_instances_stat(context,
                                                   node['hypervisor_hostname'])
            instances.extend(node_instances)
        compute_stats = utils.fill_compute_stats(instances, compute_nodes)
        host_loads = utils.calculate_host_loads(compute_nodes, compute_stats)
        for node in host_loads:
            memory = host_loads[node]['mem']
            cpu = host_loads[node]['cpu']
            if (cpu < cpu_max) and (memory < memory_max):
                # Underload is needed.
                LOG.debug('underload is needed')
                return True
