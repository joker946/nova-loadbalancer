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
from nova.openstack.common import log as logging

from oslo.config import cfg


lb_opts = [
    cfg.IntOpt('cpu_threshold',
               default=70,
               help='LoadBalancer CPU threshold, percent'),
    cfg.IntOpt('memory_threshold',
               default=70,
               help='LoadBalancer Memory threshold, percent')
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer_step_threshold')


class Step_Threshold(base.Base):
    def __init__(self):
        pass

    def indicate(self, context):
        compute_nodes = db.get_compute_node_stats(context)
        cpu_td = CONF.loadbalancer_step_threshold.cpu_threshold
        memory_td = CONF.loadbalancer_step_threshold.memory_threshold
        LOG.debug(_(cpu_td))
        LOG.debug(_(memory_td))
        for node in compute_nodes:
            cpu_used_percent = node['cpu_used_percent']
            memory_used = node['memory_used']
            memory_used_percent = round(
                (float(memory_used) / float(node['memory_total'])) * 100.00, 0
            )
            LOG.debug(_(cpu_used_percent))
            LOG.debug(_(memory_used_percent))
            if cpu_used_percent > cpu_td or memory_used_percent > memory_td:
                return node, compute_nodes, {}
        return [], [], {}
